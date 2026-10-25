# FinAlly — Team Contract

Shared contract for the agent team. PLAN.md is the spec; this file pins down the interfaces between
team members so everyone can build in parallel. If you need to change anything here, edit this file
AND message the affected teammates.

## Team & File Ownership

Only edit files you own. Need a change elsewhere? Message the owner.

| Member (agent name) | Owns |
|---|---|
| `db-engineer` | `backend/app/db/**`, `backend/tests/db/**` |
| `backend-engineer` | `backend/app/main.py`, `backend/app/api/**` (except `chat.py`), `backend/app/services/**`, `backend/tests/api/**`, `backend/tests/services/**`, `backend/CLAUDE.md` |
| `llm-engineer` | `backend/app/llm/**`, `backend/app/api/chat.py`, `backend/tests/llm/**` |
| `frontend-engineer` | `frontend/**` |
| `devops-engineer` | `Dockerfile`, `.dockerignore`, `docker-compose.yml`, `scripts/**`, `.env.example`, `db/.gitkeep`, `.gitignore`, `README.md` |
| `integration-tester` | `test/**` |

`backend/app/market/**` is complete — do not modify without messaging the lead.
`backend/pyproject.toml` / `uv.lock`: `backend-engineer` owns them; dependencies `litellm`, `pydantic`,
`python-dotenv`, `httpx` are already added. Ask `backend-engineer` for any additional dependency.

## Runtime Conventions

- Python package root is `backend/app`. Run from `backend/`: `uv run uvicorn app.main:app --port 8000`.
- `.env` lives in the project root; `app/main.py` loads it with `python-dotenv` (search upward, don't fail if missing).
- DB path: env `FINALLY_DB_PATH`, default `<project root>/db/finally.db` (resolve relative to the
  `backend/` dir's parent). In Docker, `/app/db/finally.db`.
- Static frontend: env `STATIC_DIR`, default `backend/static`. If the dir exists, FastAPI mounts it at `/`
  with `html=True` **after** all `/api` routes. Next.js export output (`frontend/out`) is copied there.
- User id is always `"default"`.
- App state set in the FastAPI lifespan (`app/main.py`): `app.state.price_cache`, `app.state.market_source`.
  Startup: `init_db()`, start the market source with watchlist tickers ∪ position tickers, start the
  30-second snapshot task. Shutdown: stop both.

## DB Layer API (`app.db`, owner: db-engineer)

stdlib `sqlite3`, synchronous, one short-lived connection per call (or a thread-safe helper),
`PRAGMA foreign_keys=ON`, WAL mode. All timestamps ISO-8601 UTC strings. Schema exactly as PLAN.md §7.
Every function takes an optional `user_id: str = "default"` keyword.

```python
init_db(db_path: str | None = None) -> None          # idempotent: create tables + seed if empty
get_cash_balance() -> float
get_watchlist() -> list[str]                           # ordered by added_at
add_watchlist_ticker(ticker: str) -> bool              # False if already present
remove_watchlist_ticker(ticker: str) -> bool           # False if not present
get_positions() -> list[dict]                          # {ticker, quantity, avg_cost, updated_at}
get_position(ticker: str) -> dict | None
apply_trade(ticker, side, quantity, price, new_cash, new_quantity, new_avg_cost) -> dict
    # ONE transaction: insert trade row, set cash, upsert position (delete row if new_quantity == 0)
    # returns the trade: {id, ticker, side, quantity, price, executed_at}
get_trades(limit: int | None = None) -> list[dict]     # newest first
insert_snapshot(total_value: float) -> None
get_snapshots(limit: int | None = None) -> list[dict]  # {total_value, recorded_at}, oldest first
insert_chat_message(role: str, content: str, actions: dict | None = None) -> dict
get_chat_messages(limit: int = 20) -> list[dict]       # {id, role, content, actions(parsed), created_at}, oldest first
```

Tests must use a tmp DB via `init_db(tmp_path / "test.db")` (the module keeps the active path).

## Services (`app.services`, owner: backend-engineer)

```python
# app/services/portfolio.py
class TradeError(Exception): ...                       # message is user-facing
execute_trade(price_cache, ticker, side, quantity) -> dict   # validates, computes, calls db.apply_trade, records snapshot
get_portfolio(price_cache) -> dict                     # shape of GET /api/portfolio
# app/services/watchlist.py
class WatchlistError(Exception): ...
async add_ticker(market_source, ticker) -> dict        # validate, db add, market_source.add_ticker
async remove_ticker(market_source, price_cache, ticker) -> None  # keep streaming if a position is held
```

Validation: ticker uppercased, regex `^[A-Z][A-Z0-9.]{0,9}$`; quantity > 0 (fractional ok);
side in `buy|sell`; buy needs `cash >= qty*price`; sell needs `held >= qty` (tolerance 1e-9);
no cached price → error "No price available for X". avg_cost on buy is weighted; unchanged on sell.

## REST API (owner: backend-engineer, chat: llm-engineer)

Errors: non-2xx with `{"detail": "human readable message"}`.

| Method/Path | Request | Response |
|---|---|---|
| GET `/api/health` | — | `{"status": "ok"}` |
| GET `/api/portfolio` | — | `{cash_balance, positions_value, total_value, unrealized_pnl, unrealized_pnl_percent, positions: [{ticker, quantity, avg_cost, current_price, market_value, unrealized_pnl, unrealized_pnl_percent}]}` |
| POST `/api/portfolio/trade` | `{ticker, quantity, side}` | 200 `{trade: {id, ticker, side, quantity, price, executed_at}, portfolio: <GET /api/portfolio>}`; 400 on validation failure |
| GET `/api/portfolio/history` | — | `{snapshots: [{total_value, recorded_at}]}` |
| GET `/api/watchlist` | — | `{tickers: [{ticker, price, previous_price, change, change_percent, direction}]}` (price fields null if not yet priced) |
| POST `/api/watchlist` | `{ticker}` | 201 one item as above; 409 duplicate; 400 invalid |
| DELETE `/api/watchlist/{ticker}` | — | 204; 404 if absent |
| POST `/api/chat` | `{message}` | 200 `{message, trades: [{ticker, side, quantity, price, status: "executed"\|"failed", error}], watchlist_changes: [{ticker, action, status, error}]}` |
| GET `/api/chat/history` | — | `{messages: [{id, role, content, actions, created_at}]}` |
| GET `/api/stream/prices` | — | SSE (existing). Each event: `data: {"AAPL": {ticker, price, previous_price, timestamp, change, change_percent, direction}, ...}` — a map of ALL tickers |

Percent values are percentages (e.g. `2.5` means 2.5%).

## LLM (owner: llm-engineer)

`app/llm/` — follow `.claude/skills/cerebras/SKILL.md` (LiteLLM → `openrouter/openai/gpt-oss-120b`,
Cerebras provider, Pydantic structured output). Call `completion` via `asyncio.to_thread` (or `acompletion`).
Chat flow per PLAN.md §9. Trades/watchlist changes go through `app.services` (same validation as manual).
Store user message and assistant message (with `actions` = `{trades, watchlist_changes}` results) in DB.
On LLM error/malformed output: return 200 with an apologetic `message` and empty actions (log it).

**Mock mode (`LLM_MOCK=true`) — deterministic, relied on by E2E tests:**
- message matches `buy <qty> <TICKER>` (case-insensitive) → trade buy; `sell <qty> <TICKER>` → trade sell
- `add <TICKER>` / `watch <TICKER>` → watchlist add; `remove <TICKER>` / `unwatch <TICKER>` → remove
- actions are actually executed; reply `message` starts with `"[mock] "` and summarises what happened
- anything else → `"[mock] Hello! I'm FinAlly, your AI trading assistant. Your portfolio is worth $<total>."`

## Frontend ↔ E2E Test Hooks (owner: frontend-engineer, consumer: integration-tester)

Use these `data-testid`s (add more as needed and tell `integration-tester`):

- `connection-status` (with attribute `data-status="connected|reconnecting|disconnected"`)
- `header-total-value`, `header-cash`
- `watchlist`, `watchlist-row-<TICKER>`, `watchlist-price-<TICKER>`, `watchlist-remove-<TICKER>`,
  `watchlist-add-input`, `watchlist-add-button`
- `main-chart` (with `data-ticker`)
- `trade-ticker`, `trade-quantity`, `trade-buy`, `trade-sell`, `trade-error`
- `positions-table`, `position-row-<TICKER>`
- `portfolio-heatmap`, `pnl-chart`
- `chat-panel`, `chat-input`, `chat-send`, `chat-loading`, `chat-message` (each message; `data-role`),
  `chat-action` (each inline trade/watchlist confirmation)

## Done Criteria

- Each member: own unit tests pass; `uv run --extra dev ruff check app/ tests/` clean for backend code.
- `docker build` succeeds, container serves UI + API on :8000, scripts are idempotent.
- `integration-tester`: Playwright suite in `test/` passes against the container with `LLM_MOCK=true`,
  covering the PLAN.md §12 scenarios.
