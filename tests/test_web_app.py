from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

import aetherquant.web.app as web_app


def _sample_frame(offset: int = 0) -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=8, freq="D") + pd.Timedelta(days=offset)
    close = [100, 101, 102, 101, 103, 104, 105, 106]
    return pd.DataFrame(
        {
            "open": close,
            "high": [v + 1 for v in close],
            "low": [v - 1 for v in close],
            "close": close,
            "volume": [1_000] * len(close),
        },
        index=index,
    )


class _Provider:
    def fetch_ohlcv(self, symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        return _sample_frame()


class _SplitProvider:
    def fetch_ohlcv(self, symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        if symbol == "SPY":
            return _sample_frame(offset=0)
        return _sample_frame(offset=20)


class _SecuredSettings:
    app_name = "AetherQuant"
    env = "test"
    api_key = "secret-key"
    admin_api_key = "admin-key"
    initial_cash = 100_000.0
    commission_bps = 1.0
    slippage_bps = 0.5
    database_url = None
    rate_limit_per_minute = 120
    live_broker_endpoint = None
    live_broker_key_id = None
    live_broker_token = None
    live_broker_provider = "generic-rest"
    live_broker_dry_run = True

    def __init__(self) -> None:
        pass


def test_home_page_renders() -> None:
    client = TestClient(web_app.create_app())
    response = client.get("/")
    assert response.status_code == 200
    assert "AetherQuant Dashboard" in response.text


def test_health_and_readiness_endpoints() -> None:
    client = TestClient(web_app.create_app())
    health = client.get("/healthz")
    ready = client.get("/readyz")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"


def test_request_id_header_roundtrip() -> None:
    client = TestClient(web_app.create_app())
    response = client.get("/healthz", headers={"X-Request-ID": "req-123"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-123"
    assert "X-Process-Time-Ms" in response.headers


def test_rate_limit_blocks_excess_api_requests(monkeypatch) -> None:
    monkeypatch.setattr(web_app, "YFinanceProvider", _Provider)
    monkeypatch.setenv("AETHERQ_RATE_LIMIT_PER_MINUTE", "1")
    client = TestClient(web_app.create_app())
    first = client.post("/api/backtest", json={"symbol": "SPY"})
    second = client.post("/api/backtest", json={"symbol": "SPY"})
    assert first.status_code == 200
    assert second.status_code == 429
    assert "Retry-After" in second.headers


def test_backtest_endpoint_returns_metrics(monkeypatch) -> None:
    monkeypatch.setattr(web_app, "YFinanceProvider", _Provider)
    client = TestClient(web_app.create_app())
    response = client.post("/api/backtest", json={"symbol": "SPY"})
    body = response.json()
    assert response.status_code == 200
    assert body["symbol"] == "SPY"
    assert "annual_return" in body
    assert "benchmark_annual_return" in body
    assert "excess_annual_return" in body


def test_api_endpoints_require_api_key_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web_app, "YFinanceProvider", _Provider)
    monkeypatch.setattr(web_app, "Settings", _SecuredSettings)
    client = TestClient(web_app.create_app())
    response = client.post("/api/backtest", json={"symbol": "SPY"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Unauthorized"


def test_api_endpoints_accept_valid_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web_app, "YFinanceProvider", _Provider)
    monkeypatch.setattr(web_app, "Settings", _SecuredSettings)
    client = TestClient(web_app.create_app())
    response = client.post(
        "/api/backtest",
        json={"symbol": "SPY"},
        headers={"X-API-Key": "secret-key"},
    )
    assert response.status_code == 200


def test_api_endpoints_accept_bearer_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web_app, "YFinanceProvider", _Provider)
    monkeypatch.setattr(web_app, "Settings", _SecuredSettings)
    client = TestClient(web_app.create_app())
    response = client.post(
        "/api/backtest",
        json={"symbol": "SPY"},
        headers={"Authorization": "Bearer secret-key"},
    )
    assert response.status_code == 200


def test_api_endpoints_accept_quoted_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web_app, "YFinanceProvider", _Provider)
    monkeypatch.setattr(web_app, "Settings", _SecuredSettings)
    client = TestClient(web_app.create_app())
    response = client.post(
        "/api/backtest",
        json={"symbol": "SPY"},
        headers={"X-API-Key": '"secret-key"'},
    )
    assert response.status_code == 200


def test_admin_endpoint_forbids_trader_role(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web_app, "Settings", _SecuredSettings)
    client = TestClient(web_app.create_app())
    response = client.get("/api/runs", headers={"X-API-Key": "secret-key"})
    assert response.status_code == 403
    assert response.json()["detail"] == "Forbidden"


def test_runs_endpoint_requires_persistence_configuration() -> None:
    client = TestClient(web_app.create_app())
    response = client.get("/api/runs")
    assert response.status_code == 400
    assert response.json()["detail"] == "Persistence is not configured."


def test_backtest_persists_run_and_runs_endpoint_lists_it(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(web_app, "YFinanceProvider", _Provider)
    monkeypatch.setenv("AETHERQ_DATABASE_URL", f"sqlite:///{tmp_path / 'aq-web.db'}")
    monkeypatch.setenv("AETHERQ_ADMIN_API_KEY", "admin-key")
    client = TestClient(web_app.create_app())

    backtest = client.post(
        "/api/backtest",
        json={"symbol": "SPY"},
        headers={"X-API-Key": "admin-key"},
    )
    assert backtest.status_code == 200
    assert "run_id" in backtest.json()

    runs = client.get("/api/runs", headers={"X-API-Key": "admin-key"})
    assert runs.status_code == 200
    body = runs.json()
    assert len(body["runs"]) >= 1
    assert body["runs"][0]["run_type"] == "backtest"


def test_audit_endpoint_lists_events(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(web_app, "YFinanceProvider", _Provider)
    monkeypatch.setenv("AETHERQ_DATABASE_URL", f"sqlite:///{tmp_path / 'aq-audit.db'}")
    monkeypatch.setenv("AETHERQ_API_KEY", "trader-key")
    monkeypatch.setenv("AETHERQ_ADMIN_API_KEY", "admin-key")
    client = TestClient(web_app.create_app())

    backtest = client.post(
        "/api/backtest",
        json={"symbol": "SPY"},
        headers={"X-API-Key": "trader-key"},
    )
    assert backtest.status_code == 200

    audit = client.get("/api/audit", headers={"X-API-Key": "admin-key"})
    assert audit.status_code == 200
    events = audit.json()["events"]
    assert len(events) >= 1
    assert events[0]["path"].startswith("/api/")


def test_papertrade_endpoint_returns_equity(monkeypatch) -> None:
    monkeypatch.setattr(web_app, "YFinanceProvider", _Provider)
    client = TestClient(web_app.create_app())
    response = client.post("/api/papertrade", json={"symbol": "SPY"})
    body = response.json()
    assert response.status_code == 200
    assert body["broker"] == "paper"
    assert body["orders_placed"] >= 0
    assert body["final_equity"] > 0


def test_papertrade_live_mode_works_with_explicit_credentials(monkeypatch) -> None:
    monkeypatch.setattr(web_app, "YFinanceProvider", _Provider)
    client = TestClient(web_app.create_app())
    response = client.post(
        "/api/papertrade",
        json={
            "symbol": "SPY",
            "broker": "live",
            "broker_provider": "generic-rest",
            "broker_endpoint": "https://broker.example",
            "broker_token": "secret-token",
        },
    )
    body = response.json()
    assert response.status_code == 200
    assert body["broker"] == "live"


def test_papertrade_live_alpaca_requires_key_id(monkeypatch) -> None:
    monkeypatch.setattr(web_app, "YFinanceProvider", _Provider)
    client = TestClient(web_app.create_app())
    response = client.post(
        "/api/papertrade",
        json={
            "symbol": "SPY",
            "broker": "live",
            "broker_provider": "alpaca",
            "broker_endpoint": "https://paper-api.alpaca.markets",
            "broker_token": "secret-token",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "broker_key_id is required for alpaca provider."


def test_optimize_endpoint_returns_weights(monkeypatch) -> None:
    monkeypatch.setattr(web_app, "YFinanceProvider", _Provider)
    client = TestClient(web_app.create_app())
    response = client.post(
        "/api/optimize",
        json={"symbols": ["SPY", "QQQ", "TLT"], "method": "mean-variance"},
    )
    body = response.json()
    assert response.status_code == 200
    assert body["method"] == "mean-variance"
    assert set(body["weights"]) == {"SPY", "QQQ", "TLT"}


def test_optimize_endpoint_rejects_too_few_symbols(monkeypatch) -> None:
    monkeypatch.setattr(web_app, "YFinanceProvider", _Provider)
    client = TestClient(web_app.create_app())
    response = client.post("/api/optimize", json={"symbols": ["SPY"]})
    assert response.status_code == 400
    assert response.json()["detail"] == "Provide at least two symbols."


def test_optimize_endpoint_rejects_duplicate_symbols(monkeypatch) -> None:
    monkeypatch.setattr(web_app, "YFinanceProvider", _Provider)
    client = TestClient(web_app.create_app())
    response = client.post("/api/optimize", json={"symbols": ["SPY", "QQQ", "SPY"]})
    assert response.status_code == 400
    assert response.json()["detail"] == "symbols must be unique."


def test_optimize_endpoint_rejects_non_overlapping_data(monkeypatch) -> None:
    monkeypatch.setattr(web_app, "YFinanceProvider", _SplitProvider)
    client = TestClient(web_app.create_app())
    response = client.post("/api/optimize", json={"symbols": ["SPY", "QQQ"]})
    assert response.status_code == 400
    assert response.json()["detail"] == "No overlapping data to optimize."


def test_papertrade_request_validation() -> None:
    client = TestClient(web_app.create_app())
    response = client.post("/api/papertrade", json={"symbol": "SPY", "slippage_bps": -1})
    assert response.status_code == 422
