"""System prompt and portfolio-context construction for the chat assistant."""

from __future__ import annotations

import json

SYSTEM_PROMPT = """You are FinAlly, an AI trading assistant inside a simulated trading workstation.
The user trades a virtual portfolio with fake money; market orders fill instantly at the current price.

Your job:
- Analyze the user's portfolio composition, risk concentration and P&L using the context provided.
- Suggest trades with brief, data-driven reasoning.
- Execute trades when the user asks for them or agrees to your suggestion, by listing them in "trades".
- Manage the watchlist proactively via "watchlist_changes" (add tickers the user is interested in,
  remove ones they no longer want).
- Be concise. Use numbers from the context; never invent prices or holdings.

Rules:
- Only include a trade if the user asked for it or explicitly agreed. Quantities must be > 0.
- Buys need enough cash (quantity * price <= cash); sells need enough shares held.
- Results of previously executed actions appear in the conversation; failed actions include the reason.
- Always respond with valid JSON matching the schema:
  {"message": str, "trades": [{"ticker": str, "side": "buy"|"sell", "quantity": number}],
   "watchlist_changes": [{"ticker": str, "action": "add"|"remove"}]}
  Use empty arrays when there are no actions."""


def build_portfolio_context(portfolio: dict, watchlist: list[dict]) -> str:
    """Render the user's current state as a compact text block for the LLM.

    ``portfolio`` has the GET /api/portfolio shape; ``watchlist`` items are
    ``{ticker, price, change_percent}`` (price may be None).
    """
    lines = [
        "Current portfolio state:",
        f"- Cash: ${portfolio.get('cash_balance', 0.0):,.2f}",
        f"- Positions value: ${portfolio.get('positions_value', 0.0):,.2f}",
        f"- Total value: ${portfolio.get('total_value', 0.0):,.2f}",
        f"- Unrealized P&L: ${portfolio.get('unrealized_pnl', 0.0):,.2f} "
        f"({portfolio.get('unrealized_pnl_percent', 0.0):.2f}%)",
    ]

    positions = portfolio.get("positions") or []
    if positions:
        lines.append("Positions:")
        for p in positions:
            price = p.get("current_price")
            price_txt = f"${price:,.2f}" if price is not None else "n/a"
            lines.append(
                f"- {p['ticker']}: qty {p['quantity']:g}, avg cost ${p['avg_cost']:,.2f}, "
                f"price {price_txt}, value ${p.get('market_value', 0.0):,.2f}, "
                f"P&L ${p.get('unrealized_pnl', 0.0):,.2f} ({p.get('unrealized_pnl_percent', 0.0):.2f}%)"
            )
    else:
        lines.append("Positions: none")

    if watchlist:
        lines.append("Watchlist (live prices):")
        for w in watchlist:
            if w.get("price") is None:
                lines.append(f"- {w['ticker']}: no price yet")
            else:
                lines.append(
                    f"- {w['ticker']}: ${w['price']:,.2f} ({w.get('change_percent', 0.0):+.2f}% last tick)"
                )
    else:
        lines.append("Watchlist: empty")
    return "\n".join(lines)


def format_history_message(msg: dict) -> dict:
    """Convert a stored chat message to an LLM message, appending action results for context."""
    content = msg["content"]
    actions = msg.get("actions")
    if msg["role"] == "assistant" and actions and (actions.get("trades") or actions.get("watchlist_changes")):
        content = f"{content}\n[actions taken: {json.dumps(actions)}]"
    return {"role": msg["role"], "content": content}
