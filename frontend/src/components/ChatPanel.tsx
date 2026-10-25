"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { fmtQty, fmtUsd } from "@/lib/format";
import type { ChatActions, ChatMessage } from "@/lib/types";

function ActionChips({ actions }: { actions: ChatActions | null }) {
  const trades = actions?.trades ?? [];
  const changes = actions?.watchlist_changes ?? [];
  if (!trades.length && !changes.length) return null;
  return (
    <ul className="mt-2 flex flex-col gap-1">
      {trades.map((t, i) => {
        const ok = t.status === "executed";
        return (
          <li
            key={`t${i}`}
            data-testid="chat-action"
            data-kind="trade"
            data-status={t.status}
            className={`num flex items-center gap-2 border-l-2 bg-ink/60 px-2 py-1 text-[12px] ${
              ok ? "border-up" : "border-down"
            }`}
          >
            <span className={`font-semibold ${t.side === "buy" ? "text-up" : "text-down"}`}>
              {ok ? (t.side === "buy" ? "Bought" : "Sold") : t.side === "buy" ? "Buy" : "Sell"}
            </span>{" "}
            <span>
              {fmtQty(t.quantity)} {t.ticker}
              {ok && t.price != null ? ` @ ${fmtUsd(t.price)}` : ""}
            </span>{" "}
            {!ok && <span className="text-down">— failed: {t.error ?? "rejected"}</span>}
          </li>
        );
      })}
      {changes.map((c, i) => {
        const ok = c.status === "executed";
        return (
          <li
            key={`w${i}`}
            data-testid="chat-action"
            data-kind="watchlist"
            data-status={c.status}
            className={`flex items-center gap-2 border-l-2 bg-ink/60 px-2 py-1 text-[12px] ${
              ok ? "border-azure" : "border-down"
            }`}
          >
            <span className="font-semibold text-azure">
              {ok ? (c.action === "add" ? "Added" : "Removed") : c.action === "add" ? "Add" : "Remove"}
            </span>{" "}
            <span>{c.ticker}</span>{" "}
            {!ok && <span className="text-down">— failed: {c.error ?? "rejected"}</span>}
          </li>
        );
      })}
    </ul>
  );
}

const SUGGESTIONS = ["How is my portfolio doing?", "Buy 5 NVDA", "Where am I most concentrated?"];

export function ChatPanel({
  messages,
  loading,
  onSend,
  collapsed,
  onToggle,
}: {
  messages: ChatMessage[];
  loading: boolean;
  onSend: (text: string) => void;
  collapsed: boolean;
  onToggle: () => void;
}) {
  const [text, setText] = useState("");
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: "end" });
  }, [messages.length, loading, collapsed]);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const msg = text.trim();
    if (!msg || loading) return;
    onSend(msg);
    setText("");
  };

  if (collapsed) {
    return (
      <aside data-testid="chat-panel" data-collapsed="true" className="panel flex flex-1 flex-col items-center py-2">
        <button
          type="button"
          data-testid="chat-toggle"
          onClick={onToggle}
          aria-label="Open FinAlly assistant"
          className="flex flex-col items-center gap-2 px-2 py-2 text-gold hover:text-fg"
        >
          <span className="grid h-7 w-7 place-items-center border border-gold text-[12px] font-bold">AI</span>
          <span className="text-[12px] text-dim [writing-mode:vertical-rl]">Ask FinAlly</span>
        </button>
      </aside>
    );
  }

  return (
    <aside data-testid="chat-panel" data-collapsed="false" className="panel flex flex-1 flex-col">
      <div className="panel-head">
        <span className="grid h-5 w-5 place-items-center bg-gold text-[10px] font-bold text-ink">AI</span>
        <h2>FinAlly assistant</h2>
        <button
          type="button"
          data-testid="chat-toggle"
          onClick={onToggle}
          aria-label="Collapse assistant"
          className="ml-auto px-1 text-[16px] leading-none text-dim hover:text-fg"
        >
          ›
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-3 py-3">
        {messages.length === 0 && !loading && (
          <div className="text-dim">
            <p className="mb-3 text-fg">
              Ask about your holdings, get a read on risk, or tell me what to trade. I execute orders and
              update your watchlist directly.
            </p>
            <div className="flex flex-col items-start gap-1.5">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => onSend(s)}
                  className="border border-line px-2 py-1 text-left text-[12px] text-dim hover:border-azure hover:text-fg"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        <ol className="flex flex-col gap-3">
          {messages.map((m) => (
            <li
              key={m.id}
              data-testid="chat-message"
              data-role={m.role}
              className={m.role === "user" ? "self-end max-w-[88%]" : "max-w-[96%]"}
            >
              {m.role === "user" ? (
                <div className="bg-plum/30 px-3 py-1.5 text-fg">{m.content}</div>
              ) : (
                <div className="border-l-2 border-gold pl-3">
                  <div className="whitespace-pre-wrap text-fg">{m.content}</div>
                  <ActionChips actions={m.actions} />
                </div>
              )}
            </li>
          ))}
        </ol>
        {loading && (
          <div data-testid="chat-loading" className="mt-3 flex items-center gap-2 border-l-2 border-gold pl-3 text-dim">
            Thinking
            <span className="think text-gold" aria-hidden="true">
              <span>•</span>
              <span>•</span>
              <span>•</span>
            </span>
          </div>
        )}
        <div ref={endRef} />
      </div>

      <form onSubmit={submit} className="flex gap-2 border-t border-line-soft p-2">
        <input
          data-testid="chat-input"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Ask or instruct FinAlly…"
          aria-label="Message FinAlly"
          className="min-w-0 flex-1 border border-line bg-ink px-2 py-1.5 text-[13px] outline-none focus:border-azure"
        />
        <button
          data-testid="chat-send"
          type="submit"
          disabled={loading || !text.trim()}
          className="bg-plum px-4 text-[13px] font-semibold text-white hover:bg-plum-hi disabled:opacity-40"
        >
          Send
        </button>
      </form>
    </aside>
  );
}
