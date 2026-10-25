"""Structured-output parsing."""

import json

import pytest

from app.llm.schema import ChatResponse, LLMOutputError, parse_llm_output


def test_full_valid_response():
    raw = json.dumps(
        {
            "message": "Bought for you.",
            "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}],
            "watchlist_changes": [{"ticker": "PYPL", "action": "add"}],
        }
    )
    resp = parse_llm_output(raw)
    assert resp.message == "Bought for you."
    assert resp.trades[0].ticker == "AAPL"
    assert resp.trades[0].side == "buy"
    assert resp.trades[0].quantity == 10.0
    assert resp.watchlist_changes[0].action == "add"


def test_missing_optional_fields_default_to_empty():
    resp = parse_llm_output('{"message": "Hi"}')
    assert resp == ChatResponse(message="Hi", trades=[], watchlist_changes=[])


def test_fractional_quantity():
    resp = parse_llm_output(
        '{"message": "ok", "trades": [{"ticker": "AAPL", "side": "sell", "quantity": 0.5}]}'
    )
    assert resp.trades[0].quantity == 0.5


def test_code_fenced_json():
    resp = parse_llm_output('```json\n{"message": "fenced"}\n```')
    assert resp.message == "fenced"


def test_invalid_action_keeps_message_drops_actions():
    raw = json.dumps(
        {"message": "Trying", "trades": [{"ticker": "AAPL", "side": "short", "quantity": 1}]}
    )
    resp = parse_llm_output(raw)
    assert resp.message == "Trying"
    assert resp.trades == []
    assert resp.watchlist_changes == []


@pytest.mark.parametrize(
    "raw",
    [None, "", "   ", "not json at all", '{"message": ', "[1, 2]", '{"trades": []}', '{"message": 5}'],
)
def test_malformed_raises(raw):
    with pytest.raises(LLMOutputError):
        parse_llm_output(raw)


def test_schema_is_valid_response_format():
    schema = ChatResponse.model_json_schema()
    assert schema["required"] == ["message"]
    assert {"message", "trades", "watchlist_changes"} <= set(schema["properties"])
