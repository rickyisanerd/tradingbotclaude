"""All database read/write operations."""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from db.engine import get_connection
from db.models import Trade, AnalyzerScore, Weight
from config.constants import DEFAULT_WEIGHTS, ANALYZER_NAMES

log = logging.getLogger(__name__)


# ── Trades ──────────────────────────────────────────────────────────────

def insert_trade(trade: Trade) -> int:
    conn = get_connection()
    try:
        cur = conn.execute(
            """INSERT INTO trades
               (symbol, side, quantity, entry_price, entry_time, final_score,
                reward_risk, status, alpaca_order_id, stop_price, target_price)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                trade.symbol, trade.side, trade.quantity, trade.entry_price,
                trade.entry_time, trade.final_score, trade.reward_risk,
                trade.status, trade.alpaca_order_id, trade.stop_price,
                trade.target_price,
            ),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def close_trade(trade_id: int, exit_price: float, exit_reason: str) -> None:
    conn = get_connection()
    try:
        row = conn.execute("SELECT entry_price, quantity FROM trades WHERE id = ?", (trade_id,)).fetchone()
        if not row:
            return
        entry_price = row["entry_price"]
        quantity = row["quantity"]
        pnl_dollars = (exit_price - entry_price) * quantity if entry_price else 0
        pnl_pct = (exit_price - entry_price) / entry_price if entry_price else 0
        conn.execute(
            """UPDATE trades
               SET exit_price = ?, exit_time = datetime('now'), exit_reason = ?,
                   pnl_dollars = ?, pnl_pct = ?, status = 'closed'
               WHERE id = ?""",
            (exit_price, exit_reason, pnl_dollars, pnl_pct, trade_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_open_trades() -> list[Trade]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM trades WHERE status = 'open'").fetchall()
        return [Trade(**dict(r)) for r in rows]
    finally:
        conn.close()


def get_recently_closed_trades(hours: int = 24) -> list[Trade]:
    conn = get_connection()
    try:
        cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
        rows = conn.execute(
            "SELECT * FROM trades WHERE status = 'closed' AND exit_time >= ?",
            (cutoff,),
        ).fetchall()
        return [Trade(**dict(r)) for r in rows]
    finally:
        conn.close()


def get_all_trades(limit: int = 100) -> list[Trade]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM trades ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [Trade(**dict(r)) for r in rows]
    finally:
        conn.close()


def get_trade_by_symbol(symbol: str) -> Optional[Trade]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM trades WHERE symbol = ? AND status = 'open' LIMIT 1",
            (symbol,),
        ).fetchone()
        return Trade(**dict(row)) if row else None
    finally:
        conn.close()


# ── Analyzer Scores ─────────────────────────────────────────────────────

def insert_analyzer_scores(trade_id: int, scores: dict[str, tuple[float, float]]) -> None:
    """scores: {analyzer_name: (raw_score, weighted_score)}"""
    conn = get_connection()
    try:
        for name, (raw, weighted) in scores.items():
            conn.execute(
                """INSERT INTO analyzer_scores (trade_id, analyzer_name, raw_score, weighted_score)
                   VALUES (?, ?, ?, ?)""",
                (trade_id, name, raw, weighted),
            )
        conn.commit()
    finally:
        conn.close()


def get_scores_for_trade(trade_id: int) -> dict[str, float]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT analyzer_name, raw_score FROM analyzer_scores WHERE trade_id = ?",
            (trade_id,),
        ).fetchall()
        return {r["analyzer_name"]: r["raw_score"] for r in rows}
    finally:
        conn.close()


# ── Weights ─────────────────────────────────────────────────────────────

def get_current_weights() -> dict[str, float]:
    conn = get_connection()
    try:
        weights = {}
        for name in ANALYZER_NAMES:
            row = conn.execute(
                """SELECT weight FROM weights
                   WHERE analyzer_name = ?
                   ORDER BY updated_at DESC LIMIT 1""",
                (name,),
            ).fetchone()
            weights[name] = row["weight"] if row else DEFAULT_WEIGHTS.get(name, 0.25)
        return weights
    finally:
        conn.close()


def insert_weights(weights: dict[str, float], reason: str) -> None:
    conn = get_connection()
    try:
        for name, w in weights.items():
            conn.execute(
                "INSERT INTO weights (analyzer_name, weight, reason) VALUES (?, ?, ?)",
                (name, w, reason),
            )
        conn.commit()
    finally:
        conn.close()


def get_weight_history(limit: int = 50) -> list[Weight]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM weights ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [Weight(**dict(r)) for r in rows]
    finally:
        conn.close()


def initialize_default_weights() -> None:
    """Seed default weights if none exist."""
    current = get_current_weights()
    conn = get_connection()
    try:
        row = conn.execute("SELECT COUNT(*) as cnt FROM weights").fetchone()
        if row["cnt"] == 0:
            insert_weights(DEFAULT_WEIGHTS, "initial")
            log.info("Seeded default analyzer weights: %s", DEFAULT_WEIGHTS)
    finally:
        conn.close()


# ── Signal Cache ────────────────────────────────────────────────────────

def get_cached_signal(cache_key: str) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute(
            """SELECT payload, expires_at FROM signal_cache
               WHERE cache_key = ? ORDER BY fetched_at DESC LIMIT 1""",
            (cache_key,),
        ).fetchone()
        if not row:
            return None
        expires = datetime.fromisoformat(row["expires_at"])
        is_fresh = datetime.utcnow() < expires
        return {
            "payload": json.loads(row["payload"]),
            "fresh": is_fresh,
        }
    finally:
        conn.close()


def upsert_signal_cache(cache_key: str, source_name: str, payload: dict, ttl_hours: int) -> None:
    conn = get_connection()
    try:
        expires = (datetime.utcnow() + timedelta(hours=ttl_hours)).isoformat()
        conn.execute(
            """INSERT INTO signal_cache (cache_key, source_name, payload, expires_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(cache_key)
               DO UPDATE SET payload = excluded.payload,
                             fetched_at = datetime('now'),
                             expires_at = excluded.expires_at""",
            (cache_key, source_name, json.dumps(payload), expires),
        )
        conn.commit()
    finally:
        conn.close()


# ── Source Health ───────────────────────────────────────────────────────

def update_source_health(source_name: str, success: bool) -> None:
    conn = get_connection()
    try:
        existing = conn.execute(
            "SELECT * FROM source_health WHERE source_name = ?", (source_name,)
        ).fetchone()
        now = datetime.utcnow().isoformat()

        if success:
            if existing:
                conn.execute(
                    """UPDATE source_health
                       SET last_success_at = ?, consecutive_failures = 0,
                           status = 'healthy', last_check_at = ?
                       WHERE source_name = ?""",
                    (now, now, source_name),
                )
            else:
                conn.execute(
                    """INSERT INTO source_health
                       (source_name, last_success_at, consecutive_failures, status, last_check_at)
                       VALUES (?, ?, 0, 'healthy', ?)""",
                    (source_name, now, now),
                )
        else:
            if existing:
                fails = existing["consecutive_failures"] + 1
                status = "degraded" if fails >= 2 else "healthy"
                if fails >= 5:
                    status = "down"
                conn.execute(
                    """UPDATE source_health
                       SET last_failure_at = ?, consecutive_failures = ?,
                           status = ?, last_check_at = ?
                       WHERE source_name = ?""",
                    (now, fails, status, now, source_name),
                )
            else:
                conn.execute(
                    """INSERT INTO source_health
                       (source_name, last_failure_at, consecutive_failures, status, last_check_at)
                       VALUES (?, ?, 1, 'healthy', ?)""",
                    (source_name, now, now),
                )
        conn.commit()
    finally:
        conn.close()


def get_all_source_health() -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM source_health").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ── Audit Log ──────────────────────────────────────────────────────────

def audit(event_type: str, details: dict | str | None = None) -> None:
    conn = get_connection()
    try:
        det = json.dumps(details) if isinstance(details, dict) else details
        conn.execute(
            "INSERT INTO audit_log (event_type, details) VALUES (?, ?)",
            (event_type, det),
        )
        conn.commit()
    finally:
        conn.close()


def get_audit_log(limit: int = 100) -> list[dict]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
