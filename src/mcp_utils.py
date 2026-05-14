# mcp_utils.py
import json

from fastmcp import Client

from db.database import get_cached_result, set_cached_result, _extract_ticker
from skills.manage_position import manage_position as _manage_position_direct


async def execute_tool(mcp: Client, block, depot: dict) -> dict:
    args = dict(block.input)
    if block.name == "get_portfolio_summary":
        args["depot"] = depot
    result = await mcp.call_tool(block.name, args)
    content = result.content[0].text if result.content else "{}"
    return {"type": "tool_result", "tool_use_id": block.id, "content": content}


async def execute_tool_cached(mcp, block, depot) -> dict:
    # manage_position owns its own file I/O — call it directly, not via MCP
    if block.name == "manage_position":
        args = dict(block.input)
        try:
            result = await _manage_position_direct(depot=depot, **args)
            # Invalidate portfolio summary cache — depot just changed
        except Exception as e:
            result = {"error": str(e)}
        from db.database import invalidate_cache
        invalidate_cache("get_portfolio_summary", "PORTFOLIO")
        return {
            "type":        "tool_result",
            "tool_use_id": block.id,
            "content":     json.dumps(result),
        }

    # Everything else — read-only — goes through MCP with caching
    ticker = _extract_ticker(block)
    cached = get_cached_result(block.name, ticker)
    if cached:
        print(f"  [cache] ✅ hit  — {block.name}({ticker})")
        return {"type": "tool_result", "tool_use_id": block.id, "content": cached}

    print(f"  [cache] ❌ miss — {block.name}({ticker}) → calling API")
    result = await execute_tool(mcp, block, depot)
    set_cached_result(block.name, ticker, result["content"])

    if block.name == "get_portfolio_summary":
        seed_price_cache_from_summary(result["content"])

    return result


async def get_tools(mcp: Client) -> list:
    tools = await mcp.list_tools()
    return [
        {
            "name":         t.name,
            "description":  t.description,
            "input_schema": t.inputSchema,
        }
        for t in tools
    ]


def seed_price_cache_from_summary(summary_json: str):
    data = json.loads(summary_json)
    for holding in data.get("holdings", []):
        symbol = holding["symbol"]
        payload = json.dumps({
            "symbol":        symbol,
            "current_price": holding["current_price"],
            "currency":      data.get("currency", "USD"),
        })
        set_cached_result("get_prices", symbol, payload)
        print(f"  [cache] seeded get_prices({symbol}) from portfolio summary")