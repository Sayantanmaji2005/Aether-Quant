from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from aetherquant.execution.models import Order

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(slots=True, frozen=True)
class StoredRun:
    run_id: int
    created_at: str
    run_type: str
    symbol: str
    final_equity: float | None
    orders_placed: int | None


@dataclass(slots=True, frozen=True)
class AuditEvent:
    event_id: int
    created_at: str
    method: str
    path: str
    status_code: int
    request_id: str
    actor_role: str


class RunStorage:
    def __init__(self, database_url: str) -> None:
        if not database_url:
            raise ValueError("database_url must be non-empty")
        self.database_url = database_url
        self._is_postgres = database_url.startswith(("postgresql://", "postgres://"))
        self._sqlite_path: str | None
        if database_url.startswith("sqlite:///"):
            self._sqlite_path = database_url.removeprefix("sqlite:///")
        elif self._is_postgres:
            self._sqlite_path = None
        else:
            raise ValueError("database_url must start with sqlite:/// or postgresql://")

    def init_schema(self) -> None:
        with self._connect() as conn:
            self._run_schema_migrations(conn)
            conn.commit()

    def record_run(
        self,
        run_type: str,
        symbol: str,
        payload: dict[str, Any],
        metrics: dict[str, float],
        *,
        period: str | None = None,
        interval: str | None = None,
        orders: Sequence[Order] | None = None,
    ) -> int:
        if not run_type.strip():
            raise ValueError("run_type must be non-empty")
        if not symbol.strip():
            raise ValueError("symbol must be non-empty")

        payload_json = json.dumps(payload, sort_keys=True)
        created_at = datetime.now(UTC).isoformat()
        final_equity = payload.get("final_equity")
        orders_placed = len(orders) if orders is not None else payload.get("orders_placed")

        with self._connect() as conn:
            self._run_schema_migrations(conn)
            cur = conn.cursor()
            self._execute(
                cur,
                """
                INSERT INTO strategy_runs
                    (
                        created_at,
                        run_type,
                        symbol,
                        period,
                        interval,
                        payload_json,
                        final_equity,
                        orders_placed
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    created_at,
                    run_type,
                    symbol,
                    period,
                    interval,
                    payload_json,
                    self._to_float_or_none(final_equity),
                    self._to_int_or_none(orders_placed),
                ),
            )
            if self._is_postgres:
                inserted = cur.fetchone()
                if inserted is None:
                    raise ValueError("Failed to read inserted run id")
                run_id = int(inserted[0])
            else:
                run_id = int(cur.lastrowid)

            for metric_name, metric_value in metrics.items():
                self._execute(
                    cur,
                    """
                    INSERT INTO run_metrics (run_id, metric_name, metric_value)
                    VALUES (?, ?, ?)
                    """,
                    (run_id, metric_name, float(metric_value)),
                )

            for order in orders or ():
                self._execute(
                    cur,
                    """
                    INSERT INTO execution_orders
                        (run_id, symbol, side, quantity, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        order.symbol,
                        str(order.side),
                        float(order.quantity),
                        order.timestamp.isoformat(),
                    ),
                )

            conn.commit()
        return run_id

    def list_runs(self, limit: int = 20) -> list[StoredRun]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        with self._connect() as conn:
            self._run_schema_migrations(conn)
            cur = conn.cursor()
            self._execute(
                cur,
                """
                SELECT id, created_at, run_type, symbol, final_equity, orders_placed
                FROM strategy_runs
                ORDER BY id DESC
                LIMIT ?
                """,
                (int(limit),),
            )
            rows = cur.fetchall()

        return [
            StoredRun(
                run_id=int(row[0]),
                created_at=str(row[1]),
                run_type=str(row[2]),
                symbol=str(row[3]),
                final_equity=self._to_float_or_none(row[4]),
                orders_placed=self._to_int_or_none(row[5]),
            )
            for row in rows
        ]

    def record_audit_event(
        self,
        method: str,
        path: str,
        status_code: int,
        request_id: str,
        actor_role: str,
    ) -> int:
        created_at = datetime.now(UTC).isoformat()
        with self._connect() as conn:
            self._run_schema_migrations(conn)
            cur = conn.cursor()
            self._execute(
                cur,
                """
                INSERT INTO api_audit_logs
                    (created_at, method, path, status_code, request_id, actor_role)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (created_at, method, path, int(status_code), request_id, actor_role),
            )
            if self._is_postgres:
                inserted = cur.fetchone()
                if inserted is None:
                    raise ValueError("Failed to read inserted audit event id")
                event_id = int(inserted[0])
            else:
                event_id = int(cur.lastrowid)
            conn.commit()
        return event_id

    def list_audit_events(self, limit: int = 100) -> list[AuditEvent]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        with self._connect() as conn:
            self._run_schema_migrations(conn)
            cur = conn.cursor()
            self._execute(
                cur,
                """
                SELECT id, created_at, method, path, status_code, request_id, actor_role
                FROM api_audit_logs
                ORDER BY id DESC
                LIMIT ?
                """,
                (int(limit),),
            )
            rows = cur.fetchall()
        return [
            AuditEvent(
                event_id=int(row[0]),
                created_at=str(row[1]),
                method=str(row[2]),
                path=str(row[3]),
                status_code=int(row[4]),
                request_id=str(row[5]),
                actor_role=str(row[6]),
            )
            for row in rows
        ]

    def _connect(self) -> Any:
        if self._is_postgres:
            try:
                import psycopg
            except ImportError as exc:  # pragma: no cover
                raise ValueError(
                    "PostgreSQL URL configured but psycopg is not installed."
                ) from exc
            return psycopg.connect(self.database_url)

        assert self._sqlite_path is not None
        path = Path(self._sqlite_path)
        if str(path) != ":memory:":
            path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path))
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _run_schema_migrations(self, conn: Any) -> None:
        cur = conn.cursor()
        if self._is_postgres:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS strategy_runs (
                    id BIGSERIAL PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    run_type TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    period TEXT,
                    interval TEXT,
                    payload_json TEXT NOT NULL,
                    final_equity DOUBLE PRECISION,
                    orders_placed INTEGER
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS run_metrics (
                    id BIGSERIAL PRIMARY KEY,
                    run_id BIGINT NOT NULL REFERENCES strategy_runs(id) ON DELETE CASCADE,
                    metric_name TEXT NOT NULL,
                    metric_value DOUBLE PRECISION NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS execution_orders (
                    id BIGSERIAL PRIMARY KEY,
                    run_id BIGINT NOT NULL REFERENCES strategy_runs(id) ON DELETE CASCADE,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity DOUBLE PRECISION NOT NULL,
                    timestamp TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS api_audit_logs (
                    id BIGSERIAL PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    method TEXT NOT NULL,
                    path TEXT NOT NULL,
                    status_code INTEGER NOT NULL,
                    request_id TEXT NOT NULL,
                    actor_role TEXT NOT NULL
                )
                """
            )
        else:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS strategy_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    run_type TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    period TEXT,
                    interval TEXT,
                    payload_json TEXT NOT NULL,
                    final_equity REAL,
                    orders_placed INTEGER
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS run_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL REFERENCES strategy_runs(id) ON DELETE CASCADE,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS execution_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL REFERENCES strategy_runs(id) ON DELETE CASCADE,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    timestamp TEXT NOT NULL
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS api_audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    method TEXT NOT NULL,
                    path TEXT NOT NULL,
                    status_code INTEGER NOT NULL,
                    request_id TEXT NOT NULL,
                    actor_role TEXT NOT NULL
                )
                """
            )

    def _execute(self, cur: Any, query: str, params: tuple[Any, ...]) -> None:
        if self._is_postgres:
            pg_query = query.replace("?", "%s")
            if "INSERT INTO strategy_runs" in query or "INSERT INTO api_audit_logs" in query:
                pg_query += " RETURNING id"
            cur.execute(pg_query, params)
        else:
            cur.execute(query, params)

    @staticmethod
    def _to_float_or_none(value: Any) -> float | None:
        if value is None:
            return None
        return float(value)

    @staticmethod
    def _to_int_or_none(value: Any) -> int | None:
        if value is None:
            return None
        return int(value)
