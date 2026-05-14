"""
main.py — FinAgent entry point.

Responsibilities:
  - Load SOUL.md, DEPOT.yaml once at startup
  - Open MCP client once, share across all tasks
  - Persist message history to history.json (survives restarts)
  - Run chat_loop and heartbeat_loop concurrently
  - "bye" / "exit" pauses chat input — process keeps running
"""

import asyncio
import datetime
from datetime import datetime, timedelta
import json, os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from fastmcp import Client

from loop import run_react
from src.mcp_utils import get_tools
from heartbeat import run_heartbeat

from db.database import init_databases, log_message, get_history_db, get_cache_db

load_dotenv()

# SOUL_PATH  = Path("SOUL.md")
# DEPOT_PATH = Path("DEPOT.yaml")
from config import SOUL_PATH, DEPOT_PATH

HEARTBEAT_INTERVAL = 60 ** 2  # seconds


# ── Persistence ───────────────────────────────────────────────────────────────

def load_recent_messages(hours: int = 4) -> list[dict]:
    """Load messages from the last N hours to seed messages[] on startup."""
    cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    with get_history_db() as conn:
        rows = conn.execute(
            "SELECT role, content FROM messages WHERE timestamp > ? ORDER BY id", (cutoff,)
        ).fetchall()
    return [{"role": r["role"], "content": json.loads(r["content"])} for r in rows]


def build_system(soul: str, depot: dict) -> str:
    """Builds system prompt"""
    base = (
        soul
        + "\n\n## Your Current Depot\n"
        + "```yaml\n"
        + yaml.dump(depot, allow_unicode=True)
        + "\n```"
    )
    if not depot.get("holdings"):
        base += (
            "\n\n## Startup Task\n"
            "The depot is empty. On your very first response, greet the user "
            "and ask them to share their holdings — name or ticker, quantity, "
            "and optionally the price paid. Do not show any analysis until at "
            "least one position has been added."
        )
    return base


# no in mcp tools
# async def get_tools(mcp: Client) -> list:
#     """Fetch tools from the MCP server and convert to Anthropic format."""
#     tools = await mcp.list_tools()
#     return [
#         {
#             "name": t.name,
#             "description": t.description,
#             "input_schema": t.inputSchema,
#         }
#         for t in tools
#     ]


# ── Chat loop ─────────────────────────────────────────────────────────────────

async def chat_loop(mcp, system, tools, messages, depot):
    print("[finagent] ready. type 'exit' to quit.\n")
    while True:
        try:
            user_input = await asyncio.to_thread(input, "> ")
        except EOFError:
            await asyncio.sleep(5)
            continue

        user_input = user_input.strip()
        if not user_input:
            continue
        if user_input.lower() in ("bye", "exit", "q"):
            print("[finagent] chat paused. heartbeat still running.")
            await asyncio.sleep(3610)
            continue

        messages.append({"role": "user", "content": user_input})
        log_message("user", user_input, source="chat")
        reply = await run_react(mcp, system, tools, messages, depot)
        print(f"\nAgent: {reply}\n")


# ── Heartbeat loop ────────────────────────────────────────────────────────────

async def heartbeat_loop(mcp: Client, system: str, tools: list, messages: list, depot: dict):
    await asyncio.sleep(10)  # small delay so chat loop starts first
    while True:
        print("\n[heartbeat] running portfolio check...")
        summary = await run_heartbeat(mcp, system, tools, messages, depot)
        if summary:
            messages.append({"role": "assistant", "content": f"[Heartbeat] {summary}"})
            log_message("assistant", f"[Heartbeat] {summary}", source="heartbeat")
            print(f"\n[heartbeat] {summary}\n")
        await asyncio.sleep(HEARTBEAT_INTERVAL)


# ── Entry point ───────────────────────────────────────────────────────────────

async def main():
    init_databases()

    soul   = SOUL_PATH.read_text()
    if not DEPOT_PATH.exists():
        DEPOT_PATH.write_text(yaml.dump({"holdings": []}, allow_unicode=True))
    depot = yaml.safe_load(DEPOT_PATH.read_text()) or {}
    system = build_system(soul, depot)

    messages = load_recent_messages(hours=4)
    if messages:
        print(f"[finagent] loaded {len(messages)} messages from history.\n")

    async with Client("mcp/finance_server.py") as mcp:
        tools = await get_tools(mcp)
        print(f"[mcp] connected — {len(tools)} tools: {[t['name'] for t in tools]}")

        await asyncio.gather(
            chat_loop(mcp, system, tools, messages, depot),
            heartbeat_loop(mcp, system, tools, messages, depot),
        )


if __name__ == "__main__":
    asyncio.run(main())