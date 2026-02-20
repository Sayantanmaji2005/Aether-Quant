from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from aetherquant.portfolio import PortfolioConfig, equity_curve
from aetherquant.risk import annualized_return, max_drawdown, sharpe_ratio
from aetherquant.strategies.base import TradingStrategy


@dataclass(slots=True)
class BacktestResult:
    equity: pd.Series
    positions: pd.Series
    annual_return: float
    max_drawdown: float
    sharpe: float
    benchmark_equity: pd.Series
    benchmark_annual_return: float
    benchmark_max_drawdown: float
    benchmark_sharpe: float


class BacktestEngine:
    def __init__(self, strategy: TradingStrategy, portfolio_config: PortfolioConfig) -> None:
        self.strategy = strategy
        self.portfolio_config = portfolio_config

    def run(self, data: pd.DataFrame) -> BacktestResult:
        positions = self.strategy.generate_signals(data)
        curve = equity_curve(
            positions=positions,
            prices=data["close"],
            config=self.portfolio_config,
        )
        benchmark_positions = pd.Series(1.0, index=data.index)
        benchmark_curve = equity_curve(
            positions=benchmark_positions,
            prices=data["close"],
            config=self.portfolio_config,
        )

        return BacktestResult(
            equity=curve,
            positions=positions,
            annual_return=annualized_return(curve),
            max_drawdown=max_drawdown(curve),
            sharpe=sharpe_ratio(curve),
            benchmark_equity=benchmark_curve,
            benchmark_annual_return=annualized_return(benchmark_curve),
            benchmark_max_drawdown=max_drawdown(benchmark_curve),
            benchmark_sharpe=sharpe_ratio(benchmark_curve),
        )
