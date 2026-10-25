import { APIRequestContext, Locator, Page, expect } from "@playwright/test";

export const DEFAULT_TICKERS = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"];

export interface Position {
  ticker: string;
  quantity: number;
  avg_cost: number;
  current_price: number | null;
  market_value: number;
  unrealized_pnl: number;
  unrealized_pnl_percent: number;
}

export interface Portfolio {
  cash_balance: number;
  positions_value: number;
  total_value: number;
  unrealized_pnl: number;
  unrealized_pnl_percent: number;
  positions: Position[];
}

export const tid = (page: Page, id: string): Locator => page.getByTestId(id);

/** Parse "$10,000.00" / "-$1,234.5" / "10000" into a number. Prefers a data-value attribute if present. */
export async function readMoney(locator: Locator): Promise<number> {
  const raw = await locator.getAttribute("data-value");
  if (raw !== null && raw.trim() !== "" && !Number.isNaN(Number(raw))) return Number(raw);
  const text = (await locator.innerText()).replace(/[^0-9.\-]/g, "");
  return parseFloat(text);
}

export async function getPortfolio(request: APIRequestContext): Promise<Portfolio> {
  const res = await request.get("/api/portfolio");
  expect(res.status(), await res.text()).toBe(200);
  return res.json();
}

export async function heldQuantity(request: APIRequestContext, ticker: string): Promise<number> {
  const p = await getPortfolio(request);
  return p.positions.find((x) => x.ticker === ticker)?.quantity ?? 0;
}

export async function getWatchlist(request: APIRequestContext): Promise<string[]> {
  const res = await request.get("/api/watchlist");
  expect(res.status()).toBe(200);
  const body = await res.json();
  return body.tickers.map((t: { ticker: string }) => t.ticker);
}

/** Wait until the backend has a cached price for the ticker (the simulator needs a tick after an add). */
export async function waitForPrice(request: APIRequestContext, ticker: string): Promise<number> {
  let price: number | null = null;
  await expect
    .poll(
      async () => {
        const res = await request.get("/api/watchlist");
        const body = await res.json();
        price = body.tickers.find((t: { ticker: string }) => t.ticker === ticker)?.price ?? null;
        return price;
      },
      { timeout: 15_000, message: `price for ${ticker}` },
    )
    .not.toBeNull();
  return price as unknown as number;
}

export async function apiTrade(request: APIRequestContext, ticker: string, side: "buy" | "sell", quantity: number) {
  const res = await request.post("/api/portfolio/trade", { data: { ticker, side, quantity } });
  expect(res.status(), await res.text()).toBe(200);
  return res.json();
}

export async function ensureWatched(request: APIRequestContext, ticker: string) {
  const res = await request.post("/api/watchlist", { data: { ticker } });
  expect([201, 409], await res.text()).toContain(res.status());
}

export async function ensureNotWatched(request: APIRequestContext, ticker: string) {
  const res = await request.delete(`/api/watchlist/${ticker}`);
  expect([204, 404], await res.text()).toContain(res.status());
}

/** Restore the 10 default tickers so specs don't depend on each other's watchlist edits. */
export async function ensureDefaultWatchlist(request: APIRequestContext) {
  for (const t of DEFAULT_TICKERS) await ensureWatched(request, t);
}

/** Open the app and wait until the price stream is live. */
export async function openApp(page: Page) {
  await page.goto("/");
  await expect(tid(page, "connection-status")).toHaveAttribute("data-status", "connected", { timeout: 20_000 });
}
