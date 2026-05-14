"""
heartbeat.py — FinAgent heartbeat monitor.

Runs one portfolio check pass:
  - Appends a heartbeat prompt to the SHARED message history
  - Runs a ReAct loop using the shared MCP client and tools
  - Returns a summary string (or None if nothing noteworthy)
  - Never manages its own loop, sleep, or MCP connection — main.py owns those
"""

import asyncio
from fastmcp import Client
from dotenv import load_dotenv

from src.llm import call_llm, parse_response, HEARTBEAT_MODEL, get_safe_context
from src.mcp_utils import execute_tool_cached as execute_tool
from db.database import log_message

load_dotenv()

HEARTBEAT_PROMPT = (
    "Run a quick heartbeat check. Do NOT check every holding. "
    "Focus only on holdings with recent volatility or news. "
    "Use get_portfolio_summary first to get an overview, then only "
    "drill into individual tickers if something looks unusual. "
    "Maximum 3 tool calls total. Be brief."
)

HEARTBEAT_SYSTEM_SUFFIX = (
    "\n\n## Heartbeat Role\n"
    "You are a continuous monitoring agent for the user's stock depot. "
    "When called for a heartbeat check, use tools to inspect prices, "
    "indicators, and news. Be concise. Use ✅ for good, ⚠️ for neutral, ❌ for bad. "
    "If the news are similar to what was already discussed in the message history, just "
    "greet the user and let them know there are no significant updates to earlier."
    "If no real news to last heartbeat, just say so, not listing details."
)


async def run_heartbeat(
    mcp: Client,
    system: str,
    tools: list,
    messages: list,  # shared history — READ from it, append to it
    depot: dict,
) -> str | None:
    """
    Run one heartbeat ReAct pass.
    Appends the heartbeat prompt + assistant reply to shared messages.
    Returns the reply string, or None if an error occurred.
    """
    heartbeat_system = system + HEARTBEAT_SYSTEM_SUFFIX

    # Append heartbeat trigger to SHARED history (not a local copy)
    messages.append({"role": "user", "content": HEARTBEAT_PROMPT})
    log_message("user", HEARTBEAT_PROMPT, source="heartbeat")

    try:
        for _ in range(5):
            response = await call_llm(
                model=HEARTBEAT_MODEL,
                system=heartbeat_system,
                tools=tools,
                messages=get_safe_context(
                    messages, max_messages=6
                ),  # rolling window — keep token cost flat
                max_tokens=256,
            )

            tool_blocks, text_block = parse_response(response)

            if not tool_blocks:
                answer = text_block.text if text_block else "(no response)"
                messages.append({"role": "assistant", "content": answer})
                log_message("assistant", answer, source="heartbeat")
                return answer

            print(f"[heartbeat] calling tools: {[b.name for b in tool_blocks]}")
            messages.append({"role": "assistant", "content": response.content})

            results = await asyncio.gather(*[execute_tool(mcp, b, depot) for b in tool_blocks])
            messages.append({"role": "user", "content": list(results)})

    except Exception as exc:
        print(f"[heartbeat] error: {exc}")
        return None

    return "(max iterations reached)"
