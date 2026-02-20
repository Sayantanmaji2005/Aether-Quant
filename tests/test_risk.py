import pandas as pd

from aetherquant.risk import annualized_return, max_drawdown, sharpe_ratio


def test_max_drawdown_negative() -> None:
    equity = pd.Series([100, 110, 90, 120])
    assert max_drawdown(equity) < 0


def test_sharpe_ratio_is_float() -> None:
    equity = pd.Series([100, 101, 102, 100, 103])
    assert isinstance(sharpe_ratio(equity), float)


def test_annualized_return_non_negative_for_upward_curve() -> None:
    equity = pd.Series([100, 101, 102, 103, 104])
    assert annualized_return(equity) >= 0
