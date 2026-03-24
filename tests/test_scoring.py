"""Tests for the scoring pipeline."""

import pandas as pd
import numpy as np
from unittest.mock import patch


def _make_bars(days=60, base=5.0):
    np.random.seed(42)
    dates = pd.date_range(end=pd.Timestamp.now(), periods=days, freq="B")
    returns = np.random.normal(0.001, 0.02, days)
    prices = base * np.cumprod(1 + returns)
    return pd.DataFrame({
        "open": prices * 1.001,
        "high": prices * 1.015,
        "low": prices * 0.985,
        "close": prices,
        "volume": np.random.randint(500_000, 3_000_000, days).astype(float),
        "vwap": prices * 0.999,
    }, index=dates)


@patch("bot.scoring.get_current_weights")
def test_score_candidate_computes_final(mock_weights):
    mock_weights.return_value = {
        "momentum": 0.30, "reversion": 0.25,
        "risk": 0.25, "decision_support": 0.20,
    }
    from bot.scoring import score_candidate
    bars = _make_bars()
    result = score_candidate("TEST", bars)
    assert 0.0 <= result.final_score <= 1.0
    assert len(result.raw_scores) == 4
    assert result.symbol == "TEST"


@patch("bot.scoring.get_current_weights")
def test_score_all_sorted_descending(mock_weights):
    mock_weights.return_value = {
        "momentum": 0.30, "reversion": 0.25,
        "risk": 0.25, "decision_support": 0.20,
    }
    from bot.scoring import score_all
    bars_map = {"A": _make_bars(base=5.0), "B": _make_bars(base=7.0)}
    results = score_all(bars_map)
    assert len(results) == 2
    assert results[0].final_score >= results[1].final_score
