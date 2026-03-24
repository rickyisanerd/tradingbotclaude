"""SQLite connection factory with WAL mode."""

import sqlite3
import logging
from pathlib import Path

from config.settings import settings

log = logging.getLogger(__name__)

_SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    path = db_path or settings.db_path
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str | None = None) -> None:
    """Create tables if they don't exist."""
    conn = get_connection(db_path)
    try:
        schema_sql = _SCHEMA_PATH.read_text()
        conn.executescript(schema_sql)
        conn.commit()
        log.info("Database initialized at %s", db_path or settings.db_path)
    finally:
        conn.close()
