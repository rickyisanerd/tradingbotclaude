"""Tests for the momentum analyzer."""

from analyzers.momentum import MomentumAnalyzer


def test_momentum_returns_valid_score(sample_bars):
    analyzer = MomentumAnalyzer()
    result = analyzer.analyze("TEST", sample_bars)
    assert 0.0 <= result.score <= 1.0
    assert "rsi" in result.details
    assert "macd_score" in result.details
    assert "vol_ratio" in result.details


def test_momentum_insufficient_data():
    import pandas as pd
    short_df = pd.DataFrame({"close": [5.0] * 10, "volume": [1000] * 10})
    analyzer = MomentumAnalyzer()
    result = analyzer.analyze("TEST", short_df)
    assert result.score == 0.0
    assert "error" in result.details
