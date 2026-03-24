"""Alpaca client wrapper using alpaca-py SDK."""

import logging
from functools import lru_cache

from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from config.settings import settings

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_trading_client() -> TradingClient:
    if not settings.alpaca_api_key or not settings.alpaca_secret_key:
        raise RuntimeError("ALPACA_API_KEY and ALPACA_SECRET_KEY must be set")
    paper = "paper" in settings.alpaca_base_url
    client = TradingClient(
        api_key=settings.alpaca_api_key,
        secret_key=settings.alpaca_secret_key,
        paper=paper,
    )
    log.info("Alpaca trading client initialized (paper=%s)", paper)
    return client


@lru_cache(maxsize=1)
def get_data_client() -> StockHistoricalDataClient:
    return StockHistoricalDataClient(
        api_key=settings.alpaca_api_key,
        secret_key=settings.alpaca_secret_key,
    )
