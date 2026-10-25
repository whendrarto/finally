"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { fmtPct, fmtPrice, tone } from "@/lib/format";
import type { PricePoint } from "@/lib/usePriceStream";
import { Sparkline } from "./Sparkline";

export interface WatchRow {
  ticker: string;
  price: number | null;
  changePercent: number | null;
  history: PricePoint[] | undefined;
}

const TONE_TEXT = { up: "text-up", down: "text-down", flat: "text-dim" } as const;

export function WatchlistRow({
  row,
  selected,
  onSelect,
  onRemove,
}: {
  row: WatchRow;
  selected: boolean;
  onSelect: (t: string) => void;
  onRemove: (t: string) => void;
}) {
  const prev = useRef<number | null>(row.price);
  const [flash, setFlash] = useState<{ dir: "up" | "down"; n: number } | null>(null);

  useEffect(() => {
    const before = prev.current;
    prev.current = row.price;
    if (before == null || row.price == null || row.price === before) return;
    setFlash((f) => ({ dir: row.price! > before ? "up" : "down", n: (f?.n ?? 0) + 1 }));
    const t = setTimeout(() => setFlash(null), 600);
    return () => clearTimeout(t);
  }, [row.price]);

  const chTone = tone(row.changePercent);
  return (
    <li
      data-testid={`watchlist-row-${row.ticker}`}
      aria-selected={selected}
      onClick={() => onSelect(row.ticker)}
      className={`group relative grid cursor-pointer grid-cols-[1fr_auto] items-center gap-x-2 border-b border-line-soft py-1.5 pr-2 pl-3 hover:bg-panel-2 ${
        selected ? "bg-panel-2" : ""
      }`}
    >
      {selected && <span className="absolute top-0 bottom-0 left-0 w-[3px] bg-gold" />}
      <div className="flex min-w-0 items-center gap-2">
        <span className="w-14 text-[14px] font-semibold tracking-wide">{row.ticker}</span>
        <Sparkline points={row.history} />
      </div>
      <div className="flex items-center gap-1">
        <div className="text-right">
          <div
            key={flash?.n ?? 0}
            data-testid={`watchlist-price-${row.ticker}`}
            className={`num px-1 text-[14px] font-medium ${flash ? `flash-${flash.dir}` : ""}`}
          >
            {fmtPrice(row.price)}
          </div>
          <div className={`num px-1 text-[11.5px] ${TONE_TEXT[chTone]}`}>{fmtPct(row.changePercent)}</div>
        </div>
        <button
          type="button"
          data-testid={`watchlist-remove-${row.ticker}`}
          aria-label={`Remove ${row.ticker} from watchlist`}
          onClick={(e) => {
            e.stopPropagation();
            onRemove(row.ticker);
          }}
          className="grid h-5 w-5 place-items-center text-faint opacity-40 group-hover:opacity-100 hover:text-down focus-visible:opacity-100"
        >
          ×
        </button>
      </div>
    </li>
  );
}

export function Watchlist({
  rows,
  selected,
  onSelect,
  onAdd,
  onRemove,
}: {
  rows: WatchRow[];
  selected: string | null;
  onSelect: (t: string) => void;
  onAdd: (t: string) => Promise<string | null>;
  onRemove: (t: string) => void;
}) {
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const t = value.trim().toUpperCase();
    if (!t) return;
    setBusy(true);
    const err = await onAdd(t);
    setBusy(false);
    setError(err);
    if (!err) setValue("");
  };

  return (
    <section data-testid="watchlist" className="panel flex flex-1 flex-col">
      <div className="panel-head">
        <h2>Watchlist</h2>
        <span className="num ml-auto text-faint">{rows.length}</span>
      </div>
      <form onSubmit={submit} className="flex gap-1 border-b border-line-soft p-2">
        <input
          data-testid="watchlist-add-input"
          value={value}
          onChange={(e) => setValue(e.target.value.toUpperCase())}
          placeholder="Add symbol"
          aria-label="Ticker to add"
          maxLength={10}
          className="min-w-0 flex-1 border border-line bg-ink px-2 py-1 text-[13px] tracking-wide uppercase outline-none focus:border-azure"
        />
        <button
          data-testid="watchlist-add-button"
          type="submit"
          disabled={busy}
          className="border border-line px-3 text-[12px] font-semibold text-azure hover:border-azure disabled:opacity-50"
        >
          Add
        </button>
      </form>
      {error && (
        <p data-testid="watchlist-error" className="px-3 py-1 text-[12px] text-down">
          {error}
        </p>
      )}
      <ul className="min-h-0 flex-1 overflow-y-auto">
        {rows.map((r) => (
          <WatchlistRow
            key={r.ticker}
            row={r}
            selected={r.ticker === selected}
            onSelect={onSelect}
            onRemove={onRemove}
          />
        ))}
        {rows.length === 0 && (
          <li className="px-3 py-6 text-dim">Your watchlist is empty. Add a symbol above to start streaming prices.</li>
        )}
      </ul>
    </section>
  );
}
