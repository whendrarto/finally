"""SQLite persistence layer for FinAlly.

See the "DB Layer API" section of planning/TEAM_CONTRACT.md.
"""

from .connection import get_connection, get_db_path, init_db
from .repository import (
    add_watchlist_ticker,
    apply_trade,
    get_cash_balance,
    get_chat_messages,
    get_position,
    get_positions,
    get_snapshots,
    get_trades,
    get_watchlist,
    insert_chat_message,
    insert_snapshot,
    remove_watchlist_ticker,
)
from .seed import DEFAULT_CASH_BALANCE, DEFAULT_USER_ID, DEFAULT_WATCHLIST

__all__ = [
    "DEFAULT_CASH_BALANCE",
    "DEFAULT_USER_ID",
    "DEFAULT_WATCHLIST",
    "add_watchlist_ticker",
    "apply_trade",
    "get_cash_balance",
    "get_chat_messages",
    "get_connection",
    "get_db_path",
    "get_position",
    "get_positions",
    "get_snapshots",
    "get_trades",
    "get_watchlist",
    "init_db",
    "insert_chat_message",
    "insert_snapshot",
    "remove_watchlist_ticker",
]
