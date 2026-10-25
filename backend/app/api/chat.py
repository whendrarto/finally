"""Chat endpoints: talk to the FinAlly AI assistant."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app import llm

router = APIRouter(prefix="/api/chat", tags=["chat"])

MAX_MESSAGE_LENGTH = 4000


class ChatRequest(BaseModel):
    message: str


@router.post("")
async def chat(body: ChatRequest, request: Request) -> dict:
    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message must not be empty")
    if len(message) > MAX_MESSAGE_LENGTH:
        raise HTTPException(
            status_code=400, detail=f"Message must be at most {MAX_MESSAGE_LENGTH} characters"
        )
    state = request.app.state
    return await llm.handle_chat(message, state.price_cache, state.market_source)


@router.get("/history")
async def history() -> dict:
    return {"messages": await llm.get_history()}
