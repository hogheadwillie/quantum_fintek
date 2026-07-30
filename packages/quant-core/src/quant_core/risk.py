"""Risk metrics used across the platform."""

from __future__ import annotations

import numpy as np


class RiskMetrics:
    """Common risk calculations."""

    @staticmethod
    def historical_var(returns: np.ndarray, confidence: float = 0.95) -> float:
        """Historical Value-at-Risk (positive number = loss)."""
        if len(returns) == 0:
            return 0.0
        cutoff = np.percentile(returns, (1 - confidence) * 100)
        return float(-cutoff)

    @staticmethod
    def cvar(returns: np.ndarray, confidence: float = 0.95) -> float:
        """Conditional VaR / Expected Shortfall."""
        if len(returns) == 0:
            return 0.0
        var = -np.percentile(returns, (1 - confidence) * 100)
        tail = returns[returns <= -var]
        if len(tail) == 0:
            return var
        return float(-np.mean(tail))

    @staticmethod
    def volatility(returns: np.ndarray, annualize: bool = True) -> float:
        vol = float(np.std(returns, ddof=1))
        if annualize:
            vol *= np.sqrt(252)
        return vol
