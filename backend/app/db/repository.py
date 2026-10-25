"""Data-access functions (the `app.db` contract in planning/TEAM_CONTRACT.md)."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from .connection import get_connection, new_id, now_iso
from .seed import DEFAULT_USER_ID

# Positions with |quantity| below this are treated as fully closed.
ZERO_QUANTITY_TOLERANCE = 1e-9


# --- Users -----------------------------------------------------------------


def get_cash_balance(*, user_id: str = DEFAULT_USER_ID) -> float:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)
        ).fetchone()
    return float(row["cash_balance"]) if row else 0.0


# --- Watchlist -------------------------------------------------------------


def get_watchlist(*, user_id: str = DEFAULT_USER_ID) -> list[str]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT ticker FROM watchlist WHERE user_id = ? ORDER BY added_at, rowid",
            (user_id,),
        ).fetchall()
    return [row["ticker"] for row in rows]


def add_watchlist_ticker(ticker: str, *, user_id: str = DEFAULT_USER_ID) -> bool:
    """Add a ticker. Returns False if it is already on the watchlist."""
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            (new_id(), user_id, ticker.upper(), now_iso()),
        )
        return cur.rowcount == 1


def remove_watchlist_ticker(ticker: str, *, user_id: str = DEFAULT_USER_ID) -> bool:
    """Remove a ticker. Returns False if it was not on the watchlist."""
    with get_connection() as conn:
        cur = conn.execute(
            "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?",
            (user_id, ticker.upper()),
        )
        return cur.rowcount > 0


# --- Positions & trades ----------------------------------------------------


def _position_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "ticker": row["ticker"],
        "quantity": row["quantity"],
        "avg_cost": row["avg_cost"],
        "updated_at": row["updated_at"],
    }


def get_positions(*, user_id: str = DEFAULT_USER_ID) -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT ticker, quantity, avg_cost, updated_at FROM positions "
            "WHERE user_id = ? ORDER BY ticker",
            (user_id,),
        ).fetchall()
    return [_position_dict(row) for row in rows]


def get_position(ticker: str, *, user_id: str = DEFAULT_USER_ID) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT ticker, quantity, avg_cost, updated_at FROM positions "
            "WHERE user_id = ? AND ticker = ?",
            (user_id, ticker.upper()),
        ).fetchone()
    return _position_dict(row) if row else None


def apply_trade(
    ticker: str,
    side: str,
    quantity: float,
    price: float,
    new_cash: float,
    new_quantity: float,
    new_avg_cost: float,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> dict[str, Any]:
    """Persist an already-validated trade in ONE transaction.

    Inserts the trade row, sets the user's cash, and upserts the position
    (deleting it when new_quantity is zero). Returns the trade record.
    """
    ticker = ticker.upper()
    trade = {
        "id": new_id(),
        "ticker": ticker,
        "side": side,
        "quantity": quantity,
        "price": price,
        "executed_at": now_iso(),
    }
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (trade["id"], user_id, ticker, side, quantity, price, trade["executed_at"]),
        )
        cur = conn.execute(
            "UPDATE users_profile SET cash_balance = ? WHERE id = ?", (new_cash, user_id)
        )
        if cur.rowcount == 0:
            raise ValueError(f"Unknown user: {user_id}")
        if abs(new_quantity) < ZERO_QUANTITY_TOLERANCE:
            conn.execute(
                "DELETE FROM positions WHERE user_id = ? AND ticker = ?", (user_id, ticker)
            )
        else:
            conn.execute(
                "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?) "
                "ON CONFLICT (user_id, ticker) DO UPDATE SET "
                "quantity = excluded.quantity, avg_cost = excluded.avg_cost, "
                "updated_at = excluded.updated_at",
                (new_id(), user_id, ticker, new_quantity, new_avg_cost, trade["executed_at"]),
            )
    return trade


def get_trades(
    limit: int | None = None, *, user_id: str = DEFAULT_USER_ID
) -> list[dict[str, Any]]:
    """Trade history, newest first."""
    sql = (
        "SELECT id, ticker, side, quantity, price, executed_at FROM trades "
        "WHERE user_id = ? ORDER BY executed_at DESC, rowid DESC"
    )
    params: tuple[Any, ...] = (user_id,)
    if limit is not None:
        sql += " LIMIT ?"
        params += (limit,)
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


# --- Portfolio snapshots ---------------------------------------------------


def insert_snapshot(total_value: float, *, user_id: str = DEFAULT_USER_ID) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) "
            "VALUES (?, ?, ?, ?)",
            (new_id(), user_id, total_value, now_iso()),
        )


def get_snapshots(
    limit: int | None = None, *, user_id: str = DEFAULT_USER_ID
) -> list[dict[str, Any]]:
    """Snapshots oldest first. With `limit`, the most recent `limit` snapshots."""
    sql = (
        "SELECT total_value, recorded_at FROM portfolio_snapshots "
        "WHERE user_id = ? ORDER BY recorded_at DESC, rowid DESC"
    )
    params: tuple[Any, ...] = (user_id,)
    if limit is not None:
        sql += " LIMIT ?"
        params += (limit,)
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in reversed(rows)]


# --- Chat ------------------------------------------------------------------


def insert_chat_message(
    role: str,
    content: str,
    actions: dict[str, Any] | None = None,
    *,
    user_id: str = DEFAULT_USER_ID,
) -> dict[str, Any]:
    message = {
        "id": new_id(),
        "role": role,
        "content": content,
        "actions": actions,
        "created_at": now_iso(),
    }
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                message["id"],
                user_id,
                role,
                content,
                json.dumps(actions) if actions is not None else None,
                message["created_at"],
            ),
        )
    return message


def get_chat_messages(
    limit: int = 20, *, user_id: str = DEFAULT_USER_ID
) -> list[dict[str, Any]]:
    """The most recent `limit` messages, oldest first, with `actions` parsed from JSON."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, role, content, actions, created_at FROM chat_messages "
            "WHERE user_id = ? ORDER BY created_at DESC, rowid DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    messages = []
    for row in reversed(rows):
        msg = dict(row)
        msg["actions"] = json.loads(msg["actions"]) if msg["actions"] is not None else None
        messages.append(msg)
    return messages
