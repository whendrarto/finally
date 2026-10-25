"""Fixtures for LLM chat tests: tmp DB, seeded price cache, fake market source."""

import pytest

from app import db
from app.market import PriceCache


class FakeMarketSource:
    """Records add/remove calls; never touches the network."""

    def __init__(self) -> None:
        self.added: list[str] = []
        self.removed: list[str] = []

    async def start(self, tickers: list[str]) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def add_ticker(self, ticker: str) -> None:
        self.added.append(ticker)

    async def remove_ticker(self, ticker: str) -> None:
        self.removed.append(ticker)

    def get_tickers(self) -> list[str]:
        return []


@pytest.fixture(autouse=True)
def tmp_db(tmp_path):
    db.init_db(tmp_path / "test.db")
    yield


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Fail loudly if anything tries to reach the real LLM."""

    def _blocked(*args, **kwargs):
        raise AssertionError("Real LLM call attempted in tests")

    monkeypatch.setattr("app.llm.client.completion", _blocked)


@pytest.fixture
def price_cache():
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    cache.update("TSLA", 250.0)
    cache.update("PYPL", 60.0)
    return cache


@pytest.fixture
def market_source():
    return FakeMarketSource()
