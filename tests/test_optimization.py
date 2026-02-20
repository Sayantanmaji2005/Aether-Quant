import pandas as pd
import pytest

from aetherquant.optimization import (
    OptimizerConstraints,
    mean_variance_weights,
    risk_parity_weights,
)


def _sample_returns() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "SPY": [0.01, 0.005, -0.002, 0.007, 0.004],
            "QQQ": [0.013, 0.004, -0.003, 0.009, 0.006],
            "TLT": [0.002, 0.003, 0.004, -0.001, 0.001],
        }
    )


def test_risk_parity_weights_sum_to_one() -> None:
    weights = risk_parity_weights(
        _sample_returns(),
        OptimizerConstraints(allow_short=False, max_weight=0.9),
    )
    assert abs(float(weights.sum()) - 1.0) < 1e-6
    assert (weights >= 0.0).all()


def test_mean_variance_weights_sum_to_one() -> None:
    weights = mean_variance_weights(_sample_returns(), risk_aversion=2.0)
    assert abs(float(weights.sum()) - 1.0) < 1e-6


def test_optimizer_constraints_rejects_non_positive_max_weight() -> None:
    with pytest.raises(ValueError, match="max_weight must be greater than zero"):
        OptimizerConstraints(max_weight=0.0)


def test_mean_variance_weights_rejects_non_positive_risk_aversion() -> None:
    with pytest.raises(ValueError, match="risk_aversion must be greater than zero"):
        mean_variance_weights(_sample_returns(), risk_aversion=0.0)


def test_risk_parity_rejects_empty_returns() -> None:
    with pytest.raises(ValueError, match="returns must contain at least one asset"):
        risk_parity_weights(pd.DataFrame())


def test_risk_parity_rejects_infeasible_long_only_constraints() -> None:
    with pytest.raises(ValueError, match="Infeasible constraints"):
        risk_parity_weights(
            _sample_returns(),
            OptimizerConstraints(allow_short=False, max_weight=0.3),
        )


def test_mean_variance_rejects_infeasible_long_only_constraints() -> None:
    with pytest.raises(ValueError, match="Infeasible constraints"):
        mean_variance_weights(
            _sample_returns(),
            constraints=OptimizerConstraints(allow_short=False, max_weight=0.3),
        )
