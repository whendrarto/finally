"""Tests for the portfolio service."""

import pytest

from app import db
from app.services.portfolio import TradeError, execute_trade, get_portfolio, normalize_ticker

pytestmark = pytest.mark.usefixtures("tmp_db")


def test_buy_reduces_cash_and_creates_position(cache):
    trade = execute_trade(cache, "aapl", "buy", 10)
    assert trade["ticker"] == "AAPL"
    assert trade["side"] == "buy"
    assert trade["quantity"] == 10
    assert trade["price"] == 100.0
    assert {"id", "executed_at"} <= trade.keys()
    assert db.get_cash_balance() == pytest.approx(9000.0)
    pos = db.get_position("AAPL")
    assert pos["quantity"] == 10
    assert pos["avg_cost"] == 100.0


def test_buy_records_snapshot(cache):
    execute_trade(cache, "AAPL", "buy", 1)
    snaps = db.get_snapshots()
    assert len(snaps) == 1
    assert snaps[0]["total_value"] == pytest.approx(10000.0)


def test_weighted_avg_cost(cache):
    execute_trade(cache, "AAPL", "buy", 10)
    cache.update("AAPL", 200.0)
    execute_trade(cache, "AAPL", "buy", 10)
    assert db.get_position("AAPL")["avg_cost"] == pytest.approx(150.0)


def test_fractional_shares(cache):
    execute_trade(cache, "AAPL", "buy", 0.5)
    assert db.get_position("AAPL")["quantity"] == pytest.approx(0.5)
    assert db.get_cash_balance() == pytest.approx(9950.0)


def test_insufficient_cash(cache):
    with pytest.raises(TradeError, match="Insufficient cash"):
        execute_trade(cache, "AAPL", "buy", 101)
    assert db.get_cash_balance() == 10000.0
    assert db.get_position("AAPL") is None
    assert db.get_trades() == []


def test_buy_exactly_all_cash(cache):
    execute_trade(cache, "AAPL", "buy", 100)
    assert db.get_cash_balance() == pytest.approx(0.0)


def test_oversell(cache):
    execute_trade(cache, "AAPL", "buy", 5)
    with pytest.raises(TradeError, match="Insufficient shares"):
        execute_trade(cache, "AAPL", "sell", 6)
    assert db.get_position("AAPL")["quantity"] == 5


def test_sell_without_position(cache):
    with pytest.raises(TradeError, match="Insufficient shares"):
        execute_trade(cache, "AAPL", "sell", 1)


def test_partial_sell_keeps_avg_cost(cache):
    execute_trade(cache, "AAPL", "buy", 10)
    cache.update("AAPL", 120.0)
    execute_trade(cache, "AAPL", "sell", 4)
    pos = db.get_position("AAPL")
    assert pos["quantity"] == pytest.approx(6)
    assert pos["avg_cost"] == pytest.approx(100.0)
    assert db.get_cash_balance() == pytest.approx(9000.0 + 480.0)


def test_sell_at_loss(cache):
    execute_trade(cache, "AAPL", "buy", 10)
    cache.update("AAPL", 80.0)
    execute_trade(cache, "AAPL", "sell", 10)
    assert db.get_cash_balance() == pytest.approx(9800.0)
    assert db.get_position("AAPL") is None


def test_full_close_with_float_dust(cache):
    execute_trade(cache, "AAPL", "buy", 0.1)
    execute_trade(cache, "AAPL", "buy", 0.2)
    execute_trade(cache, "AAPL", "sell", 0.3)  # 0.1 + 0.2 != 0.3 in floats
    assert db.get_position("AAPL") is None


@pytest.mark.parametrize("qty", [0, -1, "abc", None, float("nan"), float("inf")])
def test_invalid_quantity(cache, qty):
    with pytest.raises(TradeError):
        execute_trade(cache, "AAPL", "buy", qty)


@pytest.mark.parametrize("side", ["hold", "", None])
def test_invalid_side(cache, side):
    with pytest.raises(TradeError, match="Side"):
        execute_trade(cache, "AAPL", side, 1)


def test_side_case_insensitive(cache):
    assert execute_trade(cache, "AAPL", "BUY", 1)["side"] == "buy"


@pytest.mark.parametrize("ticker", ["", "1ABC", "TOOLONGTICKER", "AA PL", "$AAPL"])
def test_invalid_ticker(cache, ticker):
    with pytest.raises(TradeError, match="Invalid ticker"):
        execute_trade(cache, ticker, "buy", 1)


def test_no_price(cache):
    with pytest.raises(TradeError, match="No price available for ZZZ"):
        execute_trade(cache, "zzz", "buy", 1)


def test_normalize_ticker():
    assert normalize_ticker(" brk.b ") == "BRK.B"
    assert normalize_ticker("1X") is None
    assert normalize_ticker(None) is None


def test_get_portfolio_empty(cache):
    assert get_portfolio(cache) == {
        "cash_balance": 10000.0,
        "positions_value": 0.0,
        "total_value": 10000.0,
        "unrealized_pnl": 0.0,
        "unrealized_pnl_percent": 0.0,
        "positions": [],
    }


def test_get_portfolio_pnl(cache):
    execute_trade(cache, "AAPL", "buy", 10)
    execute_trade(cache, "TSLA", "buy", 4)
    cache.update("AAPL", 110.0)
    cache.update("TSLA", 200.0)
    p = get_portfolio(cache)
    assert p["cash_balance"] == pytest.approx(8000.0)
    assert p["positions_value"] == pytest.approx(1100.0 + 800.0)
    assert p["total_value"] == pytest.approx(9900.0)
    assert p["unrealized_pnl"] == pytest.approx(100.0 - 200.0)
    assert p["unrealized_pnl_percent"] == pytest.approx(-100.0 / 2000.0 * 100)
    by_ticker = {pos["ticker"]: pos for pos in p["positions"]}
    aapl = by_ticker["AAPL"]
    assert aapl["current_price"] == 110.0
    assert aapl["market_value"] == pytest.approx(1100.0)
    assert aapl["unrealized_pnl"] == pytest.approx(100.0)
    assert aapl["unrealized_pnl_percent"] == pytest.approx(10.0)
    assert by_ticker["TSLA"]["unrealized_pnl_percent"] == pytest.approx(-20.0)


def test_get_portfolio_unpriced_falls_back_to_cost(cache):
    execute_trade(cache, "AAPL", "buy", 10)
    cache.remove("AAPL")
    pos = get_portfolio(cache)["positions"][0]
    assert pos["current_price"] == 100.0
    assert pos["unrealized_pnl"] == 0.0
