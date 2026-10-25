import { expect, test } from "@playwright/test";
import { getPortfolio } from "./helpers";

// REST contract from planning/TEAM_CONTRACT.md — read-only and rejected-request checks only, so
// 01-fresh-start still sees a pristine database. Mutating checks are in 07-api-mutations.
test.describe("REST API contract (read-only)", () => {
  test("GET /api/health", async ({ request }) => {
    const res = await request.get("/api/health");
    expect(res.status()).toBe(200);
    expect(await res.json()).toEqual({ status: "ok" });
  });

  test("GET /api/portfolio shape", async ({ request }) => {
    const p = await getPortfolio(request);
    for (const k of ["cash_balance", "positions_value", "total_value", "unrealized_pnl", "unrealized_pnl_percent"]) {
      expect(typeof (p as unknown as Record<string, unknown>)[k], k).toBe("number");
    }
    expect(Array.isArray(p.positions)).toBe(true);
    expect(p.total_value).toBeCloseTo(p.cash_balance + p.positions_value, 4);
  });

  test("GET /api/watchlist shape", async ({ request }) => {
    const res = await request.get("/api/watchlist");
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body.tickers)).toBe(true);
    expect(body.tickers.length).toBeGreaterThan(0);
    for (const t of body.tickers) {
      expect(Object.keys(t)).toEqual(
        expect.arrayContaining(["ticker", "price", "previous_price", "change", "change_percent", "direction"]),
      );
    }
  });

  test("GET /api/portfolio/history shape", async ({ request }) => {
    const res = await request.get("/api/portfolio/history");
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body.snapshots)).toBe(true);
    for (const s of body.snapshots) {
      expect(typeof s.total_value).toBe("number");
      expect(typeof s.recorded_at).toBe("string");
    }
  });

  test("GET /api/chat/history shape", async ({ request }) => {
    const res = await request.get("/api/chat/history");
    expect(res.status()).toBe(200);
    expect(Array.isArray((await res.json()).messages)).toBe(true);
  });

  test("GET /api/stream/prices emits SSE price maps", async ({ page }) => {
    await page.goto("/api/health");
    const result = await page.evaluate(async () => {
      const ctrl = new AbortController();
      const res = await fetch("/api/stream/prices", { signal: ctrl.signal });
      const reader = res.body!.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      const deadline = Date.now() + 10_000;
      while (Date.now() < deadline) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const m = buf.match(/data: (.+)\n\n/);
        if (m) {
          ctrl.abort();
          return { contentType: res.headers.get("content-type"), data: JSON.parse(m[1]) };
        }
      }
      ctrl.abort();
      return { contentType: res.headers.get("content-type"), data: null };
    });
    expect(result.contentType).toContain("text/event-stream");
    expect(result.data).not.toBeNull();
    const aapl = result.data.AAPL;
    expect(aapl).toBeTruthy();
    expect(Object.keys(aapl)).toEqual(expect.arrayContaining(["ticker", "price", "previous_price", "timestamp", "direction"]));
  });
});

test.describe("REST API contract (validation, no state change)", () => {
  test("trade validation errors return 400 with detail", async ({ request }) => {
    const cases = [
      { ticker: "AAPL", side: "buy", quantity: 1_000_000 }, // insufficient cash
      { ticker: "AAPL", side: "sell", quantity: 1_000_000 }, // insufficient shares
      { ticker: "AAPL", side: "buy", quantity: 0 },
      { ticker: "AAPL", side: "buy", quantity: -1 },
      { ticker: "AAPL", side: "hold", quantity: 1 },
      { ticker: "not a ticker!", side: "buy", quantity: 1 },
    ];
    for (const data of cases) {
      const res = await request.post("/api/portfolio/trade", { data });
      expect([400, 422], `${JSON.stringify(data)} -> ${res.status()}`).toContain(res.status());
      const body = await res.json();
      expect(body.detail, JSON.stringify(data)).toBeTruthy();
    }
  });

  test("watchlist validation: invalid 400, duplicate 409, missing delete 404", async ({ request }) => {
    const invalid = await request.post("/api/watchlist", { data: { ticker: "bad ticker!" } });
    expect([400, 422]).toContain(invalid.status());
    expect((await invalid.json()).detail).toBeTruthy();

    const dup = await request.post("/api/watchlist", { data: { ticker: "AAPL" } });
    expect(dup.status()).toBe(409);
    expect((await dup.json()).detail).toBeTruthy();

    const missing = await request.delete("/api/watchlist/ZZZQ");
    expect(missing.status()).toBe(404);
  });
});
