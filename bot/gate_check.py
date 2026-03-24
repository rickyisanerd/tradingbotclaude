"""Buy gates: evaluates all conditions, returns pass/fail with reasons."""

import logging
from dataclasses import dataclass, field

from bot.scoring import ScoredCandidate
from broker.account import is_pdt_restricted, get_buying_power
from config.settings import settings
from db.repository import audit

log = logging.getLogger(__name__)


@dataclass
class GateResult:
    passed: bool = False
    reasons: list = field(default_factory=list)


def check_gates(candidate: ScoredCandidate) -> GateResult:
    """Evaluate all buy gates for a scored candidate."""
    result = GateResult()
    reasons = []

    # Gate 1: Minimum final score
    if candidate.final_score < settings.min_final_score:
        reasons.append(
            f"final_score {candidate.final_score:.3f} < {settings.min_final_score}"
        )

    # Gate 2: Minimum reward/risk ratio
    rr = candidate.risk_details.get("reward_risk_ratio", 0)
    if rr < settings.min_reward_risk:
        reasons.append(f"reward_risk {rr:.2f} < {settings.min_reward_risk}")

    # Gate 3: Minimum dollar volume
    dv = candidate.risk_details.get("avg_dollar_volume", 0)
    if dv < settings.min_dollar_volume:
        reasons.append(f"dollar_volume {dv:.0f} < {settings.min_dollar_volume}")

    # Gate 4: Minimum risk score
    risk_score = candidate.raw_scores.get("risk", 0)
    if risk_score < settings.min_risk_score:
        reasons.append(f"risk_score {risk_score:.3f} < {settings.min_risk_score}")

    # Gate 5: Minimum decision-support score
    ds_score = candidate.raw_scores.get("decision_support", 0)
    if ds_score < settings.min_ds_score:
        reasons.append(f"ds_score {ds_score:.3f} < {settings.min_ds_score}")

    # Gate 6: PDT check
    try:
        if is_pdt_restricted():
            reasons.append("PDT restricted — 3+ day trades with <$25K equity")
    except Exception as e:
        log.warning("PDT check failed (allowing): %s", e)

    # Gate 7: Sufficient buying power
    try:
        bp = get_buying_power()
        # Need at least enough for minimum position
        price = candidate.risk_details.get("target_price", 10)  # rough
        min_cost = price * 1  # at least 1 share
        if bp < min_cost:
            reasons.append(f"buying_power ${bp:.2f} insufficient")
    except Exception as e:
        log.warning("Buying power check failed (allowing): %s", e)

    result.reasons = reasons
    result.passed = len(reasons) == 0

    if result.passed:
        candidate.recommendation = "buy"
        log.info("GATE PASSED: %s (score=%.3f)", candidate.symbol, candidate.final_score)
    else:
        candidate.recommendation = "watch"
        log.debug("Gate failed for %s: %s", candidate.symbol, reasons)

    return result
