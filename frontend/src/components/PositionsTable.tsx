"use client";

import { fmtPct, fmtPrice, fmtQty, fmtSignedUsd, fmtUsd, tone } from "@/lib/format";
import type { LivePosition } from "@/lib/portfolio";

const TONE_TEXT = { up: "text-up", down: "text-down", flat: "text-dim" } as const;

export function PositionsTable({
  positions,
  onSelect,
}: {
  positions: LivePosition[];
  onSelect: (t: string) => void;
}) {
  return (
    <section className="panel flex flex-col">
      <div className="panel-head">
        <h2>Positions</h2>
        <span className="num ml-auto text-faint">{positions.length}</span>
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        <table data-testid="positions-table" className="num w-full border-collapse text-right text-[13px]">
          <thead className="sticky top-0 bg-panel text-[11.5px] text-dim">
            <tr className="border-b border-line-soft">
              <th className="px-3 py-1.5 text-left font-medium">Symbol</th>
              <th className="px-2 py-1.5 font-medium">Qty</th>
              <th className="px-2 py-1.5 font-medium">Avg cost</th>
              <th className="px-2 py-1.5 font-medium">Price</th>
              <th className="px-2 py-1.5 font-medium">Value</th>
              <th className="px-2 py-1.5 font-medium">Unrealized P&amp;L</th>
              <th className="px-3 py-1.5 font-medium">%</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((p) => {
              const t = TONE_TEXT[tone(p.unrealized_pnl)];
              return (
                <tr
                  key={p.ticker}
                  data-testid={`position-row-${p.ticker}`}
                  data-quantity={p.quantity}
                  onClick={() => onSelect(p.ticker)}
                  className="cursor-pointer border-b border-line-soft hover:bg-panel-2"
                >
                  <td className="px-3 py-1.5 text-left font-semibold">{p.ticker}</td>
                  <td className="px-2 py-1.5" data-testid={`position-qty-${p.ticker}`}>
                    {fmtQty(p.quantity)}
                  </td>
                  <td className="px-2 py-1.5 text-dim">{fmtPrice(p.avg_cost)}</td>
                  <td className="px-2 py-1.5">{fmtPrice(p.current_price)}</td>
                  <td className="px-2 py-1.5">{fmtUsd(p.market_value)}</td>
                  <td className={`px-2 py-1.5 ${t}`}>{fmtSignedUsd(p.unrealized_pnl)}</td>
                  <td className={`px-3 py-1.5 ${t}`}>{fmtPct(p.unrealized_pnl_percent)}</td>
                </tr>
              );
            })}
            {positions.length === 0 && (
              <tr>
                <td colSpan={7} className="px-3 py-6 text-center text-dim">
                  No open positions
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
