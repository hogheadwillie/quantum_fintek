"""Extended backtest tests covering annualisation, Sharpe, drawdown, and edge cases."""

from __future__ import annotations

import numpy as np
import pytest
from quant_core import Backtester, BacktestResult


class TestBacktesterCore:
    def test_equity_starts_near_one(self):
        rng = np.random.default_rng(0)
        r = rng.normal(0.001, 0.01, (50, 2))
        result = Backtester().run(returns=r)
        # First equity value is 1 + r[0,:]·w
        assert abs(result.equity[0] - (1 + np.mean(r[0]))) < 1e-9

    def test_equity_monotone_on_all_positive(self):
        r = np.full((100, 2), 0.001)
        result = Backtester().run(returns=r)
        eq = np.array(result.equity)
        assert np.all(np.diff(eq) >= 0)

    def test_total_return_matches_equity_last(self):
        rng = np.random.default_rng(1)
        r = rng.normal(0.001, 0.01, (252, 3))
        result = Backtester().run(returns=r)
        assert abs(result.total_return - (result.equity[-1] - 1.0)) < 1e-6

    def test_max_drawdown_le_zero(self):
        rng = np.random.default_rng(2)
        r = rng.normal(0, 0.015, (200, 2))
        result = Backtester().run(returns=r)
        assert result.max_drawdown <= 0.0

    def test_max_drawdown_zero_on_upward_only(self):
        r = np.full((252, 1), 0.001)
        result = Backtester().run(returns=r)
        assert abs(result.max_drawdown) < 1e-9

    def test_sharpe_finite_for_constant_returns(self):
        """Constant returns → volatility = 0; Sharpe is either 0 or very large but finite."""
        r = np.full((252, 1), 0.001)
        result = Backtester(risk_free_rate=0.0).run(returns=r)
        assert np.isfinite(result.sharpe_ratio)

    def test_sharpe_positive_for_strong_uptrend(self):
        rng = np.random.default_rng(3)
        r = rng.normal(0.003, 0.005, (252, 1))  # high μ/σ
        result = Backtester(risk_free_rate=0.0).run(returns=r)
        assert result.sharpe_ratio > 0.0

    def test_annualised_return_monthly(self):
        """Monthly data: 12 periods/year, 12 periods → total ≈ annualised."""
        r = np.full((12, 1), 0.01)
        result = Backtester(periods_per_year=12).run(returns=r)
        assert abs(result.annualised_return - result.total_return) < 0.01

    def test_n_periods_correct(self):
        for T in (10, 100, 500):
            r = np.zeros((T, 2))
            result = Backtester().run(returns=r)
            assert result.n_periods == T

    def test_strategy_label_preserved(self):
        r = np.zeros((10, 1))
        result = Backtester().run(returns=r, strategy="my_strategy")
        assert result.strategy == "my_strategy"


class TestBacktesterWeights:
    def test_unnormalized_weights_normalised(self):
        rng = np.random.default_rng(4)
        r = rng.normal(0.001, 0.01, (100, 3))
        # weights don't sum to 1
        w = np.array([3.0, 1.0, 1.0])
        result = Backtester().run(returns=r, weights=w)
        assert np.isfinite(result.total_return)
        assert result.n_periods == 100

    def test_single_asset_weight_one(self):
        rng = np.random.default_rng(5)
        r = rng.normal(0.001, 0.01, (100, 3))
        # Put 100% in asset 0
        w_all_zero = np.array([1.0, 0.0, 0.0])
        result_w  = Backtester().run(returns=r, weights=w_all_zero)
        result_1d = Backtester().run(returns=r[:, 0])
        assert abs(result_w.total_return - result_1d.total_return) < 1e-6

    def test_equal_weight_default(self):
        rng = np.random.default_rng(6)
        r = rng.normal(0, 0.01, (50, 4))
        result_default = Backtester().run(returns=r)
        result_explicit = Backtester().run(returns=r, weights=np.ones(4) / 4)
        assert np.isclose(result_default.total_return, result_explicit.total_return)


class TestBacktesterFromPrices:
    def test_price_returns_same_as_manual_diff(self):
        rng = np.random.default_rng(7)
        prices = np.cumprod(1 + rng.normal(0.001, 0.01, (101, 2)), axis=0) * 100
        returns_manual = np.diff(prices, axis=0) / prices[:-1]
        r1 = Backtester().run(prices=prices)
        r2 = Backtester().run(returns=returns_manual)
        assert abs(r1.total_return - r2.total_return) < 1e-9

    def test_n_periods_is_T_minus_1(self):
        rng = np.random.default_rng(8)
        prices = rng.uniform(90, 110, (51, 3))
        result = Backtester().run(prices=prices)
        assert result.n_periods == 50


class TestBacktesterEdgeCases:
    def test_raises_without_input(self):
        with pytest.raises(ValueError):
            Backtester().run()

    def test_single_period(self):
        r = np.array([[0.02, -0.01]])
        result = Backtester().run(returns=r)
        assert result.n_periods == 1
        assert np.isfinite(result.total_return)

    def test_large_dataset_performant(self):
        rng = np.random.default_rng(9)
        r = rng.normal(0.0003, 0.01, (10_000, 10))
        result = Backtester().run(returns=r)
        assert result.n_periods == 10_000
        assert np.isfinite(result.sharpe_ratio)

    def test_all_zero_returns(self):
        r = np.zeros((252, 3))
        result = Backtester().run(returns=r)
        assert abs(result.total_return) < 1e-9
        assert np.all(np.array(result.equity) == pytest.approx(1.0))
