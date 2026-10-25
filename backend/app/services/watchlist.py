"""Watchlist service: add/remove tickers and keep the market source in sync."""

from __future__ import annotations

from app import db
from app.market import MarketDataSource, PriceCache

from .portfolio import normalize_ticker


class WatchlistError(Exception):
    """Watchlist operation failure. The message is user-facing.

    `code` is "invalid", "duplicate" or "not_found" so the API can map it to a status.
    """

    def __init__(self, message: str, code: str = "invalid") -> None:
        super().__init__(message)
        self.code = code


def watchlist_item(price_cache: PriceCache, ticker: str) -> dict:
    """Watchlist entry with latest price fields (None if not yet priced)."""
    update = price_cache.get(ticker)
    if update is None:
        return {
            "ticker": ticker,
            "price": None,
            "previous_price": None,
            "change": None,
            "change_percent": None,
            "direction": None,
        }
    return {
        "ticker": ticker,
        "price": update.price,
        "previous_price": update.previous_price,
        "change": update.change,
        "change_percent": update.change_percent,
        "direction": update.direction,
    }


def get_watchlist(price_cache: PriceCache) -> list[dict]:
    return [watchlist_item(price_cache, t) for t in db.get_watchlist()]


async def add_ticker(
    market_source: MarketDataSource, ticker: str, price_cache: PriceCache | None = None
) -> dict:
    """Add a ticker to the watchlist and start streaming it. Returns the watchlist item.

    `price_cache` is used to fill the returned item's price fields; it defaults to the
    cache the market source writes to.
    """
    symbol = normalize_ticker(ticker)
    if symbol is None:
        raise WatchlistError(f"Invalid ticker: {ticker!r}", "invalid")
    if not db.add_watchlist_ticker(symbol):
        raise WatchlistError(f"{symbol} is already in the watchlist", "duplicate")
    await market_source.add_ticker(symbol)
    cache = price_cache if price_cache is not None else getattr(market_source, "_cache", None)
    if cache is None:
        return watchlist_item(PriceCache(), symbol)
    return watchlist_item(cache, symbol)


async def remove_ticker(
    market_source: MarketDataSource, price_cache: PriceCache, ticker: str
) -> None:
    """Remove a ticker from the watchlist; keep streaming it if a position is held."""
    symbol = normalize_ticker(ticker)
    if symbol is None:
        raise WatchlistError(f"Invalid ticker: {ticker!r}", "invalid")
    if not db.remove_watchlist_ticker(symbol):
        raise WatchlistError(f"{symbol} is not in the watchlist", "not_found")
    if db.get_position(symbol) is None:
        await market_source.remove_ticker(symbol)
        price_cache.remove(symbol)

