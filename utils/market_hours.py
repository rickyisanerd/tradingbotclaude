"""Market open/close detection (US Eastern)."""

from datetime import datetime, time as dtime
import zoneinfo

ET = zoneinfo.ZoneInfo("America/New_York")

MARKET_OPEN = dtime(9, 30)
MARKET_CLOSE = dtime(16, 0)


def now_et() -> datetime:
    return datetime.now(ET)


def is_market_open() -> bool:
    now = now_et()
    if now.weekday() >= 5:  # Saturday/Sunday
        return False
    return MARKET_OPEN <= now.time() <= MARKET_CLOSE


def minutes_until_open() -> float:
    """Minutes until next market open (negative if already open)."""
    now = now_et()
    today_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    if now.weekday() >= 5 or now.time() > MARKET_CLOSE:
        # Next trading day
        days_ahead = 7 - now.weekday() if now.weekday() >= 5 else 1
        if now.weekday() == 5:
            days_ahead = 2
        from datetime import timedelta
        next_open = (now + timedelta(days=days_ahead)).replace(
            hour=9, minute=30, second=0, microsecond=0
        )
        return (next_open - now).total_seconds() / 60
    return (today_open - now).total_seconds() / 60
