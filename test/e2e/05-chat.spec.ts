import { expect, test } from "@playwright/test";
import { ensureNotWatched, ensureWatched, getWatchlist, heldQuantity, openApp, tid, waitForPrice } from "./helpers";

// Requires the backend to run with LLM_MOCK=true (see TEAM_CONTRACT.md "Mock mode").
test.describe("AI chat (mocked LLM)", () => {
  async function send(page: import("@playwright/test").Page, text: string) {
    const before = await page.locator('[data-testid="chat-message"][data-role="assistant"]').count();
    await tid(page, "chat-input").fill(text);
    await tid(page, "chat-send").click();
    const reply = page.locator('[data-testid="chat-message"][data-role="assistant"]').nth(before);
    await expect(reply).toBeVisible({ timeout: 20_000 });
    await expect(tid(page, "chat-loading")).toHaveCount(0);
    return reply;
  }

  test("greeting gets a mock reply", async ({ page }) => {
    await openApp(page);
    await expect(tid(page, "chat-panel")).toBeVisible();
    const reply = await send(page, "hello there");
    await expect(reply).toContainText("FinAlly");
    await expect(page.locator('[data-testid="chat-message"][data-role="user"]').last()).toContainText("hello there");
  });

  test("'buy 1 AAPL' executes a trade shown inline and updates the portfolio", async ({ page, request }) => {
    await ensureWatched(request, "AAPL");
    await waitForPrice(request, "AAPL");
    const heldBefore = await heldQuantity(request, "AAPL");

    await openApp(page);
    const actionsBefore = await tid(page, "chat-action").count();
    const reply = await send(page, "buy 1 AAPL");
    await expect(reply).toContainText("[mock]");

    await expect(tid(page, "chat-action")).toHaveCount(actionsBefore + 1);
    const action = tid(page, "chat-action").last();
    await expect(action).toContainText("AAPL");
    await expect(action).not.toHaveAttribute("data-status", "failed");

    await expect.poll(() => heldQuantity(request, "AAPL")).toBeCloseTo(heldBefore + 1, 6);
    await expect(tid(page, `position-row-AAPL`)).toBeVisible();
  });

  test("failed trade is reported inline", async ({ page }) => {
    await openApp(page);
    await send(page, "sell 99999 NFLX");
    const action = tid(page, "chat-action").last();
    await expect(action).toContainText("NFLX");
    await expect(action).toHaveAttribute("data-status", "failed");
  });

  test("watchlist add/remove via chat", async ({ page, request }) => {
    const ticker = "SHOP";
    await ensureNotWatched(request, ticker);
    await openApp(page);

    await send(page, `add ${ticker}`);
    await expect(tid(page, `watchlist-row-${ticker}`)).toBeVisible();
    await expect.poll(() => getWatchlist(request)).toContain(ticker);

    await send(page, `remove ${ticker}`);
    await expect(tid(page, `watchlist-row-${ticker}`)).toHaveCount(0);
    await expect.poll(() => getWatchlist(request)).not.toContain(ticker);
  });

  test("conversation history persists across reloads", async ({ page }) => {
    await openApp(page);
    await send(page, "history check ping");
    await page.reload();
    await expect(page.locator('[data-testid="chat-message"][data-role="user"]').filter({ hasText: "history check ping" }).first()).toBeVisible();
  });
});
