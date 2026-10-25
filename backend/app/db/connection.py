"""SQLite connection management and lazy initialization."""

from __future__ import annotations

import os
import sqlite3
import threading
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from .seed import DEFAULT_CASH_BALANCE, DEFAULT_USER_ID, DEFAULT_WATCHLIST

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
# backend/app/db/connection.py -> project root is three levels above this package
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = PROJECT_ROOT / "db" / "finally.db"

_lock = threading.Lock()
_db_path: Path | None = None
_initialized: set[Path] = set()


def now_iso() -> str:
    """Current time as an ISO-8601 UTC string."""
    return datetime.now(UTC).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


def _resolve_path(db_path: str | os.PathLike[str] | None) -> Path:
    if db_path is not None:
        return Path(db_path)
    env_path = os.environ.get("FINALLY_DB_PATH")
    if env_path:
        return Path(env_path)
    return DEFAULT_DB_PATH


def get_db_path() -> Path:
    """The active database path (set by init_db, else env/default)."""
    return _db_path if _db_path is not None else _resolve_path(None)


def _open(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str | os.PathLike[str] | None = None) -> None:
    """Make `db_path` the active database; create tables and seed defaults if needed.

    Idempotent: re-running never duplicates seed data or alters existing rows.
    """
    global _db_path
    path = _resolve_path(db_path)
    with _lock:
        _db_path = path
        _ensure_initialized(path)


def _ensure_initialized(path: Path) -> None:
    """Create schema + seed (caller must hold _lock)."""
    if path in _initialized and path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = _open(path)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        _seed(conn)
        conn.commit()
    finally:
        conn.close()
    _initialized.add(path)


def _seed(conn: sqlite3.Connection) -> None:
    """Seed the default user and watchlist when the user does not exist yet."""
    exists = conn.execute(
        "SELECT 1 FROM users_profile WHERE id = ?", (DEFAULT_USER_ID,)
    ).fetchone()
    if exists:
        return
    ts = now_iso()
    conn.execute(
        "INSERT INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
        (DEFAULT_USER_ID, DEFAULT_CASH_BALANCE, ts),
    )
    conn.executemany(
        "INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
        [(new_id(), DEFAULT_USER_ID, ticker, ts) for ticker in DEFAULT_WATCHLIST],
    )


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Short-lived connection to the active DB (lazily initialized).

    Commits on success, rolls back on exception, always closes.
    """
    path = get_db_path()
    if path not in _initialized or not path.exists():
        with _lock:
            _ensure_initialized(path)
    conn = _open(path)
    try:
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()
