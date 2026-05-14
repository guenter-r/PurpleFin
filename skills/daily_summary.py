"""
Skill: get_todays_summary
Fetch a quick summary of symbols: current price vs yesterday's close and daily change %.
"""

import yfinance as yf


DOC = """Use this skill to get a quick daily summary for stocks:
- Current price
- Yesterday's closing price
- Today's percentage change vs yesterday

Call it when the user asks about:
- How is my depot doing today?
- Daily performance for one or more stocks
- Quick overview of today's moves vs yesterday's close
"""


async def get_daily_summary(symbols: list[str], depot=None, **_) -> dict:
    summary = {}
    for sym in symbols:
        try:
            # Need up to 2 last closes to compute today's change vs yesterday
            hist = yf.Ticker(sym).history(period="2d")
            if hist.empty:
                summary[sym] = {"error": "No price data returned"}
                continue

            price = round(float(hist["Close"].iloc[-1]), 2)
            prev = round(float(hist["Close"].iloc[-2]), 2) if len(hist) > 1 else price
            change_pct = round((price / prev - 1) * 100, 2) if prev else 0.0

            summary[sym] = {
                "current_price": price,
                "previous_close": prev,
                "change_pct": change_pct,
            }
        except Exception as exc:
            summary[sym] = {"error": str(exc)}
    return summary


SKILL = {
    "name": "get_daily_summary",
    "description": (
        "Get today's percentage change for the given ticker symbols."
    ),
    "doc": DOC,
    "parameters": {
        "type": "object",
        "properties": {
            "symbols": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Ticker symbols to summarise for today",
            }
        },
        "required": ["symbols"],
    },
    "fn": get_daily_summary,
}