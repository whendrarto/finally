import { expect, test } from "@playwright/test";
import { ensureNotWatched, getWatchlist, openApp, tid } from "./helpers";

const NEW_TICKER = "PYPL";

test.describe("watchlist", () => {
  test.beforeEach(async ({ request }) => {
    await ensureNotWatched(request, NEW_TICKER);
  });

  test.afterAll(async ({ request }) => {
    await ensureNotWatched(request, NEW_TICKER);
  });

  test("add and remove a ticker", async ({ page, request }) => {
    await openApp(page);
    await expect(tid(page, `watchlist-row-${NEW_TICKER}`)).toHaveCount(0);

    // Add (lowercase input should be normalised)
    await tid(page, "watchlist-add-input").fill(NEW_TICKER.toLowerCase());
    await tid(page, "watchlist-add-button").click();
    await expect(tid(page, `watchlist-row-${NEW_TICKER}`)).toBeVisible();
    await expect.poll(() => getWatchlist(request)).toContain(NEW_TICKER);
    // The new ticker starts receiving streamed prices
    await expect(tid(page, `watchlist-price-${NEW_TICKER}`)).toHaveText(/\d+\.\d{2}/, { timeout: 15_000 });

    // Survives a reload (persisted)
    await page.reload();
    await expect(tid(page, `watchlist-row-${NEW_TICKER}`)).toBeVisible();

    // Remove
    await tid(page, `watchlist-row-${NEW_TICKER}`).hover();
    await tid(page, `watchlist-remove-${NEW_TICKER}`).click();
    await expect(tid(page, `watchlist-row-${NEW_TICKER}`)).toHaveCount(0);
    await expect.poll(() => getWatchlist(request)).not.toContain(NEW_TICKER);

    await page.reload();
    await expect(tid(page, "watchlist-row-AAPL")).toBeVisible();
    await expect(tid(page, `watchlist-row-${NEW_TICKER}`)).toHaveCount(0);
  });
});
