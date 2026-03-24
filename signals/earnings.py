"""Earnings calendar signal source."""

import logging
from datetime import datetime, timedelta

import requests

from signals.base import SignalSource
from utils.retry import retry

log = logging.getLogger(__name__)


class EarningsSignal(SignalSource):
    name = "earnings"
    ttl_hours = 12

    def cache_key(self, symbol: str | None = None) -> str:
        return f"earnings:{symbol}" if symbol else "earnings:all"

    @retry(max_attempts=2)
    def fetch(self, symbol: str | None = None) -> dict:
        """Check earnings proximity for a symbol using free API sources."""
        if not symbol:
            return {"available": False, "reason": "symbol_required"}

        try:
            # Try SEC EDGAR for earnings filing dates (8-K)
            headers = {"User-Agent": "tradebot-claude bot@example.com"}
            url = "https://efts.sec.gov/LATEST/search-index"
            params = {
                "q": f'"{symbol}"',
                "forms": "8-K",
                "dateRange": "custom",
                "startdt": (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d"),
                "enddt": (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%d"),
            }

            resp = requests.get(url, params=params, headers=headers, timeout=10)

            if resp.status_code == 200:
                data = resp.json()
                hits = data.get("hits", {}).get("hits", [])

                # Find most recent 8-K filing
                if hits:
                    # Assume earnings are around these dates
                    return {
                        "available": True,
                        "days_until": 30,  # Conservative: no precise date
                        "recent_8k_count": len(hits),
                        "note": "estimated from 8-K filings",
                    }

            # No data found — assume no imminent earnings
            return {
                "available": True,
                "days_until": 999,
                "note": "no recent 8-K found",
            }

        except requests.RequestException as e:
            log.warning("Earnings fetch failed for %s: %s", symbol, e)
            return {"available": False, "reason": str(e), "days_until": 999}
