"""
Skill: get_prices
Fetch current price and daily change % for a list of ticker symbols.
"""

import yfinance as yf


# only thing needed for mcp is the function, but we keep the SKILL dict for nano compatibility
async def get_prices(symbols: list[str], depot=None, **_) -> dict:
    result = {}
    for sym in symbols:
        try:
            hist = yf.Ticker(sym).history(period="1d")
            if hist.empty:
                result[sym] = {"error": "No price data returned"}
                continue
            price = round(float(hist["Close"].iloc[-1]), 2)
            prev  = round(float(hist["Close"].iloc[-2]), 2) if len(hist) > 1 else price
            change_pct = round((price / prev - 1) * 100, 2) if prev else 0.0
            result[sym] = {
                "price":          price,
                "previous_close": prev,
                "change_pct":     change_pct,
            }
        except Exception as exc:
            result[sym] = {"error": str(exc)}
    return result


# not used for mcp
DOC = """Use this skill to get the current market price and daily percentage change
for stock ticker symbols.

Call it when the user asks about:
- Current stock prices
- Daily performance ("how did X do today?")
- Any query that needs up-to-date price data

Always use the exact ticker symbols from the user's depot
(e.g. VOW3.DE for Volkswagen, ASML.AS for ASML).
"""

# not used for mcp
SKILL = {
    "name": "get_prices",
    "description": (
        "Get current stock price and daily % change for given ticker symbols. "
        "Use for any query about current prices or daily performance."
    ),
    "doc": DOC,
    "parameters": {
        "type": "object",
        "properties": {
            "symbols": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Ticker symbols, e.g. ['AAPL', 'NVDA', 'ASML.AS']",
            }
        },
        "required": ["symbols"],
    },
    "fn": get_prices,
}

