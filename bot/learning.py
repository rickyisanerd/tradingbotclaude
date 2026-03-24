"""Post-trade weight updater: bounded return contribution learning."""

import logging

from db.repository import (
    get_recently_closed_trades,
    get_scores_for_trade,
    get_current_weights,
    insert_weights,
    audit,
)
from config.settings import settings
from config.constants import ANALYZER_NAMES

log = logging.getLogger(__name__)


def update_weights_from_closed_trades(hours: int = 24) -> dict[str, float]:
    """Process recently closed trades and update analyzer weights.

    Algorithm:
    - For each closed trade, look up its analyzer scores
    - Compute bounded return (clamped to +/- max_return_contribution)
    - Win: nudge weights toward the trade's analyzer profile
    - Loss: nudge weights away from the trade's analyzer profile
    - Normalize weights to sum to 1.0
    - Enforce minimum weight floor

    Returns the new weight dict.
    """
    closed = get_recently_closed_trades(hours=hours)
    if not closed:
        log.debug("No recently closed trades for learning")
        return get_current_weights()

    weights = get_current_weights()
    lr = settings.learning_rate
    max_contrib = settings.max_return_contribution
    min_w = settings.min_weight
    updates = 0

    for trade in closed:
        if trade.pnl_pct is None:
            continue

        scores = get_scores_for_trade(trade.id)
        if not scores:
            continue

        # Bounded return
        bounded = max(-max_contrib, min(max_contrib, trade.pnl_pct))
        direction = 1.0 if bounded > 0 else -1.0
        magnitude = abs(bounded)

        # Update each analyzer's weight
        for name in ANALYZER_NAMES:
            score = scores.get(name, 0.0)
            contribution = score * magnitude
            weights[name] += lr * direction * contribution

        updates += 1

    if updates == 0:
        return weights

    # Normalize weights to sum to 1.0
    total = sum(weights.values())
    if total > 0:
        weights = {k: v / total for k, v in weights.items()}

    # Enforce minimum weight floor
    below_floor = {k: v for k, v in weights.items() if v < min_w}
    if below_floor:
        for k in below_floor:
            weights[k] = min_w
        # Re-normalize
        total = sum(weights.values())
        weights = {k: v / total for k, v in weights.items()}

    # Persist
    reason = f"learning_update_{updates}_trades"
    insert_weights(weights, reason)

    audit("weights_updated", {
        "new_weights": {k: round(v, 4) for k, v in weights.items()},
        "trades_processed": updates,
        "reason": reason,
    })

    log.info(
        "Learning update: processed %d trades, new weights: %s",
        updates,
        {k: f"{v:.3f}" for k, v in weights.items()},
    )
    return weights
