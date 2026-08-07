"""Sentiment analysis for financial text.

Provides a lexicon-based scorer using a curated financial sentiment
dictionary (positive / negative / uncertainty word lists), plus a
document-level label and confidence score.

No external model dependencies — purely rule-based so it works offline
and has deterministic output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# ---------------------------------------------------------------------------
# Minimal financial sentiment lexicon
# ---------------------------------------------------------------------------
_POSITIVE_WORDS: frozenset[str] = frozenset(
    [
        "growth", "profit", "gain", "surge", "rally", "recovery", "beat",
        "strong", "outperform", "record", "upgrade", "bullish", "positive",
        "rise", "increase", "improve", "expand", "exceeded", "opportunity",
        "dividend", "revenue", "upside", "accelerate", "momentum", "rebound",
        "robust", "confident", "optimistic", "success", "deliver", "exceed",
        "breakout", "advance", "soar", "boom", "thriving", "upbeat", "win",
        "surplus", "solid", "resilient", "promising", "uptrend", "innovative",
    ]
)

_NEGATIVE_WORDS: frozenset[str] = frozenset(
    [
        "loss", "decline", "fall", "drop", "miss", "weak", "downgrade",
        "bearish", "negative", "decrease", "shrink", "cut", "layoff",
        "risk", "default", "debt", "concern", "fraud", "lawsuit", "penalty",
        "recession", "slowdown", "warning", "volatile", "uncertain",
        "writedown", "impair", "collapse", "crisis", "sell", "downside",
        "headwind", "disappoint", "shortfall", "deficit", "downtrend",
        "struggle", "pressure", "challenge", "toxic", "lawsuit", "bankrupt",
    ]
)

_NEGATION_WORDS: frozenset[str] = frozenset(
    ["not", "no", "never", "neither", "nor", "without", "barely", "hardly"]
)

_UNCERTAINTY_WORDS: frozenset[str] = frozenset(
    ["may", "might", "could", "possibly", "perhaps", "uncertain", "unclear",
     "expect", "estimate", "approximate", "around", "about", "likely",
     "unlikely", "potential", "speculate"]
)


@dataclass
class SentimentResult:
    """Output of a sentiment analysis run."""

    label: str          # "positive" | "negative" | "neutral"
    score: float        # range [-1.0, 1.0]
    confidence: float   # [0.0, 1.0]
    positive_count: int
    negative_count: int
    uncertainty_count: int
    word_count: int


class SentimentAnalyzer:
    """Rule-based financial-domain sentiment scorer.

    Parameters
    ----------
    neutral_threshold:
        Absolute score below which a document is labelled *neutral*.
        Defaults to 0.05 — i.e. ≥5% net positivity/negativity required.
    """

    def __init__(self, neutral_threshold: float = 0.05) -> None:
        self.neutral_threshold = neutral_threshold

    @staticmethod
    def _tokenise(text: str) -> list[str]:
        return re.findall(r"[a-z']+", text.lower())

    def analyze(self, text: str) -> SentimentResult:
        """Analyse *text* and return a :class:`SentimentResult`."""
        tokens = self._tokenise(text)
        n = len(tokens)
        if n == 0:
            return SentimentResult(
                label="neutral", score=0.0, confidence=0.0,
                positive_count=0, negative_count=0, uncertainty_count=0, word_count=0,
            )

        pos_count = neg_count = unc_count = 0
        negate = False

        for i, tok in enumerate(tokens):
            # Look-back window of 3 for negation
            window_start = max(0, i - 3)
            is_negated = any(tokens[j] in _NEGATION_WORDS for j in range(window_start, i))

            if tok in _POSITIVE_WORDS:
                if is_negated:
                    neg_count += 1
                else:
                    pos_count += 1
            elif tok in _NEGATIVE_WORDS:
                if is_negated:
                    pos_count += 1
                else:
                    neg_count += 1

            if tok in _UNCERTAINTY_WORDS:
                unc_count += 1

        # Normalise
        denominator = max(pos_count + neg_count, 1)
        raw_score = (pos_count - neg_count) / denominator  # [-1, 1]

        # Penalise high uncertainty
        unc_ratio = unc_count / n
        adjusted_score = raw_score * (1.0 - 0.5 * unc_ratio)

        # Confidence: proportion of sentiment-bearing words
        confidence = min((pos_count + neg_count) / n * 5.0, 1.0)  # scale up then cap

        if abs(adjusted_score) < self.neutral_threshold:
            label = "neutral"
        elif adjusted_score > 0:
            label = "positive"
        else:
            label = "negative"

        return SentimentResult(
            label=label,
            score=round(float(adjusted_score), 4),
            confidence=round(float(confidence), 4),
            positive_count=pos_count,
            negative_count=neg_count,
            uncertainty_count=unc_count,
            word_count=n,
        )

    def analyze_batch(self, texts: list[str]) -> list[SentimentResult]:
        """Analyse a list of texts and return one result per document."""
        return [self.analyze(t) for t in texts]
