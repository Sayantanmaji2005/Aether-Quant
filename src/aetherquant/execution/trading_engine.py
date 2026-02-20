from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pandas as pd

from aetherquant.execution.base import Broker
from aetherquant.execution.models import Order, Side


@dataclass(slots=True)
class TradingRunResult:
    equity_curve: pd.Series
    orders_placed: int
    orders: tuple[Order, ...]


class TradingEngine:
    """Simple rule-based execution loop for paper/live broker adapters."""

    def __init__(self, broker: Broker, symbol: str) -> None:
        self.broker = broker
        self.symbol = symbol

    def run(self, prices: pd.Series, target_positions: pd.Series) -> TradingRunResult:
        if not prices.index.equals(target_positions.index):
            raise ValueError("prices and target_positions must have the same index")

        realized_position = 0.0
        equity_points: list[float] = []
        orders_placed = 0
        placed_orders: list[Order] = []

        for timestamp, price, target in zip(
            prices.index,
            prices.to_numpy(),
            target_positions.to_numpy(),
            strict=True,
        ):
            target_value = float(target)
            delta = target_value - realized_position

            if delta != 0.0:
                side = Side.BUY if delta > 0 else Side.SELL
                qty = abs(delta)
                order = Order(
                    symbol=self.symbol,
                    quantity=qty,
                    side=side,
                    timestamp=_to_datetime(timestamp),
                )
                self.broker.submit_order(order, market_price=float(price))
                placed_orders.append(order)
                realized_position = target_value
                orders_placed += 1

            snapshot = self.broker.account_snapshot(market_price=float(price), symbol=self.symbol)
            equity_points.append(snapshot.equity)

        equity_curve = pd.Series(equity_points, index=prices.index)
        return TradingRunResult(
            equity_curve=equity_curve,
            orders_placed=orders_placed,
            orders=tuple(placed_orders),
        )


def _to_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()
    raise TypeError("Index value must be datetime-like")
