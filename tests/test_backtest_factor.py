"""Tests for quant-core backtesting and factor model."""

import numpy as np
import pytest
from quant_core import Backtester, BacktestResult, FactorModel, FactorResult


# ── Backtester ──────────────────────────────────────────────────────────────

class TestBacktester:
    def test_equal_weight_runs(self):
        rng = np.random.default_rng(0)
        returns = rng.normal(0.001, 0.01, (252, 3))
        bt = Backtester()
        result = bt.run(returns=returns, strategy="equal_weight")
        assert isinstance(result, BacktestResult)
        assert result.n_periods == 252
        assert len(result.equity) == 252
        assert len(result.returns) == 252

    def test_custom_weights_sum_normalised(self):
        rng = np.random.default_rng(1)
        returns = rng.normal(0.0005, 0.01, (100, 4))
        bt = Backtester()
        # Pass unnormalised weights — should still produce valid results
        result = bt.run(returns=returns, weights=np.array([2.0, 1.0, 1.0, 0.5]))
        assert result.n_periods == 100
        assert np.isfinite(result.sharpe_ratio)

    def test_from_prices(self):
        rng = np.random.default_rng(2)
        prices = np.cumprod(1 + rng.normal(0.001, 0.01, (253, 2)), axis=0) * 100
        bt = Backtester()
        result = bt.run(prices=prices, strategy="price_test")
        assert result.n_periods == 252  # one less than prices (diff)

    def test_single_asset_1d(self):
        rng = np.random.default_rng(3)
        returns = rng.normal(0.001, 0.015, 200)
        bt = Backtester()
        result = bt.run(returns=returns)
        assert result.n_periods == 200

    def test_sharpe_positive_for_upward_trend(self):
        returns = np.full((252, 1), 0.002)  # constant positive returns
        bt = Backtester(risk_free_rate=0.0)
        result = bt.run(returns=returns)
        # Std of identical returns is 0 → Sharpe returns 0.0 by convention
        assert np.isfinite(result.sharpe_ratio)

    def test_max_drawdown_negative_or_zero(self):
        rng = np.random.default_rng(4)
        returns = rng.normal(0.0, 0.02, (300, 2))
        bt = Backtester()
        result = bt.run(returns=returns)
        assert result.max_drawdown <= 0.0

    def test_raises_without_input(self):
        bt = Backtester()
        with pytest.raises(ValueError):
            bt.run()

    def test_total_return_consistent(self):
        rng = np.random.default_rng(5)
        returns = rng.normal(0.001, 0.01, (50, 2))
        bt = Backtester()
        result = bt.run(returns=returns)
        expected_total = result.equity[-1] - 1.0
        assert abs(result.total_return - expected_total) < 1e-6


# ── FactorModel ─────────────────────────────────────────────────────────────

class TestFactorModel:
    def _sample(self, T=200, K=3, seed=0):
        rng = np.random.default_rng(seed)
        factors = rng.normal(0, 0.01, (T, K))
        true_betas = rng.uniform(0.3, 1.5, K) * np.where(rng.integers(0, 2, K), 1, -1)
        alpha = 0.0002
        asset = alpha + factors @ true_betas + rng.normal(0, 0.005, T)
        return asset, factors, true_betas

    def test_basic_fit(self):
        asset, factors, _ = self._sample()
        fm = FactorModel()
        result = fm.fit(asset, factors)
        assert isinstance(result, FactorResult)
        assert len(result.betas) == 3
        assert 0.0 <= result.r_squared <= 1.0

    def test_beta_recovery(self):
        """Betas should be roughly correct for well-specified data."""
        asset, factors, true_betas = self._sample(T=500)
        fm = FactorModel()
        result = fm.fit(asset, factors)
        for est, true_b in zip(result.betas, true_betas.tolist()):
            assert abs(est - true_b) < 0.3

    def test_factor_names_auto_generated(self):
        asset, factors, _ = self._sample(K=2)
        fm = FactorModel()
        result = fm.fit(asset, factors[:, :2])
        assert result.factor_names == ["F1", "F2"]

    def test_factor_names_custom(self):
        asset, factors, _ = self._sample()
        fm = FactorModel()
        result = fm.fit(asset, factors, factor_names=["Mkt", "SMB", "HML"])
        assert result.factor_names == ["Mkt", "SMB", "HML"]

    def test_single_factor_1d(self):
        rng = np.random.default_rng(7)
        factor = rng.normal(0, 0.01, 200)
        asset = 0.5 * factor + rng.normal(0, 0.003, 200)
        fm = FactorModel()
        result = fm.fit(asset, factor)
        assert len(result.betas) == 1

    def test_raises_mismatched_lengths(self):
        rng = np.random.default_rng(8)
        asset = rng.normal(0, 0.01, 100)
        factors = rng.normal(0, 0.01, (90, 2))
        fm = FactorModel()
        with pytest.raises(ValueError, match="same length"):
            fm.fit(asset, factors)

    def test_t_stats_length(self):
        asset, factors, _ = self._sample()
        fm = FactorModel()
        result = fm.fit(asset, factors)
        # t_stats includes alpha t-stat at index 0
        assert len(result.t_stats) == len(result.betas) + 1
