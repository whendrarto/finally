"""Fixtures for service tests: a temp DB and a hand-priced cache."""

import pytest

from app import db
from app.market import PriceCache


@pytest.fixture
def tmp_db(tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    monkeypatch.setenv("FINALLY_DB_PATH", str(path))
    db.init_db(path)
    return path


@pytest.fixture
def cache():
    c = PriceCache()
    c.update("AAPL", 100.0)
    c.update("TSLA", 250.0)
    return c


class FakeSource:
    """Minimal MarketDataSource stand-in that records calls."""

    def __init__(self, cache: PriceCache) -> None:
        self._cache = cache
        self.tickers: list[str] = []

    async def start(self, tickers):
        self.tickers = list(tickers)

    async def stop(self):
        pass

    async def add_ticker(self, ticker):
        if ticker not in self.tickers:
            self.tickers.append(ticker)
            self._cache.update(ticker, 42.0)

    async def remove_ticker(self, ticker):
        self.tickers = [t for t in self.tickers if t != ticker]
        self._cache.remove(ticker)

    def get_tickers(self):
        return list(self.tickers)


@pytest.fixture
def source(cache):
    return FakeSource(cache)
