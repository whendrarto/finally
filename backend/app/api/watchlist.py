"""Watchlist endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app.services import watchlist as watchlist_service
from app.services.watchlist import WatchlistError

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

_STATUS = {"invalid": 400, "duplicate": 409, "not_found": 404}


class AddTickerRequest(BaseModel):
    ticker: str


@router.get("")
async def get_watchlist(request: Request) -> dict:
    return {"tickers": watchlist_service.get_watchlist(request.app.state.price_cache)}


@router.post("", status_code=201)
async def add_ticker(body: AddTickerRequest, request: Request) -> dict:
    try:
        return await watchlist_service.add_ticker(
            request.app.state.market_source, body.ticker, request.app.state.price_cache
        )
    except WatchlistError as exc:
        raise HTTPException(status_code=_STATUS[exc.code], detail=str(exc)) from None


@router.delete("/{ticker}", status_code=204)
async def remove_ticker(ticker: str, request: Request) -> Response:
    try:
        await watchlist_service.remove_ticker(
            request.app.state.market_source, request.app.state.price_cache, ticker
        )
    except WatchlistError as exc:
        raise HTTPException(status_code=_STATUS[exc.code], detail=str(exc)) from None
    return Response(status_code=204)
