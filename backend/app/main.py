"""FinAlly FastAPI application: REST API, SSE stream, and static frontend."""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import os
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

load_dotenv(find_dotenv())  # project-root .env; real env vars take precedence

from app import db  # noqa: E402
from app.api import health, portfolio, watchlist  # noqa: E402
from app.market import PriceCache, create_market_data_source, create_stream_router  # noqa: E402
from app.services.portfolio import record_snapshot  # noqa: E402

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

BACKEND_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = Path(os.environ.get("STATIC_DIR", BACKEND_DIR / "static"))
SNAPSHOT_INTERVAL = 30.0


def _initial_tickers() -> list[str]:
    """Watchlist tickers plus any held position tickers, de-duplicated in order."""
    tickers = db.get_watchlist() + [p["ticker"] for p in db.get_positions()]
    return list(dict.fromkeys(tickers))


async def _snapshot_loop(price_cache: PriceCache, interval: float = SNAPSHOT_INTERVAL) -> None:
    while True:
        await asyncio.sleep(interval)
        try:
            await asyncio.to_thread(record_snapshot, price_cache)
        except Exception:
            logger.exception("Portfolio snapshot failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    price_cache: PriceCache = app.state.price_cache
    await asyncio.to_thread(db.init_db)

    market_source = create_market_data_source(price_cache)
    await market_source.start(await asyncio.to_thread(_initial_tickers))
    app.state.market_source = market_source

    snapshot_task = asyncio.create_task(_snapshot_loop(price_cache), name="portfolio-snapshots")
    logger.info("FinAlly started")
    try:
        yield
    finally:
        snapshot_task.cancel()
        with suppress(asyncio.CancelledError):
            await snapshot_task
        await market_source.stop()
        logger.info("FinAlly stopped")


def create_app() -> FastAPI:
    app = FastAPI(title="FinAlly", lifespan=lifespan)
    app.state.price_cache = PriceCache()

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = exc.errors()
        detail = "; ".join(
            f"{'.'.join(str(p) for p in e.get('loc', ())[1:]) or 'body'}: {e.get('msg')}"
            for e in errors
        ) or "Invalid request"
        return JSONResponse(status_code=400, content={"detail": detail})

    app.include_router(health.router)
    app.include_router(portfolio.router)
    app.include_router(watchlist.router)
    if importlib.util.find_spec("app.api.chat") is not None:
        from app.api import chat

        app.include_router(chat.router)
    else:
        logger.warning("app.api.chat not found; /api/chat disabled")
    app.include_router(create_stream_router(app.state.price_cache))

    if STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


app = create_app()
