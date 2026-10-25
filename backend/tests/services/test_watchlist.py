"""Tests for the watchlist service."""

import pytest

from app import db
from app.services.portfolio import execute_trade
from app.services.watchlist import WatchlistError, add_ticker, get_watchlist, remove_ticker

pytestmark = pytest.mark.usefixtures("tmp_db")

ITEM_KEYS = {"ticker", "price", "previous_price", "change", "change_percent", "direction"}


async def test_add_ticker(source):
    item = await add_ticker(source, " pypl ")
    assert item["ticker"] == "PYPL"
    assert item["price"] == 42.0
    assert set(item) == ITEM_KEYS
    assert "PYPL" in db.get_watchlist()
    assert "PYPL" in source.get_tickers()


async def test_add_duplicate(source):
    with pytest.raises(WatchlistError) as exc:
        await add_ticker(source, "AAPL")  # in the seed watchlist
    assert exc.value.code == "duplicate"


@pytest.mark.parametrize("ticker", ["", "123", "BAD TICKER", "WAYTOOLONGTICKER"])
async def test_add_invalid(source, ticker):
    with pytest.raises(WatchlistError) as exc:
        await add_ticker(source, ticker)
    assert exc.value.code == "invalid"


async def test_remove_ticker(source, cache):
    await add_ticker(source, "PYPL")
    await remove_ticker(source, cache, "pypl")
    assert "PYPL" not in db.get_watchlist()
    assert "PYPL" not in source.get_tickers()
    assert cache.get("PYPL") is None


async def test_remove_missing(source, cache):
    with pytest.raises(WatchlistError) as exc:
        await remove_ticker(source, cache, "ZZZZ")
    assert exc.value.code == "not_found"


async def test_remove_keeps_streaming_held_position(source, cache):
    await source.start(["AAPL"])
    execute_trade(cache, "AAPL", "buy", 1)
    await remove_ticker(source, cache, "AAPL")
    assert "AAPL" not in db.get_watchlist()
    assert "AAPL" in source.get_tickers()
    assert cache.get_price("AAPL") == 100.0


def test_get_watchlist_prices(cache):
    items = {i["ticker"]: i for i in get_watchlist(cache)}
    assert len(items) == 10
    assert items["AAPL"]["price"] == 100.0
    assert items["AAPL"]["direction"] == "flat"
    assert items["GOOGL"]["price"] is None
