"""Congressional trades signal source (QuiverQuant or similar)."""

import logging

import requests

from signals.base import SignalSource
from config.settings import settings
from utils.retry import retry

log = logging.getLogger(__name__)

QUIVER_BASE = "https://api.quiverquant.com/beta"


class CongressionalSignal(SignalSource):
    name = "congressional"
    ttl_hours = 12  # Congress trades update infrequently

    def cache_key(self, symbol: str | None = None) -> str:
        return f"congressional:{symbol}" if symbol else "congressional:all"

    @retry(max_attempts=2)
    def fetch(self, symbol: str | None = None) -> dict:
        """Fetch recent congressional trades for a symbol."""
        if not settings.quiver_api_key:
            return {"available": False, "reason": "no_api_key"}

        headers = {"Authorization": f"Bearer {settings.quiver_api_key}"}

        try:
            if symbol:
                url = f"{QUIVER_BASE}/historical/congresstrading/{symbol}"
            else:
                url = f"{QUIVER_BASE}/live/congresstrading"

            resp = requests.get(url, headers=headers, timeout=15)

            if resp.status_code == 403:
                return {"available": False, "reason": "unauthorized"}
            if resp.status_code == 429:
                return {"available": False, "reason": "rate_limited"}

            resp.raise_for_status()
            data = resp.json()

            # Count recent buys/sells (last 90 days of data)
            buys = sum(1 for t in data if t.get("Transaction", "").lower() == "purchase")
            sells = sum(1 for t in data if t.get("Transaction", "").lower() in ("sale", "sale_full"))

            return {
                "available": True,
                "recent_buys": buys,
                "recent_sells": sells,
                "net": buys - sells,
                "total_trades": len(data),
            }

        except requests.RequestException as e:
            log.warning("Congressional signal fetch failed: %s", e)
            return {"available": False, "reason": str(e)}
