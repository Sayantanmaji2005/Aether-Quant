from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(slots=True)
class PortfolioConfig:
    initial_cash: float
    commission_bps: float = 1.0


def equity_curve(positions: pd.Series, prices: pd.Series, config: PortfolioConfig) -> pd.Series:
    returns = prices.pct_change().fillna(0.0)
    shifted_positions = positions.shift(1).fillna(0.0)

    gross = shifted_positions * returns
    turnover = positions.diff().abs().fillna(0.0)
    commission = turnover * (config.commission_bps / 10_000)
    net = gross - commission

    return config.initial_cash * (1.0 + net).cumprod()
