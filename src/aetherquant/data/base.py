from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class MarketDataProvider(ABC):
    @abstractmethod
    def fetch_ohlcv(self, symbol: str, period: str = "1y", interval: str = "1d") -> pd.DataFrame:
        """Return OHLCV data indexed by timestamp."""
