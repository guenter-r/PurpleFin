"""
Skill: get_news
Fetch recent news headlines for given stock symbols via yfinance.
"""

import yfinance as yf

DOC = """Use this skill to get recent news headlines for stocks in the user's depot.

Call it when the user asks about:
- News or recent developments for a stock
- What's moving a particular stock
- A general news briefing (use the top 3-5 holdings by value)

Return only the 3-5 most relevant headlines per symbol.
Summarise rather than list everything.
"""


async def get_news(symbols: list[str], depot=None, **_) -> dict:
    result = {}
    for sym in symbols:
        try:
            items = yf.Ticker(sym).news or []
            result[sym] = [
                {
                    "title":     item.get("content", {}).get("title", ""),
                    "summary":   item.get("content", {}).get("summary", ""),
                    "published": item.get("content", {}).get("pubDate", ""),
                    "url":       (
                        item.get("content", {})
                            .get("canonicalUrl", {})
                            .get("url", "")
                    ),
                }
                for item in items[:5]
            ]
        except Exception as exc:
            result[sym] = {"error": str(exc)}
    return result


SKILL = {
    "name": "get_news",
    "description": (
        "Fetch recent news headlines for stock ticker symbols. "
        "Use for news briefings or when a stock is making unusual moves."
    ),
    "doc": DOC,
    "parameters": {
        "type": "object",
        "properties": {
            "symbols": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Ticker symbols to get news for",
            }
        },
        "required": ["symbols"],
    },
    "fn": get_news,
}
