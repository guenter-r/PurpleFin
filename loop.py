
"""
loop.py : React loop implementation for PurpleFin.
"""
import asyncio

from src.llm import call_llm, parse_response, CHAT_MODEL, get_safe_context  
from src.mcp_utils import execute_tool_cached as execute_tool
from db.database import log_message


async def run_react(mcp, system, tools, messages, depot) -> str:
    for _ in range(5):
        response = await call_llm(
            model=CHAT_MODEL,
            system=system,
            tools=tools,
            messages=get_safe_context(messages, max_messages=10), 
            max_tokens=1024,
        )

        tool_blocks, text_block = parse_response(response)

        if not tool_blocks:
            answer = text_block.text if text_block else "(no response)"
            messages.append({"role": "assistant", "content": answer})
            log_message("assistant", answer, source="chat")
            return answer

        print(f"  [loop] calling: {[b.name for b in tool_blocks]}")
        messages.append({"role": "assistant", "content": response.content})

        results = await asyncio.gather(*[execute_tool(mcp, b, depot) for b in tool_blocks])
        messages.append({"role": "user", "content": list(results)})

    return "(max iterations reached)"
