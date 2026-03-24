"""Decision-support analyzer: external signals + technical context."""

import logging

import pandas as pd
from ta.trend import EMAIndicator, SMAIndicator

from analyzers.base import AnalyzerBase, AnalyzerResult
from db.repository import get_cached_signal

log = logging.getLogger(__name__)


class DecisionSupportAnalyzer(AnalyzerBase):
    name = "decision_support"

    def analyze(self, symbol: str, bars: pd.DataFrame) -> AnalyzerResult:
        if len(bars) < 50:
            return AnalyzerResult(score=0.0, details={"error": "insufficient data"})

        close = bars["close"]
        price = close.iloc[-1]

        # ── Technical context ──────────────────────────────────────

        # Trend alignment: price > 50-SMA > 200-SMA (if enough data)
        sma50 = SMAIndicator(close, window=50).sma_indicator().iloc[-1]
        trend_score = 0.5
        if len(bars) >= 200:
            sma200 = SMAIndicator(close, window=200).sma_indicator().iloc[-1]
            if price > sma50 > sma200:
                trend_score = 1.0
            elif price > sma50:
                trend_score = 0.7
            elif price > sma200:
                trend_score = 0.4
            else:
                trend_score = 0.1
        else:
            trend_score = 0.7 if price > sma50 else 0.3

        # Volume trend: 5-day avg volume vs 20-day avg
        volume = bars["volume"]
        vol5 = volume.tail(5).mean()
        vol20 = volume.tail(20).mean()
        vol_trend = vol5 / vol20 if vol20 > 0 else 1.0
        vol_trend_score = min(1.0, vol_trend / 1.5)

        # ── External signals (cached, graceful degradation) ──────

        # Congressional trades
        congress_score = 0.5  # neutral default
        congress_data = get_cached_signal(f"congressional:{symbol}")
        if congress_data and congress_data["fresh"]:
            payload = congress_data["payload"]
            buys = payload.get("recent_buys", 0)
            sells = payload.get("recent_sells", 0)
            if buys > sells:
                congress_score = min(1.0, 0.5 + buys * 0.1)
            elif sells > buys:
                congress_score = max(0.0, 0.5 - sells * 0.1)

        # SEC insider filings
        insider_score = 0.5
        sec_data = get_cached_signal(f"sec_insider:{symbol}")
        if sec_data and sec_data["fresh"]:
            payload = sec_data["payload"]
            net_buys = payload.get("net_insider_buys", 0)
            if net_buys > 0:
                insider_score = min(1.0, 0.5 + net_buys * 0.15)
            elif net_buys < 0:
                insider_score = max(0.0, 0.5 + net_buys * 0.15)

        # Earnings proximity — avoid stocks with earnings within 3 days
        earnings_score = 0.7  # slightly positive default
        earnings_data = get_cached_signal(f"earnings:{symbol}")
        if earnings_data and earnings_data["fresh"]:
            days_to_earnings = earnings_data["payload"].get("days_until", 999)
            if days_to_earnings <= 3:
                earnings_score = 0.1  # avoid pre-earnings
            elif days_to_earnings <= 7:
                earnings_score = 0.4
            else:
                earnings_score = 0.8

        # Macro conditions
        macro_score = 0.5
        macro_data = get_cached_signal("macro:global")
        if macro_data and macro_data["fresh"]:
            payload = macro_data["payload"]
            vix = payload.get("vix", 20)
            if vix < 15:
                macro_score = 0.9
            elif vix < 20:
                macro_score = 0.7
            elif vix < 30:
                macro_score = 0.4
            else:
                macro_score = 0.1

        # Weighted combination
        score = (
            trend_score * 0.25
            + vol_trend_score * 0.10
            + congress_score * 0.15
            + insider_score * 0.15
            + earnings_score * 0.20
            + macro_score * 0.15
        )

        return AnalyzerResult(
            score=score,
            details={
                "sma50": round(sma50, 3),
                "trend_score": round(trend_score, 3),
                "vol_trend": round(vol_trend, 2),
                "vol_trend_score": round(vol_trend_score, 3),
                "congress_score": round(congress_score, 3),
                "insider_score": round(insider_score, 3),
                "earnings_score": round(earnings_score, 3),
                "macro_score": round(macro_score, 3),
                "signals_used": {
                    "congressional": congress_data is not None and congress_data.get("fresh", False),
                    "sec_insider": sec_data is not None and sec_data.get("fresh", False),
                    "earnings": earnings_data is not None and earnings_data.get("fresh", False),
                    "macro": macro_data is not None and macro_data.get("fresh", False),
                },
            },
        )
