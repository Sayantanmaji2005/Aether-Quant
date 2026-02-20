from __future__ import annotations

import math

import pandas as pd


def annualized_return(equity: pd.Series, periods_per_year: int = 252) -> float:
    if len(equity) < 2:
        return 0.0
    total_return = float((equity.iloc[-1] / equity.iloc[0]) - 1.0)
    years = len(equity) / periods_per_year
    if years <= 0:
        return 0.0
    return float((1.0 + total_return) ** (1.0 / years) - 1.0)


def max_drawdown(equity: pd.Series) -> float:
    running_max = equity.cummax()
    drawdown = (equity / running_max) - 1.0
    return float(drawdown.min())


def sharpe_ratio(
    equity: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252,
) -> float:
    returns = equity.pct_change().dropna()
    if returns.empty:
        return 0.0

    excess = returns - (risk_free_rate / periods_per_year)
    std = excess.std(ddof=1)
    if std == 0 or math.isnan(std):
        return 0.0
    return float((excess.mean() / std) * math.sqrt(periods_per_year))
