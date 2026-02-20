# Architecture Overview

## Core principles

- Deterministic strategy computation from explicit market data inputs.
- Strict separation between market data, strategy logic, execution, and allocation.
- Testable pure functions for accounting, risk metrics, and optimization.

## Components

- `data`: provider interfaces + adapters (`YFinanceProvider`).
- `strategies`: signal generation algorithms.
- `backtest`: transforms signals into equity curves and metrics.
- `execution`: broker abstraction and paper broker simulation.
- `optimization`: multi-asset weight optimization engines.
- `risk`: sharpe, drawdown, and annualized return metrics.
- `storage`: persistence for runs, metrics, execution orders, and API audit logs.
- `rate_limit`: in-memory API rate limiter for `/api/*`.

## Request flow

1. CLI receives user intent.
2. Settings are loaded from environment.
3. Data provider fetches OHLCV data.
4. Strategy computes target positions.
5. Backtest or trading engine executes portfolio logic.
6. Risk/summary payload is emitted as JSON.
7. Optional persistence layer records run results and audit events.
8. API middleware enforces auth roles and rate limits.

## Extension points

- Add a provider by implementing `MarketDataProvider`.
- Add a strategy by implementing `TradingStrategy`.
- Add a broker by implementing `Broker`.
- Add optimization method in `optimization.py` and CLI option in `cli.py`.
