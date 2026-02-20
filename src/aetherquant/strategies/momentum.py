from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from aetherquant.strategies.base import TradingStrategy


@dataclass(slots=True)
class MomentumConfig:
    lookback_fast: int = 20
    lookback_slow: int = 50


class MovingAverageCrossStrategy(TradingStrategy):
    def __init__(self, config: MomentumConfig | None = None) -> None:
        self.config = config or MomentumConfig()
        if self.config.lookback_fast >= self.config.lookback_slow:
            raise ValueError("lookback_fast must be < lookback_slow")

    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        close = data["close"]
        fast = close.rolling(
            self.config.lookback_fast,
            min_periods=self.config.lookback_fast,
        ).mean()
        slow = close.rolling(
            self.config.lookback_slow,
            min_periods=self.config.lookback_slow,
        ).mean()

        signals = pd.Series(0.0, index=close.index)
        signals[fast > slow] = 1.0
        signals[fast < slow] = -1.0
        return signals.ffill().fillna(0.0)
