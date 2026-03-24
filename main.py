"""Main entry point for tradebot-claude.

Usage:
    python main.py scheduler   — Run the automated scheduler (production)
    python main.py dashboard   — Run the web dashboard only
    python main.py trade       — Run a single trade cycle (manual)
    python main.py scan        — Run scan only, print results (no trades)
    python main.py init        — Initialize database and default weights
"""

import sys
from utils.logging_config import setup_logging
from db.engine import init_db
from db.repository import initialize_default_weights


def cmd_init():
    init_db()
    initialize_default_weights()
    print("Database initialized and default weights seeded.")


def cmd_scheduler():
    from bot.scheduler import main as scheduler_main
    scheduler_main()


def cmd_dashboard():
    from dashboard.app import create_app
    app = create_app()
    app.run(debug=True, host="0.0.0.0", port=5000)


def cmd_trade():
    init_db()
    initialize_default_weights()
    from bot.orchestrator import trade_once
    result = trade_once()
    import json
    print(json.dumps(result, indent=2, default=str))


def cmd_scan():
    init_db()
    initialize_default_weights()
    from bot.universe import build_universe
    from bot.scanner import pre_filter, fetch_bars
    from bot.scoring import score_all

    print("Building universe...")
    universe = build_universe()
    print(f"Universe: {len(universe)} symbols")

    candidates = pre_filter(universe)
    print(f"After pre-filter: {len(candidates)} candidates")

    print("Fetching bars...")
    bars_map = fetch_bars(candidates[:100])  # Cap for scan-only
    print(f"Got bars for {len(bars_map)} symbols")

    print("Scoring...")
    scored = score_all(bars_map)

    print(f"\n{'Symbol':<8} {'Score':>7} {'Mom':>6} {'Rev':>6} {'Risk':>6} {'DS':>6} {'Rec':<6}")
    print("-" * 55)
    for c in scored[:30]:
        print(
            f"{c.symbol:<8} {c.final_score:>7.3f} "
            f"{c.raw_scores.get('momentum', 0):>6.3f} "
            f"{c.raw_scores.get('reversion', 0):>6.3f} "
            f"{c.raw_scores.get('risk', 0):>6.3f} "
            f"{c.raw_scores.get('decision_support', 0):>6.3f} "
            f"{c.recommendation:<6}"
        )


COMMANDS = {
    "init": cmd_init,
    "scheduler": cmd_scheduler,
    "dashboard": cmd_dashboard,
    "trade": cmd_trade,
    "scan": cmd_scan,
}


def main():
    setup_logging()

    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        print(f"Available commands: {', '.join(COMMANDS.keys())}")
        sys.exit(1)

    COMMANDS[sys.argv[1]]()


if __name__ == "__main__":
    main()
