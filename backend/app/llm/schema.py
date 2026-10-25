"""Structured-output schema for LLM chat responses, plus tolerant parsing."""

from __future__ import annotations

import json
import logging
import re
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)


class TradeRequest(BaseModel):
    """A trade the assistant wants to execute."""

    ticker: str = Field(description="Stock ticker symbol, e.g. AAPL")
    side: Literal["buy", "sell"]
    quantity: float = Field(description="Number of shares (fractional allowed), must be > 0")


class WatchlistChange(BaseModel):
    """A watchlist modification the assistant wants to make."""

    ticker: str = Field(description="Stock ticker symbol, e.g. PYPL")
    action: Literal["add", "remove"]


class ChatResponse(BaseModel):
    """The structured response the LLM must produce."""

    message: str = Field(description="Conversational response shown to the user")
    trades: list[TradeRequest] = Field(default_factory=list)
    watchlist_changes: list[WatchlistChange] = Field(default_factory=list)


class LLMOutputError(Exception):
    """Raised when the LLM output cannot be interpreted at all."""


_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


def parse_llm_output(raw: str | None) -> ChatResponse:
    """Parse raw LLM text into a ChatResponse.

    Tolerates markdown code fences. If the full schema fails to validate but the JSON still has a
    usable string ``message``, returns that message with no actions (never executes partially-valid
    actions). Raises LLMOutputError if nothing usable can be recovered.
    """
    if not raw or not raw.strip():
        raise LLMOutputError("Empty LLM response")

    text = raw.strip()
    fence = _FENCE_RE.match(text)
    if fence:
        text = fence.group(1)

    try:
        return ChatResponse.model_validate_json(text)
    except ValidationError as exc:
        logger.warning("LLM output failed schema validation: %s", exc)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMOutputError(f"LLM output is not valid JSON: {exc}") from exc

    if isinstance(data, dict) and isinstance(data.get("message"), str) and data["message"].strip():
        return ChatResponse(message=data["message"])
    raise LLMOutputError("LLM output has no usable 'message' field")
