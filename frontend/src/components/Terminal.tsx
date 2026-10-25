"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import { revalue } from "@/lib/portfolio";
import type { ChatMessage, Portfolio, Snapshot, WatchlistItem } from "@/lib/types";
import { usePriceStream } from "@/lib/usePriceStream";
import { ChatPanel } from "./ChatPanel";
import { Header } from "./Header";
import { Heatmap } from "./Heatmap";
import { PnlChart } from "./PnlChart";
import { PositionsTable } from "./PositionsTable";
import { PriceChart } from "./PriceChart";
import { TradeBar, type TradeResult } from "./TradeBar";
import { Watchlist, type WatchRow } from "./Watchlist";

const HISTORY_REFRESH_MS = 30_000;
const errMsg = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong");

export function Terminal() {
  const stream = usePriceStream();
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [snapshots, setSnapshots] = useState<Snapshot[]>([]);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatCollapsed, setChatCollapsed] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);

  const refreshWatchlist = useCallback(
    () => api.watchlist().then((r) => setWatchlist(r.tickers)).catch(() => {}),
    [],
  );
  const refreshPortfolio = useCallback(
    () => api.portfolio().then(setPortfolio).catch(() => {}),
    [],
  );
  const refreshHistory = useCallback(
    () => api.history().then((r) => setSnapshots(r.snapshots)).catch(() => {}),
    [],
  );
  const refreshAll = useCallback(
    () => Promise.all([refreshWatchlist(), refreshPortfolio(), refreshHistory()]),
    [refreshWatchlist, refreshPortfolio, refreshHistory],
  );

  useEffect(() => {
    refreshAll();
    api
      .chatHistory()
      .then((r) => setMessages(r.messages))
      .catch(() => {});
    const id = setInterval(refreshHistory, HISTORY_REFRESH_MS);
    return () => clearInterval(id);
  }, [refreshAll, refreshHistory]);

  useEffect(() => {
    if (!selected && watchlist.length) setSelected(watchlist[0].ticker);
  }, [selected, watchlist]);

  const livePrices = useMemo(() => {
    const out: Record<string, number> = {};
    for (const [t, u] of Object.entries(stream.prices)) out[t] = u.price;
    return out;
  }, [stream.prices]);

  const priceOf = useCallback(
    (t: string): number | null =>
      livePrices[t] ?? watchlist.find((w) => w.ticker === t)?.price ?? null,
    [livePrices, watchlist],
  );

  const changeOf = useCallback(
    (t: string): number | null => {
      const open = stream.opens[t];
      const price = livePrices[t];
      if (open && price != null) return ((price - open) / open) * 100;
      return null;
    },
    [stream.opens, livePrices],
  );

  const live = useMemo(() => revalue(portfolio, livePrices), [portfolio, livePrices]);

  const rows: WatchRow[] = watchlist.map((w) => ({
    ticker: w.ticker,
    price: priceOf(w.ticker),
    changePercent: changeOf(w.ticker),
    history: stream.history[w.ticker],
  }));

  const handleAdd = async (ticker: string): Promise<string | null> => {
    try {
      await api.addTicker(ticker);
      await refreshWatchlist();
      setSelected(ticker);
      return null;
    } catch (e) {
      return errMsg(e);
    }
  };

  const handleRemove = async (ticker: string) => {
    setWatchlist((w) => w.filter((x) => x.ticker !== ticker));
    if (selected === ticker) setSelected(null);
    try {
      await api.removeTicker(ticker);
    } finally {
      refreshWatchlist();
    }
  };

  const handleTrade = async (ticker: string, quantity: number, side: "buy" | "sell"): Promise<TradeResult> => {
    try {
      const r = await api.trade(ticker, quantity, side);
      setPortfolio(r.portfolio);
      refreshHistory();
      refreshWatchlist();
      const verb = side === "buy" ? "Bought" : "Sold";
      return { ok: true, message: `${verb} ${quantity} ${ticker} @ ${r.trade.price.toFixed(2)}` };
    } catch (e) {
      return { ok: false, error: errMsg(e) };
    }
  };

  const handleSend = async (text: string) => {
    const userMsg: ChatMessage = {
      id: `local-${Date.now()}`,
      role: "user",
      content: text,
      actions: null,
      created_at: new Date().toISOString(),
    };
    setMessages((m) => [...m, userMsg]);
    setChatLoading(true);
    try {
      const r = await api.chat(text);
      setMessages((m) => [
        ...m,
        {
          id: `local-${Date.now()}-a`,
          role: "assistant",
          content: r.message,
          actions: { trades: r.trades ?? [], watchlist_changes: r.watchlist_changes ?? [] },
          created_at: new Date().toISOString(),
        },
      ]);
      if (r.trades?.length || r.watchlist_changes?.length) await refreshAll();
    } catch (e) {
      setMessages((m) => [
        ...m,
        {
          id: `local-${Date.now()}-e`,
          role: "assistant",
          content: `Couldn't reach the assistant: ${errMsg(e)}. Try again in a moment.`,
          actions: null,
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setChatLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col lg:h-screen lg:min-h-[640px]">
      <Header portfolio={live} status={stream.status} />
      <main
        className={`grid flex-1 grid-cols-1 gap-1 p-1 lg:min-h-0 ${
          chatCollapsed ? "lg:grid-cols-[300px_1fr_44px]" : "lg:grid-cols-[300px_1fr_360px]"
        }`}
      >
        <div className="flex h-[360px] flex-col lg:h-auto lg:min-h-0">
          <Watchlist
            rows={rows}
            selected={selected}
            onSelect={setSelected}
            onAdd={handleAdd}
            onRemove={handleRemove}
          />
        </div>

        <div className="grid grid-rows-[420px_auto_auto] gap-1 lg:min-h-0 lg:grid-rows-[minmax(240px,1fr)_minmax(190px,0.75fr)_minmax(200px,0.8fr)]">
          <PriceChart
            ticker={selected}
            price={selected ? priceOf(selected) : null}
            changePercent={selected ? changeOf(selected) : null}
            history={selected ? stream.history[selected] : undefined}
            tick={stream.prices}
          />
          <div className="grid h-[520px] grid-cols-1 gap-1 md:h-[260px] md:grid-cols-[1.15fr_1fr] lg:h-auto lg:min-h-0">
            <Heatmap positions={live?.positions ?? []} onSelect={setSelected} />
            <PnlChart snapshots={snapshots} liveValue={live?.totalValue ?? null} />
          </div>
          <div className="grid grid-cols-1 gap-1 md:grid-cols-[1fr_300px] lg:min-h-0">
            <PositionsTable positions={live?.positions ?? []} onSelect={setSelected} />
            <TradeBar defaultTicker={selected} priceOf={priceOf} cash={live?.cash ?? null} onTrade={handleTrade} />
          </div>
        </div>

        <div className={`flex flex-col lg:h-auto lg:min-h-0 ${chatCollapsed ? "" : "h-[480px]"}`}>
          <ChatPanel
            messages={messages}
            loading={chatLoading}
            onSend={handleSend}
            collapsed={chatCollapsed}
            onToggle={() => setChatCollapsed((c) => !c)}
          />
        </div>
      </main>
    </div>
  );
}
