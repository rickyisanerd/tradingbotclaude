"""Weighted scoring pipeline: runs all analyzers, computes final score."""

import logging
from dataclasses import dataclass, field

import pandas as pd

from analyzers.momentum import MomentumAnalyzer
from analyzers.reversion import ReversionAnalyzer
from analyzers.risk import RiskAnalyzer
from analyzers.decision_support import DecisionSupportAnalyzer
from analyzers.base import AnalyzerResult
from db.repository import get_current_weights

log = logging.getLogger(__name__)

# Instantiate analyzers once
ANALYZERS = {
    "momentum": MomentumAnalyzer(),
    "reversion": ReversionAnalyzer(),
    "risk": RiskAnalyzer(),
    "decision_support": DecisionSupportAnalyzer(),
}


@dataclass
class ScoredCandidate:
    symbol: str
    final_score: float = 0.0
    raw_scores: dict = field(default_factory=dict)       # {name: raw_score}
    weighted_scores: dict = field(default_factory=dict)   # {name: weighted_score}
    details: dict = field(default_factory=dict)           # {name: detail_dict}
    risk_details: dict = field(default_factory=dict)      # stop/target from risk analyzer
    recommendation: str = "watch"                         # 'buy' or 'watch'


def score_candidate(symbol: str, bars: pd.DataFrame) -> ScoredCandidate:
    """Run all four analyzers on a symbol and compute the weighted final score."""
    weights = get_current_weights()

    candidate = ScoredCandidate(symbol=symbol)

    for name, analyzer in ANALYZERS.items():
        try:
            result: AnalyzerResult = analyzer.analyze(symbol, bars)
            w = weights.get(name, 0.25)
            candidate.raw_scores[name] = result.score
            candidate.weighted_scores[name] = result.score * w
            candidate.details[name] = result.details

            if name == "risk":
                candidate.risk_details = result.details

        except Exception as e:
            log.error("Analyzer %s failed for %s: %s", name, symbol, e)
            candidate.raw_scores[name] = 0.0
            candidate.weighted_scores[name] = 0.0
            candidate.details[name] = {"error": str(e)}

    candidate.final_score = sum(candidate.weighted_scores.values())
    return candidate


def score_all(symbols_bars: dict[str, pd.DataFrame]) -> list[ScoredCandidate]:
    """Score all candidates and return sorted by final_score descending."""
    candidates = []
    for symbol, bars in symbols_bars.items():
        try:
            c = score_candidate(symbol, bars)
            candidates.append(c)
        except Exception as e:
            log.error("Scoring failed for %s: %s", symbol, e)

    candidates.sort(key=lambda c: c.final_score, reverse=True)
    log.info("Scored %d candidates, top: %s (%.3f)",
             len(candidates),
             candidates[0].symbol if candidates else "none",
             candidates[0].final_score if candidates else 0)
    return candidates
