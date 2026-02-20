import pandas as pd

from aetherquant.strategies.momentum import MomentumConfig, MovingAverageCrossStrategy


def test_ma_cross_strategy_holds_before_windows_are_ready() -> None:
    data = pd.DataFrame({"close": [100, 101, 102, 103, 104]})
    strategy = MovingAverageCrossStrategy(MomentumConfig(lookback_fast=2, lookback_slow=4))

    signals = strategy.generate_signals(data)

    assert signals.iloc[0] == 0.0
    assert signals.iloc[1] == 0.0


def test_ma_cross_strategy_generates_long_signal() -> None:
    data = pd.DataFrame({"close": [100, 100, 101, 102, 103, 104, 105, 106]})
    strategy = MovingAverageCrossStrategy(MomentumConfig(lookback_fast=2, lookback_slow=3))

    signals = strategy.generate_signals(data)

    assert signals.iloc[-1] == 1.0
