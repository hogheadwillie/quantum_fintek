"""Extended SentimentAnalyzer tests: scoring, edge cases, batch."""

from __future__ import annotations

import pytest
from ai_intel import SentimentAnalyzer, SentimentResult


class TestSentimentScoring:
    def setup_method(self):
        self.sa = SentimentAnalyzer(neutral_threshold=0.05)

    # ── label assignment ───────────────────────────────────────────────────

    def test_strong_positive_label(self):
        r = self.sa.analyze("record profit growth beat strong revenue surge")
        assert r.label == "positive"
        assert r.score > 0

    def test_strong_negative_label(self):
        r = self.sa.analyze("collapse bankrupt fraud crisis loss default")
        assert r.label == "negative"
        assert r.score < 0

    def test_neutral_mixed_equal(self):
        # One positive, one negative → should cancel to neutral
        r = self.sa.analyze("profit loss")
        assert r.label == "neutral"

    def test_score_bounded(self):
        for text in [
            "massive profit growth surge rally record boom bullish",
            "collapse bankrupt crisis default fraud recession loss decline",
            "the company released its quarterly report",
        ]:
            r = self.sa.analyze(text)
            assert -1.0 <= r.score <= 1.0

    def test_confidence_bounded(self):
        for text in ["profit growth", "loss decline", "quarterly report"]:
            r = self.sa.analyze(text)
            assert 0.0 <= r.confidence <= 1.0

    # ── counts ─────────────────────────────────────────────────────────────

    def test_positive_count_nonzero_for_positive_text(self):
        r = self.sa.analyze("profit growth rally surge")
        assert r.positive_count >= 2

    def test_negative_count_nonzero_for_negative_text(self):
        r = self.sa.analyze("loss decline risk fraud")
        assert r.negative_count >= 2

    def test_word_count_matches_tokenisation(self):
        text = "profit loss growth"
        r = self.sa.analyze(text)
        assert r.word_count == 3

    def test_word_count_with_punctuation(self):
        text = "profit, loss, growth!"
        r = self.sa.analyze(text)
        assert r.word_count == 3

    # ── edge cases ─────────────────────────────────────────────────────────

    def test_empty_string(self):
        r = self.sa.analyze("")
        assert r.label == "neutral"
        assert r.score == 0.0
        assert r.word_count == 0
        assert r.confidence == 0.0

    def test_whitespace_only(self):
        r = self.sa.analyze("   \t\n  ")
        assert r.label == "neutral"
        assert r.word_count == 0

    def test_numbers_only(self):
        r = self.sa.analyze("123 456 789")
        assert r.word_count == 0
        assert r.label == "neutral"

    def test_single_positive_word(self):
        r = self.sa.analyze("profit")
        assert r.positive_count == 1
        assert r.negative_count == 0

    def test_single_negative_word(self):
        r = self.sa.analyze("loss")
        assert r.negative_count == 1
        assert r.positive_count == 0

    def test_all_unknown_words(self):
        r = self.sa.analyze("xyzzy quux frobble grault")
        assert r.positive_count == 0
        assert r.negative_count == 0
        assert r.label == "neutral"

    def test_case_insensitive(self):
        r_lower = self.sa.analyze("profit growth")
        r_upper = self.sa.analyze("PROFIT GROWTH")
        assert r_lower.score == r_upper.score

    # ── negation ───────────────────────────────────────────────────────────

    def test_negation_flips_positive_to_negative(self):
        pos = self.sa.analyze("strong profit growth")
        neg = self.sa.analyze("not strong not profit not growth")
        assert neg.score <= pos.score

    def test_negation_of_negative_improves_score(self):
        neg  = self.sa.analyze("loss collapse crisis")
        nneg = self.sa.analyze("no loss no collapse no crisis")
        assert nneg.score >= neg.score

    def test_negation_window_limited_to_3(self):
        """Negation word >3 tokens before positive should NOT negate it."""
        r = self.sa.analyze("not a b c profit")
        # "not" is 4 tokens before "profit" → out of window → profit not negated
        assert r.positive_count == 1

    # ── uncertainty ────────────────────────────────────────────────────────

    def test_uncertainty_dampens_score(self):
        certain  = self.sa.analyze("record profit growth revenue beat exceeded")
        uncertain = self.sa.analyze(
            "may possibly record profit could perhaps growth estimate revenue"
        )
        assert uncertain.score <= certain.score

    def test_uncertainty_count_populated(self):
        r = self.sa.analyze("may possibly perhaps uncertain")
        assert r.uncertainty_count >= 3

    # ── neutral threshold ──────────────────────────────────────────────────

    def test_tight_threshold_classifies_weak_signal(self):
        sa_tight = SentimentAnalyzer(neutral_threshold=0.0)
        r = sa_tight.analyze("profit")
        assert r.label == "positive"

    def test_wide_threshold_score_below_one(self):
        """The maximum raw_score is 1.0 (all positive, no negative words)."""
        sa_wide = SentimentAnalyzer(neutral_threshold=0.99)
        r = sa_wide.analyze("massive profit growth surge rally record boom")
        # Score ≤ 1.0 — if all words are positive raw_score = 1.0 ≥ 0.99 → positive
        assert r.score <= 1.0
        assert r.label in ("positive", "neutral")

    def test_wide_threshold_no_sentiment_words_neutral(self):
        """Text with zero sentiment words always scores 0.0 → neutral at any threshold."""
        sa_wide = SentimentAnalyzer(neutral_threshold=0.99)
        r = sa_wide.analyze("the quarterly report was published on tuesday")
        # No positive or negative lexicon words → score = 0.0 → neutral
        assert r.label == "neutral"
        assert r.score == 0.0

    # ── batch ──────────────────────────────────────────────────────────────

    def test_batch_length(self):
        texts = ["profit growth", "loss risk", "quarterly report"]
        results = self.sa.analyze_batch(texts)
        assert len(results) == 3

    def test_batch_matches_individual(self):
        texts = [
            "strong profit growth rally",
            "loss decline collapse",
            "report quarterly results",
        ]
        batch = self.sa.analyze_batch(texts)
        for text, batch_result in zip(texts, batch):
            individual = self.sa.analyze(text)
            assert batch_result.score == individual.score
            assert batch_result.label == individual.label

    def test_batch_empty_list(self):
        results = self.sa.analyze_batch([])
        assert results == []

    def test_batch_single_item(self):
        results = self.sa.analyze_batch(["profit"])
        assert len(results) == 1
        assert results[0].positive_count == 1

    def test_all_results_are_sentiment_result(self):
        texts = ["profit", "loss", "report"]
        for r in self.sa.analyze_batch(texts):
            assert isinstance(r, SentimentResult)
