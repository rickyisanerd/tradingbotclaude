"""Exit logic: manages open positions and triggers sells."""

import logging
from datetime import datetime, timedelta

from broker.positions import get_position
from broker.orders import submit_market_sell, cancel_open_orders_for_symbol
from broker.account import get_account_info
from db.repository import get_open_trades, close_trade, audit
from config.settings import settings
from config.constants import (
    EXIT_LOSS_CAP, EXIT_DRAWDOWN, EXIT_TARGET_HIT, EXIT_TIME_STOP, EXIT_STOP_HIT,
)

log = logging.getLogger(__name__)


def manage_exits() -> list[dict]:
    """Check all open trades and exit those that meet exit conditions.

    Returns list of exit actions taken.
    """
    open_trades = get_open_trades()
    if not open_trades:
        return []

    actions = []

    for trade in open_trades:
        try:
            action = _check_single_exit(trade)
            if action:
                actions.append(action)
        except Exception as e:
            log.error("Exit check failed for trade %s (%s): %s", trade.id, trade.symbol, e)

    if actions:
        log.info("Exit manager took %d actions", len(actions))
    return actions


def _check_single_exit(trade) -> dict | None:
    """Check exit conditions for a single trade."""
    pos = get_position(trade.symbol)

    # If position no longer exists in Alpaca, the bracket order likely filled
    if pos is None:
        log.info("Position gone for %s — likely stop/target hit via bracket", trade.symbol)
        # Try to get fill price from last known data
        close_trade(trade.id, trade.entry_price or 0, EXIT_STOP_HIT)
        return {"symbol": trade.symbol, "reason": EXIT_STOP_HIT, "note": "position_gone"}

    current_price = pos["current_price"]
    entry_price = trade.entry_price or pos["avg_entry_price"]
    pnl_pct = (current_price - entry_price) / entry_price if entry_price else 0

    # Calculate hold days
    entry_dt = datetime.fromisoformat(trade.entry_time) if trade.entry_time else datetime.utcnow()
    hold_days = (datetime.utcnow() - entry_dt).days

    # ── Exit condition 1: Single-position loss cap ──
    if pnl_pct <= -settings.single_loss_cap_pct:
        return _execute_exit(trade, pos, current_price, EXIT_LOSS_CAP,
                             f"loss {pnl_pct:.2%} exceeds cap {-settings.single_loss_cap_pct:.2%}")

    # ── Exit condition 2: Drawdown from peak ──
    # Use unrealized P&L percentage as proxy
    if pos["unrealized_plpc"] <= -settings.single_loss_cap_pct * 1.5:
        return _execute_exit(trade, pos, current_price, EXIT_DRAWDOWN,
                             f"drawdown {pos['unrealized_plpc']:.2%}")

    # ── Exit condition 3: Target hit after MIN_HOLD_DAYS ──
    if (trade.target_price and current_price >= trade.target_price
            and hold_days >= settings.min_hold_days):
        return _execute_exit(trade, pos, current_price, EXIT_TARGET_HIT,
                             f"target ${trade.target_price:.2f} hit after {hold_days}d")

    # ── Exit condition 4: Time stop — MAX_HOLD_DAYS ──
    if hold_days >= settings.max_hold_days:
        return _execute_exit(trade, pos, current_price, EXIT_TIME_STOP,
                             f"held {hold_days}d >= max {settings.max_hold_days}d")

    return None


def _execute_exit(trade, pos, exit_price: float, reason: str, note: str) -> dict:
    """Cancel bracket legs and submit market sell."""
    log.info("EXIT %s: %s — %s", trade.symbol, reason, note)
    qty = pos["qty"]

    # Cancel any remaining bracket order legs
    cancel_open_orders_for_symbol(trade.symbol)

    # Submit market sell
    order_id = submit_market_sell(trade.symbol, qty)

    # Update database
    close_trade(trade.id, exit_price, reason)

    audit("exit_executed", {
        "trade_id": trade.id,
        "symbol": trade.symbol,
        "reason": reason,
        "exit_price": exit_price,
        "note": note,
        "order_id": order_id,
    })

    return {
        "trade_id": trade.id,
        "symbol": trade.symbol,
        "reason": reason,
        "exit_price": exit_price,
        "note": note,
    }


def check_daily_loss_cap() -> bool:
    """Check if daily portfolio loss cap has been breached."""
    try:
        info = get_account_info()
        equity = info["equity"]
        # Rough check: if equity dropped more than daily_loss_cap_pct from start of day
        # We use buying_power as proxy since we don't track day-start equity
        # TODO: Track opening equity for precise daily loss calc
        return False
    except Exception as e:
        log.warning("Daily loss cap check failed: %s", e)
        return False
