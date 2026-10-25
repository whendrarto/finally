"""Tests for the health, portfolio and watchlist REST endpoints."""

import pytest

PORTFOLIO_KEYS = {
    "cash_balance",
    "positions_value",
    "total_value",
    "unrealized_pnl",
    "unrealized_pnl_percent",
    "positions",
}
POSITION_KEYS = {
    "ticker",
    "quantity",
    "avg_cost",
    "current_price",
    "market_value",
    "unrealized_pnl",
    "unrealized_pnl_percent",
}
WATCH_KEYS = {"ticker", "price", "previous_price", "change", "change_percent", "direction"}


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_initial_portfolio(client):
    r = client.get("/api/portfolio")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == PORTFOLIO_KEYS
    assert body["cash_balance"] == 10000.0
    assert body["total_value"] == 10000.0
    assert body["positions"] == []


def test_buy_then_sell(client):
    r = client.post("/api/portfolio/trade", json={"ticker": "aapl", "quantity": 10, "side": "buy"})
    assert r.status_code == 200
    body = r.json()
    assert set(body["trade"]) == {"id", "ticker", "side", "quantity", "price", "executed_at"}
    assert body["trade"]["ticker"] == "AAPL"
    assert body["trade"]["price"] == 100.0
    portfolio = body["portfolio"]
    assert set(portfolio) == PORTFOLIO_KEYS
    assert portfolio["cash_balance"] == pytest.approx(9000.0)
    assert len(portfolio["positions"]) == 1
    assert set(portfolio["positions"][0]) == POSITION_KEYS

    r = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 10, "side": "sell"})
    assert r.status_code == 200
    assert r.json()["portfolio"]["positions"] == []
    assert r.json()["portfolio"]["cash_balance"] == pytest.approx(10000.0)


@pytest.mark.parametrize(
    "payload, fragment",
    [
        ({"ticker": "AAPL", "quantity": 1000, "side": "buy"}, "Insufficient cash"),
        ({"ticker": "AAPL", "quantity": 1, "side": "sell"}, "Insufficient shares"),
        ({"ticker": "AAPL", "quantity": 0, "side": "buy"}, "Quantity"),
        ({"ticker": "AAPL", "quantity": 1, "side": "short"}, "Side"),
        ({"ticker": "ZZZZ", "quantity": 1, "side": "buy"}, "No price available for ZZZZ"),
        ({"ticker": "1BAD", "quantity": 1, "side": "buy"}, "Invalid ticker"),
        ({"ticker": "AAPL", "quantity": "lots", "side": "buy"}, "quantity"),
        ({"ticker": "AAPL"}, "side"),
    ],
)
def test_trade_validation_errors(client, payload, fragment):
    r = client.post("/api/portfolio/trade", json=payload)
    assert r.status_code == 400
    assert fragment in r.json()["detail"]


def test_history_records_trade_snapshot(client):
    assert client.get("/api/portfolio/history").json() == {"snapshots": []}
    client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 1, "side": "buy"})
    snaps = client.get("/api/portfolio/history").json()["snapshots"]
    assert len(snaps) == 1
    assert set(snaps[0]) == {"total_value", "recorded_at"}
    assert snaps[0]["total_value"] == pytest.approx(10000.0)


def test_get_watchlist(client):
    r = client.get("/api/watchlist")
    assert r.status_code == 200
    tickers = r.json()["tickers"]
    assert [t["ticker"] for t in tickers][:3] == ["AAPL", "GOOGL", "MSFT"]
    assert len(tickers) == 10
    assert set(tickers[0]) == WATCH_KEYS
    assert tickers[0]["price"] == 100.0


def test_add_and_remove_watchlist(client):
    r = client.post("/api/watchlist", json={"ticker": "pypl"})
    assert r.status_code == 201
    assert r.json()["ticker"] == "PYPL"
    assert set(r.json()) == WATCH_KEYS
    assert "PYPL" in [t["ticker"] for t in client.get("/api/watchlist").json()["tickers"]]

    r = client.delete("/api/watchlist/PYPL")
    assert r.status_code == 204
    assert "PYPL" not in [t["ticker"] for t in client.get("/api/watchlist").json()["tickers"]]


def test_add_duplicate_watchlist(client):
    r = client.post("/api/watchlist", json={"ticker": "AAPL"})
    assert r.status_code == 409
    assert "already" in r.json()["detail"]


def test_add_invalid_watchlist(client):
    r = client.post("/api/watchlist", json={"ticker": "not a ticker"})
    assert r.status_code == 400
    assert "Invalid ticker" in r.json()["detail"]


def test_remove_missing_watchlist(client):
    r = client.delete("/api/watchlist/ZZZZ")
    assert r.status_code == 404
    assert "detail" in r.json()


def test_held_ticker_keeps_price_after_unwatch(client):
    client.post("/api/portfolio/trade", json={"ticker": "TSLA", "quantity": 1, "side": "buy"})
    assert client.delete("/api/watchlist/TSLA").status_code == 204
    pos = client.get("/api/portfolio").json()["positions"][0]
    assert pos["ticker"] == "TSLA"
    assert pos["current_price"] == 100.0
