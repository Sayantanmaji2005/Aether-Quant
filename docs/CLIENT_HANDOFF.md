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

### API Key Provisioning Procedure

1. Generate two keys (trader and admin) on an operator workstation.
2. Save both keys in your deployment secret manager.
3. Configure:
   - `AETHERQ_API_KEY=<trader_key>`
   - `AETHERQ_ADMIN_API_KEY=<admin_key>`
4. Share only `<trader_key>` with client-facing users.
5. Do not put real keys in repository files, tickets, or chat logs.
6. Rotate keys periodically and after any exposure event.

PowerShell key generation example:

```powershell
$b = New-Object byte[] 32; [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b); ([System.BitConverter]::ToString($b)).Replace('-', '')
```

Repository helper script:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/generate_keys.ps1
```

Additional script options:

```powershell
# Machine-readable output for CI
powershell -ExecutionPolicy Bypass -File scripts/generate_keys.ps1 -Json

# Customize key length in bytes
powershell -ExecutionPolicy Bypass -File scripts/generate_keys.ps1 -Bytes 64

# Trader-only key generation
powershell -ExecutionPolicy Bypass -File scripts/generate_keys.ps1 -NoAdmin
```

This prints:
- `TRADER_KEY=...`
- `ADMIN_KEY=...`
- ready-to-paste `AETHERQ_API_KEY=...` and `AETHERQ_ADMIN_API_KEY=...` lines.

Production env file helper:

```powershell
# Build .env.production from template with generated keys
powershell -ExecutionPolicy Bypass -File scripts/write_env_production.ps1 -GenerateKeys -Force

# Build .env.production with provided keys
powershell -ExecutionPolicy Bypass -File scripts/write_env_production.ps1 -TraderKey "<trader_key>" -AdminKey "<admin_key>" -Force
```

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

## Client Onboarding (Mobile)

### Operator Prep (before client test)

1. Generate keys with `scripts/generate_keys.ps1`.
2. Configure deployment secrets with generated values.
3. Restart/redeploy service so new keys are active.
4. Share only trader key with client through a secure channel.

### Client Steps (mobile browser)

1. Open dashboard URL over HTTPS.
2. In `API Security`, paste trader key into `X-API-Key` field.
3. Run `Backtest` with default values to validate access.
4. Confirm a JSON success payload appears (not `{"detail":"Unauthorized"}`).

### Mobile Troubleshooting

1. If `Unauthorized`, verify there are no leading/trailing spaces in the pasted key.
2. Re-copy key from secure channel and retry one endpoint.
3. Confirm operator restarted app after updating env secrets.
4. Confirm client is using trader key (not expired/rotated key).

## Client Acceptance Checklist

- Health checks return `200`.
- API key enforcement works when `AETHERQ_API_KEY` is set.
- Client can successfully call one strategy endpoint using `X-API-Key`.
- Client receives `401 Unauthorized` when key is missing or invalid.
- Rate limiting returns `429` when threshold is exceeded.
- At least one backtest run returns expected JSON payload.
- Persistence writes and lists runs when `AETHERQ_DATABASE_URL` is configured.
- Docker image builds and runs without local source edits.
- Test suite and static checks pass in CI.

## Operational Notes

- Responses include `X-Request-ID` and `X-Process-Time-Ms` for traceability.
- `/api/*` routes are unauthenticated only when `AETHERQ_API_KEY` is unset.
- API auth accepts either `X-API-Key` or `Authorization: Bearer <key>`.
- For production, use PostgreSQL instead of SQLite.

## Handoff Recommendation

For client delivery, provide:
- This repository at current revision.
- A production `.env` template with real infrastructure values.
- A short demo script that runs one backtest, one papertrade, and one optimize call.
