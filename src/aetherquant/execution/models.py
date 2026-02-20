from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Side(StrEnum):
    BUY = "buy"
    SELL = "sell"


@dataclass(slots=True, frozen=True)
class Order:
    symbol: str
    quantity: float
    side: Side
    timestamp: datetime


@dataclass(slots=True, frozen=True)
class Fill:
    order: Order
    fill_price: float
    commission: float


@dataclass(slots=True)
class Position:
    symbol: str
    quantity: float = 0.0
    avg_price: float = 0.0


@dataclass(slots=True)
class AccountSnapshot:
    cash: float
    market_value: float
    equity: float
