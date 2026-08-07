"""Fama-French style factor model for return attribution.

Supports OLS factor regression against a set of factor returns,
and provides alpha / beta / R-squared decomposition.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class FactorResult:
    """Output of a factor regression."""

    alpha: float
    betas: list[float]
    factor_names: list[str]
    r_squared: float
    t_stats: list[float]
    residual_volatility: float
    annualised_alpha: float


class FactorModel:
    """OLS factor model.

    Given a series of asset returns and a matrix of factor returns, fits an
    OLS regression:

        r_t = alpha + sum_k(beta_k * f_k_t) + epsilon_t

    Parameters
    ----------
    periods_per_year:
        Used to annualise alpha.  252 for daily, 12 for monthly.
    """

    def __init__(self, periods_per_year: int = 252) -> None:
        self.periods_per_year = periods_per_year

    def fit(
        self,
        asset_returns: np.ndarray,
        factor_returns: np.ndarray,
        factor_names: Optional[list[str]] = None,
    ) -> FactorResult:
        """Run OLS factor regression.

        Parameters
        ----------
        asset_returns:
            1-D array of shape (T,) — the dependent variable.
        factor_returns:
            2-D array of shape (T, K) or 1-D (T,) for a single factor.
        factor_names:
            Optional labels; defaults to ["F1", "F2", ...].
        """
        y = np.asarray(asset_returns, dtype=float)
        F = np.asarray(factor_returns, dtype=float)
        if F.ndim == 1:
            F = F.reshape(-1, 1)

        T, K = F.shape
        if len(y) != T:
            raise ValueError("asset_returns and factor_returns must have the same length")

        names = factor_names if factor_names and len(factor_names) == K else [f"F{i + 1}" for i in range(K)]

        # Design matrix [1, F1, F2, ...]
        X = np.column_stack([np.ones(T), F])  # (T, K+1)

        # OLS: beta_hat = (X'X)^-1 X'y
        XtX = X.T @ X
        Xty = X.T @ y
        try:
            coeffs = np.linalg.solve(XtX, Xty)
        except np.linalg.LinAlgError:
            coeffs = np.linalg.lstsq(X, y, rcond=None)[0]

        alpha_period = float(coeffs[0])
        betas = coeffs[1:].tolist()

        # Residuals and R²
        y_hat = X @ coeffs
        residuals = y - y_hat
        ss_res = float(np.sum(residuals**2))
        ss_tot = float(np.sum((y - np.mean(y)) ** 2))
        r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

        # Residual std
        dof = max(T - K - 1, 1)
        s2 = ss_res / dof
        resid_vol = float(np.sqrt(s2) * np.sqrt(self.periods_per_year))

        # T-statistics
        try:
            cov_coeffs = s2 * np.linalg.inv(XtX)
            se = np.sqrt(np.diag(cov_coeffs))
        except np.linalg.LinAlgError:
            se = np.ones(K + 1)
        t_stats = (coeffs / np.where(se > 0, se, 1e-12)).tolist()

        # Annualise alpha
        ann_alpha = float((1.0 + alpha_period) ** self.periods_per_year - 1.0)

        return FactorResult(
            alpha=round(alpha_period, 8),
            betas=[round(b, 6) for b in betas],
            factor_names=names,
            r_squared=round(r2, 6),
            t_stats=[round(t, 4) for t in t_stats],
            residual_volatility=round(resid_vol, 6),
            annualised_alpha=round(ann_alpha, 6),
        )
