from datetime import datetime

import pandas as pd

from aetherquant.execution.live_broker import LiveBroker
from aetherquant.execution.models import Order, Side
from aetherquant.execution.paper_broker import PaperBroker
from aetherquant.execution.trading_engine import TradingEngine


def test_paper_broker_buy_and_sell_round_trip() -> None:
    broker = PaperBroker(starting_cash=10_000, commission_bps=1.0, slippage_bps=0.0)
    buy = Order(symbol="SPY", quantity=10, side=Side.BUY, timestamp=datetime(2026, 1, 1))
    sell = Order(symbol="SPY", quantity=10, side=Side.SELL, timestamp=datetime(2026, 1, 2))

    broker.submit_order(buy, market_price=100.0)
    broker.submit_order(sell, market_price=101.0)

    snapshot = broker.account_snapshot(market_price=101.0, symbol="SPY")
    assert snapshot.equity > 10_000


def test_trading_engine_places_orders_on_target_change() -> None:
    index = pd.date_range("2026-01-01", periods=4, freq="D")
    prices = pd.Series([100.0, 101.0, 102.0, 101.0], index=index)
    targets = pd.Series([0.0, 1.0, 1.0, 0.0], index=index)

    broker = PaperBroker(starting_cash=1_000_000, commission_bps=0.0, slippage_bps=0.0)
    engine = TradingEngine(broker=broker, symbol="SPY")

    result = engine.run(prices=prices, target_positions=targets)

    assert result.orders_placed == 2
    assert len(result.orders) == 2
    assert len(result.equity_curve) == 4


def test_live_broker_dry_run_returns_synthetic_fill() -> None:
    broker = LiveBroker(endpoint="https://broker.example", api_token="token", dry_run=True)
    order = Order(symbol="SPY", quantity=1, side=Side.BUY, timestamp=datetime(2026, 1, 1))
    fill = broker.submit_order(order, market_price=500.0)
    assert fill.fill_price == 500.0
    assert fill.commission == 0.0


def test_live_broker_real_mode_maps_order_and_account() -> None:
    class _Transport:
        def request_json(
            self,
            method: str,
            url: str,
            headers: dict[str, str],
            payload: dict[str, object] | None,
            timeout_seconds: float,
        ) -> dict[str, object]:
            if method == "POST":
                assert url.endswith("/orders")
                assert headers["Authorization"] == "Bearer token"
                assert payload is not None
                assert payload["symbol"] == "SPY"
                return {"fill_price": 502.25, "commission": 1.2}
            assert url.endswith("/account")
            return {"cash": "1000.0", "equity": "1510.5"}

    broker = LiveBroker(
        endpoint="https://broker.example",
        api_token="token",
        dry_run=False,
        transport=_Transport(),
    )
    order = Order(symbol="SPY", quantity=1, side=Side.BUY, timestamp=datetime(2026, 1, 1))
    fill = broker.submit_order(order, market_price=500.0)
    snapshot = broker.account_snapshot(market_price=500.0, symbol="SPY")

    assert fill.fill_price == 502.25
    assert fill.commission == 1.2
    assert snapshot.cash == 1000.0
    assert snapshot.equity == 1510.5
    assert snapshot.market_value == 510.5


def test_live_broker_alpaca_headers() -> None:
    class _Transport:
        def request_json(
            self,
            method: str,
            url: str,
            headers: dict[str, str],
            payload: dict[str, object] | None,
            timeout_seconds: float,
        ) -> dict[str, object]:
            assert headers["APCA-API-KEY-ID"] == "key-id"
            assert headers["APCA-API-SECRET-KEY"] == "secret"
            if method == "POST":
                return {"fill_price": 500.0, "commission": 0.0}
            return {"cash": 1000.0, "portfolio_value": 1000.0}

    broker = LiveBroker(
        endpoint="https://paper-api.alpaca.markets",
        api_token="secret",
        api_key_id="key-id",
        provider="alpaca",
        dry_run=False,
        transport=_Transport(),
    )
    order = Order(symbol="SPY", quantity=1, side=Side.BUY, timestamp=datetime(2026, 1, 1))
    fill = broker.submit_order(order, market_price=500.0)
    assert fill.fill_price == 500.0
