from __future__ import annotations

from dataclasses import dataclass

from aetherquant.strategies.momentum import MomentumConfig, MovingAverageCrossStrategy


@dataclass(slots=True)
class StrategyConfig:
    lookback_days: int = 20
    threshold: float = 0.01


def signal(latest_return: float, config: StrategyConfig | None = None) -> str:
    cfg = config or StrategyConfig()
    if latest_return > cfg.threshold:
        return "buy"
    if latest_return < -cfg.threshold:
        return "sell"
    return "hold"


def default_momentum_strategy() -> MovingAverageCrossStrategy:
    return MovingAverageCrossStrategy(
        MomentumConfig(lookback_fast=20, lookback_slow=50),
    )
