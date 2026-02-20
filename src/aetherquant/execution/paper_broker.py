from __future__ import annotations

from aetherquant.execution.base import Broker
from aetherquant.execution.models import AccountSnapshot, Fill, Order, Position, Side


class PaperBroker(Broker):
    def __init__(
        self,
        starting_cash: float,
        commission_bps: float = 1.0,
        slippage_bps: float = 0.5,
    ) -> None:
        if starting_cash < 0:
            raise ValueError("starting_cash must be non-negative")
        if commission_bps < 0:
            raise ValueError("commission_bps must be non-negative")
        if slippage_bps < 0:
            raise ValueError("slippage_bps must be non-negative")

        self.cash = starting_cash
        self.commission_bps = commission_bps
        self.slippage_bps = slippage_bps
        self.position = Position(symbol="", quantity=0.0, avg_price=0.0)

    def submit_order(self, order: Order, market_price: float) -> Fill:
        slippage_factor = 1 + (self.slippage_bps / 10_000)
        if order.side == Side.BUY:
            execution_price = market_price * slippage_factor
        else:
            execution_price = market_price / slippage_factor

        notional = order.quantity * execution_price
        commission = notional * (self.commission_bps / 10_000)

        if order.side == Side.BUY:
            total_cost = notional + commission
            if total_cost > self.cash:
                raise ValueError("Insufficient cash for order")
            self.cash -= total_cost
            self._increase_position(order.symbol, order.quantity, execution_price)
        else:
            if order.quantity > self.position.quantity:
                raise ValueError("Insufficient position to sell")
            self.cash += notional - commission
            self.position.quantity -= order.quantity
            if self.position.quantity == 0:
                self.position.avg_price = 0.0

        return Fill(order=order, fill_price=execution_price, commission=commission)

    def account_snapshot(self, market_price: float, symbol: str) -> AccountSnapshot:
        if self.position.symbol != symbol or self.position.quantity == 0:
            market_value = 0.0
        else:
            market_value = self.position.quantity * market_price

        equity = self.cash + market_value
        return AccountSnapshot(cash=self.cash, market_value=market_value, equity=equity)

    def _increase_position(self, symbol: str, quantity: float, price: float) -> None:
        if self.position.symbol and self.position.symbol != symbol:
            raise ValueError("PaperBroker supports one active symbol per instance")

        existing_qty = self.position.quantity
        new_qty = existing_qty + quantity

        if new_qty <= 0:
            raise ValueError("Position quantity must remain positive after buy")

        self.position.symbol = symbol
        weighted_cost = (existing_qty * self.position.avg_price) + (quantity * price)
        self.position.avg_price = weighted_cost / new_qty
        self.position.quantity = new_qty
