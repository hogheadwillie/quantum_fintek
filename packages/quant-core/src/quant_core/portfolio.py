"""Portfolio optimization primitives.

Classical mean-variance and placeholders for quantum (QUBO / VQE) solvers.
"""

from __future__ import annotations

from typing import Optional
import numpy as np


class PortfolioOptimizer:
    """Basic mean-variance portfolio optimizer with quantum extension hooks."""

    def __init__(self, risk_aversion: float = 1.0) -> None:
        self.risk_aversion = risk_aversion

    def mean_variance_weights(
        self,
        expected_returns: np.ndarray,
        cov_matrix: np.ndarray,
        risk_free_rate: float = 0.0,
    ) -> np.ndarray:
        """Classical mean-variance (Markowitz) closed-form solution under full investment."""
        n = len(expected_returns)
        ones = np.ones(n)
        inv_cov = np.linalg.pinv(cov_matrix)
        excess = expected_returns - risk_free_rate

        # Unconstrained solution scaled to sum-to-one
        w = inv_cov @ excess
        w = w / np.sum(w)
        return w

    def quantum_ready_qubo(
        self,
        expected_returns: np.ndarray,
        cov_matrix: np.ndarray,
        cardinality: Optional[int] = None,
    ) -> dict:
        """Return a QUBO-ready formulation dictionary for future quantum solvers.

        This is a placeholder that encodes the problem shape; actual Qiskit / D-Wave
        integration will live in a future quantum backend module.
        """
        return {
            "problem": "portfolio_optimization",
            "n_assets": len(expected_returns),
            "expected_returns": expected_returns.tolist(),
            "covariance": cov_matrix.tolist(),
            "cardinality": cardinality,
            "solver": "pending_quantum_backend",
        }
