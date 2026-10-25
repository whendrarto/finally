# FinAlly — AI Trading Workstation

A visually stunning AI-powered trading workstation that streams live market data, simulates portfolio trading, and integrates an LLM chat assistant that can analyze positions and execute trades via natural language.

Built entirely by coding agents as a capstone project for an agentic AI coding course.

## Features

- **Live price streaming** via SSE with green/red flash animations
- **Simulated portfolio** — $10k virtual cash, market orders, instant fills
- **Portfolio visualizations** — heatmap (treemap), P&L chart, positions table
- **AI chat assistant** — analyzes holdings, suggests and auto-executes trades
- **Watchlist management** — track tickers manually or via AI
- **Dark terminal aesthetic** — Bloomberg-inspired, data-dense layout

## Architecture

Single Docker container serving everything on port 8000:

- **Frontend**: Next.js (static export) with TypeScript and Tailwind CSS
- **Backend**: FastAPI (Python/uv) with SSE streaming
- **Database**: SQLite with lazy initialization
- **AI**: LiteLLM → OpenRouter (Cerebras inference) with structured outputs
- **Market data**: Built-in GBM simulator (default) or Massive API (optional)

## Quick Start

Prerequisite: [Docker](https://www.docker.com/products/docker-desktop/) running.

```bash
# 1. Configure (optional: without .env the app still runs with the simulator, but AI chat needs a key)
cp .env.example .env
# edit .env and set OPENROUTER_API_KEY

# 2. Start (builds the image on first run, then opens http://localhost:8000)
./scripts/start_mac.sh            # macOS / Linux
.\scripts\start_windows.ps1       # Windows PowerShell

# 3. Stop (your portfolio data is kept in the `finally-data` Docker volume)
./scripts/stop_mac.sh
.\scripts\stop_windows.ps1
```

Start script options: `--build` / `-Build` forces an image rebuild (use after pulling changes);
`--no-open` / `-NoOpen` skips opening the browser. Both scripts are safe to run repeatedly.

If Windows blocks the script, run it once with
`powershell -ExecutionPolicy Bypass -File .\scripts\start_windows.ps1`.

### Alternatives

```bash
# Docker Compose
docker compose up -d --build
docker compose down               # keeps the volume; add -v to wipe data

# Plain Docker
docker build -t finally .
docker run -d --name finally -v finally-data:/app/db -p 8000:8000 --env-file .env finally
```

To reset all data: stop the app, then `docker volume rm finally-data`.

### Local development (without Docker)

```bash
# Backend (from backend/) - serves the API on :8000
uv sync --extra dev
uv run uvicorn app.main:app --reload --port 8000

# Frontend (from frontend/) - build the static export, then let the backend serve it
npm install
npm run build
rm -rf ../backend/static && cp -r out ../backend/static
```

Backend tests: `cd backend && uv run --extra dev pytest`.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | Yes | OpenRouter API key for AI chat |
| `MASSIVE_API_KEY` | No | Massive (Polygon.io) key for real market data; omit to use simulator |
| `LLM_MOCK` | No | Set `true` for deterministic mock LLM responses (testing) |

The SQLite database lives at `/app/db/finally.db` inside the container (the `finally-data` volume)
and is created and seeded automatically on first start.

## Project Structure

```
finally/
├── frontend/    # Next.js static export
├── backend/     # FastAPI uv project
├── planning/    # Project documentation and agent contracts
├── test/        # Playwright E2E tests
├── db/          # SQLite volume mount (runtime)
└── scripts/     # Start/stop helpers
```

## License

See [LICENSE](LICENSE).
