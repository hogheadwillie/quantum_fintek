"""Anomaly detection for market / sensor time series."""

from __future__ import annotations

from typing import Optional
import numpy as np
from sklearn.ensemble import IsolationForest


class AnomalyDetector:
    """Isolation Forest based anomaly detector."""

    def __init__(self, contamination: float = 0.05, random_state: int = 42) -> None:
        self.model = IsolationForest(
            contamination=contamination,
            random_state=random_state,
            n_estimators=200,
        )
        self._fitted = False

    def fit(self, X: np.ndarray) -> "AnomalyDetector":
        self.model.fit(X)
        self._fitted = True
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Return -1 for anomalies, 1 for inliers."""
        if not self._fitted:
            raise RuntimeError("Model must be fitted before prediction")
        return self.model.predict(X)

    def score(self, X: np.ndarray) -> np.ndarray:
        """Lower scores indicate more anomalous points."""
        if not self._fitted:
            raise RuntimeError("Model must be fitted before scoring")
        return self.model.decision_function(X)
