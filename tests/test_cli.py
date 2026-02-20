from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

import aetherquant.cli as cli
from aetherquant.config import Settings
from aetherquant.storage import RunStorage


def _sample_frame() -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=6, freq="D")
    return pd.DataFrame(
        {
            "open": [100, 101, 102, 103, 104, 105],
            "high": [101, 102, 103, 104, 105, 106],
            "low": [99, 100, 101, 102, 103, 104],
            "close": [100, 101, 102, 103, 104, 105],
            "volume": [1_000] * 6,
        },
        index=index,
    )


class _Provider:
    def fetch_ohlcv(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
    ) -> pd.DataFrame:
        return _sample_frame()


def test_handle_fetch_writes_csv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(cli, "YFinanceProvider", _Provider)
    output = tmp_path / "out.csv"
    args = SimpleNamespace(symbol="SPY", period="1y", interval="1d", output=str(output))
    assert cli._handle_fetch(args) == 0
    assert output.exists()


def test_handle_backtest_prints_payload(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "YFinanceProvider", _Provider)
    args = SimpleNamespace(symbol="SPY", period="1y", interval="1d")

    code = cli._handle_backtest(args, Settings())

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["symbol"] == "SPY"
    assert "annual_return" in payload
    assert "benchmark_annual_return" in payload
    assert "excess_annual_return" in payload


def test_handle_papertrade_rejects_negative_slippage() -> None:
    args = SimpleNamespace(
        symbol="SPY",
        period="6mo",
        interval="1d",
        slippage_bps=-0.1,
        broker="paper",
        broker_provider=None,
        broker_endpoint=None,
        broker_key_id=None,
        broker_token=None,
    )
    with pytest.raises(SystemExit, match="slippage-bps must be non-negative"):
        cli._handle_papertrade(args, Settings())


def test_handle_papertrade_live_requires_credentials() -> None:
    args = SimpleNamespace(
        symbol="SPY",
        period="6mo",
        interval="1d",
        slippage_bps=0.1,
        broker="live",
        broker_provider="generic-rest",
        broker_endpoint=None,
        broker_key_id=None,
        broker_token=None,
    )
    with pytest.raises(SystemExit, match="broker-endpoint is required for live broker"):
        cli._handle_papertrade(args, Settings())


def test_handle_papertrade_alpaca_requires_key_id() -> None:
    args = SimpleNamespace(
        symbol="SPY",
        period="6mo",
        interval="1d",
        slippage_bps=0.1,
        broker="live",
        broker_provider="alpaca",
        broker_endpoint="https://paper-api.alpaca.markets",
        broker_key_id=None,
        broker_token="secret",
    )
    with pytest.raises(SystemExit, match="broker-key-id is required for alpaca provider"):
        cli._handle_papertrade(args, Settings())


def test_handle_optimize_prints_weights(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "YFinanceProvider", _Provider)
    args = SimpleNamespace(
        symbols="SPY,QQQ,TLT",
        period="1y",
        interval="1d",
        method="risk-parity",
        allow_short=False,
        max_weight=1.0,
        risk_aversion=3.0,
    )

    code = cli._handle_optimize(args)

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["method"] == "risk-parity"
    assert set(payload["weights"]) == {"SPY", "QQQ", "TLT"}


def test_handle_optimize_rejects_invalid_max_weight() -> None:
    args = SimpleNamespace(
        symbols="SPY,QQQ",
        period="1y",
        interval="1d",
        method="risk-parity",
        allow_short=False,
        max_weight=0.0,
        risk_aversion=3.0,
    )
    with pytest.raises(SystemExit, match="max-weight must be greater than zero"):
        cli._handle_optimize(args)


def test_handle_optimize_rejects_invalid_risk_aversion() -> None:
    args = SimpleNamespace(
        symbols="SPY,QQQ",
        period="1y",
        interval="1d",
        method="mean-variance",
        allow_short=False,
        max_weight=1.0,
        risk_aversion=0.0,
    )
    with pytest.raises(SystemExit, match="risk-aversion must be greater than zero"):
        cli._handle_optimize(args)


def test_handle_optimize_rejects_duplicate_symbols() -> None:
    args = SimpleNamespace(
        symbols="SPY,QQQ,SPY",
        period="1y",
        interval="1d",
        method="risk-parity",
        allow_short=False,
        max_weight=1.0,
        risk_aversion=3.0,
    )
    with pytest.raises(SystemExit, match="symbols must be unique"):
        cli._handle_optimize(args)


def test_main_converts_value_error_to_clean_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli, "configure_logging", lambda level: None)
    monkeypatch.setattr(
        cli,
        "_handle_fetch",
        lambda args: (_ for _ in ()).throw(ValueError("boom")),
    )
    monkeypatch.setattr("sys.argv", ["aetherquant", "fetch"])

    with pytest.raises(SystemExit, match="boom"):
        cli.main()


def test_db_init_and_db_runs(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db_url = f"sqlite:///{tmp_path / 'aq.db'}"
    settings = Settings(database_url=db_url)

    init_args = SimpleNamespace(database_url=None)
    assert cli._handle_db_init(init_args, settings) == 0

    # Seed one run directly through storage path used by CLI.
    backtest_args = SimpleNamespace(symbol="SPY", period="1y", interval="1d", database_url=None)
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(cli, "YFinanceProvider", _Provider)
        assert cli._handle_backtest(backtest_args, settings) == 0
        _ = capsys.readouterr()

    list_args = SimpleNamespace(database_url=None, limit=5)
    assert cli._handle_db_runs(list_args, settings) == 0
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["runs"]) >= 1

    storage = RunStorage(db_url)
    storage.record_audit_event(
        method="POST",
        path="/api/backtest",
        status_code=200,
        request_id="req-123",
        actor_role="trader",
    )
    audit_args = SimpleNamespace(database_url=None, limit=10)
    assert cli._handle_db_audit(audit_args, settings) == 0
    audit_payload = json.loads(capsys.readouterr().out)
    assert len(audit_payload["events"]) >= 1
