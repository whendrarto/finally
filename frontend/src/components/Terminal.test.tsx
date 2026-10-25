import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Terminal } from "./Terminal";

// Canvas charts can't render in jsdom; stub the chart hook.
vi.mock("@/lib/chart", async (orig) => ({
  ...(await orig<typeof import("@/lib/chart")>()),
  useChart: () => ({ containerRef: { current: null }, ready: null }),
}));

class FakeEventSource {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSED = 2;
  static last: FakeEventSource | null = null;
  readyState = 0;
  onopen: (() => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(public url: string) {
    FakeEventSource.last = this;
  }
  close() {
    this.readyState = 2;
  }
  emit(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }
}

const json = (body: unknown, status = 200) =>
  Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));

let portfolio = {
  cash_balance: 10000,
  positions_value: 0,
  total_value: 10000,
  unrealized_pnl: 0,
  unrealized_pnl_percent: 0,
  positions: [] as unknown[],
};

beforeEach(() => {
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      if (url === "/api/watchlist" && method === "GET")
        return json({
          tickers: [
            { ticker: "AAPL", price: 190, previous_price: 190, change: 0, change_percent: 0, direction: "flat" },
            { ticker: "MSFT", price: 410, previous_price: 410, change: 0, change_percent: 0, direction: "flat" },
          ],
        });
      if (url === "/api/portfolio") return json(portfolio);
      if (url === "/api/portfolio/history") return json({ snapshots: [] });
      if (url === "/api/chat/history") return json({ messages: [] });
      if (url === "/api/portfolio/trade") {
        portfolio = {
          ...portfolio,
          cash_balance: 9810,
          positions: [
            { ticker: "AAPL", quantity: 1, avg_cost: 190, current_price: 190, market_value: 190, unrealized_pnl: 0, unrealized_pnl_percent: 0 },
          ],
        };
        return json({
          trade: { id: "t1", ticker: "AAPL", side: "buy", quantity: 1, price: 190, executed_at: "" },
          portfolio,
        });
      }
      if (url === "/api/chat")
        return json({
          message: "[mock] Bought 1 AAPL",
          trades: [{ ticker: "AAPL", side: "buy", quantity: 1, price: 190, status: "executed", error: null }],
          watchlist_changes: [],
        });
      return json({ detail: "not found" }, 404);
    }),
  );
});

afterEach(() => vi.unstubAllGlobals());

describe("Terminal", () => {
  it("loads data, streams prices, and executes a manual trade", async () => {
    render(<Terminal />);
    await waitFor(() => expect(screen.getByTestId("header-cash")).toHaveTextContent("$10,000.00"));
    expect(screen.getByTestId("watchlist-row-AAPL")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("main-chart")).toHaveAttribute("data-ticker", "AAPL"));
    expect(screen.getByTestId("connection-status")).toHaveAttribute("data-status", "reconnecting");

    act(() => {
      FakeEventSource.last!.onopen?.();
      FakeEventSource.last!.emit({
        AAPL: { ticker: "AAPL", price: 191.5, previous_price: 190, timestamp: 1, change: 1.5, change_percent: 0.79, direction: "up" },
      });
    });
    expect(screen.getByTestId("connection-status")).toHaveAttribute("data-status", "connected");
    expect(screen.getByTestId("watchlist-price-AAPL")).toHaveTextContent("191.50");

    fireEvent.click(screen.getByTestId("watchlist-row-MSFT"));
    expect(screen.getByTestId("main-chart")).toHaveAttribute("data-ticker", "MSFT");
    expect(screen.getByTestId("trade-ticker")).toHaveValue("MSFT");

    fireEvent.change(screen.getByTestId("trade-ticker"), { target: { value: "AAPL" } });
    fireEvent.change(screen.getByTestId("trade-quantity"), { target: { value: "1" } });
    await act(async () => fireEvent.click(screen.getByTestId("trade-buy")));
    await waitFor(() => expect(screen.getByTestId("position-row-AAPL")).toBeInTheDocument());
    expect(screen.getByTestId("header-cash")).toHaveTextContent("$9,810.00");
  });

  it("sends a chat message and shows the reply with inline actions", async () => {
    render(<Terminal />);
    await waitFor(() => expect(screen.getByTestId("header-cash")).toBeInTheDocument());
    fireEvent.change(screen.getByTestId("chat-input"), { target: { value: "buy 1 AAPL" } });
    fireEvent.click(screen.getByTestId("chat-send"));
    expect(screen.getByTestId("chat-loading")).toBeInTheDocument();
    await waitFor(() => expect(screen.getAllByTestId("chat-message")).toHaveLength(2));
    expect(screen.getByTestId("chat-action")).toHaveTextContent("AAPL");
    expect(screen.queryByTestId("chat-loading")).toBeNull();
  });
});
