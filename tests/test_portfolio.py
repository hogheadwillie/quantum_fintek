"""Comprehensive tests for PortfolioOptimizer."""

from __future__ import annotations

import numpy as np
import pytest
from quant_core import PortfolioOptimizer


def _make_cov(n: int, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Return a random (mu, cov) pair for n assets."""
    rng = np.random.default_rng(seed)
    mu = rng.uniform(0.03, 0.12, n)
    A = rng.normal(0, 0.1, (n, n))
    cov = A @ A.T + np.eye(n) * 0.01  # PSD
    return mu, cov


class TestMeanVarianceWeights:
    def test_weights_sum_to_one(self):
        mu, cov = _make_cov(3)
        w = PortfolioOptimizer().mean_variance_weights(mu, cov)
        assert np.isclose(w.sum(), 1.0)

    def test_shape_matches_assets(self):
        for n in (2, 4, 8, 16):
            mu, cov = _make_cov(n)
            w = PortfolioOptimizer().mean_variance_weights(mu, cov)
            assert w.shape == (n,)

    def test_all_finite(self):
        mu, cov = _make_cov(5)
        w = PortfolioOptimizer().mean_variance_weights(mu, cov)
        assert np.all(np.isfinite(w))

    def test_two_assets_extreme_returns(self):
        """When one asset dominates return, its weight should be higher."""
        mu = np.array([0.20, 0.01])
        cov = np.array([[0.01, 0.0], [0.0, 0.01]])
        w = PortfolioOptimizer().mean_variance_weights(mu, cov)
        assert w.sum() == pytest.approx(1.0, abs=1e-6)

    def test_risk_free_rate_shifts_weights(self):
        mu, cov = _make_cov(4, seed=5)
        w0 = PortfolioOptimizer().mean_variance_weights(mu, cov, risk_free_rate=0.0)
        w1 = PortfolioOptimizer().mean_variance_weights(mu, cov, risk_free_rate=0.05)
        assert not np.allclose(w0, w1)

    def test_identical_assets_equal_weight(self):
        """Identical μ and identical diagonal σ² → equal weights."""
        n = 4
        mu = np.full(n, 0.07)
        cov = np.eye(n) * 0.01
        w = PortfolioOptimizer().mean_variance_weights(mu, cov)
        expected = np.full(n, 1.0 / n)
        assert np.allclose(w, expected, atol=1e-6)

    def test_sum_to_one_with_rfr(self):
        mu, cov = _make_cov(6, seed=7)
        w = PortfolioOptimizer().mean_variance_weights(mu, cov, risk_free_rate=0.03)
        assert np.isclose(w.sum(), 1.0)

    def test_two_assets_sum_one(self):
        mu = np.array([0.05, 0.08])
        cov = np.array([[0.01, 0.002], [0.002, 0.015]])
        w = PortfolioOptimizer().mean_variance_weights(mu, cov)
        assert np.isclose(w.sum(), 1.0)


class TestQuantumReadyQUBO:
    def test_returns_dict(self):
        mu, cov = _make_cov(3)
        result = PortfolioOptimizer().quantum_ready_qubo(mu, cov)
        assert isinstance(result, dict)

    def test_contains_required_keys(self):
        mu, cov = _make_cov(3)
        result = PortfolioOptimizer().quantum_ready_qubo(mu, cov)
        for key in ("problem", "n_assets", "expected_returns", "covariance", "solver"):
            assert key in result

    def test_n_assets_correct(self):
        for n in (2, 5, 10):
            mu, cov = _make_cov(n)
            result = PortfolioOptimizer().quantum_ready_qubo(mu, cov)
            assert result["n_assets"] == n

    def test_cardinality_stored(self):
        mu, cov = _make_cov(4)
        result = PortfolioOptimizer().quantum_ready_qubo(mu, cov, cardinality=2)
        assert result["cardinality"] == 2

    def test_none_cardinality_by_default(self):
        mu, cov = _make_cov(3)
        result = PortfolioOptimizer().quantum_ready_qubo(mu, cov)
        assert result["cardinality"] is None

    def test_returns_list_serialisable(self):
        import json
        mu, cov = _make_cov(3)
        result = PortfolioOptimizer().quantum_ready_qubo(mu, cov)
        json.dumps(result)  # should not raise
