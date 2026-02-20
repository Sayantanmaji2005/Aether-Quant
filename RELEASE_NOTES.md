# Release Notes

## Version

`v0.1.0`

## Release Summary

AetherQuant `v0.1.0` is a client-delivery release of a quant platform foundation with research, backtesting, optimization, paper/live broker workflows, and operational controls.

## Highlights

- CLI workflows for fetch, signal, backtest, papertrade, optimize.
- FastAPI web dashboard with JSON APIs.
- Risk metrics and benchmark comparison.
- Portfolio optimization (risk-parity and mean-variance).
- Persistence layer for strategy runs, metrics, orders, and API audit logs.
- Role-based API access:
  - trader role (`AETHERQ_API_KEY`)
  - admin role (`AETHERQ_ADMIN_API_KEY`)
- API rate limiting (`AETHERQ_RATE_LIMIT_PER_MINUTE`).
- Live broker adapter scaffold with provider support:
  - `generic-rest`
  - `alpaca` auth headers (`APCA-API-KEY-ID`, `APCA-API-SECRET-KEY`)
- Docker support and CI quality gates.
- Release workflow for tagged Docker image publishing to GHCR.

## Quality Status

- Tests: passing
- Lint: passing
- Type checks: passing
- Coverage threshold: exceeded

## Delivery Checklist

- Set production secrets and keys via environment.
- Configure PostgreSQL and set `AETHERQ_DATABASE_URL`.
- Run `aetherquant db-init` once per environment.
- Verify `/healthz`, `/readyz`, and authenticated `/api/*` routes.
- Create and push release tag (`vX.Y.Z`) to trigger container release workflow.

## Upgrade Notes

- For Alpaca live provider, set:
  - `AETHERQ_LIVE_BROKER_PROVIDER=alpaca`
  - `AETHERQ_LIVE_BROKER_ENDPOINT` (e.g., paper endpoint)
  - `AETHERQ_LIVE_BROKER_KEY_ID`
  - `AETHERQ_LIVE_BROKER_TOKEN`
