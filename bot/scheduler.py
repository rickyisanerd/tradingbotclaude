"""APScheduler: pre-market refresh -> scan -> trade -> post-market learn."""

import logging
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from utils.logging_config import setup_logging
from db.engine import init_db
from db.repository import initialize_default_weights

log = logging.getLogger(__name__)


def job_refresh_signals():
    """Pre-market: refresh all external signal caches."""
    from signals.health import refresh_signals
    from bot.universe import build_universe
    from bot.safety import safe_execute

    log.info("=== SIGNAL REFRESH START ===")
    # Build universe first to know which symbols to refresh
    symbols = safe_execute(build_universe, fallback=[], context="universe_for_refresh")
    safe_execute(refresh_signals, symbols[:50], fallback={}, context="signal_refresh")
    log.info("=== SIGNAL REFRESH DONE ===")


def job_scan_and_trade():
    """Main trading job: scan, score, gate, execute."""
    from bot.orchestrator import trade_once
    from bot.safety import safe_execute

    log.info("=== TRADE CYCLE START ===")
    result = safe_execute(trade_once, fallback={"error": "trade_once_failed"}, context="trade_once")
    log.info("=== TRADE CYCLE DONE === result=%s", result)


def job_check_exits():
    """Check open positions for exit conditions."""
    from bot.exit_manager import manage_exits
    from bot.safety import safe_execute

    exits = safe_execute(manage_exits, fallback=[], context="exit_check")
    if exits:
        log.info("Exit check triggered %d exits", len(exits))


def job_post_market_learn():
    """Post-market: update analyzer weights from closed trades."""
    from bot.learning import update_weights_from_closed_trades
    from bot.safety import safe_execute

    log.info("=== LEARNING UPDATE START ===")
    safe_execute(update_weights_from_closed_trades, fallback={}, context="learning")
    log.info("=== LEARNING UPDATE DONE ===")


def job_health_check():
    """Periodic health check of all signal sources."""
    from bot.safety import check_system_health

    status = check_system_health()
    if status.degraded:
        log.warning("Health check: DEGRADED — %s", status.degraded_sources + status.down_sources)
    else:
        log.debug("Health check: OK")


def create_scheduler() -> BlockingScheduler:
    """Create and configure the APScheduler."""
    scheduler = BlockingScheduler(timezone="America/New_York")

    # Pre-market signal refresh: 8:30 AM ET weekdays
    scheduler.add_job(
        job_refresh_signals,
        CronTrigger(day_of_week="mon-fri", hour=8, minute=30, timezone="America/New_York"),
        id="refresh_signals",
        name="Pre-market signal refresh",
        misfire_grace_time=300,
    )

    # Main scan and trade: 9:35 AM ET weekdays (5 min after open)
    scheduler.add_job(
        job_scan_and_trade,
        CronTrigger(day_of_week="mon-fri", hour=9, minute=35, timezone="America/New_York"),
        id="scan_and_trade",
        name="Scan and trade",
        misfire_grace_time=300,
    )

    # Exit check: every 5 minutes during market hours (9:30-16:00 ET)
    scheduler.add_job(
        job_check_exits,
        CronTrigger(
            day_of_week="mon-fri",
            hour="9-15",
            minute="*/5",
            timezone="America/New_York",
        ),
        id="check_exits",
        name="Exit check",
        misfire_grace_time=120,
    )

    # Also check exits at market close
    scheduler.add_job(
        job_check_exits,
        CronTrigger(day_of_week="mon-fri", hour=15, minute=55, timezone="America/New_York"),
        id="check_exits_close",
        name="Exit check (near close)",
        misfire_grace_time=120,
    )

    # Post-market learning: 4:15 PM ET weekdays
    scheduler.add_job(
        job_post_market_learn,
        CronTrigger(day_of_week="mon-fri", hour=16, minute=15, timezone="America/New_York"),
        id="post_market_learn",
        name="Post-market learning",
        misfire_grace_time=600,
    )

    # Health check: every 15 minutes
    scheduler.add_job(
        job_health_check,
        IntervalTrigger(minutes=15),
        id="health_check",
        name="System health check",
        misfire_grace_time=60,
    )

    return scheduler


def main():
    setup_logging()
    log.info("Initializing tradebot-claude scheduler...")
    init_db()
    initialize_default_weights()
    scheduler = create_scheduler()
    log.info("Scheduler configured with %d jobs. Starting...", len(scheduler.get_jobs()))
    for job in scheduler.get_jobs():
        log.info("  Job: %s — next run: %s", job.name, job.next_run_time)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler shutting down...")
        scheduler.shutdown()


if __name__ == "__main__":
    main()
