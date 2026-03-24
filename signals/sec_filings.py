"""SEC EDGAR insider filings signal source."""

import logging
from datetime import datetime, timedelta

import requests

from signals.base import SignalSource
from config.settings import settings
from utils.retry import retry

log = logging.getLogger(__name__)

EDGAR_FULL_TEXT = "https://efts.sec.gov/LATEST/search-index"
EDGAR_COMPANY = "https://data.sec.gov/submissions"


class SECFilingsSignal(SignalSource):
    name = "sec_filings"
    ttl_hours = 6

    def cache_key(self, symbol: str | None = None) -> str:
        return f"sec_insider:{symbol}" if symbol else "sec_insider:all"

    @retry(max_attempts=2)
    def fetch(self, symbol: str | None = None) -> dict:
        """Fetch recent insider transactions from SEC EDGAR."""
        if not symbol:
            return {"available": False, "reason": "symbol_required"}

        headers = {"User-Agent": settings.sec_edgar_user_agent}

        try:
            # Use EDGAR full-text search for Form 4 filings (insider transactions)
            url = "https://efts.sec.gov/LATEST/search-index"
            params = {
                "q": f'"{symbol}"',
                "dateRange": "custom",
                "startdt": (datetime.utcnow() - timedelta(days=90)).strftime("%Y-%m-%d"),
                "enddt": datetime.utcnow().strftime("%Y-%m-%d"),
                "forms": "4",
            }

            resp = requests.get(
                "https://efts.sec.gov/LATEST/search-index",
                params=params,
                headers=headers,
                timeout=15,
            )

            if resp.status_code != 200:
                # Fallback: try the simpler company search
                return self._fetch_company_filings(symbol, headers)

            data = resp.json()
            hits = data.get("hits", {}).get("hits", [])

            # Rough heuristic: count filings mentioning purchase vs disposition
            buys = 0
            sells = 0
            for hit in hits[:20]:
                source = hit.get("_source", {})
                display = str(source).lower()
                if "purchase" in display or "acquisition" in display:
                    buys += 1
                elif "disposition" in display or "sale" in display:
                    sells += 1

            return {
                "available": True,
                "net_insider_buys": buys - sells,
                "insider_buys": buys,
                "insider_sells": sells,
                "filings_found": len(hits),
            }

        except requests.RequestException as e:
            log.warning("SEC filing fetch failed for %s: %s", symbol, e)
            return {"available": False, "reason": str(e)}

    def _fetch_company_filings(self, symbol: str, headers: dict) -> dict:
        """Fallback: check recent filings count."""
        return {
            "available": False,
            "reason": "primary_search_failed",
            "net_insider_buys": 0,
        }
