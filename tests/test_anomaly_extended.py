"""Extended AnomalyDetector tests: labels, scores, contamination, edge cases."""

from __future__ import annotations

import numpy as np
import pytest
from ai_intel import AnomalyDetector


class TestAnomalyDetectorLabels:
    def test_labels_are_minus_one_or_one(self):
        rng = np.random.default_rng(0)
        X = rng.normal(0, 1, (200, 4))
        det = AnomalyDetector(contamination=0.05)
        det.fit(X)
        labels = det.predict(X)
        assert set(np.unique(labels)).issubset({-1, 1})

    def test_label_count_matches_input(self):
        rng = np.random.default_rng(1)
        X = rng.normal(0, 1, (150, 3))
        det = AnomalyDetector()
        det.fit(X)
        assert len(det.predict(X)) == 150

    def test_contamination_controls_anomaly_rate(self):
        """Labelled anomalies should be approximately contamination * N."""
        rng = np.random.default_rng(2)
        X = rng.normal(0, 1, (500, 3))
        contamination = 0.10
        det = AnomalyDetector(contamination=contamination, random_state=0)
        det.fit(X)
        labels = det.predict(X)
        anomaly_rate = (labels == -1).mean()
        # IsolationForest guarantees exactly contamination on training data
        assert abs(anomaly_rate - contamination) < 0.01

    def test_clear_outliers_detected(self):
        """Inject obvious outliers far from the cluster."""
        rng = np.random.default_rng(3)
        inliers = rng.normal(0, 0.1, (190, 2))
        outliers = rng.normal(100, 0.1, (10, 2))   # far from cluster
        X = np.vstack([inliers, outliers])
        det = AnomalyDetector(contamination=0.05, random_state=42)
        det.fit(X)
        labels = det.predict(X)
        # All 10 extreme outliers should be flagged
        assert np.all(labels[190:] == -1)

    def test_inlier_count_correct(self):
        rng = np.random.default_rng(4)
        X = rng.normal(0, 1, (200, 5))
        det = AnomalyDetector(contamination=0.05)
        det.fit(X)
        labels = det.predict(X)
        n_inliers  = (labels == 1).sum()
        n_anomalies = (labels == -1).sum()
        assert n_inliers + n_anomalies == 200


class TestAnomalyDetectorScores:
    def test_scores_shape(self):
        rng = np.random.default_rng(5)
        X = rng.normal(0, 1, (100, 3))
        det = AnomalyDetector()
        det.fit(X)
        scores = det.score(X)
        assert scores.shape == (100,)

    def test_scores_finite(self):
        rng = np.random.default_rng(6)
        X = rng.normal(0, 1, (100, 3))
        det = AnomalyDetector()
        det.fit(X)
        assert np.all(np.isfinite(det.score(X)))

    def test_outliers_have_lower_scores(self):
        """Anomaly score should be lower for outliers than inliers on average."""
        rng = np.random.default_rng(7)
        inliers  = rng.normal(0, 0.1, (200, 2))
        outliers = rng.normal(50, 0.1, (10, 2))
        X = np.vstack([inliers, outliers])
        det = AnomalyDetector(contamination=0.05, random_state=42)
        det.fit(X)
        scores = det.score(X)
        mean_inlier_score  = scores[:200].mean()
        mean_outlier_score = scores[200:].mean()
        assert mean_outlier_score < mean_inlier_score

    def test_score_aligns_with_predict(self):
        """Samples with negative scores should generally be labelled -1."""
        rng = np.random.default_rng(8)
        X = rng.normal(0, 1, (300, 3))
        det = AnomalyDetector(contamination=0.10, random_state=42)
        det.fit(X)
        labels = det.predict(X)
        scores = det.score(X)
        # Anomalies (label=-1) should have lower average score than inliers
        assert scores[labels == -1].mean() < scores[labels == 1].mean()


class TestAnomalyDetectorErrors:
    def test_predict_before_fit_raises(self):
        rng = np.random.default_rng(9)
        X = rng.normal(0, 1, (50, 3))
        det = AnomalyDetector()
        with pytest.raises(RuntimeError, match="fitted"):
            det.predict(X)

    def test_score_before_fit_raises(self):
        rng = np.random.default_rng(10)
        X = rng.normal(0, 1, (50, 3))
        det = AnomalyDetector()
        with pytest.raises(RuntimeError, match="fitted"):
            det.score(X)

    def test_fit_returns_self(self):
        rng = np.random.default_rng(11)
        X = rng.normal(0, 1, (100, 2))
        det = AnomalyDetector()
        result = det.fit(X)
        assert result is det

    def test_single_feature(self):
        rng = np.random.default_rng(12)
        X = rng.normal(0, 1, (100, 1))
        det = AnomalyDetector()
        det.fit(X)
        labels = det.predict(X)
        assert labels.shape == (100,)

    def test_predict_on_new_data(self):
        rng = np.random.default_rng(13)
        X_train = rng.normal(0, 1, (200, 3))
        X_test  = rng.normal(0, 1, (50, 3))
        det = AnomalyDetector()
        det.fit(X_train)
        labels = det.predict(X_test)
        assert labels.shape == (50,)
        assert set(np.unique(labels)).issubset({-1, 1})

    def test_reproducible_with_same_seed(self):
        rng = np.random.default_rng(14)
        X = rng.normal(0, 1, (200, 3))
        det1 = AnomalyDetector(random_state=0)
        det2 = AnomalyDetector(random_state=0)
        det1.fit(X)
        det2.fit(X)
        assert np.array_equal(det1.predict(X), det2.predict(X))
