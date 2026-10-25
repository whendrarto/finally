"use client";

import { useEffect, useRef } from "react";
import type { ISeriesApi, UTCTimestamp } from "lightweight-charts";
import { toSeries, useChart } from "@/lib/chart";
import { fmtPct, fmtPrice, tone } from "@/lib/format";
import type { PricePoint } from "@/lib/usePriceStream";

const TONE_TEXT = { up: "text-up", down: "text-down", flat: "text-dim" } as const;

export function PriceChart({
  ticker,
  price,
  changePercent,
  history,
  tick,
}: {
  ticker: string | null;
  price: number | null;
  changePercent: number | null;
  history: PricePoint[] | undefined;
  /** Changes whenever new stream data arrives, so the chart redraws. */
  tick: unknown;
}) {
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);
  const { containerRef, ready } = useChart((lw, chart) => {
    seriesRef.current = chart.addSeries(lw.AreaSeries, {
      lineColor: "#209dd7",
      lineWidth: 2,
      topColor: "rgba(32,157,215,0.28)",
      bottomColor: "rgba(32,157,215,0.0)",
      priceLineColor: "#ecad0a",
      priceLineStyle: 2,
      lastValueVisible: true,
    });
  });

  useEffect(() => {
    if (!ready || !seriesRef.current) return;
    const data = toSeries(history ?? []).map((p) => ({ time: p.time as UTCTimestamp, value: p.value }));
    seriesRef.current.setData(data);
    // Whole-session view: keep every point since page load in frame.
    ready.chart.timeScale().fitContent();
  }, [ready, history, tick, ticker]);

  const t = tone(changePercent);
  return (
    <section data-testid="main-chart" data-ticker={ticker ?? ""} className="panel flex flex-col">
      <div className="flex items-end gap-4 border-b border-line-soft px-4 pt-2 pb-2">
        <div className="text-[30px] leading-none font-bold tracking-tight text-gold">{ticker ?? "—"}</div>
        <div className="num text-[22px] leading-none font-medium">{fmtPrice(price)}</div>
        <div className={`num pb-0.5 text-[13px] ${TONE_TEXT[t]}`}>{fmtPct(changePercent)} session</div>
        <div className="ml-auto pb-0.5 text-[12px] text-faint">Since page load · live</div>
      </div>
      <div className="relative min-h-0 flex-1">
        <div ref={containerRef} className="absolute inset-0" />
        {(history?.length ?? 0) < 2 && (
          <div className="pointer-events-none absolute inset-0 grid place-items-center text-dim">
            Waiting for prices…
          </div>
        )}
      </div>
    </section>
  );
}
