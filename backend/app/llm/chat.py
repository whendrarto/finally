"""Chat flow: context -> LLM (or mock) -> execute actions -> persist -> response."""

from __future__ import annotations

import asyncio
import logging

from app import db
from app.market import MarketDataSource, PriceCache
from app.services import portfolio as portfolio_service
from app.services import watchlist as watchlist_service
from app.services.portfolio import TradeError
from app.services.watchlist import WatchlistError

from . import client
from .mock import is_mock_mode, mock_reply, parse_mock_commands
from .prompts import SYSTEM_PROMPT, build_portfolio_context, format_history_message
from .schema import ChatResponse, TradeRequest, WatchlistChange

logger = logging.getLogger(__name__)

HISTORY_LIMIT = 20
ERROR_MESSAGE = (
    "Sorry, I ran into a problem reaching my analysis engine and couldn't process that. "
    "No trades or watchlist changes were made. Please try again."
)


def _execute_trade(price_cache: PriceCache, req: TradeRequest) -> dict:
    ticker = req.ticker.strip().upper()
    try:
        trade = portfolio_service.execute_trade(price_cache, ticker, req.side, req.quantity)
    except TradeError as exc:
        return {
            "ticker": ticker,
            "side": req.side,
            "quantity": req.quantity,
            "price": price_cache.get_price(ticker),
            "status": "failed",
            "error": str(exc),
        }
    except Exception:
        logger.exception("Unexpected error executing chat trade %s", req)
        return {
            "ticker": ticker,
            "side": req.side,
            "quantity": req.quantity,
            "price": price_cache.get_price(ticker),
            "status": "failed",
            "error": "Internal error executing trade",
        }
    return {
        "ticker": trade["ticker"],
        "side": trade["side"],
        "quantity": trade["quantity"],
        "price": trade["price"],
        "status": "executed",
        "error": None,
    }


async def _apply_watchlist_change(
    market_source: MarketDataSource, price_cache: PriceCache, change: WatchlistChange
) -> dict:
    ticker = change.ticker.strip().upper()
    try:
        if change.action == "add":
            await watchlist_service.add_ticker(market_source, ticker, price_cache)
        else:
            await watchlist_service.remove_ticker(market_source, price_cache, ticker)
    except WatchlistError as exc:
        return {"ticker": ticker, "action": change.action, "status": "failed", "error": str(exc)}
    except Exception:
        logger.exception("Unexpected error applying watchlist change %s", change)
        return {
            "ticker": ticker,
            "action": change.action,
            "status": "failed",
            "error": "Internal error updating watchlist",
        }
    return {"ticker": ticker, "action": change.action, "status": "executed", "error": None}


async def _execute_actions(
    response: ChatResponse, price_cache: PriceCache, market_source: MarketDataSource
) -> tuple[list[dict], list[dict]]:
    # Watchlist changes first so a newly added ticker can start streaming before any trade on it.
    watchlist_results = [
        await _apply_watchlist_change(market_source, price_cache, c)
        for c in response.watchlist_changes
    ]
    trade_results = [
        await asyncio.to_thread(_execute_trade, price_cache, t) for t in response.trades
    ]
    return trade_results, watchlist_results


def _build_messages(
    user_message: str, history: list[dict], portfolio: dict, watchlist: list[dict]
) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": build_portfolio_context(portfolio, watchlist)},
        *(format_history_message(m) for m in history),
        {"role": "user", "content": user_message},
    ]


async def handle_chat(
    user_message: str, price_cache: PriceCache, market_source: MarketDataSource
) -> dict:
    """Process one user chat message end to end. Never raises for LLM failures.

    Returns ``{message, trades, watchlist_changes}`` per the POST /api/chat contract.
    """
    history = await asyncio.to_thread(db.get_chat_messages, HISTORY_LIMIT)
    await asyncio.to_thread(db.insert_chat_message, "user", user_message)

    if is_mock_mode():
        response = parse_mock_commands(user_message)
    else:
        portfolio = await asyncio.to_thread(portfolio_service.get_portfolio, price_cache)
        watchlist = await asyncio.to_thread(watchlist_service.get_watchlist, price_cache)
        messages = _build_messages(user_message, history, portfolio, watchlist)
        try:
            response = await client.call_llm(messages)
        except Exception:
            logger.exception("LLM call failed")
            response = ChatResponse(message=ERROR_MESSAGE)

    trade_results, watchlist_results = await _execute_actions(response, price_cache, market_source)

    reply = response.message
    if is_mock_mode():
        total = (await asyncio.to_thread(portfolio_service.get_portfolio, price_cache))["total_value"]
        reply = mock_reply(trade_results, watchlist_results, total)

    actions = {"trades": trade_results, "watchlist_changes": watchlist_results}
    await asyncio.to_thread(db.insert_chat_message, "assistant", reply, actions)
    return {"message": reply, **actions}


async def get_history(limit: int = 100) -> list[dict]:
    """Stored conversation, oldest first."""
    return await asyncio.to_thread(db.get_chat_messages, limit)
