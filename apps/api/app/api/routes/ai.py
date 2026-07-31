"""AI intelligence API routes."""

from __future__ import annotations

import numpy as np
from ai_intel import AnomalyDetector
from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/ai", tags=["ai"])


class AnomalyRequest(BaseModel):
    samples: list[list[float]] = Field(..., min_length=10, description="Feature matrix rows")
    contamination: float = Field(0.05, gt=0.0, lt=0.5)


class AnomalyResponse(BaseModel):
    labels: list[int]  # -1 anomaly, 1 inlier
    scores: list[float]
    n_anomalies: int


@router.post("/anomaly", response_model=AnomalyResponse)
def detect_anomalies(body: AnomalyRequest) -> AnomalyResponse:
    X = np.array(body.samples, dtype=float)
    detector = AnomalyDetector(contamination=body.contamination)
    detector.fit(X)
    labels = detector.predict(X).tolist()
    scores = detector.score(X).tolist()
    return AnomalyResponse(
        labels=labels,
        scores=scores,
        n_anomalies=sum(1 for x in labels if x == -1),
    )
