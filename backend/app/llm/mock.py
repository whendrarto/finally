"""Deterministic mock LLM (LLM_MOCK=true), relied on by the E2E tests.

Commands (case-insensitive), several may be joined with ",", ";", "and" or "then":
  buy <qty> <TICKER> / sell <qty> <TICKER>
  add <TICKER> / watch <TICKER> / remove <TICKER> / unwatch <TICKER>
Anything else gets a greeting with the portfolio value.
"""

from __future__ import annotations

import os
import re

from .schema import ChatResponse, TradeRequest, WatchlistChange

MOCK_PREFIX = "[mock] "

_SPLIT_RE = re.compile(r"\s*(?:[,;]|\band\b|\bthen\b)\s*", re.IGNORECASE)
_TICKER = r"([A-Za-z][A-Za-z0-9.]{0,9})"
_TRADE_RE = re.compile(rf"(buy|sell)\s+(\d+(?:\.\d+)?|\.\d+)\s+(?:shares?\s+(?:of\s+)?)?{_TICKER}", re.IGNORECASE)
_WATCH_RE = re.compile(rf"(add|watch|remove|unwatch)\s+{_TICKER}", re.IGNORECASE)


def is_mock_mode() -> bool:
    return os.getenv("LLM_MOCK", "").strip().lower() == "true"


def parse_mock_commands(message: str) -> ChatResponse:
    """Extract trades and watchlist changes from a command-style message.

    The returned message is empty; it is filled in by ``mock_reply`` once actions have run.
    """
    trades: list[TradeRequest] = []
    changes: list[WatchlistChange] = []
    for part in _SPLIT_RE.split(message.strip()):
        part = part.strip().rstrip(".!?").strip()
        if not part:
            continue
        if m := _TRADE_RE.fullmatch(part):
            trades.append(
                TradeRequest(side=m.group(1).lower(), quantity=float(m.group(2)), ticker=m.group(3).upper())
            )
        elif m := _WATCH_RE.fullmatch(part):
            action = "add" if m.group(1).lower() in ("add", "watch") else "remove"
            changes.append(WatchlistChange(action=action, ticker=m.group(2).upper()))
    return ChatResponse(message="", trades=trades, watchlist_changes=changes)


def _fmt_qty(quantity: float) -> str:
    return f"{quantity:g}"


def mock_reply(trade_results: list[dict], watchlist_results: list[dict], total_value: float) -> str:
    """Build the deterministic mock reply summarising executed actions."""
    if not trade_results and not watchlist_results:
        return (
            f"{MOCK_PREFIX}Hello! I'm FinAlly, your AI trading assistant. "
            f"Your portfolio is worth ${total_value:,.2f}."
        )

    parts: list[str] = []
    for t in trade_results:
        qty = _fmt_qty(t["quantity"])
        if t["status"] == "executed":
            verb = "Bought" if t["side"] == "buy" else "Sold"
            parts.append(f"{verb} {qty} {t['ticker']} at ${t['price']:,.2f}.")
        else:
            parts.append(f"Failed to {t['side']} {qty} {t['ticker']}: {t['error']}")
    for w in watchlist_results:
        if w["status"] == "executed":
            if w["action"] == "add":
                parts.append(f"Added {w['ticker']} to the watchlist.")
            else:
                parts.append(f"Removed {w['ticker']} from the watchlist.")
        else:
            parts.append(f"Failed to {w['action']} {w['ticker']}: {w['error']}")
    return MOCK_PREFIX + " ".join(parts)
