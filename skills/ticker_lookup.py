"""
Look up stock ticker symbols by company name via Yahoo Finance.
"""
import asyncio
import json
import urllib.parse
import urllib.request
import logging

logger = logging.getLogger(__name__)

def _blocking_lookup_ticker(query: str) -> list[dict]:
    """
    Blocking call to Yahoo Finance search endpoint.
    """
    url = f"https://query2.finance.yahoo.com/v1/finance/search?q={urllib.parse.quote(query)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            quotes = data.get("quotes", [])

            # Extract relevant fields and return top 5 results
            results = []
            for q in quotes:
                if "symbol" in q:
                    results.append({
                        "symbol": q.get("symbol"),
                        "shortname": q.get("shortname"),
                        "longname": q.get("longname"),
                        "exchange": q.get("exchange"),
                        "quoteType": q.get("quoteType")
                    })
            return results[:5]
    except Exception as e:
        logger.error(f"Error looking up ticker for '{query}': {e}")
        return []

async def lookup_ticker(query: str) -> list[dict]:
    """
    Look up a stock ticker symbol by company name.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _blocking_lookup_ticker, query)
