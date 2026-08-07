"""Quantitative analytics API routes (JWT + role protected)."""

from __future__ import annotations

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from quant_core import Backtester, FactorModel, PortfolioOptimizer, RiskMetrics

from app.api.deps import require_roles
from app.identity.security import TokenPayload

router = APIRouter(prefix="/quant", tags=["quant"])

Analyst = Depends(require_roles("analyst", "quant"))


class OptimizeRequest(BaseModel):
    expected_returns: list[float] = Field(..., min_length=2)
    covariance: list[list[float]]
    risk_free_rate: float = 0.0


class OptimizeResponse(BaseModel):
    weights: list[float]
    n_assets: int


class RiskRequest(BaseModel):
    returns: list[float] = Field(..., min_length=2)
    confidence: float = Field(0.95, gt=0.5, lt=1.0)


class RiskResponse(BaseModel):
    historical_var: float
    cvar: float
    volatility_annual: float


class QuboRequest(BaseModel):
    expected_returns: list[float] = Field(..., min_length=2)
    covariance: list[list[float]]
    cardinality: int | None = None


class BacktestRequest(BaseModel):
    returns: list[list[float]] = Field(
        ...,
        min_length=2,
        description="Matrix of shape (T, N) — period returns per asset",
    )
    weights: list[float] | None = Field(
        None, description="Asset weights; defaults to equal-weight"
    )
    risk_free_rate: float = 0.0
    periods_per_year: int = Field(252, ge=1, le=365)
    strategy: str = "custom"


class BacktestResponse(BaseModel):
    total_return: float
    annualised_return: float
    annualised_volatility: float
    sharpe_ratio: float
    max_drawdown: float
    n_periods: int
    strategy: str
    equity: list[float]


class FactorRequest(BaseModel):
    asset_returns: list[float] = Field(..., min_length=10)
    factor_returns: list[list[float]] = Field(
        ...,
        min_length=10,
        description="Matrix of shape (T, K) — factor return series",
    )
    factor_names: list[str] | None = None
    periods_per_year: int = Field(252, ge=1, le=365)


class FactorResponse(BaseModel):
    alpha: float
    annualised_alpha: float
    betas: list[float]
    factor_names: list[str]
    r_squared: float
    t_stats: list[float]
    residual_volatility: float


@router.post("/optimize", response_model=OptimizeResponse)
def optimize_portfolio(
    body: OptimizeRequest,
    _user: TokenPayload = Analyst,
) -> OptimizeResponse:
    mu = np.array(body.expected_returns, dtype=float)
    cov = np.array(body.covariance, dtype=float)
    if cov.shape != (len(mu), len(mu)):
        raise HTTPException(status_code=400, detail="covariance must be n x n matching expected_returns")
    opt = PortfolioOptimizer()
    weights = opt.mean_variance_weights(mu, cov, risk_free_rate=body.risk_free_rate)
    return OptimizeResponse(weights=weights.tolist(), n_assets=len(weights))


@router.post("/risk", response_model=RiskResponse)
def compute_risk(
    body: RiskRequest,
    _user: TokenPayload = Analyst,
) -> RiskResponse:
    r = np.array(body.returns, dtype=float)
    return RiskResponse(
        historical_var=RiskMetrics.historical_var(r, body.confidence),
        cvar=RiskMetrics.cvar(r, body.confidence),
        volatility_annual=RiskMetrics.volatility(r, annualize=True),
    )


@router.post("/backtest", response_model=BacktestResponse)
def run_backtest(
    body: BacktestRequest,
    _user: TokenPayload = Analyst,
) -> BacktestResponse:
    ret_matrix = np.array(body.returns, dtype=float)
    weights = np.array(body.weights, dtype=float) if body.weights else None
    bt = Backtester(
        risk_free_rate=body.risk_free_rate,
        periods_per_year=body.periods_per_year,
    )
    result = bt.run(returns=ret_matrix, weights=weights, strategy=body.strategy)
    return BacktestResponse(
        total_return=result.total_return,
        annualised_return=result.annualised_return,
        annualised_volatility=result.annualised_volatility,
        sharpe_ratio=result.sharpe_ratio,
        max_drawdown=result.max_drawdown,
        n_periods=result.n_periods,
        strategy=result.strategy,
        equity=result.equity,
    )


@router.post("/factor", response_model=FactorResponse)
def run_factor_model(
    body: FactorRequest,
    _user: TokenPayload = Analyst,
) -> FactorResponse:
    asset_r = np.array(body.asset_returns, dtype=float)
    factor_r = np.array(body.factor_returns, dtype=float)
    if factor_r.ndim == 1:
        factor_r = factor_r.reshape(-1, 1)
    if len(asset_r) != len(factor_r):
        raise HTTPException(
            status_code=400,
            detail="asset_returns and factor_returns must have the same number of rows",
        )
    fm = FactorModel(periods_per_year=body.periods_per_year)
    result = fm.fit(asset_r, factor_r, factor_names=body.factor_names)
    return FactorResponse(
        alpha=result.alpha,
        annualised_alpha=result.annualised_alpha,
        betas=result.betas,
        factor_names=result.factor_names,
        r_squared=result.r_squared,
        t_stats=result.t_stats,
        residual_volatility=result.residual_volatility,
    )


@router.post("/qubo")
def quantum_qubo(
    body: QuboRequest,
    _user: TokenPayload = Analyst,
) -> dict:
    mu = np.array(body.expected_returns, dtype=float)
    cov = np.array(body.covariance, dtype=float)
    opt = PortfolioOptimizer()
    return opt.quantum_ready_qubo(mu, cov, cardinality=body.cardinality)
