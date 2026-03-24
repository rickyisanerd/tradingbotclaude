"""Central configuration loaded from environment variables."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _env_float(key: str, default: float = 0.0) -> float:
    return float(_env(key, str(default)))


def _env_int(key: str, default: int = 0) -> int:
    return int(_env(key, str(default)))


@dataclass(frozen=True)
class Settings:
    # Alpaca
    alpaca_api_key: str = field(default_factory=lambda: _env("ALPACA_API_KEY"))
    alpaca_secret_key: str = field(default_factory=lambda: _env("ALPACA_SECRET_KEY"))
    alpaca_base_url: str = field(
        default_factory=lambda: _env("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
    )

    # Database path resolution: Railway volume > local ./data
    db_path: str = field(default_factory=lambda: _resolve_db_path())

    # Gates
    min_final_score: float = field(default_factory=lambda: _env_float("MIN_FINAL_SCORE", 0.65))
    min_reward_risk: float = field(default_factory=lambda: _env_float("MIN_REWARD_RISK", 2.0))
    min_dollar_volume: float = field(default_factory=lambda: _env_float("MIN_DOLLAR_VOLUME", 500_000))
    min_risk_score: float = field(default_factory=lambda: _env_float("MIN_RISK_SCORE", 0.4))
    min_ds_score: float = field(default_factory=lambda: _env_float("MIN_DS_SCORE", 0.3))

    # Hold limits
    min_hold_days: int = field(default_factory=lambda: _env_int("MIN_HOLD_DAYS", 1))
    max_hold_days: int = field(default_factory=lambda: _env_int("MAX_HOLD_DAYS", 5))

    # Learning
    learning_rate: float = field(default_factory=lambda: _env_float("LEARNING_RATE", 0.05))
    min_weight: float = field(default_factory=lambda: _env_float("MIN_WEIGHT", 0.05))
    max_return_contribution: float = field(
        default_factory=lambda: _env_float("MAX_RETURN_CONTRIBUTION", 0.10)
    )

    # Safety
    max_consecutive_failures: int = field(
        default_factory=lambda: _env_int("MAX_CONSECUTIVE_FAILURES", 3)
    )
    signal_soft_ttl_hours: int = field(
        default_factory=lambda: _env_int("SIGNAL_SOFT_TTL_HOURS", 4)
    )
    signal_hard_ttl_hours: int = field(
        default_factory=lambda: _env_int("SIGNAL_HARD_TTL_HOURS", 24)
    )
    pdt_equity_threshold: float = field(
        default_factory=lambda: _env_float("PDT_EQUITY_THRESHOLD", 25_000)
    )

    # Universe filters
    universe_min_price: float = field(default_factory=lambda: _env_float("UNIVERSE_MIN_PRICE", 2.0))
    universe_max_price: float = field(default_factory=lambda: _env_float("UNIVERSE_MAX_PRICE", 10.0))
    universe_min_avg_volume: int = field(
        default_factory=lambda: _env_int("UNIVERSE_MIN_AVG_VOLUME", 500_000)
    )

    # External signal keys
    quiver_api_key: str = field(default_factory=lambda: _env("QUIVER_API_KEY"))
    sec_edgar_user_agent: str = field(
        default_factory=lambda: _env("SEC_EDGAR_USER_AGENT", "tradebot-claude bot@example.com")
    )

    # Dashboard
    flask_secret_key: str = field(
        default_factory=lambda: _env("FLASK_SECRET_KEY", "dev-secret-change-me")
    )

    # Position sizing
    max_position_pct: float = field(default_factory=lambda: _env_float("MAX_POSITION_PCT", 0.10))
    max_open_positions: int = field(default_factory=lambda: _env_int("MAX_OPEN_POSITIONS", 5))

    # Loss caps
    single_loss_cap_pct: float = field(
        default_factory=lambda: _env_float("SINGLE_LOSS_CAP_PCT", 0.05)
    )
    daily_loss_cap_pct: float = field(
        default_factory=lambda: _env_float("DAILY_LOSS_CAP_PCT", 0.03)
    )


def _resolve_db_path() -> str:
    railway_vol = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH")
    if railway_vol:
        db_dir = Path(railway_vol)
    else:
        # Avoid OneDrive for SQLite on Windows
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data and "OneDrive" in str(Path.cwd()):
            db_dir = Path(local_app_data) / "tradebot-claude" / "data"
        else:
            db_dir = Path(__file__).resolve().parent.parent / "data"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_name = os.environ.get("DB_NAME", "tradebot.db")
    return str(db_dir / db_name)


# Singleton
settings = Settings()
