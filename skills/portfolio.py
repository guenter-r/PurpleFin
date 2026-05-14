"""
Skill: get_portfolio_summary
Compute current value and P&L for every holding in the user's depot.

This skill takes no arguments — it reads the depot from context and
fetches live prices for each holding automatically.
"""

import yfinance as yf

DOC = """Use this skill to compute the full portfolio snapshot:
- Current value of each position (shares × current price)
- Profit/loss per holding vs. average buy price (in € and %)
- Total portfolio value and total P&L

Call it when the user asks for:
- A portfolio overview or summary
- Total portfolio value
- Overall P&L ("am I in profit?")
- A comparison of all holdings

This skill requires no arguments — it uses the depot from context.
"""


async def get_portfolio_summary(depot=None, **_) -> dict:
    if not depot:
        return {"error": "No depot configured"}

    holdings = depot.get("holdings", [])
    currency = depot.get("currency", "USD")

    rows = []
    total_invested    = 0.0
    total_current_val = 0.0

    for h in holdings:
        sym      = h["symbol"]
        shares   = h["shares"]
        avg_buy  = h["avg_buy_price"]

        try:
            hist  = yf.Ticker(sym).history(period="2d")
            price = float(hist["Close"].iloc[-1]) if not hist.empty else None
        except Exception:
            price = None

        invested      = shares * avg_buy
        current_value = shares * price if price is not None else None
        pnl           = (current_value - invested) if current_value is not None else None
        pnl_pct       = (pnl / invested * 100)     if pnl is not None and invested > 0 else None

        total_invested    += invested
        total_current_val += current_value or 0.0

        rows.append({
            "symbol":        sym,
            "name":          h.get("name", sym),
            "shares":        shares,
            "avg_buy_price": avg_buy,
            "current_price": round(price, 2)         if price is not None else None,
            "invested":      round(invested, 2),
            "current_value": round(current_value, 2) if current_value is not None else None,
            "pnl":           round(pnl, 2)           if pnl is not None else None,
            "pnl_pct":       round(pnl_pct, 2)       if pnl_pct is not None else None,
        })

    total_pnl     = total_current_val - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0.0

    return {
        "currency":            currency,
        "holdings":            rows,
        "total_invested":      round(total_invested, 2),
        "total_current_value": round(total_current_val, 2),
        "total_pnl":           round(total_pnl, 2),
        "total_pnl_pct":       round(total_pnl_pct, 2),
    }


SKILL = {
    "name": "get_portfolio_summary",
    "description": (
        "Compute current value and P&L for every holding. "
        "Use for portfolio overview, total value, and P&L breakdown. "
        "Takes no arguments — uses the depot from context automatically."
    ),
    "doc": DOC,
    "parameters": {
        "type": "object",
        "properties": {},   # no args needed — depot is injected by the loop
        "required": [],
    },
    "fn": get_portfolio_summary,
}
