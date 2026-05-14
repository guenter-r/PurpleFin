"""
Skill: get_technical_indicators
Compute common technical indicators for given symbols:
- Moving averages (short / medium / long)
- RSI-14
- Basic risk / return metrics
- 52-week highs/lows and MA cross flags
"""

import math
import yfinance as yf

DOC = """Use this skill to compute technical indicators and basic risk metrics for stocks:
- Short-, medium-, and long-term moving averages (e.g. 20/50/200-day)
- RSI-14: momentum oscillator (>70 = overbought, <30 = oversold)
- Annualised return and volatility based on 1-year daily data
- Sharpe ratio (risk-adjusted return, assuming risk-free ≈ 0)
- 52-week high/low and distance from each
- Golden/death cross flags (50 vs 200-day MA)

Call it when the user asks about:
- Technical analysis, trend, or momentum signals
- Whether a stock is above/below its key moving averages
- Volatility, risk-adjusted performance (Sharpe), or 52-week extremes
"""


def _compute(sym: str) -> dict:
    # Use 1 year of daily data
    df = yf.download(sym, period="1y", auto_adjust=True, progress=False)
    if df.empty:
        return {"error": "No data available"}

    close = df["Close"].squeeze()
    price = float(close.iloc[-1])

    # Moving averages
    ma20 = float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else None
    ma50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None
    ma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None

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

        "ma20": round(ma20, 2) if ma20 else None,
        "ma50": round(ma50, 2) if ma50 else None,
        "ma200": round(ma200, 2) if ma200 else None,
        "above_ma20": (price > ma20) if ma20 else None,
        "above_ma50": (price > ma50) if ma50 else None,
        "above_ma200": (price > ma200) if ma200 else None,

        "rsi_14": round(rsi, 1),

        "annual_return": round(ann_return, 4) if ann_return is not None else None,    # 0.12 = 12%
        "annual_volatility": round(ann_vol, 4) if ann_vol is not None else None,      # 0.25 = 25%
        "sharpe_ratio": round(sharpe, 2) if sharpe is not None else None,

        "high_52w": round(high_52w, 2),
        "low_52w": round(low_52w, 2),
        "off_high_pct": round(off_high_pct, 2) if off_high_pct is not None else None,
        "off_low_pct": round(off_low_pct, 2) if off_low_pct is not None else None,

        "golden_cross": golden_cross,
        "death_cross": death_cross,
    }


async def get_technical_indicators(symbols: list[str], depot=None, **_) -> dict:
    """
    Async wrapper that computes technical indicators for each symbol.
    Runs blocking yfinance work in an executor.
    """
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
    "name": "get_technical_indicators",
    "description": (
        "Compute common technical indicators (moving averages, RSI-14, "
        "annualised return/volatility, Sharpe, 52-week extremes, MA crosses) "
        "for stock symbols."
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
    "fn": get_technical_indicators,
}