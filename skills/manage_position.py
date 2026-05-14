"""
Skill: manage_position
Add, adjust, or remove a stock position in the user's depot.
"""

import asyncio
import yaml, os
from pathlib import Path
import yfinance as yf

DEPOT_PATH = Path(os.getenv("DATA_DIR", "data")) / "DEPOT.yaml"

DOC = """
## manage_position
Use this skill to add, adjust, or remove a stock position in the user's portfolio.
- Positive quantity = buy / add shares
- Negative quantity = sell / reduce shares
- To fully exit a position, use the negative of the current share count
- Fetches current market price automatically if not provided
"""

SKILL = {
    "name": "manage_position",
    "description": (
        "Add, adjust, or remove a stock position in the depot. "
        "Positive quantity = buy/add. Negative quantity = sell/reduce. "
        "Fetches current market price if price is not provided."
        "Adjust the portfolio position according to the user's specifications."
    ),
    "doc": DOC,
    "parameters": {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Ticker symbol, e.g. 'AAPL' or 'EBS.VI'",
            },
            "quantity": {
                "type": "number",
                "description": "Shares to add (positive = buy, negative = sell/remove)",
            },
            "price": {
                "type": ["number", "null"],
                "description": "Price per share. Fetched automatically if null.",
            },
            "name": {
                "type": ["string", "null"],
                "description": "Company name e.g. 'Erste Group Bank'. Optional, used for new positions.",
            },
        },
        "required": ["symbol", "quantity"],
    },
}


def _fetch_price(symbol: str) -> float:
    hist = yf.Ticker(symbol).history(period="1d")
    if hist.empty:
        raise ValueError(f"No price data for '{symbol}'.")
    return round(float(hist["Close"].iloc[-1]), 2)


async def manage_position(
    symbol: str,
    quantity: float,
    price: float | None = None,
    name: str | None = None,
    depot: dict | None = None,
    manual_override: bool = False,
    **_,
) -> dict:

    if manual_override:
        return {
            "symbol": symbol,
            "action": "manual_override",
            "quantity_change": quantity,
            "price_per_share": price,
            "new_shares": None,
            "new_avg_price": price,
            "depot_updated": True,
        }

    # Fetch price if not provided (only needed when adding/buying)
    if price is None and quantity > 0:
        try:
            loop = asyncio.get_event_loop()
            price = await loop.run_in_executor(None, _fetch_price, symbol)
        except Exception as exc:
            return {"error": str(exc)}

    if price is not None:
        price = round(price, 2)

    # Load current depot — create empty file if it doesn't exist yet
    if not DEPOT_PATH.exists():
        DEPOT_PATH.write_text(yaml.dump({"holdings": []}, allow_unicode=True))
    depot_data = yaml.safe_load(DEPOT_PATH.read_text()) or {}
    holdings = depot_data.get("holdings", [])

    # Find existing position
    existing = next((h for h in holdings if h["symbol"] == symbol), None)

    if existing:
        old_shares = existing["shares"]
        old_avg = existing["avg_buy_price"]
        new_shares = old_shares + quantity

        if new_shares <= 0:
            # Full exit — remove position entirely
            holdings.remove(existing)
            action = "removed"
            result_shares = 0
            result_avg = 0.0
        else:
            # Partial add or reduce
            if quantity > 0:
                # Buying more — recalculate average price
                new_avg = ((old_avg * old_shares) + (price * quantity)) / new_shares
                existing["avg_buy_price"] = round(new_avg, 2)
                action = "increased"
            else:
                # Selling — average price unchanged
                new_avg = old_avg
                action = "reduced"
            existing["shares"] = new_shares
            result_shares = new_shares
            result_avg = existing["avg_buy_price"]

    elif quantity > 0:
        # New position
        holdings.append(
            {
                "symbol": symbol,
                "name": name or symbol,
                "shares": quantity,
                "avg_buy_price": price,
            }
        )
        action = "added"
        result_shares = quantity
        result_avg = price

    else:
        # Tried to sell a stock not in depot
        return {"error": f"{symbol} is not in your depot — nothing to sell."}

    depot_data["holdings"] = holdings
    DEPOT_PATH.write_text(yaml.dump(depot_data, default_flow_style=False, allow_unicode=True))

    return {
        "symbol": symbol,
        "action": action,
        "quantity_change": quantity,
        "price_per_share": price,
        "new_shares": result_shares,
        "new_avg_price": result_avg,
        "depot_updated": True,
    }


SKILL["fn"] = manage_position