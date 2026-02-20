from __future__ import annotations

from abc import ABC, abstractmethod

from aetherquant.execution.models import AccountSnapshot, Fill, Order


class Broker(ABC):
    @abstractmethod
    def submit_order(self, order: Order, market_price: float) -> Fill:
        """Execute an order and return fill details."""

    @abstractmethod
    def account_snapshot(self, market_price: float, symbol: str) -> AccountSnapshot:
        """Return account values at the provided mark price."""
