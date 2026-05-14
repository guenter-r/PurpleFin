"""
Skill: get_indicators
Compute 200-day MA, 50-day MA, RSI-14, basic risk metrics, and 52-week levels.
"""

import math
import yfinance as yf

DOC = """Use this skill to compute technical indicators and basic risk metrics for stocks:
- 200-day moving average (MA200): long-term trend baseline
- 50-day moving average (MA50): medium-term trend
- RSI-14: momentum oscillator (>70 = overbought, <30 = oversold)
- Annualised return and volatility based on 1-year daily data
- Sharpe ratio (risk-adjusted return, risk-free rate approximated as 0)
- 52-week high/low and distance from each
- Golden/death cross flags (50-day MA vs 200-day MA)

Call it when the user asks about:
- Technical analysis or trend signals
- Whether a stock is above/below its 200-day line
- Momentum or overbought/oversold conditions
- Volatility, risk-adjusted performance (Sharpe), or 52-week extremes
"""


def _compute(sym: str) -> dict:
    # 1 year of data is enough for MA, RSI, risk metrics, 52-week levels
    df = yf.download(sym, period="1y", auto_adjust=True, progress=False)
    if df.empty:
        return {"error": "No data available"}

    close = df["Close"].squeeze()
    price = float(close.iloc[-1])

    # Moving averages
    ma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None
    ma50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None

    # RSI-14
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rsi = float((100 - 100 / (1 + gain / loss)).iloc[-1])

    # Daily returns for risk metrics
    returns = close.pct_change().dropna()
    if not returns.empty:
        mean_daily = float(returns.mean())
        std_daily = float(returns.std())

        trading_days = 252
        ann_return = mean_daily * trading_days
        ann_vol = std_daily * math.sqrt(trading_days) if std_daily > 0 else None
        sharpe = (ann_return / ann_vol) if ann_vol and ann_vol != 0 else None
    else:
        ann_return = None
        ann_vol = None
        sharpe = None

    # 52-week high/low and distances
    high_52w = float(close.max())
    low_52w = float(close.min())
    off_high_pct = (price / high_52w - 1) * 100 if high_52w else None
    off_low_pct = (price / low_52w - 1) * 100 if low_52w else None

    # MA cross flags
    golden_cross = None
    death_cross = None
    if ma50 is not None and ma200 is not None:
        golden_cross = ma50 > ma200
        death_cross = ma50 < ma200

    return {
        "price": round(price, 2),

        "ma200": round(ma200, 2) if ma200 else None,
        "ma50": round(ma50, 2) if ma50 else None,
        "above_ma200": (price > ma200) if ma200 else None,
        "above_ma50": (price > ma50) if ma50 else None,

        "rsi_14": round(rsi, 1),

        # Risk/return metrics
        "annual_return": round(ann_return, 4) if ann_return is not None else None,   # decimal, e.g. 0.12 for 12%
        "annual_volatility": round(ann_vol, 4) if ann_vol is not None else None,    # decimal
        "sharpe_ratio": round(sharpe, 2) if sharpe is not None else None,

        # 52-week levels
        "high_52w": round(high_52w, 2),
        "low_52w": round(low_52w, 2),
        "off_high_pct": round(off_high_pct, 2) if off_high_pct is not None else None,
        "off_low_pct": round(off_low_pct, 2) if off_low_pct is not None else None,

        # Trend structure
        "golden_cross": golden_cross,
        "death_cross": death_cross,
    }


async def get_indicators(symbols: list[str], depot=None, **_) -> dict:
    # yfinance downloads are blocking — run in executor to stay async-friendly
    import asyncio

    loop = asyncio.get_event_loop()
    results = {}
    for sym in symbols:
        try:
            results[sym] = await loop.run_in_executor(None, _compute, sym)
        except Exception as exc:
            results[sym] = {"error": str(exc)}
    return results


SKILL = {
    "name": "get_indicators",
    "description": (
        "Compute 200-day MA, 50-day MA, RSI-14, basic risk metrics (annualised "
        "return, volatility, Sharpe), 52-week extremes, and MA cross flags for "
        "stock symbols. Use for trend analysis, momentum, and risk-adjusted performance."
    ),
    "doc": DOC,
    "parameters": {
        "type": "object",
        "properties": {
            "symbols": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Ticker symbols to analyse",
            }
        },
        "required": ["symbols"],
    },
    "fn": get_indicators,
}