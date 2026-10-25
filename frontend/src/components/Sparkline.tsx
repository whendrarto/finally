import type { PricePoint } from "@/lib/usePriceStream";

export function Sparkline({
  points,
  width = 84,
  height = 24,
}: {
  points: PricePoint[] | undefined;
  width?: number;
  height?: number;
}) {
  if (!points || points.length < 2) {
    return <svg width={width} height={height} aria-hidden="true" />;
  }
  const vals = points.map((p) => p.value);
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const span = max - min || 1;
  const step = width / (points.length - 1);
  const d = vals
    .map((v, i) => `${(i * step).toFixed(1)},${(height - 2 - ((v - min) / span) * (height - 4)).toFixed(1)}`)
    .join(" ");
  const up = vals[vals.length - 1] >= vals[0];
  return (
    <svg width={width} height={height} aria-hidden="true" data-testid="sparkline">
      <polyline
        points={d}
        fill="none"
        stroke={up ? "var(--color-up)" : "var(--color-down)"}
        strokeWidth={1.25}
        strokeLinejoin="round"
      />
    </svg>
  );
}
