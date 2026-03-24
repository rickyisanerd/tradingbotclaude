"""Macro signals: VIX level, broad market conditions."""

import logging

import requests

from signals.base import SignalSource
from utils.retry import retry
from broker.client import get_data_client
from alpaca.data.requests import StockBarsRequest, StockLatestBarRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta

log = logging.getLogger(__name__)


class MacroSignal(SignalSource):
    name = "macro"
    ttl_hours = 2  # Market conditions change faster

    def cache_key(self, symbol: str | None = None) -> str:
        return "macro:global"

    @retry(max_attempts=2)
    def fetch(self, symbol: str | None = None) -> dict:
        """Fetch macro conditions: VIX proxy, SPY trend, sector health."""
        data_client = get_data_client()
        result = {"available": True}

        # VIX proxy: use VIXY ETF or SPY volatility as stand-in
        try:
            end = datetime.utcnow()
            start = end - timedelta(days=30)
            spy_req = StockBarsRequest(
                symbol_or_symbols=["SPY"],
                timeframe=TimeFrame.Day,
                start=start,
                end=end,
            )
            spy_bars = data_client.get_stock_bars(spy_req).get("SPY", [])

            if spy_bars and len(spy_bars) >= 5:
                closes = [b.close for b in spy_bars]
                # Compute realized volatility as VIX proxy
                import numpy as np
                returns = np.diff(np.log(closes))
                realized_vol = np.std(returns[-20:]) * np.sqrt(252) * 100
                result["vix"] = round(float(realized_vol), 1)

                # SPY trend: last close vs 20-day SMA
                sma20 = np.mean(closes[-20:])
                result["spy_trend"] = "bullish" if closes[-1] > sma20 else "bearish"
                result["spy_last"] = round(float(closes[-1]), 2)
            else:
                result["vix"] = 20  # neutral default
                result["spy_trend"] = "neutral"

        except Exception as e:
            log.warning("Macro SPY fetch failed: %s", e)
            result["vix"] = 20
            result["spy_trend"] = "neutral"

        return result
