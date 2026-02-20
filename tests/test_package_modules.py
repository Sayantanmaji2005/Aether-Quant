from __future__ import annotations

import logging
import runpy
from datetime import datetime

import aetherquant
import aetherquant.allocation as allocation
import aetherquant.data as data_mod
import aetherquant.domain as domain_mod
import aetherquant.web as web_mod
from aetherquant.domain.models import PriceBar, SignalEvent
from aetherquant.logging_config import configure_logging


def test_top_level_package_exports() -> None:
    assert "Settings" in aetherquant.__all__
    assert isinstance(aetherquant.__version__, str)


def test_reexport_modules() -> None:
    assert "OptimizerConstraints" in allocation.__all__
    assert "MarketDataProvider" in data_mod.__all__
    assert "PriceBar" in domain_mod.__all__
    assert "create_app" in web_mod.__all__


def test_domain_models_are_constructible() -> None:
    ts = datetime(2026, 1, 1)
    bar = PriceBar(timestamp=ts, open=1.0, high=2.0, low=0.5, close=1.5, volume=100.0)
    event = SignalEvent(timestamp=ts, symbol="SPY", action="buy", price=500.0)
    assert bar.close == 1.5
    assert event.action == "buy"


def test_configure_logging_uses_uppercase_level(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _fake_basic_config(**kwargs) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(logging, "basicConfig", _fake_basic_config)
    configure_logging("debug")
    assert captured["level"] == "DEBUG"


def test_main_module_invokes_cli_main(monkeypatch) -> None:
    called = {"count": 0}

    def _fake_main() -> None:
        called["count"] += 1

    monkeypatch.setattr("aetherquant.cli.main", _fake_main)
    runpy.run_module("aetherquant.__main__", run_name="__main__")
    assert called["count"] == 1
