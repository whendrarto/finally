"""Tests for schema creation, seeding, and DB path resolution."""

import sqlite3

import pytest

from app import db
from app.db import connection

EXPECTED_TABLES = {
    "users_profile",
    "watchlist",
    "positions",
    "trades",
    "portfolio_snapshots",
    "chat_messages",
}


class TestInit:
    def test_creates_all_tables(self, db_path):
        conn = sqlite3.connect(db_path)
        tables = {
            row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        conn.close()
        assert EXPECTED_TABLES <= tables

    def test_wal_mode(self, db_path):
        conn = sqlite3.connect(db_path)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()
        assert mode.lower() == "wal"

    def test_seeds_default_user(self, db_path):
        assert db.get_cash_balance() == 10000.0

    def test_seeds_default_watchlist_in_order(self, db_path):
        assert db.get_watchlist() == list(db.DEFAULT_WATCHLIST)
        assert len(db.get_watchlist()) == 10

    def test_starts_empty(self, db_path):
        assert db.get_positions() == []
        assert db.get_trades() == []
        assert db.get_snapshots() == []
        assert db.get_chat_messages() == []

    def test_idempotent(self, db_path):
        db.add_watchlist_ticker("PYPL")
        db.apply_trade("AAPL", "buy", 1, 100.0, 9900.0, 1, 100.0)
        db.init_db(db_path)
        db.init_db(db_path)
        assert db.get_watchlist().count("AAPL") == 1
        assert "PYPL" in db.get_watchlist()
        assert db.get_cash_balance() == 9900.0
        assert len(db.get_positions()) == 1

    def test_reinit_after_file_deleted_reseeds(self, tmp_path):
        path = tmp_path / "gone.db"
        db.init_db(path)
        db.add_watchlist_ticker("PYPL")
        for suffix in ("", "-wal", "-shm"):
            p = path.with_name(path.name + suffix)
            if p.exists():
                p.unlink()
        # lazy init recreates the schema on next access
        assert db.get_watchlist() == list(db.DEFAULT_WATCHLIST)

    def test_creates_parent_directory(self, tmp_path):
        path = tmp_path / "nested" / "dir" / "finally.db"
        db.init_db(path)
        assert path.exists()
        assert db.get_db_path() == path

    def test_accepts_str_path(self, tmp_path):
        path = tmp_path / "str.db"
        db.init_db(str(path))
        assert path.exists()

    def test_switching_paths_isolates_data(self, tmp_path):
        db.init_db(tmp_path / "a.db")
        db.add_watchlist_ticker("PYPL")
        db.init_db(tmp_path / "b.db")
        assert "PYPL" not in db.get_watchlist()
        db.init_db(tmp_path / "a.db")
        assert "PYPL" in db.get_watchlist()


class TestPathResolution:
    def test_env_var_used_when_no_path(self, tmp_path, monkeypatch):
        path = tmp_path / "env.db"
        monkeypatch.setenv("FINALLY_DB_PATH", str(path))
        db.init_db()
        assert db.get_db_path() == path
        assert path.exists()

    def test_default_path_is_project_db_dir(self, monkeypatch):
        monkeypatch.delenv("FINALLY_DB_PATH", raising=False)
        assert connection._resolve_path(None) == connection.PROJECT_ROOT / "db" / "finally.db"
        assert (connection.PROJECT_ROOT / "backend").is_dir()

    def test_explicit_path_beats_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("FINALLY_DB_PATH", str(tmp_path / "env.db"))
        db.init_db(tmp_path / "explicit.db")
        assert db.get_db_path() == tmp_path / "explicit.db"


class TestConnection:
    def test_rollback_on_error(self, db_path):
        try:
            with db.get_connection() as conn:
                conn.execute("UPDATE users_profile SET cash_balance = 1 WHERE id = 'default'")
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        assert db.get_cash_balance() == 10000.0

    def test_check_constraints(self, db_path):

        with pytest.raises(sqlite3.IntegrityError):
            db.insert_chat_message("system", "nope")
        with pytest.raises(sqlite3.IntegrityError):
            db.apply_trade("AAPL", "hold", 1, 1.0, 9999.0, 1, 1.0)
        # failed trade left nothing behind
        assert db.get_trades() == []
        assert db.get_cash_balance() == 10000.0
