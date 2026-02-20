# AetherQuant

AetherQuant is a company-grade quant platform starter with research, backtesting, paper execution, and portfolio allocation building blocks.

## Capabilities

- Data abstraction with pluggable providers (`yfinance` included).
- Strategy abstraction with a moving-average crossover baseline.
- Backtesting engine with risk metrics.
- Paper broker and trading engine for simulated execution.
- Multi-asset optimizers (risk parity and mean-variance).
- CI quality gates with linting, type checks, and tests.

## Quick Start (Windows PowerShell)

```powershell
python -m venv .venv
. .venv/Scripts/Activate.ps1
pip install -e .[dev]
```

## CLI Workflows

```powershell
# Rule classification
aetherquant signal --latest-return 0.015

# Fetch OHLCV
aetherquant fetch --symbol SPY --period 1y --interval 1d --output data/spy.csv

# Backtest baseline momentum strategy
aetherquant backtest --symbol SPY --period 2y --interval 1d

# Paper-trading simulation
aetherquant papertrade --symbol SPY --period 6mo --interval 1d
aetherquant papertrade --symbol SPY --period 6mo --interval 1d --broker live --broker-provider generic-rest --broker-endpoint https://broker.example --broker-token $env:BROKER_TOKEN
aetherquant papertrade --symbol SPY --period 6mo --interval 1d --broker live --broker-provider alpaca --broker-endpoint https://paper-api.alpaca.markets --broker-key-id $env:ALPACA_KEY_ID --broker-token $env:ALPACA_SECRET_KEY

# Multi-asset optimization
aetherquant optimize --symbols SPY,QQQ,TLT --method risk-parity
aetherquant optimize --symbols SPY,QQQ,TLT --method mean-variance --risk-aversion 4

# Persistence schema and recent runs
aetherquant db-init --database-url postgresql://user:pass@localhost:5432/aetherquant
aetherquant db-runs --database-url postgresql://user:pass@localhost:5432/aetherquant --limit 20
aetherquant db-audit --database-url postgresql://user:pass@localhost:5432/aetherquant --limit 100
```

All command outputs are JSON-safe for pipeline integration except `signal` (single token output).

## Web Dashboard

```powershell
aetherquant-web
```

Then open: `http://127.0.0.1:8000`

Operational endpoints:
- `GET /healthz`
- `GET /readyz`
- `GET /api/runs` (requires persistence configuration)
- `GET /api/audit` (requires persistence configuration)

If `AETHERQ_API_KEY` or `AETHERQ_ADMIN_API_KEY` is set, `/api/*` endpoints require `X-API-Key`.
Role rules:
- `AETHERQ_API_KEY`: trader role (backtest/papertrade/optimize)
- `AETHERQ_ADMIN_API_KEY`: admin role (includes `/api/runs` and `/api/audit`)
If `AETHERQ_DATABASE_URL` is set (`postgresql://...` or `sqlite:///...`), run outputs are persisted and include `run_id`.
Rate limiting applies to `/api/*` requests based on `AETHERQ_RATE_LIMIT_PER_MINUTE`.

## Client API Key Handoff

API keys are generated and managed by the deployment owner, not by the web UI.

Recommended process:

1. Generate strong keys (trader and admin).
2. Store keys only in deployment secrets (`AETHERQ_API_KEY`, `AETHERQ_ADMIN_API_KEY`).
3. Share only the trader key with client users via a secure channel.
4. Keep admin key restricted to operators.
5. Rotate keys on a schedule and immediately after any suspected leak.

PowerShell key generation example:

```powershell
$b = New-Object byte[] 32; [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); ([System.BitConverter]::ToString($b)).Replace('-', '')
```

Scripted key generation:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/generate_keys.ps1
```

Options:

```powershell
# JSON output for CI/pipelines
powershell -ExecutionPolicy Bypass -File scripts/generate_keys.ps1 -Json

# 64-byte keys
powershell -ExecutionPolicy Bypass -File scripts/generate_keys.ps1 -Bytes 64

# Trader-only key (no admin key)
powershell -ExecutionPolicy Bypass -File scripts/generate_keys.ps1 -NoAdmin
```

Write `.env.production` directly:

```powershell
# Generate keys and write a full .env.production file
powershell -ExecutionPolicy Bypass -File scripts/write_env_production.ps1 -GenerateKeys -Force

# Or provide your own keys
powershell -ExecutionPolicy Bypass -File scripts/write_env_production.ps1 -TraderKey "<trader_key>" -AdminKey "<admin_key>" -Force
```

Header formats accepted by API routes:
- `X-API-Key: <key>`
- `Authorization: Bearer <key>`

## Docker

```powershell
docker build -t aetherquant:latest .
docker run --rm --env-file .env -v ${PWD}/data:/app/data aetherquant:latest backtest --symbol SPY --period 1y --interval 1d
```

Or with compose:

```powershell
docker compose up --build
```

## Project Layout

- `src/aetherquant/config.py`: environment-backed runtime settings.
- `src/aetherquant/data/`: market data provider interfaces and adapters.
- `src/aetherquant/strategies/`: strategy interfaces and implementations.
- `src/aetherquant/backtest.py`: backtest orchestration.
- `src/aetherquant/execution/`: broker abstractions and paper execution.
- `src/aetherquant/optimization.py`: portfolio optimization engines.
- `src/aetherquant/risk.py`: risk/performance metrics.
- `tests/`: automated test suite.
- `.github/workflows/ci.yml`: CI checks.
- `.github/workflows/release.yml`: tagged Docker release to GHCR.
- `docs/CLIENT_HANDOFF.md`: client onboarding and operational runbook.
- `docs/DEPLOY_RENDER.md`: one-click Render deployment guide.
- `RELEASE_NOTES.md`: release summary and delivery checklist.
- `.env.production.example`: production environment template.

## Team Quality Workflow

```powershell
ruff check .
mypy src
pytest
```

## Environment Variables

Prefix: `AETHERQ_`

- `AETHERQ_LOG_LEVEL` (default `INFO`)
- `AETHERQ_DEFAULT_SYMBOL` (default `SPY`)
- `AETHERQ_INITIAL_CASH` (default `100000`)
- `AETHERQ_COMMISSION_BPS` (default `1.0`)
- `AETHERQ_SLIPPAGE_BPS` (default `0.5`)
- `AETHERQ_API_KEY` (default unset; when set, protects `/api/*`)
- `AETHERQ_ADMIN_API_KEY` (default unset; admin access for operational endpoints)
- `AETHERQ_DATABASE_URL` (default unset; enables run/order/metric persistence)
- `AETHERQ_RATE_LIMIT_PER_MINUTE` (default `120`)
- `AETHERQ_LIVE_BROKER_ENDPOINT` (default unset; required for live broker mode)
- `AETHERQ_LIVE_BROKER_KEY_ID` (default unset; required for `alpaca`)
- `AETHERQ_LIVE_BROKER_TOKEN` (default unset; required for live broker mode)
- `AETHERQ_LIVE_BROKER_PROVIDER` (default `generic-rest`; supports `generic-rest` and `alpaca`)
- `AETHERQ_LIVE_BROKER_DRY_RUN` (default `true`)
