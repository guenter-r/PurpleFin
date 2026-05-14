# mcp/finance_server.py
"""
FinAgent Finance MCP Server.

Exposes the skills/ business logic as MCP tools.
Skills are imported with private aliases (_) to avoid
name collisions with the public MCP tool definitions.

Run standalone:
    python mcp/finance_server.py

Or connected via loop.py's MCP client.
"""
import sys
from pathlib import Path

# Add project root to sys.path so 'skills' is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
from fastmcp import FastMCP

# added _ to make sure no name collisions occur
from skills.indicators           import get_indicators           as _get_indicators
from skills.prices               import get_prices               as _get_prices
from skills.news                 import get_news                 as _get_news
from skills.portfolio            import get_portfolio_summary    as _get_portfolio_summary
from skills.manage_position      import manage_position          as _manage_position
from skills.daily_summary        import get_daily_summary   as _get_daily_summary
from skills.technical_indicators import get_technical_indicators as _get_technical_indicators

# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="FinAgent Finance Server",
    instructions=(
        "Provides real-time and historical financial data for stock analysis. "
        "Use get_indicators for moving averages and RSI, get_prices for live quotes, "
        "get_news for recent headlines, and get_portfolio_summary for depot overview."
    ),
)

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_indicators(symbols: list[str]) -> dict:
    """
    Compute technical indicators for the given ticker symbols.
    Returns 50-day MA, 200-day MA, RSI-14, and current price.
    Example: symbols=["AAPL", "MSFT"]
    """
    return await _get_indicators(symbols)


@mcp.tool()
async def get_prices(symbols: list[str]) -> dict:
    """
    Get current stock price and daily percentage change for the given tickers.
    Example: symbols=["AAPL", "NVDA"]
    """
    return await _get_prices(symbols)


@mcp.tool()
async def get_news(symbols: list[str]) -> dict:
    """
    Fetch the latest news headlines and links for the given ticker symbols.
    Returns up to 3 recent articles per symbol.
    Example: symbols=["TSLA"]
    """
    return await _get_news(symbols)


@mcp.tool()
async def get_portfolio_summary(depot: dict | None = None) -> dict:
    """
    Summarise the current depot: positions, total value, daily P&L.
    Depot data is injected automatically by the agent loop.
    """
    return await _get_portfolio_summary(depot=depot)


@mcp.tool()
async def manage_position(
    symbol: str,
    quantity: float,
    price: float | None = None,
    name: str | None = None,
    depot: dict | None = None,
    manual_override: bool = False,
) -> dict:
    """
    Add/remove shares from the depot. Positive quantity to buy/add, negative to sell/remove.
    If price is not provided when buying, it will be fetched automatically.
    If manual_override is True, the position will be updated without fetching price or checking
    depot.
    This is also used to set up the initial depot by adding positions with quantity > 0. Iterate
    to add multiple holdings.
    """
    return await _manage_position(
        symbol=symbol,
        quantity=quantity,
        price=price,
        name=name,
        depot=depot,
        manual_override=manual_override,
    )


@mcp.tool()
async def get_daily_summary(symbols: list[str]) -> dict:
    """
    Get today's percentage change for the given ticker symbols.
    Example: symbols=["AAPL", "GOOGL"]
    """
    prices = await _get_daily_summary(symbols)
    return {sym: data.get("change_pct") for sym, data in prices.items()}

@mcp.tool()
async def get_technical_indicators(symbols: list[str]) -> dict:
    """
    Compute common technical indicators (moving averages, RSI-14,
    annualised return/volatility, Sharpe, 52-week extremes, MA crosses)
    for stock symbols. This is a good tool for supporting buy/sell decisions
    and overall trend strength.

    Example: symbols=["AAPL", "MSFT", "EBS.VI", "SAP.DE"]
    """
    return await _get_technical_indicators(symbols)


if __name__ == "__main__":
    # stdio transport — loop.py connects to this process via stdin/stdout
    mcp.run()