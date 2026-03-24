"""Mean-reversion analyzer: Bollinger %B, RSI oversold, VWAP distance, red days."""

import numpy as np
import pandas as pd
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands

from analyzers.base import AnalyzerBase, AnalyzerResult


class ReversionAnalyzer(AnalyzerBase):
    name = "reversion"

    def analyze(self, symbol: str, bars: pd.DataFrame) -> AnalyzerResult:
        if len(bars) < 20:
            return AnalyzerResult(score=0.0, details={"error": "insufficient data"})

        close = bars["close"]

        # Bollinger %B — lower means more stretched to downside (better for reversion)
        bb = BollingerBands(close, window=20, window_dev=2)
        pct_b = bb.bollinger_pband().iloc[-1]
        # %B < 0 means below lower band = strong reversion signal
        if pct_b < 0:
            bb_score = 1.0
        elif pct_b < 0.2:
            bb_score = 0.8 + (0.2 - pct_b)
        elif pct_b < 0.5:
            bb_score = (0.5 - pct_b) / 0.3 * 0.6
        else:
            bb_score = 0.0

        # RSI oversold — lower RSI is stronger reversion signal
        rsi = RSIIndicator(close, window=14).rsi().iloc[-1]
        if rsi < 30:
            rsi_score = 1.0
        elif rsi < 40:
            rsi_score = (40 - rsi) / 10
        elif rsi < 50:
            rsi_score = (50 - rsi) / 20
        else:
            rsi_score = 0.0

        # Distance below VWAP (if available)
        vwap_score = 0.5  # neutral default
        if "vwap" in bars.columns:
            vwap = bars["vwap"].iloc[-1]
            if vwap and vwap > 0:
                dist = (close.iloc[-1] - vwap) / vwap
                if dist < -0.03:
                    vwap_score = 1.0
                elif dist < 0:
                    vwap_score = abs(dist) / 0.03
                else:
                    vwap_score = 0.0

        # Consecutive red days — more red days = more stretched
        red_days = 0
        for i in range(len(close) - 1, max(0, len(close) - 8), -1):
            if close.iloc[i] < close.iloc[i - 1]:
                red_days += 1
            else:
                break
        red_score = min(1.0, red_days / 4.0)  # 4+ red days = 1.0

        score = (
            bb_score * 0.30
            + rsi_score * 0.30
            + vwap_score * 0.20
            + red_score * 0.20
        )

        return AnalyzerResult(
            score=score,
            details={
                "bb_pct_b": round(float(pct_b), 3),
                "bb_score": round(bb_score, 3),
                "rsi": round(rsi, 2),
                "rsi_score": round(rsi_score, 3),
                "vwap_score": round(vwap_score, 3),
                "red_days": red_days,
                "red_score": round(red_score, 3),
            },
        )
