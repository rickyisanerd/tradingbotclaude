"""Candidate scanner: fetch bars and apply quick pre-filters."""

import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from broker.client import get_data_client
from broker.positions import get_open_symbols
from utils.retry import retry

log = logging.getLogger(__name__)


@retry(max_attempts=2)
def fetch_bars(symbols: list[str], days: int = 60) -> dict[str, pd.DataFrame]:
    """Fetch daily bars for a list of symbols. Returns {symbol: DataFrame}."""
    if not symbols:
        return {}

    data_client = get_data_client()
    end = datetime.utcnow()
    start = end - timedelta(days=days + 10)  # padding for weekends

    result = {}
    batch_size = 100

    for i in range(0, len(symbols), batch_size):
        batch = symbols[i : i + batch_size]
        try:
            request = StockBarsRequest(
                symbol_or_symbols=batch,
                timeframe=TimeFrame.Day,
                start=start,
                end=end,
            )
            bars_response = data_client.get_stock_bars(request)

            for sym in batch:
                sym_bars = bars_response.get(sym)
                if not sym_bars or len(sym_bars) < 20:
                    continue

                df = pd.DataFrame([
                    {
                        "open": b.open,
                        "high": b.high,
                        "low": b.low,
                        "close": b.close,
                        "volume": b.volume,
                        "vwap": b.vwap,
                        "timestamp": b.timestamp,
                    }
                    for b in sym_bars
                ])
                df.set_index("timestamp", inplace=True)
                df.sort_index(inplace=True)
                result[sym] = df

        except Exception as e:
            log.warning("Bar fetch batch %d-%d failed: %s", i, i + batch_size, e)
            continue

    log.info("Fetched bars for %d/%d symbols", len(result), len(symbols))
    return result


def pre_filter(symbols: list[str]) -> list[str]:
    """Quick pre-filter: skip symbols already held."""
    held = get_open_symbols()
    filtered = [s for s in symbols if s not in held]
    if len(symbols) != len(filtered):
        log.info("Pre-filter: removed %d held symbols", len(symbols) - len(filtered))
    return filtered
