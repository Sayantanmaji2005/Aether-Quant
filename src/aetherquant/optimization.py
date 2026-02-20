from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize  # type: ignore[import-untyped]


@dataclass(slots=True)
class OptimizerConstraints:
    allow_short: bool = False
    max_weight: float = 1.0

    def __post_init__(self) -> None:
        if self.max_weight <= 0:
            raise ValueError("max_weight must be greater than zero")

    def validate_feasibility(self, n_assets: int) -> None:
        if n_assets <= 0:
            raise ValueError("n_assets must be greater than zero")
        if not self.allow_short and (self.max_weight * n_assets) < 1.0:
            raise ValueError(
                "Infeasible constraints: max_weight is too small for long-only allocation."
            )


def risk_parity_weights(
    returns: pd.DataFrame,
    constraints: OptimizerConstraints | None = None,
) -> pd.Series:
    _validate_returns(returns)
    cfg = constraints or OptimizerConstraints()
    cov = returns.cov().to_numpy()
    n_assets = cov.shape[0]
    cfg.validate_feasibility(n_assets)

    initial = np.full(n_assets, 1.0 / n_assets)
    bounds = _bounds(n_assets, cfg)
    cons = ({"type": "eq", "fun": lambda w: np.sum(w) - 1.0},)

    def objective(weights: np.ndarray) -> float:
        portfolio_var = float(weights.T @ cov @ weights)
        if portfolio_var <= 0:
            return 1e9
        marginal = cov @ weights
        contrib = weights * marginal / np.sqrt(portfolio_var)
        target = np.full(n_assets, np.mean(contrib))
        return float(np.sum((contrib - target) ** 2))

    result = minimize(objective, initial, method="SLSQP", bounds=bounds, constraints=cons)
    if not result.success:
        raise ValueError(f"Risk parity optimization failed: {result.message}")

    return pd.Series(result.x, index=returns.columns)


def mean_variance_weights(
    returns: pd.DataFrame,
    risk_aversion: float = 3.0,
    constraints: OptimizerConstraints | None = None,
) -> pd.Series:
    _validate_returns(returns)
    if risk_aversion <= 0:
        raise ValueError("risk_aversion must be greater than zero")

    cfg = constraints or OptimizerConstraints()
    mu = returns.mean().to_numpy()
    cov = returns.cov().to_numpy()
    n_assets = cov.shape[0]
    cfg.validate_feasibility(n_assets)

    initial = np.full(n_assets, 1.0 / n_assets)
    bounds = _bounds(n_assets, cfg)
    cons = ({"type": "eq", "fun": lambda w: np.sum(w) - 1.0},)

    def objective(weights: np.ndarray) -> float:
        expected = float(mu @ weights)
        variance = float(weights.T @ cov @ weights)
        return -expected + risk_aversion * variance

    result = minimize(objective, initial, method="SLSQP", bounds=bounds, constraints=cons)
    if not result.success:
        raise ValueError(f"Mean-variance optimization failed: {result.message}")

    return pd.Series(result.x, index=returns.columns)


def _bounds(n_assets: int, cfg: OptimizerConstraints) -> tuple[tuple[float, float], ...]:
    low = -cfg.max_weight if cfg.allow_short else 0.0
    return tuple((low, cfg.max_weight) for _ in range(n_assets))


def _validate_returns(returns: pd.DataFrame) -> None:
    if returns.empty or returns.shape[1] == 0:
        raise ValueError("returns must contain at least one asset with data")
