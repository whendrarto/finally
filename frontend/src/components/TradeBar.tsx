"use client";

import { useEffect, useState } from "react";
import { fmtPrice, fmtUsd } from "@/lib/format";

export type TradeResult = { ok: true; message: string } | { ok: false; error: string };

export function TradeBar({
  defaultTicker,
  priceOf,
  cash,
  onTrade,
}: {
  defaultTicker: string | null;
  priceOf: (t: string) => number | null;
  cash: number | null;
  onTrade: (ticker: string, quantity: number, side: "buy" | "sell") => Promise<TradeResult>;
}) {
  const [ticker, setTicker] = useState(defaultTicker ?? "");
  const [qty, setQty] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<TradeResult | null>(null);

  useEffect(() => {
    if (defaultTicker) setTicker(defaultTicker);
  }, [defaultTicker]);

  const t = ticker.trim().toUpperCase();
  const q = Number(qty);
  const price = t ? priceOf(t) : null;
  const notional = price != null && q > 0 ? price * q : null;

  const submit = async (side: "buy" | "sell") => {
    if (!t) return setResult({ ok: false, error: "Enter a ticker symbol." });
    if (!(q > 0)) return setResult({ ok: false, error: "Enter a quantity greater than zero." });
    setBusy(true);
    setResult(await onTrade(t, q, side));
    setBusy(false);
  };

  return (
    <section className="panel flex flex-col">
      <div className="panel-head">
        <h2>Trade ticket</h2>
        <span className="ml-auto text-faint">Market order · instant fill</span>
      </div>
      <form
        className="flex flex-1 flex-col gap-2 p-3"
        onSubmit={(e) => {
          e.preventDefault();
          submit("buy");
        }}
      >
        <div className="grid grid-cols-2 gap-2">
          <label className="flex flex-col gap-1 text-[11.5px] text-dim">
            Symbol
            <input
              data-testid="trade-ticker"
              value={ticker}
              onChange={(e) => setTicker(e.target.value.toUpperCase())}
              maxLength={10}
              className="border border-line bg-ink px-2 py-1.5 text-[15px] font-semibold tracking-wide text-fg uppercase outline-none focus:border-azure"
            />
          </label>
          <label className="flex flex-col gap-1 text-[11.5px] text-dim">
            Quantity
            <input
              data-testid="trade-quantity"
              value={qty}
              onChange={(e) => setQty(e.target.value)}
              inputMode="decimal"
              type="number"
              min="0"
              step="any"
              placeholder="0"
              className="num border border-line bg-ink px-2 py-1.5 text-[15px] text-fg outline-none focus:border-azure"
            />
          </label>
        </div>
        <div className="num flex justify-between text-[12px] text-dim">
          <span>
            @ <span className="text-fg">{fmtPrice(price)}</span>
          </span>
          <span>
            Est. <span className="text-fg">{notional != null ? fmtUsd(notional) : "—"}</span>
          </span>
          <span>
            Cash <span className="text-fg">{fmtUsd(cash)}</span>
          </span>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            data-testid="trade-buy"
            disabled={busy}
            onClick={() => submit("buy")}
            className="bg-plum py-2 text-[14px] font-semibold text-white hover:bg-plum-hi disabled:opacity-50"
          >
            Buy
          </button>
          <button
            type="button"
            data-testid="trade-sell"
            disabled={busy}
            onClick={() => submit("sell")}
            className="border border-down/60 py-2 text-[14px] font-semibold text-down hover:bg-down/10 disabled:opacity-50"
          >
            Sell
          </button>
        </div>
        <div className="min-h-[18px] text-[12px]" aria-live="polite">
          {result &&
            (result.ok ? (
              <span data-testid="trade-status" className="text-up">
                {result.message}
              </span>
            ) : (
              <span data-testid="trade-error" className="text-down">
                {result.error}
              </span>
            ))}
        </div>
      </form>
    </section>
  );
}
