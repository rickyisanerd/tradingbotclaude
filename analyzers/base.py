"""Base class for all analyzers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import pandas as pd


@dataclass
class AnalyzerResult:
    score: float  # 0.0 to 1.0
    details: dict = field(default_factory=dict)

    def __post_init__(self):
        self.score = max(0.0, min(1.0, self.score))


class AnalyzerBase(ABC):
    name: str = "base"

    @abstractmethod
    def analyze(self, symbol: str, bars: pd.DataFrame) -> AnalyzerResult:
        """Analyze a symbol given its daily bar data.

        Args:
            symbol: Ticker symbol
            bars: DataFrame with columns: open, high, low, close, volume, vwap
                  Indexed by date, sorted ascending.

        Returns:
            AnalyzerResult with score 0-1 and detail breakdown.
        """
        ...
