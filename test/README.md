# FinAlly E2E tests

Playwright (TypeScript) suite covering PLAN.md §12. The backend must run with `LLM_MOCK=true`.
Specs run serially in file order against one shared database; `01-fresh-start` asserts the seeded
$10k state only when the database is pristine.

## In Docker (fresh DB every run)

```bash
docker compose -f test/docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from playwright
docker compose -f test/docker-compose.test.yml down
```

## Locally

```bash
# terminal 1 — backend with the frontend export in backend/static
cd backend
LLM_MOCK=true FINALLY_DB_PATH=/tmp/finally-e2e.db uv run uvicorn app.main:app --port 8000

# terminal 2
cd test
npm ci && npx playwright install chromium
npx playwright test            # BASE_URL defaults to http://localhost:8000
```

| Spec | Covers |
|---|---|
| `00-api` | REST contract: shapes, SSE event format, validation errors (no state change) |
| `01-fresh-start` | 10 default tickers, $10k, prices streaming, chart selection |
| `02-watchlist` | add + remove ticker via UI, persistence |
| `03-trading` | buy, sell (partial + full), rejected orders |
| `04-portfolio-viz` | heatmap tiles + P&L colouring, P&L chart, positions table |
| `05-chat` | mocked AI chat: reply, inline trade, failed trade, watchlist via chat, history |
| `06-sse-resilience` | connection status degrades and recovers when the stream is blocked |
| `07-api-mutations` | REST contract for state-changing calls |
