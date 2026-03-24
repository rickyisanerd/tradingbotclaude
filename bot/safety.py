"""Safety module: degraded mode, PDT cooldown, freshness, graceful failures."""

import logging
from dataclasses import dataclass, field

from db.repository import get_all_source_health, audit
from config.settings import settings

log = logging.getLogger(__name__)


@dataclass
class SystemStatus:
    degraded: bool = False
    degraded_sources: list = field(default_factory=list)
    down_sources: list = field(default_factory=list)
    pdt_cooldown: bool = False
    can_trade: bool = True
    reasons: list = field(default_factory=list)


def check_system_health() -> SystemStatus:
    """Evaluate overall system health and determine if trading should proceed."""
    status = SystemStatus()

    # Check source health
    sources = get_all_source_health()
    for src in sources:
        if src["status"] == "degraded":
            status.degraded_sources.append(src["source_name"])
        elif src["status"] == "down":
            status.down_sources.append(src["source_name"])

    if status.degraded_sources or status.down_sources:
        status.degraded = True
        log.warning(
            "System degraded: degraded=%s, down=%s",
            status.degraded_sources,
            status.down_sources,
        )

    # Critical sources that block trading if down
    critical_down = [s for s in status.down_sources if s in ("alpaca_data", "alpaca_trading")]
    if critical_down:
        status.can_trade = False
        status.reasons.append(f"Critical sources down: {critical_down}")

    return status


def get_gate_adjustments(status: SystemStatus) -> dict:
    """When degraded, return stricter gate thresholds."""
    if not status.degraded:
        return {}

    adjustments = {}
    # Raise minimum scores in degraded mode to be more conservative
    severity = len(status.degraded_sources) + len(status.down_sources) * 2

    if severity >= 2:
        adjustments["min_final_score_boost"] = 0.05 * severity
        adjustments["skip_decision_support"] = any(
            s in status.down_sources
            for s in ("congressional", "sec_filings", "earnings", "macro")
        )
        log.info("Degraded gate adjustments: %s", adjustments)

    return adjustments


def safe_execute(func, *args, fallback=None, context="unknown", **kwargs):
    """Execute a function with graceful failure handling."""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        log.error("Safe execute failed [%s]: %s", context, e)
        audit("safe_execute_failure", {"context": context, "error": str(e)})
        return fallback
