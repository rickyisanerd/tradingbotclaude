"""Symbol universe builder from Alpaca active tradable US equities."""

import logging
from datetime import datetime, timedelta

import pandas as pd
from alpaca.trading.requests import GetAssetsRequest
from alpaca.trading.enums import AssetClass, AssetStatus
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from broker.client import get_trading_client, get_data_client
from config.settings import settings
from utils.retry import retry
from db.repository import audit

log = logging.getLogger(__name__)


@retry(max_attempts=2)
def get_tradable_assets() -> list[dict]:
    """Fetch all active, tradable US equity assets from Alpaca."""
    client = get_trading_client()
    request = GetAssetsRequest(
        asset_class=AssetClass.US_EQUITY,
        status=AssetStatus.ACTIVE,
    )
    assets = client.get_all_assets(request)
    tradable = [
        {"symbol": a.symbol, "name": a.name, "exchange": str(a.exchange)}
        for a in assets
        if a.tradable and not a.symbol.isdigit() and "." not in a.symbol
    ]
    log.info("Fetched %d tradable US equities from Alpaca", len(tradable))
    return tradable


def build_universe() -> list[str]:
    """Build a filtered symbol universe: $2-$10 price range, meets min volume.

    Steps:
    1. Get all tradable assets from Alpaca
    2. Fetch recent bars in batches to check price and volume
    3. Filter for price range and minimum average volume
    """
    assets = get_tradable_assets()
    symbols = [a["symbol"] for a in assets]
    log.info("Starting universe filter on %d symbols", len(symbols))

    # Batch fetch latest bars to filter on price/volume
    data_client = get_data_client()
    end = datetime.utcnow()
    start = end - timedelta(days=10)

    qualified = []
    batch_size = 200

    for i in range(0, len(symbols), batch_size):
        batch = symbols[i : i + batch_size]
        try:
            request = StockBarsRequest(
                symbol_or_symbols=batch,
                timeframe=TimeFrame.Day,
                start=start,
                end=end,
                limit=5,
            )
            bars_response = data_client.get_stock_bars(request)

            for sym in batch:
                sym_bars = bars_response.get(sym)
                if not sym_bars or len(sym_bars) < 2:
                    continue

                last_bar = sym_bars[-1]
                price = last_bar.close

                # Price filter
                if not (settings.universe_min_price <= price <= settings.universe_max_price):
                    continue

                # Volume filter — average over available bars
                avg_vol = sum(b.volume for b in sym_bars) / len(sym_bars)
                if avg_vol < settings.universe_min_avg_volume:
                    continue

                qualified.append(sym)

        except Exception as e:
            log.warning("Universe batch %d-%d failed: %s", i, i + batch_size, e)
            continue

    log.info(
        "Universe built: %d symbols pass price ($%.0f-$%.0f) and volume (%d) filters",
        len(qualified),
        settings.universe_min_price,
        settings.universe_max_price,
        settings.universe_min_avg_volume,
    )
    audit("universe_built", {"count": len(qualified), "sample": qualified[:10]})
    return qualified
