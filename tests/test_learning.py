"""Tests for the learning/weight update system."""

from unittest.mock import patch
from db.models import Trade


@patch("bot.learning.get_recently_closed_trades")
@patch("bot.learning.get_scores_for_trade")
@patch("bot.learning.get_current_weights")
@patch("bot.learning.insert_weights")
@patch("bot.learning.audit")
def test_weight_update_on_winning_trade(mock_audit, mock_insert, mock_weights, mock_scores, mock_trades):
    mock_trades.return_value = [
        Trade(id=1, pnl_pct=0.05, status="closed"),
    ]
    mock_scores.return_value = {
        "momentum": 0.8,
        "reversion": 0.2,
        "risk": 0.6,
        "decision_support": 0.5,
    }
    mock_weights.return_value = {
        "momentum": 0.25,
        "reversion": 0.25,
        "risk": 0.25,
        "decision_support": 0.25,
    }

    from bot.learning import update_weights_from_closed_trades
    new_weights = update_weights_from_closed_trades(hours=24)

    # Winning trade should boost momentum (highest score) more
    assert mock_insert.called
    stored = mock_insert.call_args[0][0]
    # Momentum had highest raw score, should have highest weight after update
    assert stored["momentum"] > stored["reversion"]


@patch("bot.learning.get_recently_closed_trades")
def test_no_trades_returns_current(mock_trades):
    mock_trades.return_value = []
    with patch("bot.learning.get_current_weights", return_value={"momentum": 0.3, "reversion": 0.25, "risk": 0.25, "decision_support": 0.20}):
        from bot.learning import update_weights_from_closed_trades
        result = update_weights_from_closed_trades()
        assert result["momentum"] == 0.3
