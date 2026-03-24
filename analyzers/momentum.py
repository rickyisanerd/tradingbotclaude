"""Momentum analyzer: RSI, MACD, EMA trend, volume surge."""

import numpy as np
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD, EMAIndicator

from analyzers.base import AnalyzerBase, AnalyzerResult


class MomentumAnalyzer(AnalyzerBase):
    name = "momentum"

    def analyze(self, symbol: str, bars: pd.DataFrame) -> AnalyzerResult:
        if len(bars) < 26:
            return AnalyzerResult(score=0.0, details={"error": "insufficient data"})

        close = bars["close"]
        volume = bars["volume"]

        # RSI (14) — normalize: 50-70 is ideal momentum zone -> 1.0
        rsi = RSIIndicator(close, window=14).rsi().iloc[-1]
        if 50 <= rsi <= 70:
            rsi_score = 1.0
        elif 40 <= rsi < 50:
            rsi_score = (rsi - 40) / 10
        elif 70 < rsi <= 80:
            rsi_score = (80 - rsi) / 10
        else:
            rsi_score = 0.0

        # MACD histogram — positive and rising is good
        macd = MACD(close)
        hist = macd.macd_diff()
        if len(hist) >= 2:
            curr_hist = hist.iloc[-1]
            prev_hist = hist.iloc[-2]
            macd_score = 1.0 if curr_hist > 0 and curr_hist > prev_hist else (
                0.6 if curr_hist > 0 else (0.3 if curr_hist > prev_hist else 0.0)
            )
        else:
            macd_score = 0.0

        # Price vs 20-EMA — above EMA is bullish
        ema20 = EMAIndicator(close, window=20).ema_indicator().iloc[-1]
        price = close.iloc[-1]
        ema_pct = (price - ema20) / ema20 if ema20 else 0
        if ema_pct > 0.03:
            ema_score = 1.0
        elif ema_pct > 0:
            ema_score = ema_pct / 0.03
        else:
            ema_score = max(0.0, 0.3 + ema_pct / 0.05)

        # Volume ratio — current vs 20-day avg
        avg_vol = volume.rolling(20).mean().iloc[-1]
        curr_vol = volume.iloc[-1]
        vol_ratio = curr_vol / avg_vol if avg_vol > 0 else 0
        vol_score = min(1.0, vol_ratio / 2.0)  # 2x average = 1.0

        # Weighted average
        score = (
            rsi_score * 0.25
            + macd_score * 0.30
            + ema_score * 0.25
            + vol_score * 0.20
        )

        return AnalyzerResult(
            score=score,
            details={
                "rsi": round(rsi, 2),
                "rsi_score": round(rsi_score, 3),
                "macd_hist": round(float(hist.iloc[-1]), 4),
                "macd_score": round(macd_score, 3),
                "ema20": round(ema20, 3),
                "ema_score": round(ema_score, 3),
                "vol_ratio": round(vol_ratio, 2),
                "vol_score": round(vol_score, 3),
            },
        )
