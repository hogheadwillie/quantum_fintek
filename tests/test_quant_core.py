"""Basic smoke tests for quant-core."""

import numpy as np
from quant_core import PortfolioOptimizer, RiskMetrics


def test_mean_variance_weights_sum_to_one():
    returns = np.array([0.05, 0.07, 0.06])
    cov = np.array([
        [0.01, 0.002, 0.001],
        [0.002, 0.015, 0.003],
        [0.001, 0.003, 0.012],
    ])
    opt = PortfolioOptimizer()
    w = opt.mean_variance_weights(returns, cov)
    assert np.isclose(w.sum(), 1.0)
    assert w.shape == (3,)


def test_historical_var():
    rng = np.random.default_rng(42)
    returns = rng.normal(0.001, 0.02, 1000)
    var = RiskMetrics.historical_var(returns, confidence=0.95)
    assert var > 0
