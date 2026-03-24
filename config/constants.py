"""Non-gate constants used across the project."""

# Retry
RETRY_BASE_SECONDS = 2
RETRY_MAX_SECONDS = 60
RETRY_MAX_ATTEMPTS = 3
RETRY_JITTER_FACTOR = 0.25

# Default analyzer weights (must sum to 1.0)
DEFAULT_WEIGHTS = {
    "momentum": 0.30,
    "reversion": 0.25,
    "risk": 0.25,
    "decision_support": 0.20,
}

ANALYZER_NAMES = list(DEFAULT_WEIGHTS.keys())

# Exit reasons
EXIT_STOP_HIT = "stop_hit"
EXIT_LOSS_CAP = "loss_cap"
EXIT_TARGET_HIT = "target_hit"
EXIT_TIME_STOP = "time_stop"
EXIT_MANUAL = "manual"
EXIT_DRAWDOWN = "drawdown_cap"
EXIT_ALGO = "algo_sell"
