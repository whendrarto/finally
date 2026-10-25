"""Mock-mode command parsing and reply formatting."""

import pytest

from app.llm.mock import is_mock_mode, mock_reply, parse_mock_commands


@pytest.mark.parametrize(
    ("text", "side", "qty", "ticker"),
    [
        ("buy 10 AAPL", "buy", 10.0, "AAPL"),
        ("BUY 10 aapl", "buy", 10.0, "AAPL"),
        ("Sell 2.5 TSLA.", "sell", 2.5, "TSLA"),
        ("buy 3 shares of NVDA", "buy", 3.0, "NVDA"),
        ("  sell 1 brk.b  ", "sell", 1.0, "BRK.B"),
    ],
)
def test_trade_commands(text, side, qty, ticker):
    resp = parse_mock_commands(text)
    assert len(resp.trades) == 1
    t = resp.trades[0]
    assert (t.side, t.quantity, t.ticker) == (side, qty, ticker)
    assert resp.watchlist_changes == []


@pytest.mark.parametrize(
    ("text", "action", "ticker"),
    [
        ("add PYPL", "add", "PYPL"),
        ("watch pypl", "add", "PYPL"),
        ("remove NFLX", "remove", "NFLX"),
        ("Unwatch nflx!", "remove", "NFLX"),
    ],
)
def test_watchlist_commands(text, action, ticker):
    resp = parse_mock_commands(text)
    assert resp.trades == []
    assert [(c.action, c.ticker) for c in resp.watchlist_changes] == [(action, ticker)]


def test_multiple_commands():
    resp = parse_mock_commands("add PYPL and buy 5 PYPL, sell 1 AAPL")
    assert [(c.action, c.ticker) for c in resp.watchlist_changes] == [("add", "PYPL")]
    assert [(t.side, t.quantity, t.ticker) for t in resp.trades] == [
        ("buy", 5.0, "PYPL"),
        ("sell", 1.0, "AAPL"),
    ]


@pytest.mark.parametrize(
    "text", ["hello", "How is my portfolio doing?", "add some tech exposure please", "buy AAPL"]
)
def test_non_commands_have_no_actions(text):
    resp = parse_mock_commands(text)
    assert resp.trades == [] and resp.watchlist_changes == []


def test_greeting_reply():
    assert mock_reply([], [], 10000.0) == (
        "[mock] Hello! I'm FinAlly, your AI trading assistant. Your portfolio is worth $10,000.00."
    )


def test_action_reply():
    reply = mock_reply(
        [
            {"ticker": "AAPL", "side": "buy", "quantity": 10.0, "price": 190.0,
             "status": "executed", "error": None},
            {"ticker": "TSLA", "side": "sell", "quantity": 1.0, "price": 250.0,
             "status": "failed", "error": "Insufficient shares"},
        ],
        [{"ticker": "PYPL", "action": "add", "status": "executed", "error": None}],
        10000.0,
    )
    assert reply.startswith("[mock] ")
    assert "Bought 10 AAPL at $190.00." in reply
    assert "Failed to sell 1 TSLA: Insufficient shares" in reply
    assert "Added PYPL to the watchlist." in reply


@pytest.mark.parametrize(("value", "expected"), [("true", True), ("TRUE", True), ("false", False), ("", False)])
def test_is_mock_mode(monkeypatch, value, expected):
    monkeypatch.setenv("LLM_MOCK", value)
    assert is_mock_mode() is expected
