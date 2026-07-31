"""Quantitative analytics API routes (JWT protected)."""

from __future__ import annotations

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from quant_core import PortfolioOptimizer, RiskMetrics

from app.api.deps import get_current_payload
from app.identity.security import TokenPayload

router = APIRouter(prefix="/quant", tags=["quant"])


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


@router.post("/optimize", response_model=OptimizeResponse)
def optimize_portfolio(
    body: OptimizeRequest,
    _user: TokenPayload = Depends(get_current_payload),
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
    _user: TokenPayload = Depends(get_current_payload),
) -> RiskResponse:
    r = np.array(body.returns, dtype=float)
    return RiskResponse(
        historical_var=RiskMetrics.historical_var(r, body.confidence),
        cvar=RiskMetrics.cvar(r, body.confidence),
        volatility_annual=RiskMetrics.volatility(r, annualize=True),
    )


@router.post("/qubo")
def quantum_qubo(
    body: QuboRequest,
    _user: TokenPayload = Depends(get_current_payload),
) -> dict:
    mu = np.array(body.expected_returns, dtype=float)
    cov = np.array(body.covariance, dtype=float)
    opt = PortfolioOptimizer()
    return opt.quantum_ready_qubo(mu, cov, cardinality=body.cardinality)
