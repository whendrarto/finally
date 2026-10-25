"""Fixtures for API tests: the real app against a temp DB with fixed prices."""

import pytest
from fastapi.testclient import TestClient

from app import main
from tests.services.conftest import FakeSource


class FixedPriceSource(FakeSource):
    """Seeds every started ticker at $100 and never moves prices."""

    async def start(self, tickers):
        await super().start(tickers)
        for ticker in tickers:
            self._cache.update(ticker, 100.0)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("FINALLY_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(main, "create_market_data_source", FixedPriceSource)
    cache = main.app.state.price_cache
    for ticker in list(cache.get_all()):
        cache.remove(ticker)
    with TestClient(main.app) as c:
        yield c
