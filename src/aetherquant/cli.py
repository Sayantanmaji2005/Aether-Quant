from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import pandas as pd

from aetherquant.backtest import BacktestEngine
from aetherquant.config import Settings
from aetherquant.data.yfinance_provider import YFinanceProvider
from aetherquant.execution.base import Broker
from aetherquant.execution.live_broker import LiveBroker
from aetherquant.execution.paper_broker import PaperBroker
from aetherquant.execution.trading_engine import TradingEngine
from aetherquant.logging_config import configure_logging
from aetherquant.optimization import (
    OptimizerConstraints,
    mean_variance_weights,
    risk_parity_weights,
)
from aetherquant.portfolio import PortfolioConfig
from aetherquant.storage import RunStorage
from aetherquant.strategy import default_momentum_strategy, signal

logger = logging.getLogger(__name__)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AetherQuant CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch = subparsers.add_parser("fetch", help="Download OHLCV data")
    fetch.add_argument("--symbol", default="SPY")
    fetch.add_argument("--period", default="1y")
    fetch.add_argument("--interval", default="1d")
    fetch.add_argument("--output", default="data/latest.csv")

    backtest = subparsers.add_parser("backtest", help="Run baseline MA cross backtest")
    backtest.add_argument("--symbol", default="SPY")
    backtest.add_argument("--period", default="1y")
    backtest.add_argument("--interval", default="1d")

    signal_cmd = subparsers.add_parser("signal", help="Classify latest return")
    signal_cmd.add_argument("--latest-return", type=float, required=True)

    papertrade = subparsers.add_parser("papertrade", help="Run paper-trading simulation")
    papertrade.add_argument("--symbol", default="SPY")
    papertrade.add_argument("--period", default="6mo")
    papertrade.add_argument("--interval", default="1d")
    papertrade.add_argument("--slippage-bps", type=float, default=None)
    papertrade.add_argument("--broker", choices=["paper", "live"], default="paper")
    papertrade.add_argument(
        "--broker-provider",
        choices=["generic-rest", "alpaca"],
        default=None,
    )
    papertrade.add_argument("--broker-endpoint", default=None)
    papertrade.add_argument("--broker-key-id", default=None)
    papertrade.add_argument("--broker-token", default=None)

    optimize = subparsers.add_parser(
        "optimize",
        help="Optimize multi-asset portfolio weights",
    )
    optimize.add_argument(
        "--symbols",
        required=True,
        help="Comma-separated symbols, e.g. SPY,QQQ,TLT",
    )
    optimize.add_argument("--period", default="1y")
    optimize.add_argument("--interval", default="1d")
    optimize.add_argument(
        "--method",
        choices=["risk-parity", "mean-variance"],
        default="risk-parity",
    )
    optimize.add_argument("--allow-short", action="store_true")
    optimize.add_argument("--max-weight", type=float, default=1.0)
    optimize.add_argument("--risk-aversion", type=float, default=3.0)

    db_init = subparsers.add_parser("db-init", help="Initialize persistence schema")
    db_init.add_argument("--database-url", default=None)

    db_runs = subparsers.add_parser("db-runs", help="List recent persisted runs")
    db_runs.add_argument("--database-url", default=None)
    db_runs.add_argument("--limit", type=int, default=20)

    db_audit = subparsers.add_parser("db-audit", help="List recent API audit events")
    db_audit.add_argument("--database-url", default=None)
    db_audit.add_argument("--limit", type=int, default=100)

    return parser


def _handle_fetch(args: argparse.Namespace) -> int:
    provider = YFinanceProvider()
    frame = provider.fetch_ohlcv(args.symbol, period=args.period, interval=args.interval)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output)
    logger.info("Saved %s rows to %s", len(frame), output)
    return 0


def _handle_backtest(args: argparse.Namespace, settings: Settings) -> int:
    provider = YFinanceProvider()
    frame = provider.fetch_ohlcv(args.symbol, period=args.period, interval=args.interval)

    engine = BacktestEngine(
        strategy=default_momentum_strategy(),
        portfolio_config=PortfolioConfig(
            initial_cash=settings.initial_cash,
            commission_bps=settings.commission_bps,
        ),
    )
    result = engine.run(frame)

    payload = {
        "symbol": args.symbol,
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
    storage = _get_storage(settings, getattr(args, "database_url", None))
    if storage is not None:
        run_id = storage.record_run(
            run_type="backtest",
            symbol=args.symbol,
            period=args.period,
            interval=args.interval,
            payload=payload,
            metrics={
                "annual_return": result.annual_return,
                "max_drawdown": result.max_drawdown,
                "sharpe": result.sharpe,
                "benchmark_annual_return": result.benchmark_annual_return,
                "benchmark_max_drawdown": result.benchmark_max_drawdown,
                "benchmark_sharpe": result.benchmark_sharpe,
                "excess_annual_return": result.annual_return - result.benchmark_annual_return,
            },
        )
        payload["run_id"] = run_id
    print(json.dumps(payload))
    return 0


def _handle_signal(args: argparse.Namespace) -> int:
    print(signal(args.latest_return))
    return 0


def _handle_papertrade(args: argparse.Namespace, settings: Settings) -> int:
    provider = YFinanceProvider()
    frame = provider.fetch_ohlcv(args.symbol, period=args.period, interval=args.interval)
    strategy = default_momentum_strategy()
    targets = strategy.generate_signals(frame).clip(lower=0.0)

    slippage = settings.slippage_bps if args.slippage_bps is None else args.slippage_bps
    if slippage < 0:
        raise SystemExit("slippage-bps must be non-negative")

    broker: Broker
    if args.broker == "paper":
        broker = PaperBroker(
            starting_cash=settings.initial_cash,
            commission_bps=settings.commission_bps,
            slippage_bps=slippage,
        )
    else:
        broker_provider = args.broker_provider or settings.live_broker_provider
        endpoint = args.broker_endpoint or settings.live_broker_endpoint
        key_id = args.broker_key_id or settings.live_broker_key_id
        token = args.broker_token or settings.live_broker_token
        if not endpoint:
            raise SystemExit("broker-endpoint is required for live broker")
        if not token:
            raise SystemExit("broker-token is required for live broker")
        if broker_provider == "alpaca" and not key_id:
            raise SystemExit("broker-key-id is required for alpaca provider")
        broker = LiveBroker(
            endpoint=endpoint,
            api_token=token,
            api_key_id=key_id,
            provider=broker_provider,
            dry_run=settings.live_broker_dry_run,
        )
    engine = TradingEngine(broker=broker, symbol=args.symbol)
    run_result = engine.run(prices=frame["close"], target_positions=targets)

    payload = {
        "symbol": args.symbol,
        "broker": args.broker,
        "orders_placed": run_result.orders_placed,
        "final_equity": round(float(run_result.equity_curve.iloc[-1]), 2),
        "start_equity": round(float(run_result.equity_curve.iloc[0]), 2),
    }
    storage = _get_storage(settings, getattr(args, "database_url", None))
    if storage is not None:
        run_id = storage.record_run(
            run_type="papertrade",
            symbol=args.symbol,
            period=args.period,
            interval=args.interval,
            payload=payload,
            metrics={
                "start_equity": float(run_result.equity_curve.iloc[0]),
                "final_equity": float(run_result.equity_curve.iloc[-1]),
            },
            orders=run_result.orders,
        )
        payload["run_id"] = run_id
    print(json.dumps(payload))
    return 0


def _handle_optimize(args: argparse.Namespace) -> int:
    provider = YFinanceProvider()
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    if len(symbols) < 2:
        raise SystemExit("Provide at least two symbols for optimization")
    if len(set(symbols)) != len(symbols):
        raise SystemExit("symbols must be unique")
    if args.max_weight <= 0:
        raise SystemExit("max-weight must be greater than zero")
    if args.risk_aversion <= 0:
        raise SystemExit("risk-aversion must be greater than zero")

    close_data: dict[str, pd.Series] = {}
    for symbol in symbols:
        frame = provider.fetch_ohlcv(symbol, period=args.period, interval=args.interval)
        close_data[symbol] = frame["close"]

    close = pd.DataFrame(close_data).dropna(how="any")
    returns = close.pct_change().dropna(how="any")
    if returns.empty:
        raise SystemExit("Insufficient overlapping data to optimize")

    constraints = OptimizerConstraints(
        allow_short=args.allow_short,
        max_weight=args.max_weight,
    )
    if args.method == "risk-parity":
        weights = risk_parity_weights(returns, constraints=constraints)
    else:
        weights = mean_variance_weights(
            returns,
            risk_aversion=args.risk_aversion,
            constraints=constraints,
        )

    payload = {
        "method": args.method,
        "symbols": symbols,
        "weights": {k: round(float(v), 6) for k, v in weights.items()},
    }
    settings = Settings()
    storage = _get_storage(settings, getattr(args, "database_url", None))
    if storage is not None:
        run_id = storage.record_run(
            run_type="optimize",
            symbol=",".join(symbols),
            period=args.period,
            interval=args.interval,
            payload=payload,
            metrics={f"weight_{k}": float(v) for k, v in weights.items()},
        )
        payload["run_id"] = run_id
    print(json.dumps(payload))
    return 0


def _handle_db_init(args: argparse.Namespace, settings: Settings) -> int:
    storage = _require_storage(settings, args.database_url)
    storage.init_schema()
    print(json.dumps({"status": "ok"}))
    return 0


def _handle_db_runs(args: argparse.Namespace, settings: Settings) -> int:
    if args.limit <= 0:
        raise SystemExit("limit must be greater than zero")
    storage = _require_storage(settings, args.database_url)
    rows = storage.list_runs(limit=args.limit)
    payload = {
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
    print(json.dumps(payload))
    return 0


def _handle_db_audit(args: argparse.Namespace, settings: Settings) -> int:
    if args.limit <= 0:
        raise SystemExit("limit must be greater than zero")
    storage = _require_storage(settings, args.database_url)
    events = storage.list_audit_events(limit=args.limit)
    payload = {
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
            for row in events
        ]
    }
    print(json.dumps(payload))
    return 0


def _get_storage(settings: Settings, override_database_url: str | None) -> RunStorage | None:
    database_url = override_database_url or settings.database_url
    if not database_url:
        return None
    storage = RunStorage(database_url)
    storage.init_schema()
    return storage


def _require_storage(settings: Settings, override_database_url: str | None) -> RunStorage:
    storage = _get_storage(settings, override_database_url)
    if storage is None:
        raise SystemExit("database-url is required (or set AETHERQ_DATABASE_URL)")
    return storage


def main() -> None:
    settings = Settings()
    configure_logging(settings.log_level)

    parser = _build_parser()
    args = parser.parse_args()

    try:
        if args.command == "fetch":
            raise SystemExit(_handle_fetch(args))
        if args.command == "backtest":
            raise SystemExit(_handle_backtest(args, settings))
        if args.command == "signal":
            raise SystemExit(_handle_signal(args))
        if args.command == "papertrade":
            raise SystemExit(_handle_papertrade(args, settings))
        if args.command == "optimize":
            raise SystemExit(_handle_optimize(args))
        if args.command == "db-init":
            raise SystemExit(_handle_db_init(args, settings))
        if args.command == "db-runs":
            raise SystemExit(_handle_db_runs(args, settings))
        if args.command == "db-audit":
            raise SystemExit(_handle_db_audit(args, settings))
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    raise SystemExit("Unknown command")


if __name__ == "__main__":
    main()
