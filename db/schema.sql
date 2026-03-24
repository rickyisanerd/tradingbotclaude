-- Core schema for tradebot-claude

CREATE TABLE IF NOT EXISTS trades (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol          TEXT NOT NULL,
    side            TEXT NOT NULL DEFAULT 'buy',
    quantity         REAL NOT NULL,
    entry_price     REAL,
    exit_price      REAL,
    entry_time      TEXT NOT NULL,
    exit_time       TEXT,
    exit_reason     TEXT,
    final_score     REAL,
    reward_risk     REAL,
    pnl_dollars     REAL,
    pnl_pct         REAL,
    status          TEXT NOT NULL DEFAULT 'open',
    alpaca_order_id TEXT,
    stop_price      REAL,
    target_price    REAL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS analyzer_scores (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id      INTEGER NOT NULL REFERENCES trades(id),
    analyzer_name TEXT NOT NULL,
    raw_score     REAL NOT NULL,
    weighted_score REAL NOT NULL,
    recorded_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS weights (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    analyzer_name TEXT NOT NULL,
    weight        REAL NOT NULL,
    reason        TEXT NOT NULL DEFAULT 'initial',
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS signal_cache (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    cache_key   TEXT NOT NULL UNIQUE,
    source_name TEXT NOT NULL,
    payload     TEXT NOT NULL,
    fetched_at  TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_health (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name           TEXT NOT NULL UNIQUE,
    last_success_at       TEXT,
    last_failure_at       TEXT,
    consecutive_failures  INTEGER NOT NULL DEFAULT 0,
    status                TEXT NOT NULL DEFAULT 'healthy',
    last_check_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    details    TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
CREATE INDEX IF NOT EXISTS idx_analyzer_scores_trade ON analyzer_scores(trade_id);
CREATE INDEX IF NOT EXISTS idx_signal_cache_key ON signal_cache(cache_key);
CREATE INDEX IF NOT EXISTS idx_audit_log_type ON audit_log(event_type);
