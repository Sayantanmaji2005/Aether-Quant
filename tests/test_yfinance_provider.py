from __future__ import annotations

import pandas as pd
import pytest

import aetherquant.data.yfinance_provider as yfp


def test_fetch_ohlcv_rejects_empty_download(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(yfp.yf, "download", lambda *args, **kwargs: pd.DataFrame())

    class _Ticker:
        def history(self, *args, **kwargs) -> pd.DataFrame:
            return pd.DataFrame()

    monkeypatch.setattr(yfp.yf, "Ticker", lambda *args, **kwargs: _Ticker())
    provider = yfp.YFinanceProvider()

    with pytest.raises(ValueError, match="No data returned"):
        provider.fetch_ohlcv("SPY")


def test_fetch_ohlcv_flattens_multiindex_and_orders_columns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    index = pd.date_range("2026-01-01", periods=2, freq="D")
    frame = pd.DataFrame(
        {
            ("Open", "SPY"): [100.0, 101.0],
            ("High", "SPY"): [101.0, 102.0],
            ("Low", "SPY"): [99.0, 100.0],
            ("Close", "SPY"): [100.5, 101.5],
            ("Volume", "SPY"): [1_000.0, 1_200.0],
        },
        index=index,
    )
    monkeypatch.setattr(yfp.yf, "download", lambda *args, **kwargs: frame)

    result = yfp.YFinanceProvider().fetch_ohlcv("SPY")

    assert list(result.columns) == ["open", "high", "low", "close", "volume"]
    assert len(result) == 2


def test_fetch_ohlcv_rejects_missing_columns(monkeypatch: pytest.MonkeyPatch) -> None:
    index = pd.date_range("2026-01-01", periods=2, freq="D")
    frame = pd.DataFrame({"Open": [100.0, 101.0], "Close": [101.0, 102.0]}, index=index)
    monkeypatch.setattr(yfp.yf, "download", lambda *args, **kwargs: frame)

    with pytest.raises(ValueError, match="Missing expected columns"):
        yfp.YFinanceProvider().fetch_ohlcv("SPY")
