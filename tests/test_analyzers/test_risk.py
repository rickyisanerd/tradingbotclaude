"""Tests for the risk analyzer."""

from analyzers.risk import RiskAnalyzer


def test_risk_returns_valid_score(sample_bars):
    analyzer = RiskAnalyzer()
    result = analyzer.analyze("TEST", sample_bars)
    assert 0.0 <= result.score <= 1.0
    assert "atr" in result.details
    assert "stop_price" in result.details
    assert "target_price" in result.details
    assert result.details["stop_price"] < result.details["target_price"]


def test_risk_provides_reward_risk_ratio(sample_bars):
    analyzer = RiskAnalyzer()
    result = analyzer.analyze("TEST", sample_bars)
    assert result.details["reward_risk_ratio"] > 0
