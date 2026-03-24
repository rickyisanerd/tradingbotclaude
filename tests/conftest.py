"""Test fixtures: in-memory SQLite, sample data."""

import os
import pytest
import numpy as np
import pandas as pd

# Force test DB path before any imports
os.environ["RAILWAY_VOLUME_MOUNT_PATH"] = ""
os.environ["ALPACA_API_KEY"] = "test"
os.environ["ALPACA_SECRET_KEY"] = "test"


@pytest.fixture
def sample_bars():
    """Generate realistic daily bar data for testing analyzers."""
    np.random.seed(42)
    days = 60
    dates = pd.date_range(end=pd.Timestamp.now(), periods=days, freq="B")

    # Simulate a stock around $5 with realistic movement
    base_price = 5.0
    returns = np.random.normal(0.001, 0.02, days)
    prices = base_price * np.cumprod(1 + returns)

    df = pd.DataFrame(
        {
            "open": prices * (1 + np.random.uniform(-0.01, 0.01, days)),
            "high": prices * (1 + np.abs(np.random.normal(0, 0.015, days))),
            "low": prices * (1 - np.abs(np.random.normal(0, 0.015, days))),
            "close": prices,
            "volume": np.random.randint(500_000, 3_000_000, days).astype(float),
            "vwap": prices * (1 + np.random.uniform(-0.005, 0.005, days)),
        },
        index=dates,
    )
    return df


@pytest.fixture
def oversold_bars():
    """Generate bars showing an oversold condition for reversion testing."""
    np.random.seed(99)
    days = 60
    dates = pd.date_range(end=pd.Timestamp.now(), periods=days, freq="B")

    # Steady then sharp decline in last 5 days
    prices = np.full(days, 6.0)
    prices[-5:] = [5.5, 5.2, 4.9, 4.6, 4.3]  # 5 red days, big drop

    df = pd.DataFrame(
        {
            "open": prices + 0.05,
            "high": prices + 0.15,
            "low": prices - 0.10,
            "close": prices,
            "volume": np.random.randint(1_000_000, 5_000_000, days).astype(float),
            "vwap": prices - 0.02,
        },
        index=dates,
    )
    return df


@pytest.fixture
def test_db(tmp_path):
    """Create a test database in a temp directory."""
    db_path = str(tmp_path / "test.db")
    from db.engine import init_db
    init_db(db_path)
    return db_path
