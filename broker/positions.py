"""Position manager: current holdings, P&L."""

import logging

from broker.client import get_trading_client
from utils.retry import retry

log = logging.getLogger(__name__)


@retry(max_attempts=3)
def get_all_positions() -> list[dict]:
    client = get_trading_client()
    positions = client.get_all_positions()
    return [
        {
            "symbol": p.symbol,
            "qty": float(p.qty),
            "avg_entry_price": float(p.avg_entry_price),
            "current_price": float(p.current_price),
            "market_value": float(p.market_value),
            "unrealized_pl": float(p.unrealized_pl),
            "unrealized_plpc": float(p.unrealized_plpc),
            "side": p.side,
        }
        for p in positions
    ]


def get_position(symbol: str) -> dict | None:
    positions = get_all_positions()
    for p in positions:
        if p["symbol"] == symbol:
            return p
    return None


def get_open_symbols() -> set[str]:
    return {p["symbol"] for p in get_all_positions()}
