"""Extended factor model tests: OLS accuracy, R², t-stats, edge cases."""

from __future__ import annotations

import numpy as np
import pytest
from quant_core import FactorModel, FactorResult


def _make_factor_data(
    T: int = 300,
    K: int = 3,
    true_alpha: float = 0.0002,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    factors = rng.normal(0, 0.01, (T, K))
    true_betas = rng.uniform(0.3, 1.5, K) * np.where(rng.integers(0, 2, K), 1, -1)
    asset = true_alpha + factors @ true_betas + rng.normal(0, 0.003, T)
    return asset, factors, true_betas


class TestFactorModelFit:
    def test_returns_factor_result(self):
        asset, factors, _ = _make_factor_data()
        result = FactorModel().fit(asset, factors)
        assert isinstance(result, FactorResult)

    def test_beta_count_matches_factors(self):
        for K in (1, 2, 3, 5):
            asset, factors, _ = _make_factor_data(K=K)
            result = FactorModel().fit(asset, factors)
            assert len(result.betas) == K

    def test_r_squared_in_unit_interval(self):
        asset, factors, _ = _make_factor_data(T=500)
        result = FactorModel().fit(asset, factors)
        assert 0.0 <= result.r_squared <= 1.0

    def test_high_r_squared_for_well_specified_model(self):
        """Low noise → R² should be near 1."""
        T, K = 500, 3
        rng = np.random.default_rng(1)
        factors = rng.normal(0, 0.01, (T, K))
        betas = np.array([1.0, 0.5, -0.3])
        asset = factors @ betas + rng.normal(0, 1e-5, T)  # tiny noise
        result = FactorModel().fit(asset, factors)
        assert result.r_squared > 0.99

    def test_beta_recovery_low_noise(self):
        T, K = 1000, 3
        rng = np.random.default_rng(2)
        factors = rng.normal(0, 0.01, (T, K))
        true_betas = np.array([1.2, -0.6, 0.8])
        asset = factors @ true_betas + rng.normal(0, 1e-5, T)
        result = FactorModel().fit(asset, factors)
        for est, true in zip(result.betas, true_betas.tolist()):
            assert abs(est - true) < 0.01

    def test_t_stats_length(self):
        """t_stats has K+1 entries: alpha + K betas."""
        for K in (1, 3, 5):
            asset, factors, _ = _make_factor_data(K=K)
            result = FactorModel().fit(asset, factors)
            assert len(result.t_stats) == K + 1

    def test_significant_beta_has_large_t_stat(self):
        """A large-signal beta should produce |t| > 2."""
        T = 1000
        rng = np.random.default_rng(3)
        factor = rng.normal(0, 0.01, T)
        asset = 2.0 * factor + rng.normal(0, 0.001, T)  # beta ≈ 2, tiny noise
        result = FactorModel().fit(asset, factor)
        # t_stats[0]=alpha t-stat, t_stats[1]=beta t-stat
        assert abs(result.t_stats[1]) > 10.0

    def test_residual_volatility_positive(self):
        asset, factors, _ = _make_factor_data()
        result = FactorModel().fit(asset, factors)
        assert result.residual_volatility >= 0.0

    def test_annualised_alpha_formula(self):
        """Check (1 + alpha)^252 - 1 == annualised_alpha."""
        asset, factors, _ = _make_factor_data()
        result = FactorModel(periods_per_year=252).fit(asset, factors)
        expected = (1.0 + result.alpha) ** 252 - 1.0
        assert abs(result.annualised_alpha - expected) < 1e-5

    def test_custom_periods_per_year(self):
        """Monthly model: annualised alpha uses 12 periods."""
        asset, factors, _ = _make_factor_data(T=120)
        result12 = FactorModel(periods_per_year=12).fit(asset, factors)
        result252 = FactorModel(periods_per_year=252).fit(asset, factors)
        # Same alpha period, different annualisation
        assert abs(result12.alpha - result252.alpha) < 1e-10
        assert abs(result12.annualised_alpha - result252.annualised_alpha) > 1e-6


class TestFactorModelNames:
    def test_default_names_generated(self):
        asset, factors, _ = _make_factor_data(K=3)
        result = FactorModel().fit(asset, factors)
        assert result.factor_names == ["F1", "F2", "F3"]

    def test_custom_names_used(self):
        asset, factors, _ = _make_factor_data(K=3)
        names = ["Mkt-RF", "SMB", "HML"]
        result = FactorModel().fit(asset, factors, factor_names=names)
        assert result.factor_names == names

    def test_wrong_length_names_ignored(self):
        asset, factors, _ = _make_factor_data(K=3)
        result = FactorModel().fit(asset, factors, factor_names=["A", "B"])
        # Wrong count → auto-generate
        assert result.factor_names == ["F1", "F2", "F3"]

    def test_single_factor_name(self):
        rng = np.random.default_rng(4)
        factor = rng.normal(0, 0.01, 200)
        asset = 0.8 * factor + rng.normal(0, 0.003, 200)
        result = FactorModel().fit(asset, factor, factor_names=["Market"])
        assert result.factor_names == ["Market"]


class TestFactorModelEdgeCases:
    def test_1d_factor_reshaped(self):
        """1-D factor array should be treated as single factor."""
        rng = np.random.default_rng(5)
        factor = rng.normal(0, 0.01, 200)
        asset = 0.5 * factor + rng.normal(0, 0.003, 200)
        result = FactorModel().fit(asset, factor)
        assert len(result.betas) == 1

    def test_raises_mismatched_lengths(self):
        rng = np.random.default_rng(6)
        asset = rng.normal(0, 0.01, 100)
        factors = rng.normal(0, 0.01, (90, 2))
        with pytest.raises(ValueError, match="same length"):
            FactorModel().fit(asset, factors)

    def test_zero_variance_asset(self):
        """Constant asset return → alpha finite; R² defined (may be 0 or degenerate)."""
        T = 100
        factors = np.random.default_rng(7).normal(0, 0.01, (T, 2))
        asset = np.full(T, 0.001)
        result = FactorModel().fit(asset, factors)
        assert np.isfinite(result.alpha)
        # When asset has zero variance (ss_tot=0) the implementation sets r2=0
        # unless floating-point rounding causes a tiny non-zero ss_tot.
        assert np.isfinite(result.r_squared)
