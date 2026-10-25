import { expect, test } from "@playwright/test";
import { apiTrade, ensureWatched, getPortfolio, heldQuantity, openApp, readMoney, tid, waitForPrice } from "./helpers";

async function placeOrder(page: import("@playwright/test").Page, ticker: string, qty: number, side: "buy" | "sell") {
  await tid(page, "trade-ticker").fill(ticker);
  await tid(page, "trade-quantity").fill(String(qty));
  await tid(page, side === "buy" ? "trade-buy" : "trade-sell").click();
}

test.describe("trading", () => {
  test("buy shares: cash decreases and the position appears", async ({ page, request }) => {
    const ticker = "MSFT";
    await ensureWatched(request, ticker);
    await waitForPrice(request, ticker);
    const before = await getPortfolio(request);
    const heldBefore = before.positions.find((p) => p.ticker === ticker)?.quantity ?? 0;

    await openApp(page);
    await expect.poll(() => readMoney(tid(page, "header-cash"))).toBeCloseTo(before.cash_balance, 2);

    await placeOrder(page, ticker, 2, "buy");

    await expect.poll(() => heldQuantity(request, ticker)).toBeCloseTo(heldBefore + 2, 6);
    const after = await getPortfolio(request);
    expect(after.cash_balance).toBeLessThan(before.cash_balance);

    await expect(tid(page, `position-row-${ticker}`)).toBeVisible();
    await expect.poll(() => readMoney(tid(page, "header-cash"))).toBeCloseTo(after.cash_balance, 2);
    await expect(tid(page, "trade-error")).toHaveCount(0);
  });

  test("sell shares: cash increases, position shrinks then disappears", async ({ page, request }) => {
    const ticker = "JPM";
    await ensureWatched(request, ticker);
    await waitForPrice(request, ticker);
    await apiTrade(request, ticker, "buy", 3);
    const held = await heldQuantity(request, ticker);
    const before = await getPortfolio(request);

    await openApp(page);
    await expect(tid(page, `position-row-${ticker}`)).toBeVisible();

    // Partial sell
    await placeOrder(page, ticker, 1, "sell");
    await expect.poll(() => heldQuantity(request, ticker)).toBeCloseTo(held - 1, 6);
    const mid = await getPortfolio(request);
    expect(mid.cash_balance).toBeGreaterThan(before.cash_balance);
    await expect.poll(() => readMoney(tid(page, "header-cash"))).toBeCloseTo(mid.cash_balance, 2);
    await expect(tid(page, `position-row-${ticker}`)).toBeVisible();

    // Sell the rest — the row disappears
    await placeOrder(page, ticker, held - 1, "sell");
    await expect.poll(() => heldQuantity(request, ticker)).toBe(0);
    const after = await getPortfolio(request);
    expect(after.cash_balance).toBeGreaterThan(mid.cash_balance);
    await expect(tid(page, `position-row-${ticker}`)).toHaveCount(0);
  });

  test("rejected orders show an error and change nothing", async ({ page, request }) => {
    await openApp(page);
    const before = await getPortfolio(request);

    // Way more than $10k worth
    await placeOrder(page, "AAPL", 1_000_000, "buy");
    await expect(tid(page, "trade-error")).toBeVisible();

    // Selling something we don't hold
    await placeOrder(page, "NFLX", 1_000_000, "sell");
    await expect(tid(page, "trade-error")).toBeVisible();

    const after = await getPortfolio(request);
    expect(after.cash_balance).toBeCloseTo(before.cash_balance, 6);
    expect(after.positions.length).toBe(before.positions.length);
  });
});
