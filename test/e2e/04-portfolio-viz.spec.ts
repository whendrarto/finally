import { expect, test } from "@playwright/test";
import { apiTrade, ensureWatched, getPortfolio, openApp, tid, waitForPrice } from "./helpers";

test.describe("portfolio visualisation", () => {
  test.beforeAll(async ({ request }) => {
    await ensureWatched(request, "V");
    await waitForPrice(request, "V");
    await apiTrade(request, "V", "buy", 1); // guarantees a position and a snapshot
  });

  test("heatmap renders a tile per position, coloured by P&L", async ({ page, request }) => {
    await openApp(page);
    const heatmap = tid(page, "portfolio-heatmap");
    await expect(heatmap).toBeVisible();

    const box = await heatmap.boundingBox();
    expect(box && box.width * box.height).toBeGreaterThan(0);

    const portfolio = await getPortfolio(request);
    expect(portfolio.positions.length).toBeGreaterThan(0);
    for (const p of portfolio.positions) {
      const tile = tid(page, `heatmap-tile-${p.ticker}`);
      await expect(tile, `heatmap tile ${p.ticker}`).toHaveCount(1);
      await expect(tile).toHaveAttribute("data-pnl", /^(positive|negative|flat)$/);
    }

    // The rendered colour agrees with the tile's P&L sign: gains are never red, losses never green.
    // (Near-zero P&L may render neutral grey.)
    const tiles = await page.locator('[data-testid^="heatmap-tile-"]').evaluateAll((els) =>
      els.map((e) => {
        const [r, g] = (getComputedStyle(e).backgroundColor.match(/\d+(\.\d+)?/g) ?? []).map(Number);
        return { id: e.getAttribute("data-testid"), pnl: e.getAttribute("data-pnl"), r, g };
      }),
    );
    for (const t of tiles) {
      if (t.pnl === "positive") expect(t.r - t.g, `${t.id} is positive but red`).toBeLessThan(50);
      if (t.pnl === "negative") expect(t.g - t.r, `${t.id} is negative but green`).toBeLessThan(50);
    }

    // The sign matches the backend for every position whose P&L is clearly non-zero.
    // Prices move between our API read and the UI render, so poll; fresh positions may all be ~0 (vacuous).
    await expect
      .poll(
        async () => {
          const pf = await getPortfolio(request);
          const mismatches: string[] = [];
          for (const p of pf.positions) {
            if (Math.abs(p.unrealized_pnl_percent) < 0.1) continue;
            const attr = await tid(page, `heatmap-tile-${p.ticker}`).getAttribute("data-pnl");
            const expected = p.unrealized_pnl > 0 ? "positive" : "negative";
            if (attr !== expected) mismatches.push(`${p.ticker}: ui=${attr} api=${expected}`);
          }
          return mismatches;
        },
        { timeout: 20_000, message: "heatmap P&L signs should match the backend" },
      )
      .toEqual([]);
  });

  test("P&L chart renders with data points", async ({ page, request }) => {
    const res = await request.get("/api/portfolio/history");
    expect(res.status()).toBe(200);
    const { snapshots } = await res.json();
    expect(snapshots.length).toBeGreaterThan(0);

    await openApp(page);
    const chart = tid(page, "pnl-chart");
    await expect(chart).toBeVisible();
    await expect(chart.locator("canvas, svg").first()).toBeVisible();
    await expect.poll(async () => Number(await chart.getAttribute("data-points"))).toBeGreaterThan(0);
  });

  test("positions table lists every position", async ({ page, request }) => {
    await openApp(page);
    const portfolio = await getPortfolio(request);
    await expect(tid(page, "positions-table")).toBeVisible();
    for (const p of portfolio.positions) {
      await expect(tid(page, `position-row-${p.ticker}`)).toBeVisible();
    }
  });
});
