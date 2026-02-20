# Client Handoff Runbook

## Project Status

As of February 20, 2026, this repository is release-ready for client onboarding.

Current verification status:
- `pytest -q -o addopts=''`: passing
- `ruff check .`: passing
- `mypy src`: passing

## Prerequisites

- Python 3.11+
- Optional: Docker Desktop
- Optional: PostgreSQL 14+ (for persistence in production)

## First-Time Setup (Windows PowerShell)

```powershell
python -m venv .venv
. .venv/Scripts/Activate.ps1
pip install -e .[dev]
Copy-Item -Force .env.example .env
```

## Environment Configuration

Required for basic operation:
- `AETHERQ_LOG_LEVEL`
- `AETHERQ_INITIAL_CASH`
- `AETHERQ_COMMISSION_BPS`
- `AETHERQ_SLIPPAGE_BPS`

Recommended for client deployments:
- `AETHERQ_API_KEY` (trader role for strategy endpoints)
- `AETHERQ_ADMIN_API_KEY` (admin role for operational endpoints)
- `AETHERQ_DATABASE_URL` (`postgresql://...` for production)
- `AETHERQ_RATE_LIMIT_PER_MINUTE` (API abuse protection)

## Database Initialization

If persistence is enabled:

```powershell
aetherquant db-init --database-url postgresql://user:pass@host:5432/aetherquant
```

## Run Commands

CLI examples:

```powershell
aetherquant backtest --symbol SPY --period 1y --interval 1d
aetherquant papertrade --symbol SPY --period 6mo --interval 1d
aetherquant optimize --symbols SPY,QQQ,TLT --method risk-parity
aetherquant db-runs --limit 20
```

Web API:

```powershell
aetherquant-web
```

Endpoints:
- `GET /healthz`
- `GET /readyz`
- `POST /api/backtest`
- `POST /api/papertrade`
- `POST /api/optimize`
- `GET /api/runs` (requires persistence)
- `GET /api/audit` (requires persistence)

## Client Acceptance Checklist

- Health checks return `200`.
- API key enforcement works when `AETHERQ_API_KEY` is set.
- Rate limiting returns `429` when threshold is exceeded.
- At least one backtest run returns expected JSON payload.
- Persistence writes and lists runs when `AETHERQ_DATABASE_URL` is configured.
- Docker image builds and runs without local source edits.
- Test suite and static checks pass in CI.

## Operational Notes

- Responses include `X-Request-ID` and `X-Process-Time-Ms` for traceability.
- `/api/*` routes are unauthenticated only when `AETHERQ_API_KEY` is unset.
- For production, use PostgreSQL instead of SQLite.

## Handoff Recommendation

For client delivery, provide:
- This repository at current revision.
- A production `.env` template with real infrastructure values.
- A short demo script that runs one backtest, one papertrade, and one optimize call.
