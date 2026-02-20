from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class TradingStrategy(ABC):
    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.Series:
        """Return a position series indexed like data.close."""
