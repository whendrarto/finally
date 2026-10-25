import { expect, test } from "@playwright/test";
import { apiTrade, ensureNotWatched, ensureWatched, heldQuantity, waitForPrice } from "./helpers";

// State-changing REST contract checks; numbered last so 01-fresh-start sees a pristine database.

test.describe("REST API contract (mutating)", () => {
  test("watchlist add 201 -> delete 204", async ({ request }) => {
    await ensureNotWatched(request, "ORCL");
    const res = await request.post("/api/watchlist", { data: { ticker: "orcl" } });
    expect(res.status()).toBe(201);
    const item = await res.json();
    expect(item.ticker).toBe("ORCL");
    expect(Object.keys(item)).toEqual(expect.arrayContaining(["price", "previous_price", "change", "change_percent", "direction"]));
    const del = await request.delete("/api/watchlist/ORCL");
    expect(del.status()).toBe(204);
  });

  test("trade buy then sell round trip", async ({ request }) => {
    await ensureWatched(request, "AMZN");
    await waitForPrice(request, "AMZN");
    const held = await heldQuantity(request, "AMZN");
    const body = await apiTrade(request, "AMZN", "buy", 0.5);
    expect(body.trade).toMatchObject({ ticker: "AMZN", side: "buy", quantity: 0.5 });
    expect(typeof body.trade.price).toBe("number");
    expect(typeof body.trade.id).toBe("string");
    expect(typeof body.trade.executed_at).toBe("string");
    expect(body.portfolio.positions.find((p: { ticker: string }) => p.ticker === "AMZN").quantity).toBeCloseTo(held + 0.5, 6);

    const sold = await apiTrade(request, "AMZN", "sell", 0.5);
    expect(sold.trade.side).toBe("sell");
    expect(await heldQuantity(request, "AMZN")).toBeCloseTo(held, 6);

    const hist = await (await request.get("/api/portfolio/history")).json();
    expect(hist.snapshots.length).toBeGreaterThan(0);
  });

  test("POST /api/chat (mock) returns contract shape", async ({ request }) => {
    const res = await request.post("/api/chat", { data: { message: "hello" } });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(typeof body.message).toBe("string");
    expect(body.message.startsWith("[mock] ")).toBe(true);
    expect(Array.isArray(body.trades)).toBe(true);
    expect(Array.isArray(body.watchlist_changes)).toBe(true);
  });
});
