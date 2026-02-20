from __future__ import annotations

from datetime import datetime

from aetherquant.execution.models import Order, Side
from aetherquant.storage import RunStorage


def test_storage_records_runs_metrics_and_orders(tmp_path) -> None:
    db_path = tmp_path / "aetherquant.db"
    storage = RunStorage(f"sqlite:///{db_path}")
    storage.init_schema()

    backtest_id = storage.record_run(
        run_type="backtest",
        symbol="SPY",
        period="1y",
        interval="1d",
        payload={"final_equity": 101234.5},
        metrics={"annual_return": 0.12, "sharpe": 1.4},
    )
    papertrade_id = storage.record_run(
        run_type="papertrade",
        symbol="SPY",
        period="6mo",
        interval="1d",
        payload={"orders_placed": 1, "final_equity": 100500.0},
        metrics={"final_equity": 100500.0},
        orders=(
            Order(
                symbol="SPY",
                quantity=1.0,
                side=Side.BUY,
                timestamp=datetime(2026, 1, 1),
            ),
        ),
    )

    rows = storage.list_runs(limit=10)

    assert backtest_id > 0
    assert papertrade_id > backtest_id
    assert len(rows) == 2
    assert rows[0].run_type == "papertrade"
    assert rows[1].run_type == "backtest"


def test_storage_records_and_lists_audit_events(tmp_path) -> None:
    db_path = tmp_path / "audit.db"
    storage = RunStorage(f"sqlite:///{db_path}")
    storage.init_schema()
    event_id = storage.record_audit_event(
        method="POST",
        path="/api/backtest",
        status_code=200,
        request_id="req-1",
        actor_role="trader",
    )
    events = storage.list_audit_events(limit=10)
    assert event_id > 0
    assert len(events) == 1
    assert events[0].path == "/api/backtest"
