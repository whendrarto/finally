"""Portfolio service: trade execution and portfolio valuation.

Shared by the REST API and the LLM chat flow so both use identical validation.
"""

from __future__ import annotations

import logging
import re

from app import db
from app.market import PriceCache

logger = logging.getLogger(__name__)

TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.]{0,9}$")
QTY_EPSILON = 1e-9


class TradeError(Exception):
    """Trade validation failure. The message is user-facing."""


def normalize_ticker(ticker: str) -> str | None:
    """Uppercase/strip a ticker; return None if it is not a valid symbol."""
    if not isinstance(ticker, str):
        return None
    ticker = ticker.strip().upper()
    return ticker if TICKER_RE.match(ticker) else None


def execute_trade(price_cache: PriceCache, ticker: str, side: str, quantity: float) -> dict:
    """Validate and execute a market order at the current cached price.

    Returns the trade dict {id, ticker, side, quantity, price, executed_at}.
    Raises TradeError with a user-facing message on validation failure.
    """
    symbol = normalize_ticker(ticker)
    if symbol is None:
        raise TradeError(f"Invalid ticker: {ticker!r}")

    side = (side or "").strip().lower() if isinstance(side, str) else ""
    if side not in ("buy", "sell"):
        raise TradeError("Side must be 'buy' or 'sell'")

    try:
        quantity = float(quantity)
    except (TypeError, ValueError):
        raise TradeError("Quantity must be a number") from None
    if not quantity > 0 or quantity == float("inf"):
        raise TradeError("Quantity must be greater than 0")

    price = price_cache.get_price(symbol)
    if price is None:
        raise TradeError(f"No price available for {symbol}")

    cash = db.get_cash_balance()
    position = db.get_position(symbol)
    held = position["quantity"] if position else 0.0
    avg_cost = position["avg_cost"] if position else 0.0
    cost = quantity * price

    if side == "buy":
        if cash + QTY_EPSILON < cost:
            raise TradeError(
                f"Insufficient cash: need ${cost:,.2f} to buy {quantity:g} {symbol}, "
                f"have ${cash:,.2f}"
            )
        new_cash = cash - cost
        new_quantity = held + quantity
        new_avg_cost = (held * avg_cost + cost) / new_quantity
    else:
        if held + QTY_EPSILON < quantity:
            raise TradeError(
                f"Insufficient shares: cannot sell {quantity:g} {symbol}, hold {held:g}"
            )
        new_cash = cash + cost
        new_quantity = held - quantity
        if new_quantity < QTY_EPSILON:
            new_quantity = 0.0
        new_avg_cost = avg_cost

    trade = db.apply_trade(
        symbol, side, quantity, price, max(new_cash, 0.0), new_quantity, new_avg_cost
    )
    logger.info("Executed %s %g %s @ %.2f", side, quantity, symbol, price)

    try:
        record_snapshot(price_cache)
    except Exception:
        logger.exception("Failed to record post-trade snapshot")

    return trade


def get_portfolio(price_cache: PriceCache) -> dict:
    """Current portfolio valued at cached prices (falls back to avg_cost if unpriced)."""
    cash = db.get_cash_balance()
    positions = []
    positions_value = 0.0
    cost_basis = 0.0

    for pos in db.get_positions():
        qty = pos["quantity"]
        avg_cost = pos["avg_cost"]
        current = price_cache.get_price(pos["ticker"])
        if current is None:
            current = avg_cost
        market_value = qty * current
        basis = qty * avg_cost
        pnl = market_value - basis
        positions.append(
            {
                "ticker": pos["ticker"],
                "quantity": qty,
                "avg_cost": avg_cost,
                "current_price": current,
                "market_value": market_value,
                "unrealized_pnl": pnl,
                "unrealized_pnl_percent": (pnl / basis * 100) if basis else 0.0,
            }
        )
        positions_value += market_value
        cost_basis += basis

    unrealized_pnl = positions_value - cost_basis
    return {
        "cash_balance": cash,
        "positions_value": positions_value,
        "total_value": cash + positions_value,
        "unrealized_pnl": unrealized_pnl,
        "unrealized_pnl_percent": (unrealized_pnl / cost_basis * 100) if cost_basis else 0.0,
        "positions": positions,
    }


def record_snapshot(price_cache: PriceCache) -> float:
    """Persist the current total portfolio value; returns it."""
    total = get_portfolio(price_cache)["total_value"]
    db.insert_snapshot(total)
    return total
