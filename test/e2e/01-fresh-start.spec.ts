import { expect, test } from "@playwright/test";
import { DEFAULT_TICKERS, getPortfolio, openApp, readMoney, tid } from "./helpers";

// Runs first (file order, single worker) so the docker-compose run sees a pristine database.
test.describe("fresh start", () => {
  test("shows the default watchlist, $10k cash and live prices", async ({ page, request }) => {
    const portfolio = await getPortfolio(request);
    const pristine = portfolio.positions.length === 0 && portfolio.cash_balance === 10000;

    await openApp(page);

    // Ten default tickers in the watchlist
    const watchlist = tid(page, "watchlist");
    await expect(watchlist).toBeVisible();
    for (const t of DEFAULT_TICKERS) {
      await expect(tid(page, `watchlist-row-${t}`), `watchlist row ${t}`).toBeVisible();
    }
    if (pristine) {
      await expect(watchlist.locator('[data-testid^="watchlist-row-"]')).toHaveCount(DEFAULT_TICKERS.length);
    }

    // Cash in the header matches the backend; $10,000 on a fresh database
    await expect.poll(() => readMoney(tid(page, "header-cash"))).toBeCloseTo(portfolio.cash_balance, 2);
    if (pristine) {
      await expect(tid(page, "header-cash")).toContainText("10,000");
      await expect.poll(() => readMoney(tid(page, "header-total-value"))).toBeCloseTo(10000, 2);
    } else {
      test.info().annotations.push({ type: "note", description: "DB not pristine; skipped exact $10k assertion" });
    }

    // Prices are streaming: a price cell shows a number and changes over time
    const price = tid(page, "watchlist-price-AAPL");
    await expect(price).toHaveText(/\d+\.\d{2}/);
    const first = await price.innerText();
    await expect.poll(() => price.innerText(), { timeout: 15_000, message: "AAPL price should update" }).not.toBe(first);
  });

  test("API reports the seeded state on a fresh database", async ({ request }) => {
    const portfolio = await getPortfolio(request);
    test.skip(portfolio.positions.length > 0 || portfolio.cash_balance !== 10000, "database is not fresh");
    expect(portfolio.cash_balance).toBe(10000);
    expect(portfolio.total_value).toBeCloseTo(10000, 2);
    const wl = await (await request.get("/api/watchlist")).json();
    expect(wl.tickers.map((t: { ticker: string }) => t.ticker).sort()).toEqual([...DEFAULT_TICKERS].sort());
  });

  test("clicking a watchlist ticker selects it in the main chart", async ({ page }) => {
    await openApp(page);
    await tid(page, "watchlist-row-MSFT").click();
    await expect(tid(page, "main-chart")).toHaveAttribute("data-ticker", "MSFT");
    await tid(page, "watchlist-row-TSLA").click();
    await expect(tid(page, "main-chart")).toHaveAttribute("data-ticker", "TSLA");
  });
});
