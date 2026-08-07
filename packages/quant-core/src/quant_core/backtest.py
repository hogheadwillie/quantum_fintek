"""Simple vectorised backtesting engine.

Supports equal-weight and custom-weight strategies over a price series.
Returns a BacktestResult with equity curve, drawdowns, and summary stats.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class BacktestResult:
    """Summary and time-series output from a backtest run."""

    equity: list[float]
    returns: list[float]
    total_return: float
    annualised_return: float
    annualised_volatility: float
    sharpe_ratio: float
    max_drawdown: float
    n_periods: int
    strategy: str


class Backtester:
    """Vectorised single-period backtest on price or return series.

    Parameters
    ----------
    prices:
        2-D array of shape (T, N) — T timesteps, N assets.
        Pass either *prices* or *returns*, not both.
    returns:
        2-D array of shape (T, N) — pre-computed period returns.
    risk_free_rate:
        Annual risk-free rate used for Sharpe calculation.
    periods_per_year:
        Annualisation factor (252 for daily, 12 for monthly, 4 for quarterly).
    """

    def __init__(
        self,
        risk_free_rate: float = 0.0,
        periods_per_year: int = 252,
    ) -> None:
        self.risk_free_rate = risk_free_rate
        self.periods_per_year = periods_per_year

    def run(
        self,
        prices: Optional[np.ndarray] = None,
        returns: Optional[np.ndarray] = None,
        weights: Optional[np.ndarray] = None,
        strategy: str = "equal_weight",
    ) -> BacktestResult:
        """Run the backtest and return a :class:`BacktestResult`.

        Parameters
        ----------
        prices:
            Shape (T, N). Used to derive period returns if *returns* is not given.
        returns:
            Shape (T, N) or (T,) for a single-asset series.
        weights:
            Shape (N,) — constant rebalancing weights. Defaults to equal-weight.
        strategy:
            Label stored in the result.
        """
        if prices is not None and returns is None:
            prices = np.asarray(prices, dtype=float)
            returns = np.diff(prices, axis=0) / prices[:-1]
        elif returns is not None:
            returns = np.asarray(returns, dtype=float)
        else:
            raise ValueError("Provide either prices or returns.")

        if returns.ndim == 1:
            returns = returns.reshape(-1, 1)

        T, N = returns.shape

        if weights is None:
            w = np.ones(N) / N
        else:
            w = np.asarray(weights, dtype=float)
            w = w / w.sum()  # normalise

        # Portfolio return each period
        port_returns: np.ndarray = returns @ w  # shape (T,)

        # Equity curve (starts at 1.0)
        equity = np.cumprod(1.0 + port_returns)

        # Total return
        total_ret = float(equity[-1] - 1.0)

        # Annualised return (CAGR)
        n_years = T / self.periods_per_year
        ann_ret = float((1.0 + total_ret) ** (1.0 / max(n_years, 1e-9)) - 1.0)

        # Annualised volatility
        ann_vol = float(np.std(port_returns, ddof=1) * np.sqrt(self.periods_per_year))

        # Sharpe ratio
        rfr_period = self.risk_free_rate / self.periods_per_year
        excess = port_returns - rfr_period
        sharpe = (
            float(np.mean(excess) / np.std(excess, ddof=1) * np.sqrt(self.periods_per_year))
            if np.std(excess, ddof=1) > 0
            else 0.0
        )

        # Maximum drawdown
        running_max = np.maximum.accumulate(equity)
        drawdowns = (equity - running_max) / running_max
        max_dd = float(np.min(drawdowns))

        return BacktestResult(
            equity=equity.tolist(),
            returns=port_returns.tolist(),
            total_return=round(total_ret, 6),
            annualised_return=round(ann_ret, 6),
            annualised_volatility=round(ann_vol, 6),
            sharpe_ratio=round(sharpe, 4),
            max_drawdown=round(max_dd, 6),
            n_periods=T,
            strategy=strategy,
        )
