"use client";

import { useEffect, useRef, useState } from "react";
import { fmtPct } from "@/lib/format";
import type { LivePosition } from "@/lib/portfolio";
import { squarify } from "@/lib/treemap";

/** Color a cell by P&L %: intensity grows with magnitude, capped at ±4%. */
export function heatColor(pnlPercent: number): string {
  if (Math.abs(pnlPercent) < 0.01) return "rgb(86 98 122 / 0.35)";
  const m = Math.min(Math.abs(pnlPercent) / 4, 1);
  const alpha = (0.14 + 0.66 * Math.sqrt(m)).toFixed(2);
  return pnlPercent > 0 ? `rgb(47 208 143 / ${alpha})` : `rgb(255 93 108 / ${alpha})`;
}

export function Heatmap({
  positions,
  onSelect,
}: {
  positions: LivePosition[];
  onSelect: (t: string) => void;
}) {
  const boxRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 400, h: 200 });

  useEffect(() => {
    const el = boxRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      if (width > 0 && height > 0) setSize({ w: width, h: height });
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const cells = squarify(positions, (p) => p.market_value, { x: 0, y: 0, w: size.w, h: size.h });

  return (
    <section data-testid="portfolio-heatmap" className="panel flex flex-col">
      <div className="panel-head">
        <h2>Holdings map</h2>
        <span className="ml-auto text-faint">Size = weight · color = P&amp;L</span>
      </div>
      <div ref={boxRef} className="relative m-1 min-h-0 flex-1">
        {cells.map(({ item: p, rect }) => {
          const small = rect.w < 70 || rect.h < 40;
          const tiny = rect.w < 44 || rect.h < 22;
          return (
            <button
              type="button"
              key={p.ticker}
              data-testid={`heatmap-tile-${p.ticker}`}
              data-pnl={Math.abs(p.unrealized_pnl) < 0.005 ? "flat" : p.unrealized_pnl > 0 ? "positive" : "negative"}
              onClick={() => onSelect(p.ticker)}
              title={`${p.ticker}: ${(p.weight * 100).toFixed(1)}% of holdings, ${fmtPct(p.unrealized_pnl_percent)}`}
              className="absolute overflow-hidden border border-ink p-1.5 text-left hover:brightness-125"
              style={{
                left: `${(rect.x / size.w) * 100}%`,
                top: `${(rect.y / size.h) * 100}%`,
                width: `${(rect.w / size.w) * 100}%`,
                height: `${(rect.h / size.h) * 100}%`,
                background: heatColor(p.unrealized_pnl_percent),
              }}
            >
              {!tiny && (
                <div className={`font-semibold ${small ? "text-[11px]" : "text-[14px]"}`}>{p.ticker}</div>
              )}
              {!small && (
                <div className="num text-[12px] text-fg/80">
                  {fmtPct(p.unrealized_pnl_percent)} · {(p.weight * 100).toFixed(0)}%
                </div>
              )}
            </button>
          );
        })}
        {positions.length === 0 && (
          <div className="absolute inset-0 grid place-items-center px-6 text-center text-dim">
            No holdings yet. Buy a position with the trade ticket or ask FinAlly.
          </div>
        )}
      </div>
    </section>
  );
}
