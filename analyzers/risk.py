"""Risk analyzer: ATR volatility, dollar volume, gap risk. Higher = safer."""

import numpy as np
import pandas as pd
from ta.volatility import AverageTrueRange

from analyzers.base import AnalyzerBase, AnalyzerResult


class RiskAnalyzer(AnalyzerBase):
    name = "risk"

    def analyze(self, symbol: str, bars: pd.DataFrame) -> AnalyzerResult:
        if len(bars) < 14:
            return AnalyzerResult(score=0.0, details={"error": "insufficient data"})

        close = bars["close"]
        high = bars["high"]
        low = bars["low"]
        volume = bars["volume"]
        price = close.iloc[-1]

        # ATR as % of price — lower is safer
        atr_ind = AverageTrueRange(high, low, close, window=14)
        atr = atr_ind.average_true_range().iloc[-1]
        atr_pct = atr / price if price > 0 else 1.0
        # 2% ATR = safe (1.0), 8%+ ATR = risky (0.0)
        if atr_pct <= 0.02:
            atr_score = 1.0
        elif atr_pct >= 0.08:
            atr_score = 0.0
        else:
            atr_score = 1.0 - (atr_pct - 0.02) / 0.06

        # Dollar volume — higher is more liquid/safer
        avg_dollar_vol = (close * volume).rolling(20).mean().iloc[-1]
        # $1M+ = good, $5M+ = great
        if avg_dollar_vol >= 5_000_000:
            liquidity_score = 1.0
        elif avg_dollar_vol >= 1_000_000:
            liquidity_score = 0.6 + 0.4 * (avg_dollar_vol - 1_000_000) / 4_000_000
        elif avg_dollar_vol >= 500_000:
            liquidity_score = 0.3 + 0.3 * (avg_dollar_vol - 500_000) / 500_000
        else:
            liquidity_score = max(0.0, avg_dollar_vol / 500_000 * 0.3)

        # Gap risk — average overnight gap as % of close
        if len(bars) >= 2:
            opens = bars["open"].iloc[1:]
            prev_closes = close.iloc[:-1]
            gaps = np.abs((opens.values - prev_closes.values) / prev_closes.values)
            avg_gap = np.mean(gaps[-20:]) if len(gaps) >= 20 else np.mean(gaps)
            # < 1% gap = safe, > 4% = dangerous
            if avg_gap <= 0.01:
                gap_score = 1.0
            elif avg_gap >= 0.04:
                gap_score = 0.0
            else:
                gap_score = 1.0 - (avg_gap - 0.01) / 0.03
        else:
            gap_score = 0.5

        # Price stability — standard deviation of returns
        returns = close.pct_change().dropna().tail(20)
        if len(returns) > 5:
            volatility = returns.std()
            # < 2% daily std = stable, > 6% = volatile
            if volatility <= 0.02:
                stability_score = 1.0
            elif volatility >= 0.06:
                stability_score = 0.0
            else:
                stability_score = 1.0 - (volatility - 0.02) / 0.04
        else:
            stability_score = 0.5

        score = (
            atr_score * 0.30
            + liquidity_score * 0.30
            + gap_score * 0.20
            + stability_score * 0.20
        )

        return AnalyzerResult(
            score=score,
            details={
                "atr": round(atr, 4),
                "atr_pct": round(atr_pct, 4),
                "atr_score": round(atr_score, 3),
                "avg_dollar_volume": round(avg_dollar_vol, 0),
                "liquidity_score": round(liquidity_score, 3),
                "avg_gap_pct": round(float(avg_gap) if len(bars) >= 2 else 0, 4),
                "gap_score": round(gap_score, 3),
                "stability_score": round(stability_score, 3),
                "stop_price": round(price - 2 * atr, 2),
                "target_price": round(price + 3 * atr, 2),
                "reward_risk_ratio": round(3 * atr / (2 * atr), 2) if atr > 0 else 0,
            },
        )
