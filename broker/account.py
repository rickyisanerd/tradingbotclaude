"""Account info: buying power, PDT status, equity."""

import logging

from broker.client import get_trading_client
from config.settings import settings
from utils.retry import retry

log = logging.getLogger(__name__)


@retry(max_attempts=3)
def get_account_info() -> dict:
    client = get_trading_client()
    acct = client.get_account()
    return {
        "equity": float(acct.equity),
        "buying_power": float(acct.buying_power),
        "cash": float(acct.cash),
        "daytrade_count": int(acct.daytrade_count),
        "pattern_day_trader": acct.pattern_day_trader,
        "trading_blocked": acct.trading_blocked,
        "account_blocked": acct.account_blocked,
    }


def is_pdt_restricted() -> bool:
    """Check if account is PDT-restricted (small account, 3+ day trades)."""
    info = get_account_info()
    if info["equity"] >= settings.pdt_equity_threshold:
        return False
    return info["daytrade_count"] >= 3


def get_buying_power() -> float:
    return get_account_info()["buying_power"]
