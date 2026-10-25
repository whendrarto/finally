"""LiteLLM -> OpenRouter -> Cerebras call with structured output."""

from __future__ import annotations

import asyncio

from litellm import completion

from .schema import ChatResponse, parse_llm_output

MODEL = "openrouter/openai/gpt-oss-120b"
EXTRA_BODY = {"provider": {"order": ["cerebras"]}}


def _call_llm_sync(messages: list[dict]) -> ChatResponse:
    response = completion(
        model=MODEL,
        messages=messages,
        response_format=ChatResponse,
        reasoning_effort="low",
        extra_body=EXTRA_BODY,
    )
    return parse_llm_output(response.choices[0].message.content)


async def call_llm(messages: list[dict]) -> ChatResponse:
    """Call the LLM without blocking the event loop. Raises on network/parse failure."""
    return await asyncio.to_thread(_call_llm_sync, messages)
