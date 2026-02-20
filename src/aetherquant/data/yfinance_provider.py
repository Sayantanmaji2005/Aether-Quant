from __future__ import annotations

from typing import Any, cast

import pandas as pd
import yfinance as yf  # type: ignore[import-untyped]

from aetherquant.data.base import MarketDataProvider


class YFinanceProvider(MarketDataProvider):
    def fetch_ohlcv(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
    ) -> pd.DataFrame:
        frame = cast(
            pd.DataFrame,
            yf.download(
                symbol,
                period=period,
                interval=interval,
                progress=False,
                auto_adjust=True,
            ),
        )
        if frame.empty:
            raise ValueError(f"No data returned for symbol={symbol}")

        if isinstance(frame.columns, pd.MultiIndex):
            frame.columns = frame.columns.get_level_values(0)

        normalized = frame.rename(columns=str.lower)
        ordered_columns = ["open", "high", "low", "close", "volume"]
        expected = set(ordered_columns)
        missing = expected.difference(normalized.columns)
        if missing:
            raise ValueError(f"Missing expected columns: {sorted(missing)}")

        result: Any = normalized[ordered_columns].sort_index()
        return cast(pd.DataFrame, result)
