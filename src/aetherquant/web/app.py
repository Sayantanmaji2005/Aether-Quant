from __future__ import annotations

import hmac
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Literal
from uuid import uuid4

import pandas as pd
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from aetherquant.backtest import BacktestEngine
from aetherquant.config import Settings
from aetherquant.data.yfinance_provider import YFinanceProvider
from aetherquant.execution.base import Broker
from aetherquant.execution.live_broker import LiveBroker
from aetherquant.execution.paper_broker import PaperBroker
from aetherquant.execution.trading_engine import TradingEngine
from aetherquant.optimization import (
    OptimizerConstraints,
    mean_variance_weights,
    risk_parity_weights,
)
from aetherquant.portfolio import PortfolioConfig
from aetherquant.rate_limit import InMemoryRateLimiter
from aetherquant.storage import RunStorage
from aetherquant.strategy import default_momentum_strategy

logger = logging.getLogger(__name__)


class BacktestRequest(BaseModel):
    symbol: str = "SPY"
    period: str = "1y"
    interval: str = "1d"


class PaperTradeRequest(BaseModel):
    symbol: str = "SPY"
    period: str = "6mo"
    interval: str = "1d"
    broker: Literal["paper", "live"] = "paper"
    broker_provider: Literal["generic-rest", "alpaca"] | None = None
    broker_endpoint: str | None = None
    broker_key_id: str | None = None
    broker_token: str | None = None
    slippage_bps: float | None = Field(default=None, ge=0.0)


class OptimizeRequest(BaseModel):
    symbols: list[str] = Field(default_factory=lambda: ["SPY", "QQQ", "TLT"])
    period: str = "1y"
    interval: str = "1d"
    method: Literal["risk-parity", "mean-variance"] = "risk-parity"
    allow_short: bool = False
    max_weight: float = Field(default=1.0, gt=0.0)
    risk_aversion: float = Field(default=3.0, gt=0.0)


PAGE = """
<!doctype html>
<html>
<head>
<meta charset='utf-8'/>
<meta name='viewport' content='width=device-width,initial-scale=1'/>
<title>AetherQuant Web</title>
<style>
body{
  font-family:Segoe UI,Arial,sans-serif;
  max-width:980px;
  margin:20px auto;
  padding:0 12px;
  background:#f5f7fb;
  color:#111
}
.card{background:#fff;border:1px solid #d8dee9;border-radius:10px;padding:14px;margin:12px 0}
.row{display:flex;gap:8px;flex-wrap:wrap}
input,select,button{padding:8px;border:1px solid #c6cfdd;border-radius:6px}
button{background:#0b57d0;color:#fff;border:none;cursor:pointer}
pre{background:#0f172a;color:#e2e8f0;padding:12px;border-radius:8px;overflow:auto}
h1{margin-bottom:6px}
</style>
</head>
<body>
<h1>AetherQuant Dashboard</h1>
<div class='card'>
<h3>API Security</h3>
<div class='row'>
<input id='api_key' placeholder='X-API-Key (optional)' style='min-width:260px'/>
</div>
</div>
<div class='card'>
<h3>Backtest</h3>
<div class='row'>
<input id='b_symbol' value='SPY' placeholder='Symbol'/>
<input id='b_period' value='1y' placeholder='Period'/>
<input id='b_interval' value='1d' placeholder='Interval'/>
<button onclick='runBacktest()'>Run</button>
</div>
</div>
<div class='card'>
<h3>Paper Trade</h3>
<div class='row'>
<input id='p_symbol' value='SPY'/>
<input id='p_period' value='6mo'/>
<input id='p_interval' value='1d'/>
<select id='p_broker'>
<option value='paper'>paper</option>
<option value='live'>live</option>
</select>
<select id='p_provider'>
<option value='generic-rest'>generic-rest</option>
<option value='alpaca'>alpaca</option>
</select>
<input id='p_endpoint' placeholder='Broker Endpoint' style='min-width:220px'/>
<input id='p_key_id' placeholder='Broker Key ID (alpaca)'/>
<input id='p_token' placeholder='Broker Token/Secret' style='min-width:220px'/>
<button onclick='runPaper()'>Run</button>
</div>
</div>
<div class='card'>
<h3>Optimize</h3>
<div class='row'>
<input id='o_symbols' value='SPY,QQQ,TLT' style='min-width:220px'/>
<select id='o_method'>
<option value='risk-parity'>risk-parity</option>
<option value='mean-variance'>mean-variance</option>
</select>
<button onclick='runOptimize()'>Run</button>
</div>
</div>
<pre id='out'>Ready.</pre>
<script>
async function post(url, payload){
  const apiKey = api_key.value.trim();
  const headers = {'Content-Type':'application/json'};
  if (apiKey) {
    headers['X-API-Key'] = apiKey;
  }
  const r = await fetch(url,{
    method:'POST',
    headers,
    body:JSON.stringify(payload)
  });
  const j = await r.json();
  document.getElementById('out').textContent = JSON.stringify(j,null,2);
}
function runBacktest(){
  post('/api/backtest',{symbol:b_symbol.value,period:b_period.value,interval:b_interval.value});
}
function runPaper(){
  post('/api/papertrade',{
    symbol:p_symbol.value,
    period:p_period.value,
    interval:p_interval.value,
    broker:p_broker.value,
    broker_provider:p_provider.value || null,
    broker_endpoint:p_endpoint.value.trim() || null,
    broker_key_id:p_key_id.value.trim() || null,
    broker_token:p_token.value.trim() || null
  });
}
function runOptimize(){
  post('/api/optimize',{symbols:o_symbols.value.split(',').map(x=>x.trim()).filter(Boolean),method:o_method.value});
}
</script>
</body>
</html>
"""


def _require_api_key(request: Request, settings: Settings) -> None:
    _require_role(request, settings, allowed_roles={"trader", "admin"})


def _request_role(request: Request, settings: Settings) -> str:
    if not settings.api_key and not settings.admin_api_key:
        return "anonymous"
    provided_key = request.headers.get("X-API-Key")
    if not provided_key:
        return ""
    if settings.admin_api_key and hmac.compare_digest(provided_key, settings.admin_api_key):
        return "admin"
    if settings.api_key and hmac.compare_digest(provided_key, settings.api_key):
        return "trader"
    return ""


def _require_role(request: Request, settings: Settings, allowed_roles: set[str]) -> str:
    role = _request_role(request, settings)
    if role == "anonymous":
        return role
    if not role:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if role not in allowed_roles:
        raise HTTPException(status_code=403, detail="Forbidden")
    return role


def _get_storage(settings: Settings) -> RunStorage | None:
    if not settings.database_url:
        return None
    storage = RunStorage(settings.database_url)
    storage.init_schema()
    return storage


def create_app() -> FastAPI:
    app = FastAPI(title="AetherQuant Web", version="0.1.0")
    rate_limit_per_minute = int(getattr(Settings(), "rate_limit_per_minute", 120))
    limiter = InMemoryRateLimiter(rate_limit_per_minute)

    @app.middleware("http")
    async def request_context_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        settings = Settings()
        storage = _get_storage(settings)
        actor_role = _request_role(request, settings) or "unauthenticated"
        principal = request.headers.get("X-API-Key") or (
            request.client.host if request.client else "unknown"
        )
        request_id = request.headers.get("X-Request-ID", uuid4().hex)
        started = time.perf_counter()
        if request.url.path.startswith("/api/"):
            allowed, retry_after = limiter.allow(principal)
            if not allowed:
                response = Response(status_code=429, content='{"detail":"Rate limit exceeded"}')
                response.headers["Content-Type"] = "application/json"
                response.headers["Retry-After"] = str(max(1, int(retry_after)))
            else:
                response = await call_next(request)
        else:
            response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"
        logger.info(
            "%s %s status=%s request_id=%s duration_ms=%.2f",
            request.method,
            request.url.path,
            response.status_code,
            request_id,
            elapsed_ms,
        )
        if storage is not None and request.url.path.startswith("/api/"):
            try:
                storage.record_audit_event(
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    request_id=request_id,
                    actor_role=actor_role,
                )
            except ValueError:
                logger.exception("Failed to persist audit event")
        return response

    @app.get("/", response_class=HTMLResponse)
    def home() -> str:
        return PAGE

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        settings = Settings()
        return {"status": "ok", "env": settings.env, "app": settings.app_name}

    @app.get("/readyz")
    def readyz() -> dict[str, str]:
        return {"status": "ready"}

    @app.post("/api/backtest")
    def backtest(req: BacktestRequest, request: Request) -> dict[str, float | int | str]:
        try:
            settings = Settings()
            _require_role(request, settings, allowed_roles={"trader", "admin"})
            storage = _get_storage(settings)
            provider = YFinanceProvider()
            frame = provider.fetch_ohlcv(req.symbol, period=req.period, interval=req.interval)

            engine = BacktestEngine(
                strategy=default_momentum_strategy(),
                portfolio_config=PortfolioConfig(
                    initial_cash=settings.initial_cash,
                    commission_bps=settings.commission_bps,
                ),
            )
            result = engine.run(frame)
            payload: dict[str, float | int | str] = {
                "symbol": req.symbol,
                "rows": int(len(frame)),
                "annual_return": round(result.annual_return, 6),
                "max_drawdown": round(result.max_drawdown, 6),
                "sharpe": round(result.sharpe, 6),
                "final_equity": round(float(result.equity.iloc[-1]), 2),
                "benchmark_annual_return": round(result.benchmark_annual_return, 6),
                "benchmark_max_drawdown": round(result.benchmark_max_drawdown, 6),
                "benchmark_sharpe": round(result.benchmark_sharpe, 6),
                "benchmark_final_equity": round(float(result.benchmark_equity.iloc[-1]), 2),
                "excess_annual_return": round(
                    result.annual_return - result.benchmark_annual_return,
                    6,
                ),
            }
            if storage is not None:
                run_id = storage.record_run(
                    run_type="backtest",
                    symbol=req.symbol,
                    period=req.period,
                    interval=req.interval,
                    payload=payload,
                    metrics={
                        "annual_return": result.annual_return,
                        "max_drawdown": result.max_drawdown,
                        "sharpe": result.sharpe,
                        "benchmark_annual_return": result.benchmark_annual_return,
                        "benchmark_max_drawdown": result.benchmark_max_drawdown,
                        "benchmark_sharpe": result.benchmark_sharpe,
                        "excess_annual_return": (
                            result.annual_return - result.benchmark_annual_return
                        ),
                    },
                )
                payload["run_id"] = run_id
            return payload
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/papertrade")
    def papertrade(req: PaperTradeRequest, request: Request) -> dict[str, float | int | str]:
        try:
            settings = Settings()
            _require_role(request, settings, allowed_roles={"trader", "admin"})
            storage = _get_storage(settings)
            provider = YFinanceProvider()
            frame = provider.fetch_ohlcv(req.symbol, period=req.period, interval=req.interval)
            targets = default_momentum_strategy().generate_signals(frame).clip(lower=0.0)

            broker: Broker
            if req.broker == "paper":
                broker = PaperBroker(
                    starting_cash=settings.initial_cash,
                    commission_bps=settings.commission_bps,
                    slippage_bps=(
                        settings.slippage_bps if req.slippage_bps is None else req.slippage_bps
                    ),
                )
            else:
                broker_provider = req.broker_provider or settings.live_broker_provider
                endpoint = req.broker_endpoint or settings.live_broker_endpoint
                key_id = req.broker_key_id or settings.live_broker_key_id
                token = req.broker_token or settings.live_broker_token
                if not endpoint:
                    raise HTTPException(
                        status_code=400,
                        detail="broker_endpoint is required for live broker.",
                    )
                if not token:
                    raise HTTPException(
                        status_code=400,
                        detail="broker_token is required for live broker.",
                    )
                if broker_provider == "alpaca" and not key_id:
                    raise HTTPException(
                        status_code=400,
                        detail="broker_key_id is required for alpaca provider.",
                    )
                broker = LiveBroker(
                    endpoint=endpoint,
                    api_key_id=key_id,
                    api_token=token,
                    provider=broker_provider,
                    dry_run=settings.live_broker_dry_run,
                )
            run_result = TradingEngine(broker=broker, symbol=req.symbol).run(
                prices=frame["close"],
                target_positions=targets,
            )

            payload: dict[str, float | int | str] = {
                "symbol": req.symbol,
                "broker": req.broker,
                "orders_placed": run_result.orders_placed,
                "start_equity": round(float(run_result.equity_curve.iloc[0]), 2),
                "final_equity": round(float(run_result.equity_curve.iloc[-1]), 2),
            }
            if storage is not None:
                run_id = storage.record_run(
                    run_type="papertrade",
                    symbol=req.symbol,
                    period=req.period,
                    interval=req.interval,
                    payload=payload,
                    metrics={
                        "start_equity": float(run_result.equity_curve.iloc[0]),
                        "final_equity": float(run_result.equity_curve.iloc[-1]),
                    },
                    orders=run_result.orders,
                )
                payload["run_id"] = run_id
            return payload
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/optimize")
    def optimize(req: OptimizeRequest, request: Request) -> dict[str, object]:
        try:
            settings = Settings()
            _require_role(request, settings, allowed_roles={"trader", "admin"})
            storage = _get_storage(settings)
            provider = YFinanceProvider()
            normalized = [s.strip().upper() for s in req.symbols if s.strip()]
            if len(normalized) < 2:
                raise HTTPException(status_code=400, detail="Provide at least two symbols.")
            if len(set(normalized)) != len(normalized):
                raise HTTPException(status_code=400, detail="symbols must be unique.")

            close_data: dict[str, pd.Series] = {}
            for symbol in normalized:
                frame = provider.fetch_ohlcv(symbol, period=req.period, interval=req.interval)
                close_data[symbol] = frame["close"]

            close = pd.DataFrame(close_data).dropna(how="any")
            returns = close.pct_change().dropna(how="any")
            if returns.empty:
                raise HTTPException(status_code=400, detail="No overlapping data to optimize.")

            constraints = OptimizerConstraints(
                allow_short=req.allow_short,
                max_weight=req.max_weight,
            )
            if req.method == "risk-parity":
                weights = risk_parity_weights(returns, constraints=constraints)
            else:
                weights = mean_variance_weights(
                    returns,
                    risk_aversion=req.risk_aversion,
                    constraints=constraints,
                )

            payload: dict[str, object] = {
                "method": req.method,
                "symbols": normalized,
                "weights": {k: round(float(v), 6) for k, v in weights.items()},
            }
            if storage is not None:
                run_id = storage.record_run(
                    run_type="optimize",
                    symbol=",".join(normalized),
                    period=req.period,
                    interval=req.interval,
                    payload=payload,
                    metrics={f"weight_{k}": float(v) for k, v in weights.items()},
                )
                payload["run_id"] = run_id
            return payload
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/runs")
    def runs(request: Request, limit: int = 20) -> dict[str, object]:
        settings = Settings()
        _require_role(request, settings, allowed_roles={"admin"})
        storage = _get_storage(settings)
        if storage is None:
            raise HTTPException(status_code=400, detail="Persistence is not configured.")
        rows = storage.list_runs(limit=limit)
        return {
            "runs": [
                {
                    "run_id": row.run_id,
                    "created_at": row.created_at,
                    "run_type": row.run_type,
                    "symbol": row.symbol,
                    "final_equity": row.final_equity,
                    "orders_placed": row.orders_placed,
                }
                for row in rows
            ]
        }

    @app.get("/api/audit")
    def audit(request: Request, limit: int = 100) -> dict[str, object]:
        settings = Settings()
        _require_role(request, settings, allowed_roles={"admin"})
        storage = _get_storage(settings)
        if storage is None:
            raise HTTPException(status_code=400, detail="Persistence is not configured.")
        rows = storage.list_audit_events(limit=limit)
        return {
            "events": [
                {
                    "event_id": row.event_id,
                    "created_at": row.created_at,
                    "method": row.method,
                    "path": row.path,
                    "status_code": row.status_code,
                    "request_id": row.request_id,
                    "actor_role": row.actor_role,
                }
                for row in rows
            ]
        }

    return app


def run() -> None:
    uvicorn.run("aetherquant.web.app:create_app", factory=True, host="127.0.0.1", port=8000)


app = create_app()
