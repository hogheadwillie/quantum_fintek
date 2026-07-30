"""Basic smoke tests for ai-intel."""

import numpy as np
from ai_intel import AnomalyDetector


def test_anomaly_detector_fit_predict():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(200, 5))
    detector = AnomalyDetector(contamination=0.05)
    detector.fit(X)
    preds = detector.predict(X)
    assert set(np.unique(preds)).issubset({-1, 1})
