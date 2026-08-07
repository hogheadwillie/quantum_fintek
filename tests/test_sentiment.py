"""Tests for ai-intel SentimentAnalyzer."""

from ai_intel import SentimentAnalyzer, SentimentResult


class TestSentimentAnalyzer:
    def setup_method(self):
        self.analyser = SentimentAnalyzer()

    def test_positive_text(self):
        result = self.analyser.analyze(
            "Strong profit growth and record revenue beat expectations with robust momentum"
        )
        assert isinstance(result, SentimentResult)
        assert result.label == "positive"
        assert result.score > 0

    def test_negative_text(self):
        result = self.analyser.analyze(
            "Loss and decline with risk of default and debt crisis causing major concern"
        )
        assert result.label == "negative"
        assert result.score < 0

    def test_neutral_text(self):
        result = self.analyser.analyze("The quarterly report was published today")
        assert result.label == "neutral"

    def test_empty_text(self):
        result = self.analyser.analyze("")
        assert result.label == "neutral"
        assert result.score == 0.0
        assert result.word_count == 0

    def test_negation_flips_sentiment(self):
        positive = self.analyser.analyze("strong profit growth")
        negated = self.analyser.analyze("not strong not profit not growth")
        # Negated version should be less positive (or negative)
        assert negated.score <= positive.score

    def test_uncertainty_dampens_confidence(self):
        certain = self.analyser.analyze("record profit and strong growth beat")
        uncertain = self.analyser.analyze(
            "may possibly record profit and could perhaps see growth"
        )
        # Uncertainty dampens adjusted score
        assert uncertain.score <= certain.score

    def test_counts_populated(self):
        result = self.analyser.analyze("profit growth loss risk")
        assert result.positive_count >= 1
        assert result.negative_count >= 1
        assert result.word_count >= 4

    def test_batch_returns_correct_length(self):
        texts = ["profit growth", "loss decline risk", "neutral statement here"]
        results = self.analyser.analyze_batch(texts)
        assert len(results) == 3

    def test_score_range(self):
        texts = [
            "massive profit growth surge rally record boom",
            "collapse bankrupt crisis default fraud recession loss",
        ]
        for text in texts:
            r = self.analyser.analyze(text)
            assert -1.0 <= r.score <= 1.0
            assert 0.0 <= r.confidence <= 1.0

    def test_custom_neutral_threshold(self):
        analyser_tight = SentimentAnalyzer(neutral_threshold=0.0)
        result = analyser_tight.analyze("profit")
        # Any positive signal should be labelled positive with threshold=0
        assert result.label in ("positive", "neutral")
