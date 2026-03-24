"""Dataclass row objects for the database."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Trade:
    id: Optional[int] = None
    symbol: str = ""
    side: str = "buy"
    quantity: float = 0.0
    entry_price: Optional[float] = None
    exit_price: Optional[float] = None
    entry_time: str = ""
    exit_time: Optional[str] = None
    exit_reason: Optional[str] = None
    final_score: Optional[float] = None
    reward_risk: Optional[float] = None
    pnl_dollars: Optional[float] = None
    pnl_pct: Optional[float] = None
    status: str = "open"
    alpaca_order_id: Optional[str] = None
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    created_at: str = ""


@dataclass
class AnalyzerScore:
    id: Optional[int] = None
    trade_id: int = 0
    analyzer_name: str = ""
    raw_score: float = 0.0
    weighted_score: float = 0.0
    recorded_at: str = ""


@dataclass
class Weight:
    id: Optional[int] = None
    analyzer_name: str = ""
    weight: float = 0.0
    reason: str = "initial"
    updated_at: str = ""


@dataclass
class SignalCacheEntry:
    id: Optional[int] = None
    cache_key: str = ""
    source_name: str = ""
    payload: str = ""
    fetched_at: str = ""
    expires_at: str = ""


@dataclass
class SourceHealth:
    id: Optional[int] = None
    source_name: str = ""
    last_success_at: Optional[str] = None
    last_failure_at: Optional[str] = None
    consecutive_failures: int = 0
    status: str = "healthy"
    last_check_at: str = ""
