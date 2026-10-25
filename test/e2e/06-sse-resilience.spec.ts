import { expect, test } from "@playwright/test";
import { tid } from "./helpers";

const STREAM = "**/api/stream/prices";

test.describe("SSE resilience", () => {
  test("status leaves 'connected' while the stream is unreachable and recovers afterwards", async ({ page }) => {
    // Block the stream from the very first request
    await page.route(STREAM, (route) => route.abort("connectionrefused"));
    await page.goto("/");
    const status = tid(page, "connection-status");
    await expect(status).toHaveAttribute("data-status", /reconnecting|disconnected/, { timeout: 20_000 });

    // Let it through again: EventSource / the app's retry must reconnect on its own (no reload)
    await page.unroute(STREAM);
    await expect(status).toHaveAttribute("data-status", "connected", { timeout: 30_000 });

    const price = tid(page, "watchlist-price-AAPL");
    await expect(price).toHaveText(/\d+\.\d{2}/, { timeout: 15_000 });
    const first = await price.innerText();
    await expect.poll(() => price.innerText(), { timeout: 15_000 }).not.toBe(first);
  });

  test("drops mid-session and reconnects", async ({ page }) => {
    // An already-open EventSource can't be cut from outside the page (setOffline doesn't affect it),
    // so the first stream request is served as a finite response: one price event, then the server
    // closes the connection. Reconnect attempts are refused until we restore the network.
    const SENTINEL = 123.45;
    let calls = 0;
    let down = true;
    await page.route(STREAM, async (route) => {
      calls += 1;
      if (calls === 1) {
        const ts = Date.now() / 1000;
        const event = {
          AAPL: { ticker: "AAPL", price: SENTINEL, previous_price: SENTINEL, timestamp: ts, change: 0, change_percent: 0, direction: "flat" },
        };
        await route.fulfill({
          status: 200,
          headers: { "content-type": "text/event-stream", "cache-control": "no-cache" },
          body: `retry: 500\n\ndata: ${JSON.stringify(event)}\n\n`,
        });
      } else if (down) {
        await route.abort("internetdisconnected");
      } else {
        await route.continue();
      }
    });

    await page.goto("/");
    const status = tid(page, "connection-status");
    const price = tid(page, "watchlist-price-AAPL");

    // The session was live (our event arrived) and then the stream dropped
    await expect(price).toHaveText(SENTINEL.toFixed(2), { timeout: 20_000 });
    await expect(status).toHaveAttribute("data-status", /reconnecting|disconnected/, { timeout: 20_000 });
    await expect.poll(() => calls, { timeout: 20_000, message: "client should retry the stream" }).toBeGreaterThan(1);

    // Network comes back: the client reconnects by itself and real prices flow again
    down = false;
    await expect(status).toHaveAttribute("data-status", "connected", { timeout: 30_000 });
    await expect.poll(() => price.innerText(), { timeout: 15_000 }).not.toBe(SENTINEL.toFixed(2));
  });
});
