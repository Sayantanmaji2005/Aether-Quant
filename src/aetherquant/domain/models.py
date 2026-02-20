from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True, frozen=True)
class PriceBar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(slots=True, frozen=True)
class SignalEvent:
    timestamp: datetime
    symbol: str
    action: str
    price: float
