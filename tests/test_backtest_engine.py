import pandas as pd

from aetherquant.backtest import BacktestEngine
from aetherquant.portfolio import PortfolioConfig
from aetherquant.strategies.momentum import MomentumConfig, MovingAverageCrossStrategy


def test_backtest_engine_returns_metrics() -> None:
    prices = pd.DataFrame(
        {
            "close": [100, 101, 102, 101, 103, 104, 103, 106],
            "open": [100, 101, 102, 101, 103, 104, 103, 106],
            "high": [100, 101, 102, 101, 103, 104, 103, 106],
            "low": [100, 101, 102, 101, 103, 104, 103, 106],
            "volume": [1_000] * 8,
        }
    )

    engine = BacktestEngine(
        strategy=MovingAverageCrossStrategy(MomentumConfig(lookback_fast=2, lookback_slow=3)),
        portfolio_config=PortfolioConfig(initial_cash=100_000, commission_bps=1.0),
    )
    result = engine.run(prices)

    assert len(result.equity) == len(prices)
    assert isinstance(result.annual_return, float)
    assert isinstance(result.max_drawdown, float)
    assert isinstance(result.sharpe, float)
    assert isinstance(result.benchmark_annual_return, float)
    assert isinstance(result.benchmark_max_drawdown, float)
    assert isinstance(result.benchmark_sharpe, float)
    assert result.equity.iloc[-1] > 0
    assert result.benchmark_equity.iloc[-1] > 0
