"""Comprehensive tests for RiskMetrics."""

from __future__ import annotations

import numpy as np
import pytest
from quant_core import RiskMetrics


class TestHistoricalVaR:
    def test_positive_returns_var_negative(self):
        """VaR on all-positive returns should be <= 0 loss."""
        returns = np.full(100, 0.01)
        var = RiskMetrics.historical_var(returns, confidence=0.95)
        assert var <= 0.0

    def test_negative_returns_var_positive(self):
        """VaR on all-negative returns should be a positive loss figure."""
        returns = np.full(100, -0.02)
        var = RiskMetrics.historical_var(returns, confidence=0.95)
        assert var > 0.0

    def test_empty_returns_zero(self):
        assert RiskMetrics.historical_var(np.array([]), 0.95) == 0.0

    def test_single_return(self):
        var = RiskMetrics.historical_var(np.array([-0.05]), 0.95)
        assert np.isfinite(var)

    def test_confidence_ordering(self):
        """Higher confidence should give higher (or equal) VaR."""
        rng = np.random.default_rng(0)
        r = rng.normal(0, 0.01, 1000)
        v90 = RiskMetrics.historical_var(r, 0.90)
        v95 = RiskMetrics.historical_var(r, 0.95)
        v99 = RiskMetrics.historical_var(r, 0.99)
        assert v90 <= v95 <= v99

    def test_var_equals_percentile(self):
        rng = np.random.default_rng(1)
        r = rng.normal(0, 0.01, 2000)
        var = RiskMetrics.historical_var(r, 0.95)
        expected = -np.percentile(r, 5.0)
        assert abs(var - expected) < 1e-12

    def test_var_is_finite(self):
        rng = np.random.default_rng(2)
        r = rng.normal(0.001, 0.02, 500)
        assert np.isfinite(RiskMetrics.historical_var(r, 0.95))


class TestCVaR:
    def test_cvar_geq_var(self):
        """CVaR must be >= VaR by definition."""
        rng = np.random.default_rng(10)
        r = rng.normal(0, 0.015, 1000)
        var  = RiskMetrics.historical_var(r, 0.95)
        cvar = RiskMetrics.cvar(r, 0.95)
        assert cvar >= var - 1e-9

    def test_empty_returns_zero(self):
        assert RiskMetrics.cvar(np.array([]), 0.95) == 0.0

    def test_all_positive_returns(self):
        """CVaR of purely positive returns should be <= 0."""
        r = np.full(200, 0.005)
        assert RiskMetrics.cvar(r, 0.95) <= 0.0

    def test_cvar_is_mean_of_tail(self):
        """Verify CVaR equals mean of worst (1-conf)% observations."""
        rng = np.random.default_rng(11)
        r = rng.normal(0, 0.02, 2000)
        conf = 0.95
        var = -np.percentile(r, (1 - conf) * 100)
        tail = r[r <= -var]
        expected_cvar = -np.mean(tail) if len(tail) > 0 else var
        cvar = RiskMetrics.cvar(r, conf)
        assert abs(cvar - expected_cvar) < 1e-10

    def test_cvar_finite(self):
        rng = np.random.default_rng(12)
        r = rng.normal(0, 0.01, 500)
        assert np.isfinite(RiskMetrics.cvar(r, 0.99))


class TestVolatility:
    def test_constant_returns_zero_vol(self):
        r = np.full(252, 0.001)
        vol = RiskMetrics.volatility(r, annualize=False)
        assert abs(vol) < 1e-12

    def test_annualised_scales_by_sqrt252(self):
        rng = np.random.default_rng(20)
        r = rng.normal(0, 0.01, 252)
        daily = RiskMetrics.volatility(r, annualize=False)
        annual = RiskMetrics.volatility(r, annualize=True)
        assert abs(annual - daily * np.sqrt(252)) < 1e-10

    def test_non_negative(self):
        rng = np.random.default_rng(21)
        r = rng.normal(0, 0.02, 100)
        assert RiskMetrics.volatility(r) >= 0.0

    def test_known_std(self):
        rng = np.random.default_rng(22)
        r = rng.normal(0, 0.02, 10000)
        vol = RiskMetrics.volatility(r, annualize=False)
        assert abs(vol - 0.02) < 0.002  # within 10% of true std
