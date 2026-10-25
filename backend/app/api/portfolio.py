"""Portfolio endpoints: positions, trades, value history."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app import db
from app.services import portfolio as portfolio_service
from app.services.portfolio import TradeError

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


class TradeRequest(BaseModel):
    ticker: str
    quantity: float
    side: str


@router.get("")
async def get_portfolio(request: Request) -> dict:
    return await asyncio.to_thread(portfolio_service.get_portfolio, request.app.state.price_cache)


@router.post("/trade")
async def trade(body: TradeRequest, request: Request) -> dict:
    cache = request.app.state.price_cache
    try:
        trade = await asyncio.to_thread(
            portfolio_service.execute_trade, cache, body.ticker, body.side, body.quantity
        )
    except TradeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    portfolio = await asyncio.to_thread(portfolio_service.get_portfolio, cache)
    return {"trade": trade, "portfolio": portfolio}


@router.get("/history")
async def history() -> dict:
    snapshots = await asyncio.to_thread(db.get_snapshots)
    return {
        "snapshots": [
            {"total_value": s["total_value"], "recorded_at": s["recorded_at"]} for s in snapshots
        ]
    }
