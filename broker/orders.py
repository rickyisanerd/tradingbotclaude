"""Order builder: bracket orders, protective stops, market sells."""

import logging
from typing import Optional

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    MarketOrderRequest,
    LimitOrderRequest,
    OrderRequest,
)
from alpaca.trading.enums import OrderSide, TimeInForce, OrderClass

from broker.client import get_trading_client
from utils.retry import retry
from db.repository import audit

log = logging.getLogger(__name__)


@retry(max_attempts=2)
def submit_bracket_buy(
    symbol: str,
    qty: float,
    take_profit_price: float,
    stop_loss_price: float,
    limit_price: Optional[float] = None,
) -> str:
    """Submit a bracket order: entry + take-profit + stop-loss.

    Returns the Alpaca order ID.
    """
    client = get_trading_client()

    order_data = MarketOrderRequest(
        symbol=symbol,
        qty=qty,
        side=OrderSide.BUY,
        time_in_force=TimeInForce.DAY,
        order_class=OrderClass.BRACKET,
        take_profit={"limit_price": round(take_profit_price, 2)},
        stop_loss={"stop_price": round(stop_loss_price, 2)},
    )

    if limit_price:
        order_data = LimitOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
            order_class=OrderClass.BRACKET,
            limit_price=round(limit_price, 2),
            take_profit={"limit_price": round(take_profit_price, 2)},
            stop_loss={"stop_price": round(stop_loss_price, 2)},
        )

    order = client.submit_order(order_data)
    order_id = str(order.id)

    audit("order_submitted", {
        "symbol": symbol,
        "qty": qty,
        "type": "bracket_buy",
        "take_profit": take_profit_price,
        "stop_loss": stop_loss_price,
        "order_id": order_id,
    })

    log.info(
        "Bracket buy submitted: %s qty=%s tp=%.2f sl=%.2f order_id=%s",
        symbol, qty, take_profit_price, stop_loss_price, order_id,
    )
    return order_id


@retry(max_attempts=2)
def submit_market_sell(symbol: str, qty: float) -> str:
    """Submit a market sell order. Returns order ID."""
    client = get_trading_client()
    order_data = MarketOrderRequest(
        symbol=symbol,
        qty=qty,
        side=OrderSide.SELL,
        time_in_force=TimeInForce.DAY,
    )
    order = client.submit_order(order_data)
    order_id = str(order.id)

    audit("order_submitted", {
        "symbol": symbol,
        "qty": qty,
        "type": "market_sell",
        "order_id": order_id,
    })

    log.info("Market sell submitted: %s qty=%s order_id=%s", symbol, qty, order_id)
    return order_id


@retry(max_attempts=2)
def cancel_open_orders_for_symbol(symbol: str) -> int:
    """Cancel all open orders for a symbol. Returns count cancelled."""
    client = get_trading_client()
    orders = client.get_orders(filter={"symbol": symbol, "status": "open"})
    cancelled = 0
    for order in orders:
        try:
            client.cancel_order_by_id(str(order.id))
            cancelled += 1
        except Exception as e:
            log.warning("Failed to cancel order %s: %s", order.id, e)
    if cancelled:
        log.info("Cancelled %d open orders for %s", cancelled, symbol)
    return cancelled


def get_order_status(order_id: str) -> dict:
    client = get_trading_client()
    order = client.get_order_by_id(order_id)
    return {
        "id": str(order.id),
        "status": str(order.status),
        "filled_avg_price": float(order.filled_avg_price) if order.filled_avg_price else None,
        "filled_qty": float(order.filled_qty) if order.filled_qty else 0,
        "symbol": order.symbol,
        "side": str(order.side),
    }
