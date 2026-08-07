"""AI intelligence API routes (JWT + role protected)."""

from __future__ import annotations

import numpy as np
from ai_intel import AnomalyDetector, SentimentAnalyzer
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.deps import require_roles
from app.identity.security import TokenPayload

router = APIRouter(prefix="/ai", tags=["ai"])

Analyst = Depends(require_roles("analyst", "quant"))


class AnomalyRequest(BaseModel):
    samples: list[list[float]] = Field(..., min_length=10, description="Feature matrix rows")
    contamination: float = Field(0.05, gt=0.0, lt=0.5)


class AnomalyResponse(BaseModel):
    labels: list[int]
    scores: list[float]
    n_anomalies: int


class SentimentRequest(BaseModel):
    texts: list[str] = Field(..., min_length=1, max_length=100, description="List of documents to analyse")
    neutral_threshold: float = Field(0.05, ge=0.0, le=0.5)


class SentimentItem(BaseModel):
    label: str
    score: float
    confidence: float
    positive_count: int
    negative_count: int
    uncertainty_count: int
    word_count: int


class SentimentResponse(BaseModel):
    results: list[SentimentItem]
    n_positive: int
    n_negative: int
    n_neutral: int
    average_score: float


@router.post("/anomaly", response_model=AnomalyResponse)
def detect_anomalies(
    body: AnomalyRequest,
    _user: TokenPayload = Analyst,
) -> AnomalyResponse:
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


@router.post("/sentiment", response_model=SentimentResponse)
def analyse_sentiment(
    body: SentimentRequest,
    _user: TokenPayload = Analyst,
) -> SentimentResponse:
    analyser = SentimentAnalyzer(neutral_threshold=body.neutral_threshold)
    raw = analyser.analyze_batch(body.texts)
    items = [
        SentimentItem(
            label=r.label,
            score=r.score,
            confidence=r.confidence,
            positive_count=r.positive_count,
            negative_count=r.negative_count,
            uncertainty_count=r.uncertainty_count,
            word_count=r.word_count,
        )
        for r in raw
    ]
    avg_score = round(sum(i.score for i in items) / len(items), 4) if items else 0.0
    return SentimentResponse(
        results=items,
        n_positive=sum(1 for i in items if i.label == "positive"),
        n_negative=sum(1 for i in items if i.label == "negative"),
        n_neutral=sum(1 for i in items if i.label == "neutral"),
        average_score=avg_score,
    )
