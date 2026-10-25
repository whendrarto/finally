"use client";

import { fmtPct, fmtSignedUsd, fmtUsd, tone } from "@/lib/format";
import type { LivePortfolio } from "@/lib/portfolio";
import type { ConnectionStatus } from "@/lib/types";

const STATUS: Record<ConnectionStatus, { label: string; color: string }> = {
  connected: { label: "Live", color: "bg-up" },
  reconnecting: { label: "Reconnecting", color: "bg-gold" },
  disconnected: { label: "Offline", color: "bg-down" },
};

const TONE_TEXT = { up: "text-up", down: "text-down", flat: "text-dim" } as const;

export function Header({
  portfolio,
  status,
}: {
  portfolio: LivePortfolio | null;
  status: ConnectionStatus;
}) {
  const s = STATUS[status];
  const pnlTone = tone(portfolio?.unrealizedPnl);
  return (
    <header className="flex items-stretch border-b border-line bg-panel">
      <div className="flex items-center gap-2 border-r border-line px-4">
        <span className="grid h-6 w-6 place-items-center bg-gold text-[13px] font-bold text-ink">F</span>
        <span className="text-[17px] font-semibold tracking-tight">
          Fin<span className="text-gold">Ally</span>
        </span>
      </div>

      <div className="flex items-baseline gap-3 border-r border-line px-5 py-2">
        <span className="text-dim">Portfolio</span>
        <span
          data-testid="header-total-value"
          data-value={portfolio?.totalValue.toFixed(2) ?? ""}
          className="num text-[26px] leading-none font-semibold text-fg">
          {portfolio ? fmtUsd(portfolio.totalValue) : "—"}
        </span>
      </div>

      <div className="hidden items-baseline gap-2 border-r border-line px-5 py-2 sm:flex">
        <span className="text-dim">Unrealized</span>
        <span className={`num text-[15px] font-medium ${TONE_TEXT[pnlTone]}`}>
          {portfolio ? fmtSignedUsd(portfolio.unrealizedPnl) : "—"}
        </span>
        <span className={`num text-[12px] ${TONE_TEXT[pnlTone]}`}>
          {portfolio ? fmtPct(portfolio.unrealizedPnlPercent) : ""}
        </span>
      </div>

      <div className="flex items-baseline gap-2 border-r border-line px-5 py-2">
        <span className="text-dim">Cash</span>
        <span data-testid="header-cash" data-value={portfolio?.cash.toFixed(2) ?? ""} className="num text-[15px] font-medium">
          {portfolio ? fmtUsd(portfolio.cash) : "—"}
        </span>
      </div>

      <div className="ml-auto flex items-center gap-2 px-4">
        <span
          data-testid="connection-status"
          data-status={status}
          title={`Price stream: ${s.label}`}
          className="flex items-center gap-2 text-dim"
        >
          <span
            className={`inline-block h-2 w-2 rounded-full ${s.color} ${status === "reconnecting" ? "dot-pulse" : ""}`}
          />
          {s.label}
        </span>
      </div>
    </header>
  );
}
