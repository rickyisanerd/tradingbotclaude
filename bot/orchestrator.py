"""Top-level orchestrator: universe -> scan -> score -> gate -> execute."""

import logging
import math
from datetime import datetime

from bot.universe import build_universe
from bot.scanner import pre_filter, fetch_bars
from bot.scoring import score_all, ScoredCandidate
from bot.gate_check import check_gates
from bot.exit_manager import manage_exits
from bot.safety import check_system_health, safe_execute
from broker.orders import submit_bracket_buy
from broker.account import get_buying_power, get_account_info
from broker.positions import get_all_positions
from db.repository import insert_trade, insert_analyzer_scores, audit, get_open_trades
from db.models import Trade
from config.settings import settings

log = logging.getLogger(__name__)


def trade_once() -> dict:
    """Main trading loop: manage exits, scan universe, buy qualifying candidates.

    Returns a summary dict of actions taken.
    """
    summary = {
        "timestamp": datetime.utcnow().isoformat(),
        "exits": [],
        "scanned": 0,
        "scored": 0,
        "buys": [],
        "watches": [],
        "errors": [],
    }

    # Step 0: System health check
    health = check_system_health()
    summary["system_health"] = {
        "degraded": health.degraded,
        "can_trade": health.can_trade,
    }
    if not health.can_trade:
        summary["errors"].append(f"Trading blocked: {health.reasons}")
        log.warning("Trading blocked: %s", health.reasons)
        audit("trade_blocked", {"reasons": health.reasons})
        return summary

    # Step 1: Manage existing positions (exits)
    try:
        exits = manage_exits()
        summary["exits"] = exits
    except Exception as e:
        log.error("Exit management failed: %s", e)
        summary["errors"].append(f"exit_error: {e}")

    # Step 2: Check capacity for new positions
    open_trades = get_open_trades()
    open_count = len(open_trades)
    if open_count >= settings.max_open_positions:
        log.info("Max open positions (%d) reached, skipping scan", settings.max_open_positions)
        summary["errors"].append(f"max_positions_reached: {open_count}")
        return summary

    slots_available = settings.max_open_positions - open_count

    # Step 3: Build universe
    try:
        universe = build_universe()
        summary["scanned"] = len(universe)
    except Exception as e:
        log.error("Universe build failed: %s", e)
        summary["errors"].append(f"universe_error: {e}")
        audit("universe_failed", {"error": str(e)})
        return summary

    if not universe:
        log.info("Empty universe — no candidates to scan")
        return summary

    # Step 4: Pre-filter (remove held symbols)
    candidates = pre_filter(universe)

    # Step 5: Fetch bars
    try:
        bars_map = fetch_bars(candidates)
    except Exception as e:
        log.error("Bar fetch failed: %s", e)
        summary["errors"].append(f"bars_error: {e}")
        return summary

    # Step 6: Score all candidates
    scored = score_all(bars_map)
    summary["scored"] = len(scored)

    # Step 7: Gate check and execute buys
    buys_executed = 0
    for candidate in scored:
        if buys_executed >= slots_available:
            break

        gate_result = check_gates(candidate)

        if gate_result.passed:
            try:
                _execute_buy(candidate)
                summary["buys"].append({
                    "symbol": candidate.symbol,
                    "score": round(candidate.final_score, 3),
                })
                buys_executed += 1
            except Exception as e:
                log.error("Buy execution failed for %s: %s", candidate.symbol, e)
                summary["errors"].append(f"buy_error_{candidate.symbol}: {e}")
        else:
            summary["watches"].append({
                "symbol": candidate.symbol,
                "score": round(candidate.final_score, 3),
                "reasons": gate_result.reasons,
            })

    audit("trade_cycle_complete", summary)
    log.info(
        "Trade cycle: scanned=%d scored=%d buys=%d watches=%d exits=%d",
        summary["scanned"], summary["scored"], buys_executed,
        len(summary["watches"]), len(summary["exits"]),
    )
    return summary


def _execute_buy(candidate: ScoredCandidate) -> None:
    """Size the position, submit bracket order, and record in database."""
    # Position sizing: max_position_pct of equity, or remaining buying power
    try:
        account = get_account_info()
        equity = account["equity"]
        buying_power = account["buying_power"]
    except Exception:
        log.error("Cannot get account info for sizing")
        raise

    max_position_value = equity * settings.max_position_pct
    position_value = min(max_position_value, buying_power * 0.95)  # 5% buffer

    # Get price and targets from risk analyzer
    stop_price = candidate.risk_details.get("stop_price")
    target_price = candidate.risk_details.get("target_price")

    if not stop_price or not target_price:
        raise ValueError(f"No stop/target prices for {candidate.symbol}")

    # Use the last close as approximate entry price
    # The actual entry will be market price
    approx_price = (stop_price + target_price) / 2  # rough midpoint
    if approx_price <= 0:
        raise ValueError(f"Invalid price for {candidate.symbol}")

    qty = math.floor(position_value / approx_price)
    if qty < 1:
        raise ValueError(f"Cannot afford even 1 share of {candidate.symbol} at ~${approx_price:.2f}")

    # Submit bracket order
    order_id = submit_bracket_buy(
        symbol=candidate.symbol,
        qty=qty,
        take_profit_price=target_price,
        stop_loss_price=stop_price,
    )

    # Record trade in database
    trade = Trade(
        symbol=candidate.symbol,
        side="buy",
        quantity=qty,
        entry_price=approx_price,
        entry_time=datetime.utcnow().isoformat(),
        final_score=candidate.final_score,
        reward_risk=candidate.risk_details.get("reward_risk_ratio"),
        status="open",
        alpaca_order_id=order_id,
        stop_price=stop_price,
        target_price=target_price,
    )
    trade_id = insert_trade(trade)

    # Record analyzer scores
    scores_dict = {
        name: (candidate.raw_scores.get(name, 0), candidate.weighted_scores.get(name, 0))
        for name in candidate.raw_scores
    }
    insert_analyzer_scores(trade_id, scores_dict)

    log.info(
        "BUY executed: %s qty=%d stop=%.2f target=%.2f score=%.3f order=%s",
        candidate.symbol, qty, stop_price, target_price, candidate.final_score, order_id,
    )
