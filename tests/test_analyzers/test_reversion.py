"""Tests for the reversion analyzer."""

from analyzers.reversion import ReversionAnalyzer


def test_reversion_returns_valid_score(sample_bars):
    analyzer = ReversionAnalyzer()
    result = analyzer.analyze("TEST", sample_bars)
    assert 0.0 <= result.score <= 1.0
    assert "bb_pct_b" in result.details
    assert "red_days" in result.details


def test_reversion_high_on_oversold(oversold_bars):
    analyzer = ReversionAnalyzer()
    result = analyzer.analyze("TEST", oversold_bars)
    # Oversold stock should get a decent reversion score
    assert result.score >= 0.3
    assert result.details["red_days"] >= 3
