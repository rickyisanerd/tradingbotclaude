"""Signal source health tracker and refresher."""

import logging
from typing import Optional

from signals.base import SignalSource
from signals.congressional import CongressionalSignal
from signals.sec_filings import SECFilingsSignal
from signals.earnings import EarningsSignal
from signals.macro import MacroSignal
from db.repository import upsert_signal_cache, update_source_health, audit

log = logging.getLogger(__name__)

ALL_SOURCES: list[SignalSource] = [
    CongressionalSignal(),
    SECFilingsSignal(),
    EarningsSignal(),
    MacroSignal(),
]


def refresh_signals(symbols: Optional[list[str]] = None) -> dict:
    """Refresh all external signal caches.

    Args:
        symbols: If provided, refresh per-symbol signals. Otherwise global only.

    Returns:
        Summary of refresh results.
    """
    results = {}

    for source in ALL_SOURCES:
        source_name = source.name

        # Global signals (e.g., macro)
        try:
            data = source.fetch(symbol=None)
            key = source.cache_key(symbol=None)
            upsert_signal_cache(key, source_name, data, source.ttl_hours)
            update_source_health(source_name, success=True)
            results[f"{source_name}:global"] = "ok"
        except Exception as e:
            update_source_health(source_name, success=False)
            results[f"{source_name}:global"] = f"error: {e}"
            log.error("Signal refresh failed for %s (global): %s", source_name, e)

        # Per-symbol signals
        if symbols:
            for sym in symbols[:50]:  # Cap to avoid excessive API calls
                try:
                    data = source.fetch(symbol=sym)
                    key = source.cache_key(symbol=sym)
                    upsert_signal_cache(key, source_name, data, source.ttl_hours)
                except Exception as e:
                    log.debug("Signal %s failed for %s: %s", source_name, sym, e)

    audit("signals_refreshed", results)
    log.info("Signal refresh complete: %s", results)
    return results
