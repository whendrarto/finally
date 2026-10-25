import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { revalue } from "@/lib/portfolio";
import type { ChatMessage, Portfolio } from "@/lib/types";
import { ChatPanel } from "./ChatPanel";
import { Header } from "./Header";
import { Heatmap, heatColor } from "./Heatmap";
import { PositionsTable } from "./PositionsTable";
import { TradeBar } from "./TradeBar";
import { Watchlist, WatchlistRow, type WatchRow } from "./Watchlist";

const portfolio: Portfolio = {
  cash_balance: 7000,
  positions_value: 3000,
  total_value: 10000,
  unrealized_pnl: 0,
  unrealized_pnl_percent: 0,
  positions: [
    { ticker: "AAPL", quantity: 10, avg_cost: 100, current_price: 100, market_value: 1000, unrealized_pnl: 0, unrealized_pnl_percent: 0 },
    { ticker: "TSLA", quantity: 4, avg_cost: 500, current_price: 500, market_value: 2000, unrealized_pnl: 0, unrealized_pnl_percent: 0 },
  ],
};
const live = revalue(portfolio, { AAPL: 120, TSLA: 450 })!;

describe("Header", () => {
  it("shows live total value, cash and connection status", () => {
    render(<Header portfolio={live} status="connected" />);
    expect(screen.getByTestId("header-total-value")).toHaveTextContent("$10,000.00");
    expect(screen.getByTestId("header-cash")).toHaveTextContent("$7,000.00");
    expect(screen.getByTestId("header-cash")).toHaveAttribute("data-value", "7000.00");
    expect(screen.getByTestId("connection-status")).toHaveAttribute("data-status", "connected");
  });

  it("reflects reconnecting and disconnected states", () => {
    const { rerender } = render(<Header portfolio={null} status="reconnecting" />);
    expect(screen.getByTestId("connection-status")).toHaveAttribute("data-status", "reconnecting");
    rerender(<Header portfolio={null} status="disconnected" />);
    expect(screen.getByTestId("connection-status")).toHaveTextContent("Offline");
  });
});

describe("WatchlistRow price flash", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  const row = (price: number): WatchRow => ({ ticker: "AAPL", price, changePercent: 1.5, history: [] });
  const renderRow = (price: number) => (
    <ul>
      <WatchlistRow row={row(price)} selected={false} onSelect={() => {}} onRemove={() => {}} />
    </ul>
  );

  it("flashes green on uptick, red on downtick, then clears", () => {
    const { rerender } = render(renderRow(100));
    const price = () => screen.getByTestId("watchlist-price-AAPL");
    expect(price()).not.toHaveClass("flash-up");
    expect(price()).toHaveTextContent("100.00");

    rerender(renderRow(101));
    expect(price()).toHaveClass("flash-up");

    rerender(renderRow(99));
    expect(price()).toHaveClass("flash-down");
    expect(price()).not.toHaveClass("flash-up");

    act(() => vi.advanceTimersByTime(700));
    expect(price()).not.toHaveClass("flash-down");
  });

  it("does not flash when the price is unchanged", () => {
    const { rerender } = render(renderRow(100));
    rerender(renderRow(100));
    expect(screen.getByTestId("watchlist-price-AAPL").className).not.toMatch(/flash-/);
  });
});

describe("Watchlist", () => {
  const rows: WatchRow[] = [
    { ticker: "AAPL", price: 190.12, changePercent: 0.5, history: [] },
    { ticker: "GOOGL", price: null, changePercent: null, history: [] },
  ];

  it("renders rows and handles select / remove / add", async () => {
    const onSelect = vi.fn();
    const onRemove = vi.fn();
    const onAdd = vi.fn().mockResolvedValue(null);
    render(<Watchlist rows={rows} selected="AAPL" onSelect={onSelect} onAdd={onAdd} onRemove={onRemove} />);

    expect(screen.getByTestId("watchlist-price-AAPL")).toHaveTextContent("190.12");
    expect(screen.getByTestId("watchlist-price-GOOGL")).toHaveTextContent("—");

    fireEvent.click(screen.getByTestId("watchlist-row-GOOGL"));
    expect(onSelect).toHaveBeenCalledWith("GOOGL");

    fireEvent.click(screen.getByTestId("watchlist-remove-AAPL"));
    expect(onRemove).toHaveBeenCalledWith("AAPL");
    expect(onSelect).toHaveBeenCalledTimes(1); // remove doesn't select

    fireEvent.change(screen.getByTestId("watchlist-add-input"), { target: { value: "pypl" } });
    await act(async () => fireEvent.click(screen.getByTestId("watchlist-add-button")));
    expect(onAdd).toHaveBeenCalledWith("PYPL");
  });

  it("shows the add error from the server", async () => {
    const onAdd = vi.fn().mockResolvedValue("AAPL is already in your watchlist");
    render(<Watchlist rows={rows} selected={null} onSelect={() => {}} onAdd={onAdd} onRemove={() => {}} />);
    fireEvent.change(screen.getByTestId("watchlist-add-input"), { target: { value: "AAPL" } });
    await act(async () => fireEvent.click(screen.getByTestId("watchlist-add-button")));
    expect(screen.getByTestId("watchlist-error")).toHaveTextContent("already");
  });
});

describe("PositionsTable", () => {
  it("renders a row per position with live P&L", () => {
    render(<PositionsTable positions={live.positions} onSelect={() => {}} />);
    const aapl = screen.getByTestId("position-row-AAPL");
    expect(aapl).toHaveTextContent("120.00");
    expect(aapl).toHaveAttribute("data-quantity", "10");
    expect(aapl).toHaveTextContent("+$200.00");
    expect(aapl).toHaveTextContent("+20.00%");
    expect(screen.getByTestId("position-row-TSLA")).toHaveTextContent("−$200.00");
  });

  it("shows an empty state", () => {
    render(<PositionsTable positions={[]} onSelect={() => {}} />);
    expect(screen.getByTestId("positions-table")).toHaveTextContent("No open positions");
  });
});

describe("Heatmap", () => {
  it("renders a cell per position colored by P&L", () => {
    render(<Heatmap positions={live.positions} onSelect={() => {}} />);
    expect(screen.getByTestId("heatmap-tile-AAPL")).toHaveAttribute("data-pnl", "positive");
    expect(screen.getByTestId("heatmap-tile-TSLA")).toHaveAttribute("data-pnl", "negative");
  });

  it("maps P&L to green/red intensity", () => {
    expect(heatColor(3)).toMatch(/^rgb\(47 208 143/);
    expect(heatColor(-3)).toMatch(/^rgb\(255 93 108/);
    expect(heatColor(20)).toBe(heatColor(4)); // capped
  });
});

describe("TradeBar", () => {
  it("validates quantity before submitting", async () => {
    const onTrade = vi.fn();
    render(<TradeBar defaultTicker="AAPL" priceOf={() => 100} cash={1000} onTrade={onTrade} />);
    await act(async () => fireEvent.click(screen.getByTestId("trade-buy")));
    expect(onTrade).not.toHaveBeenCalled();
    expect(screen.getByTestId("trade-error")).toHaveTextContent("quantity");
  });

  it("submits buy and sell and shows server errors inline", async () => {
    const onTrade = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, message: "Bought 2 AAPL @ 100.00" })
      .mockResolvedValueOnce({ ok: false, error: "Insufficient shares" });
    render(<TradeBar defaultTicker="AAPL" priceOf={() => 100} cash={1000} onTrade={onTrade} />);
    expect(screen.getByTestId("trade-ticker")).toHaveValue("AAPL");
    fireEvent.change(screen.getByTestId("trade-quantity"), { target: { value: "2" } });
    await act(async () => fireEvent.click(screen.getByTestId("trade-buy")));
    expect(onTrade).toHaveBeenLastCalledWith("AAPL", 2, "buy");
    expect(screen.getByTestId("trade-status")).toHaveTextContent("Bought 2 AAPL");

    await act(async () => fireEvent.click(screen.getByTestId("trade-sell")));
    expect(onTrade).toHaveBeenLastCalledWith("AAPL", 2, "sell");
    expect(screen.getByTestId("trade-error")).toHaveTextContent("Insufficient shares");
  });
});

describe("ChatPanel", () => {
  const messages: ChatMessage[] = [
    { id: "1", role: "user", content: "buy 5 AAPL", actions: null, created_at: "" },
    {
      id: "2",
      role: "assistant",
      content: "[mock] Bought 5 AAPL",
      actions: {
        trades: [{ ticker: "AAPL", side: "buy", quantity: 5, price: 190, status: "executed", error: null }],
        watchlist_changes: [{ ticker: "PYPL", action: "add", status: "failed", error: "Unknown ticker" }],
      },
      created_at: "",
    },
  ];

  it("renders messages with roles and inline action confirmations", () => {
    render(<ChatPanel messages={messages} loading={false} onSend={() => {}} collapsed={false} onToggle={() => {}} />);
    const msgs = screen.getAllByTestId("chat-message");
    expect(msgs.map((m) => m.getAttribute("data-role"))).toEqual(["user", "assistant"]);
    const actions = screen.getAllByTestId("chat-action");
    expect(actions).toHaveLength(2);
    expect(actions[0]).toHaveTextContent("Bought 5 AAPL @ $190.00");
    expect(actions[1]).toHaveTextContent("Add PYPL — failed: Unknown ticker");
    expect(screen.queryByTestId("chat-loading")).toBeNull();
  });

  it("shows the loading indicator and disables send while waiting", () => {
    render(<ChatPanel messages={messages} loading onSend={() => {}} collapsed={false} onToggle={() => {}} />);
    expect(screen.getByTestId("chat-loading")).toBeInTheDocument();
    fireEvent.change(screen.getByTestId("chat-input"), { target: { value: "hi" } });
    expect(screen.getByTestId("chat-send")).toBeDisabled();
  });

  it("sends the typed message and clears the input", () => {
    const onSend = vi.fn();
    render(<ChatPanel messages={[]} loading={false} onSend={onSend} collapsed={false} onToggle={() => {}} />);
    fireEvent.change(screen.getByTestId("chat-input"), { target: { value: "How am I doing?" } });
    fireEvent.click(screen.getByTestId("chat-send"));
    expect(onSend).toHaveBeenCalledWith("How am I doing?");
    expect(screen.getByTestId("chat-input")).toHaveValue("");
  });

  it("collapses to a rail", () => {
    const onToggle = vi.fn();
    render(<ChatPanel messages={[]} loading={false} onSend={() => {}} collapsed onToggle={onToggle} />);
    expect(screen.getByTestId("chat-panel")).toHaveAttribute("data-collapsed", "true");
    expect(screen.queryByTestId("chat-input")).toBeNull();
    fireEvent.click(screen.getByTestId("chat-toggle"));
    expect(onToggle).toHaveBeenCalled();
  });
});
