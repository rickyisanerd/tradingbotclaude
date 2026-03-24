"""Tests for buy gate checks."""

from unittest.mock import patch
from bot.scoring import ScoredCandidate


def _make_candidate(final=0.7, risk=0.5, ds=0.4, rr=2.5, dv=1_000_000):
    c = ScoredCandidate(symbol="TEST")
    c.final_score = final
    c.raw_scores = {"momentum": 0.6, "reversion": 0.5, "risk": risk, "decision_support": ds}
    c.risk_details = {
        "reward_risk_ratio": rr,
        "avg_dollar_volume": dv,
        "stop_price": 4.5,
        "target_price": 6.5,
    }
    return c


@patch("bot.gate_check.is_pdt_restricted", return_value=False)
@patch("bot.gate_check.get_buying_power", return_value=10_000)
def test_all_gates_pass(mock_bp, mock_pdt):
    from bot.gate_check import check_gates
    c = _make_candidate()
    result = check_gates(c)
    assert result.passed is True
    assert len(result.reasons) == 0
    assert c.recommendation == "buy"


@patch("bot.gate_check.is_pdt_restricted", return_value=False)
@patch("bot.gate_check.get_buying_power", return_value=10_000)
def test_low_score_fails(mock_bp, mock_pdt):
    from bot.gate_check import check_gates
    c = _make_candidate(final=0.3)
    result = check_gates(c)
    assert result.passed is False
    assert any("final_score" in r for r in result.reasons)


@patch("bot.gate_check.is_pdt_restricted", return_value=True)
@patch("bot.gate_check.get_buying_power", return_value=10_000)
def test_pdt_restricted_fails(mock_bp, mock_pdt):
    from bot.gate_check import check_gates
    c = _make_candidate()
    result = check_gates(c)
    assert result.passed is False
    assert any("PDT" in r for r in result.reasons)
