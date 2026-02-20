from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol
from urllib import request as urllib_request

from aetherquant.execution.base import Broker
from aetherquant.execution.models import AccountSnapshot, Fill, Order


class LiveBrokerTransport(Protocol):
    def request_json(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        payload: dict[str, object] | None,
        timeout_seconds: float,
    ) -> dict[str, Any]: ...


class UrllibLiveBrokerTransport:
    def request_json(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        payload: dict[str, object] | None,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        body = None
        merged_headers = dict(headers)
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            merged_headers["Content-Type"] = "application/json"

        req = urllib_request.Request(
            url=url,
            method=method.upper(),
            data=body,
            headers=merged_headers,
        )
        with urllib_request.urlopen(req, timeout=timeout_seconds) as resp:
            content = resp.read().decode("utf-8")
        if not content.strip():
            return {}
        loaded = json.loads(content)
        if not isinstance(loaded, dict):
            raise ValueError("Live broker response must be a JSON object")
        return loaded


@dataclass(slots=True, frozen=True)
class LiveBrokerEndpoints:
    order_path: str
    account_path: str


def _provider_endpoints(provider: str) -> LiveBrokerEndpoints:
    normalized = provider.strip().lower()
    if normalized == "generic-rest":
        return LiveBrokerEndpoints(order_path="/orders", account_path="/account")
    if normalized == "alpaca":
        return LiveBrokerEndpoints(order_path="/v2/orders", account_path="/v2/account")
    raise ValueError("Unsupported live broker provider")


class LiveBroker(Broker):
    """Live broker adapter scaffold.

    In dry-run mode, returns synthetic fills at market price with zero commission.
    Set dry_run=False after implementing concrete broker API integration.
    """

    def __init__(
        self,
        endpoint: str,
        api_token: str,
        api_key_id: str | None = None,
        provider: str = "generic-rest",
        dry_run: bool = True,
        timeout_seconds: float = 10.0,
        transport: LiveBrokerTransport | None = None,
    ) -> None:
        if not endpoint.strip():
            raise ValueError("endpoint must be non-empty")
        if not api_token.strip():
            raise ValueError("api_token must be non-empty")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")

        self.endpoint = endpoint
        self.api_token = api_token
        self.api_key_id = api_key_id
        self.provider = provider
        self.dry_run = dry_run
        self.timeout_seconds = timeout_seconds
        self.transport: LiveBrokerTransport = transport or UrllibLiveBrokerTransport()
        self.endpoints = _provider_endpoints(provider)

    def submit_order(self, order: Order, market_price: float) -> Fill:
        if self.dry_run:
            return Fill(order=order, fill_price=market_price, commission=0.0)
        response = self.transport.request_json(
            method="POST",
            url=f"{self.endpoint}{self.endpoints.order_path}",
            headers=self._headers(),
            payload={
                "symbol": order.symbol,
                "qty": order.quantity,
                "side": order.side.value,
                "type": "market",
                "time_in_force": "day",
            },
            timeout_seconds=self.timeout_seconds,
        )
        fill_price = _as_float(response.get("fill_price"), default=market_price)
        commission = _as_float(response.get("commission"), default=0.0)
        return Fill(order=order, fill_price=fill_price, commission=commission)

    def account_snapshot(self, market_price: float, symbol: str) -> AccountSnapshot:
        if self.dry_run:
            return AccountSnapshot(cash=0.0, market_value=0.0, equity=0.0)
        response = self.transport.request_json(
            method="GET",
            url=f"{self.endpoint}{self.endpoints.account_path}",
            headers=self._headers(),
            payload=None,
            timeout_seconds=self.timeout_seconds,
        )
        cash = _as_float(response.get("cash"), default=0.0)
        equity = _as_float(
            response.get("equity", response.get("portfolio_value")),
            default=cash,
        )
        market_value = _as_float(response.get("market_value"), default=(equity - cash))
        return AccountSnapshot(cash=cash, market_value=market_value, equity=equity)

    def _headers(self) -> dict[str, str]:
        if self.provider == "alpaca":
            if not self.api_key_id:
                raise ValueError("api_key_id is required for alpaca provider")
            return {
                "APCA-API-KEY-ID": self.api_key_id,
                "APCA-API-SECRET-KEY": self.api_token,
            }
        return {"Authorization": f"Bearer {self.api_token}"}


def _as_float(value: object, default: float) -> float:
    if value is None:
        return default
    if not isinstance(value, (int, float, str)):
        raise ValueError("Live broker response contains non-numeric value")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("Live broker response contains non-numeric value") from exc
