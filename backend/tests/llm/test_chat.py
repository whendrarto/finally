"""End-to-end chat flow with the LLM mocked: execution, validation failures, persistence."""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import db
from app.api.chat import router
from app.llm import chat as chat_module
from app.llm import client
from app.llm.prompts import build_portfolio_context
from app.llm.schema import ChatResponse, TradeRequest, WatchlistChange


@pytest.fixture
def real_mode(monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "false")


@pytest.fixture
def mock_mode(monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")


def stub_llm(monkeypatch, response: ChatResponse | Exception):
    calls: list[list[dict]] = []

    async def fake_call_llm(messages):
        calls.append(messages)
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(client, "call_llm", fake_call_llm)
    return calls


# --- real (non-mock) mode with the LLM stubbed -----------------------------------------------


async def test_llm_trades_and_watchlist_executed(real_mode, monkeypatch, price_cache, market_source):
    calls = stub_llm(
        monkeypatch,
        ChatResponse(
            message="Done.",
            trades=[TradeRequest(ticker="aapl", side="buy", quantity=10)],
            watchlist_changes=[WatchlistChange(ticker="PYPL", action="add")],
        ),
    )
    result = await chat_module.handle_chat("buy 10 apple and watch paypal", price_cache, market_source)

    assert result["message"] == "Done."
    assert result["trades"] == [
        {"ticker": "AAPL", "side": "buy", "quantity": 10.0, "price": 190.0,
         "status": "executed", "error": None}
    ]
    assert result["watchlist_changes"] == [
        {"ticker": "PYPL", "action": "add", "status": "executed", "error": None}
    ]
    assert db.get_cash_balance() == pytest.approx(10000 - 1900)
    assert db.get_position("AAPL")["quantity"] == 10
    assert "PYPL" in db.get_watchlist()
    assert market_source.added == ["PYPL"]

    # Prompt contains system prompt, portfolio context and the user message
    messages = calls[0]
    assert "FinAlly" in messages[0]["content"]
    assert "Cash: $10,000.00" in messages[1]["content"]
    assert messages[-1] == {"role": "user", "content": "buy 10 apple and watch paypal"}


async def test_trade_validation_failures_surface(real_mode, monkeypatch, price_cache, market_source):
    stub_llm(
        monkeypatch,
        ChatResponse(
            message="Trying.",
            trades=[
                TradeRequest(ticker="AAPL", side="buy", quantity=1000),  # insufficient cash
                TradeRequest(ticker="TSLA", side="sell", quantity=1),  # no shares held
                TradeRequest(ticker="ZZZZ", side="buy", quantity=1),  # no price
            ],
            watchlist_changes=[
                WatchlistChange(ticker="AAPL", action="add"),  # duplicate
                WatchlistChange(ticker="QQQQ", action="remove"),  # not present
            ],
        ),
    )
    result = await chat_module.handle_chat("go", price_cache, market_source)

    statuses = [t["status"] for t in result["trades"]]
    assert statuses == ["failed", "failed", "failed"]
    assert "Insufficient cash" in result["trades"][0]["error"]
    assert "Insufficient shares" in result["trades"][1]["error"]
    assert "No price available for ZZZZ" in result["trades"][2]["error"]
    assert result["trades"][2]["price"] is None
    assert [w["status"] for w in result["watchlist_changes"]] == ["failed", "failed"]
    assert all(w["error"] for w in result["watchlist_changes"])
    assert db.get_cash_balance() == 10000.0
    assert db.get_positions() == []


async def test_llm_error_returns_apology(real_mode, monkeypatch, price_cache, market_source):
    stub_llm(monkeypatch, RuntimeError("network down"))
    result = await chat_module.handle_chat("hello", price_cache, market_source)
    assert "Sorry" in result["message"]
    assert result["trades"] == [] and result["watchlist_changes"] == []
    stored = db.get_chat_messages()
    assert [m["role"] for m in stored] == ["user", "assistant"]


async def test_malformed_completion_is_graceful(real_mode, monkeypatch, price_cache, market_source):
    """The real client path with a garbage completion falls back to the apology."""
    fake = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="nope{"))])
    monkeypatch.setattr(client, "completion", lambda **kwargs: fake)
    result = await chat_module.handle_chat("hello", price_cache, market_source)
    assert "Sorry" in result["message"]
    assert result["trades"] == []


async def test_client_passes_structured_output_params(monkeypatch):
    captured = {}

    def fake_completion(**kwargs):
        captured.update(kwargs)
        content = '{"message": "hi", "trades": [], "watchlist_changes": []}'
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    monkeypatch.setattr(client, "completion", fake_completion)
    resp = await client.call_llm([{"role": "user", "content": "hi"}])
    assert resp.message == "hi"
    assert captured["model"] == "openrouter/openai/gpt-oss-120b"
    assert captured["response_format"] is ChatResponse
    assert captured["extra_body"] == {"provider": {"order": ["cerebras"]}}


async def test_history_included_in_prompt(real_mode, monkeypatch, price_cache, market_source):
    db.insert_chat_message("user", "earlier question")
    db.insert_chat_message(
        "assistant", "earlier answer", {"trades": [{"ticker": "AAPL"}], "watchlist_changes": []}
    )
    calls = stub_llm(monkeypatch, ChatResponse(message="ok"))
    await chat_module.handle_chat("now", price_cache, market_source)
    roles_contents = [(m["role"], m["content"]) for m in calls[0][2:]]
    assert roles_contents[0] == ("user", "earlier question")
    assert roles_contents[1][0] == "assistant"
    assert roles_contents[1][1].startswith("earlier answer")
    assert "AAPL" in roles_contents[1][1]
    assert roles_contents[2] == ("user", "now")


# --- mock mode -------------------------------------------------------------------------------


async def test_mock_greeting(mock_mode, price_cache, market_source):
    result = await chat_module.handle_chat("hi there", price_cache, market_source)
    assert result == {
        "message": "[mock] Hello! I'm FinAlly, your AI trading assistant. "
        "Your portfolio is worth $10,000.00.",
        "trades": [],
        "watchlist_changes": [],
    }


async def test_mock_executes_actions(mock_mode, price_cache, market_source):
    result = await chat_module.handle_chat("buy 5 AAPL", price_cache, market_source)
    assert result["message"] == "[mock] Bought 5 AAPL at $190.00."
    assert result["trades"][0]["status"] == "executed"
    assert db.get_position("AAPL")["quantity"] == 5

    result = await chat_module.handle_chat("sell 10 AAPL", price_cache, market_source)
    assert result["trades"][0]["status"] == "failed"
    assert result["message"].startswith("[mock] Failed to sell 10 AAPL")

    result = await chat_module.handle_chat("remove NFLX", price_cache, market_source)
    assert result["watchlist_changes"][0]["status"] == "executed"
    assert "NFLX" not in db.get_watchlist()


async def test_mock_never_calls_llm(mock_mode, monkeypatch, price_cache, market_source):
    stub_llm(monkeypatch, AssertionError("should not be called"))
    result = await chat_module.handle_chat("hello", price_cache, market_source)
    assert result["message"].startswith("[mock] ")


async def test_messages_persisted_with_actions(mock_mode, price_cache, market_source):
    await chat_module.handle_chat("buy 1 AAPL", price_cache, market_source)
    stored = db.get_chat_messages()
    assert [m["role"] for m in stored] == ["user", "assistant"]
    assert stored[0]["content"] == "buy 1 AAPL"
    assert stored[0]["actions"] is None
    assert stored[1]["actions"]["trades"][0]["ticker"] == "AAPL"
    assert stored[1]["actions"]["watchlist_changes"] == []


# --- context builder -------------------------------------------------------------------------


def test_portfolio_context_contents():
    text = build_portfolio_context(
        {
            "cash_balance": 5000.0,
            "positions_value": 1950.0,
            "total_value": 6950.0,
            "unrealized_pnl": 50.0,
            "unrealized_pnl_percent": 2.63,
            "positions": [
                {"ticker": "AAPL", "quantity": 10, "avg_cost": 190.0, "current_price": 195.0,
                 "market_value": 1950.0, "unrealized_pnl": 50.0, "unrealized_pnl_percent": 2.63}
            ],
        },
        [{"ticker": "AAPL", "price": 195.0, "change_percent": 0.1},
         {"ticker": "PYPL", "price": None, "change_percent": None}],
    )
    assert "Cash: $5,000.00" in text
    assert "Total value: $6,950.00" in text
    assert "AAPL: qty 10, avg cost $190.00" in text
    assert "PYPL: no price yet" in text


# --- HTTP routes -----------------------------------------------------------------------------


@pytest.fixture
def http(price_cache, market_source):
    app = FastAPI()
    app.include_router(router)
    app.state.price_cache = price_cache
    app.state.market_source = market_source
    return TestClient(app)


def test_post_chat_and_history(mock_mode, http):
    resp = http.post("/api/chat", json={"message": "add PYPL"})
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"message", "trades", "watchlist_changes"}
    assert body["watchlist_changes"][0] == {
        "ticker": "PYPL", "action": "add", "status": "executed", "error": None
    }

    hist = http.get("/api/chat/history")
    assert hist.status_code == 200
    messages = hist.json()["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert set(messages[0]) == {"id", "role", "content", "actions", "created_at"}


def test_post_chat_empty_message(http):
    resp = http.post("/api/chat", json={"message": "   "})
    assert resp.status_code == 400
    assert resp.json()["detail"]


def test_post_chat_missing_body(http):
    assert http.post("/api/chat", json={}).status_code == 422
