"use client";

import { useEffect, useMemo, useRef } from "react";
import type { ISeriesApi, UTCTimestamp } from "lightweight-charts";
import { toSeries, useChart } from "@/lib/chart";
import type { Snapshot } from "@/lib/types";

export function PnlChart({ snapshots, liveValue }: { snapshots: Snapshot[]; liveValue: number | null }) {
  const seriesRef = useRef<ISeriesApi<"Baseline"> | null>(null);
  const { containerRef, ready } = useChart((lw, chart) => {
    chart.applyOptions({ timeScale: { secondsVisible: false } });
    seriesRef.current = chart.addSeries(lw.BaselineSeries, {
      lineWidth: 2,
      topLineColor: "#2fd08f",
      topFillColor1: "rgba(47,208,143,0.25)",
      topFillColor2: "rgba(47,208,143,0.02)",
      bottomLineColor: "#ff5d6c",
      bottomFillColor1: "rgba(255,93,108,0.02)",
      bottomFillColor2: "rgba(255,93,108,0.25)",
    });
  });

  const points = useMemo(() => {
    const pts = snapshots.map((s) => ({ time: Date.parse(s.recorded_at) / 1000, value: s.total_value }));
    if (liveValue != null) pts.push({ time: Date.now() / 1000, value: liveValue });
    return pts;
  }, [snapshots, liveValue]);

  useEffect(() => {
    const series = seriesRef.current;
    if (!ready || !series) return;
    if (points.length) series.applyOptions({ baseValue: { type: "price", price: points[0].value } });
    series.setData(toSeries(points).map((p) => ({ time: p.time as UTCTimestamp, value: p.value })));
  }, [ready, points]);

  useEffect(() => {
    ready?.chart.timeScale().fitContent();
  }, [ready, snapshots.length]);

  return (
    <section data-testid="pnl-chart" data-points={snapshots.length} className="panel flex flex-col">
      <div className="panel-head">
        <h2>Portfolio value</h2>
        <span className="ml-auto text-faint">Baseline: first snapshot</span>
      </div>
      <div className="relative min-h-0 flex-1">
        <div ref={containerRef} className="absolute inset-0" />
        {points.length < 2 && (
          <div className="pointer-events-none absolute inset-0 grid place-items-center text-dim">
            Value history builds as snapshots are recorded
          </div>
        )}
      </div>
    </section>
  );
}
