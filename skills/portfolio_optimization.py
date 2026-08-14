"""
Skill: optimize_portfolio
Compute optimal portfolio weights based on modern portfolio theory (Markowitz).
Supports bounds for minimum and maximum weights, and different objectives (max sharpe, min volatility).
"""

import yfinance as yf
import asyncio
from pypfopt.expected_returns import mean_historical_return
from pypfopt.risk_models import CovarianceShrinkage
from pypfopt.efficient_frontier import EfficientFrontier

DOC = """Use this skill to optimize a portfolio based on modern portfolio theory.
It determines the optimal weight for each asset to maximize the Sharpe ratio or minimize volatility.

Call it when the user asks to:
- Optimize their portfolio
- Rebalance their depot
- Find the best allocation for a list of stocks
- Apply weight constraints like "max 20% in any stock" or "at least 5% in each"

Arguments:
- symbols (list, optional): List of tickers to optimize. If empty, uses the current depot holdings.
- min_weight (float, optional): Minimum weight for any asset (e.g., 0.05 for 5%). Defaults to 0.0.
- max_weight (float, optional): Maximum weight for any asset (e.g., 0.20 for 20%). Defaults to 1.0.
- objective (str, optional): The optimization goal. Either "max_sharpe" or "min_volatility". Defaults to "max_sharpe".
"""

def _compute_optimization(symbols: list[str], min_weight: float, max_weight: float, objective: str) -> dict:
    if not symbols or len(symbols) < 2:
        return {"error": "Portfolio optimization requires at least 2 symbols."}

    # Bound validations
    if min_weight < 0 or max_weight > 1 or min_weight > max_weight:
        return {"error": "Invalid weight bounds. Must be between 0 and 1, and min_weight <= max_weight."}

    if len(symbols) * min_weight > 1.0:
        return {"error": f"min_weight {min_weight} is too high for {len(symbols)} assets."}
    if len(symbols) * max_weight < 1.0:
        return {"error": f"max_weight {max_weight} is too low for {len(symbols)} assets."}

    import pandas as pd

    # Download 1 year of data
    df = yf.download(symbols, period="1y", auto_adjust=True, progress=False)
    if df.empty:
        return {"error": "No data available for the provided symbols."}

    # Handle single column case if yfinance returns different shape
    if isinstance(df.columns, pd.MultiIndex):
        close_prices = df["Close"]
    else:
        close_prices = df

    # Drop columns with all NaNs
    close_prices = close_prices.dropna(axis=1, how='all')
    valid_symbols = list(close_prices.columns)

    if len(valid_symbols) < 2:
         return {"error": "Not enough valid data to perform optimization (need at least 2 assets)."}

    # Check if bounds are still valid after removing invalid symbols
    if len(valid_symbols) * min_weight > 1.0:
        return {"error": f"After removing invalid data, min_weight {min_weight} is too high for {len(valid_symbols)} remaining assets."}
    if len(valid_symbols) * max_weight < 1.0:
        return {"error": f"After removing invalid data, max_weight {max_weight} is too low for {len(valid_symbols)} remaining assets."}

    try:
        mu = mean_historical_return(close_prices)
        S = CovarianceShrinkage(close_prices).ledoit_wolf()

        ef = EfficientFrontier(mu, S, weight_bounds=(min_weight, max_weight))

        if objective == "min_volatility":
            weights = ef.min_volatility()
        else: # default to max_sharpe
            weights = ef.max_sharpe()

        cleaned_weights = ef.clean_weights()
        performance = ef.portfolio_performance(verbose=False)

        return {
            "weights": {sym: round(weight, 4) for sym, weight in cleaned_weights.items()},
            "expected_annual_return": round(performance[0], 4),
            "annual_volatility": round(performance[1], 4),
            "sharpe_ratio": round(performance[2], 4),
            "objective": objective,
            "min_weight_constraint": min_weight,
            "max_weight_constraint": max_weight
        }
    except Exception as e:
        return {"error": f"Optimization failed: {str(e)}"}

async def optimize_portfolio(
    symbols: list[str] = None,
    min_weight: float = 0.0,
    max_weight: float = 1.0,
    objective: str = "max_sharpe",
    depot: dict = None,
    **_
) -> dict:

    # If no symbols provided, use depot holdings
    if not symbols:
        if not depot or not depot.get("holdings"):
            return {"error": "No symbols provided and depot is empty."}
        symbols = [h["symbol"] for h in depot.get("holdings", [])]

    loop = asyncio.get_event_loop()

    return await loop.run_in_executor(
        None,
        _compute_optimization,
        symbols,
        min_weight,
        max_weight,
        objective
    )

SKILL = {
    "name": "optimize_portfolio",
    "description": (
        "Compute optimal portfolio weights based on modern portfolio theory (Markowitz). "
        "Supports bounds for minimum and maximum weights, and different objectives (max sharpe, min volatility)."
    ),
    "doc": DOC,
    "parameters": {
        "type": "object",
        "properties": {
            "symbols": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Ticker symbols to optimize. If empty, uses the current depot holdings.",
            },
            "min_weight": {
                "type": "number",
                "description": "Minimum weight for any asset (e.g., 0.05 for 5%). Defaults to 0.0.",
            },
            "max_weight": {
                "type": "number",
                "description": "Maximum weight for any asset (e.g., 0.20 for 20%). Defaults to 1.0.",
            },
            "objective": {
                "type": "string",
                "description": "The optimization goal. Either 'max_sharpe' or 'min_volatility'. Defaults to 'max_sharpe'.",
            }
        },
        "required": [],
    },
    "fn": optimize_portfolio,
}
