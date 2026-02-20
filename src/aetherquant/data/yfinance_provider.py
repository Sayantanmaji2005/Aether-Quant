from __future__ import annotations

from typing import Any, cast

import pandas as pd
import yfinance as yf  # type: ignore[import-untyped]

from aetherquant.data.base import MarketDataProvider


class YFinanceProvider(MarketDataProvider):
    def _download(self, symbol: str, period: str, interval: str) -> pd.DataFrame:
        frame = cast(
            pd.DataFrame,
            yf.download(
                symbol,
                period=period,
                interval=interval,
                progress=False,
                auto_adjust=True,
                threads=False,
            ),
        )
        if not frame.empty:
            return frame

        ticker = yf.Ticker(symbol)
        return cast(
            pd.DataFrame,
            ticker.history(
                period=period,
                interval=interval,
                auto_adjust=True,
            ),
        )

    def fetch_ohlcv(
        self,
        symbol: str,
        period: str = "1y",
        interval: str = "1d",
    ) -> pd.DataFrame:
        normalized_symbol = symbol.strip().upper()
        frame = self._download(normalized_symbol, period=period, interval=interval)
        if frame.empty:
            raise ValueError(
                "No data returned for "
                f"symbol={normalized_symbol} period={period} interval={interval}"
            )

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
