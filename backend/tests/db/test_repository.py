"""Tests for the data-access functions."""

import sqlite3
from datetime import datetime

import pytest

from app import db


class TestWatchlist:
    def test_add_new_ticker(self, db_path):
        assert db.add_watchlist_ticker("PYPL") is True
        assert db.get_watchlist()[-1] == "PYPL"

    def test_add_duplicate_returns_false(self, db_path):
        assert db.add_watchlist_ticker("AAPL") is False
        assert db.get_watchlist().count("AAPL") == 1

    def test_add_is_case_insensitive(self, db_path):
        assert db.add_watchlist_ticker("aapl") is False
        assert db.add_watchlist_ticker("pypl") is True
        assert "PYPL" in db.get_watchlist()

    def test_remove_present(self, db_path):
        assert db.remove_watchlist_ticker("AAPL") is True
        assert "AAPL" not in db.get_watchlist()

    def test_remove_absent_returns_false(self, db_path):
        assert db.remove_watchlist_ticker("ZZZZ") is False

    def test_add_order_preserved(self, db_path):
        for t in ("PYPL", "AMD", "INTC"):
            db.add_watchlist_ticker(t)
        assert db.get_watchlist()[-3:] == ["PYPL", "AMD", "INTC"]

    def test_readd_after_remove(self, db_path):
        db.remove_watchlist_ticker("AAPL")
        assert db.add_watchlist_ticker("AAPL") is True
        assert db.get_watchlist()[-1] == "AAPL"

    def test_user_isolation(self, db_path):
        assert db.add_watchlist_ticker("AAPL", user_id="other") is True
        assert db.get_watchlist(user_id="other") == ["AAPL"]
        assert db.remove_watchlist_ticker("AAPL", user_id="other") is True
        assert "AAPL" in db.get_watchlist()

    def test_unique_constraint_enforced_in_schema(self, db_path):
        with pytest.raises(sqlite3.IntegrityError):
            with db.get_connection() as conn:
                conn.execute(
                    "INSERT INTO watchlist (id, user_id, ticker, added_at) "
                    "VALUES ('x', 'default', 'AAPL', '2024-01-01')"
                )


class TestTrades:
    def test_buy_creates_position_and_trade(self, db_path):
        trade = db.apply_trade("AAPL", "buy", 10, 190.0, 8100.0, 10, 190.0)
        assert set(trade) == {"id", "ticker", "side", "quantity", "price", "executed_at"}
        assert trade["ticker"] == "AAPL"
        assert trade["side"] == "buy"
        assert trade["quantity"] == 10
        assert trade["price"] == 190.0
        datetime.fromisoformat(trade["executed_at"])

        assert db.get_cash_balance() == 8100.0
        pos = db.get_position("AAPL")
        assert pos["quantity"] == 10
        assert pos["avg_cost"] == 190.0
        assert db.get_trades() == [trade]

    def test_second_buy_updates_position(self, db_path):
        db.apply_trade("AAPL", "buy", 10, 100.0, 9000.0, 10, 100.0)
        db.apply_trade("AAPL", "buy", 10, 200.0, 7000.0, 20, 150.0)
        positions = db.get_positions()
        assert len(positions) == 1
        assert positions[0]["quantity"] == 20
        assert positions[0]["avg_cost"] == 150.0
        assert db.get_cash_balance() == 7000.0

    def test_partial_sell(self, db_path):
        db.apply_trade("AAPL", "buy", 10, 100.0, 9000.0, 10, 100.0)
        db.apply_trade("AAPL", "sell", 4, 120.0, 9480.0, 6, 100.0)
        pos = db.get_position("AAPL")
        assert pos["quantity"] == 6
        assert pos["avg_cost"] == 100.0
        assert db.get_cash_balance() == 9480.0

    def test_full_close_deletes_position(self, db_path):
        db.apply_trade("AAPL", "buy", 10, 100.0, 9000.0, 10, 100.0)
        db.apply_trade("AAPL", "sell", 10, 90.0, 9900.0, 0, 100.0)
        assert db.get_position("AAPL") is None
        assert db.get_positions() == []
        assert len(db.get_trades()) == 2

    def test_near_zero_quantity_closes_position(self, db_path):
        db.apply_trade("AAPL", "buy", 0.3, 100.0, 9970.0, 0.3, 100.0)
        db.apply_trade("AAPL", "sell", 0.3, 100.0, 10000.0, 0.3 - 0.1 - 0.1 - 0.1, 100.0)
        assert db.get_position("AAPL") is None

    def test_fractional_shares(self, db_path):
        db.apply_trade("TSLA", "buy", 0.5, 250.0, 9875.0, 0.5, 250.0)
        assert db.get_position("tsla")["quantity"] == 0.5

    def test_ticker_uppercased(self, db_path):
        trade = db.apply_trade("nvda", "buy", 1, 800.0, 9200.0, 1, 800.0)
        assert trade["ticker"] == "NVDA"
        assert db.get_position("NVDA") is not None

    def test_get_position_missing(self, db_path):
        assert db.get_position("AAPL") is None

    def test_positions_sorted_by_ticker(self, db_path):
        db.apply_trade("TSLA", "buy", 1, 10.0, 9990.0, 1, 10.0)
        db.apply_trade("AAPL", "buy", 1, 10.0, 9980.0, 1, 10.0)
        assert [p["ticker"] for p in db.get_positions()] == ["AAPL", "TSLA"]
        assert set(db.get_positions()[0]) == {"ticker", "quantity", "avg_cost", "updated_at"}

    def test_trades_newest_first_and_limit(self, db_path):
        ids = [
            db.apply_trade("AAPL", "buy", 1, 100.0, 10000.0 - 100 * (i + 1), i + 1, 100.0)["id"]
            for i in range(5)
        ]
        trades = db.get_trades()
        assert [t["id"] for t in trades] == list(reversed(ids))
        assert [t["id"] for t in db.get_trades(limit=2)] == [ids[4], ids[3]]

    def test_unknown_user_rolls_back(self, db_path):
        with pytest.raises(ValueError):
            db.apply_trade("AAPL", "buy", 1, 100.0, 9900.0, 1, 100.0, user_id="ghost")
        assert db.get_trades(user_id="ghost") == []
        assert db.get_positions(user_id="ghost") == []

    def test_transaction_atomic_on_failure(self, db_path):
        """If a statement in apply_trade fails, nothing is persisted."""
        db.apply_trade("AAPL", "buy", 10, 100.0, 9000.0, 10, 100.0)
        with db.get_connection() as conn:
            conn.execute(
                "CREATE TRIGGER fail_pos BEFORE UPDATE ON positions "
                "BEGIN SELECT RAISE(ABORT, 'forced'); END"
            )
        with pytest.raises(sqlite3.IntegrityError):
            db.apply_trade("AAPL", "buy", 10, 100.0, 8000.0, 20, 100.0)
        assert db.get_cash_balance() == 9000.0
        assert len(db.get_trades()) == 1
        assert db.get_position("AAPL")["quantity"] == 10


class TestSnapshots:
    def test_insert_and_get_oldest_first(self, db_path):
        for v in (10000.0, 10050.0, 9990.0):
            db.insert_snapshot(v)
        snaps = db.get_snapshots()
        assert [s["total_value"] for s in snaps] == [10000.0, 10050.0, 9990.0]
        assert set(snaps[0]) == {"total_value", "recorded_at"}
        times = [s["recorded_at"] for s in snaps]
        assert times == sorted(times)

    def test_limit_returns_most_recent_oldest_first(self, db_path):
        for v in range(5):
            db.insert_snapshot(float(v))
        assert [s["total_value"] for s in db.get_snapshots(limit=2)] == [3.0, 4.0]

    def test_user_isolation(self, db_path):
        db.insert_snapshot(1.0, user_id="other")
        assert db.get_snapshots() == []
        assert len(db.get_snapshots(user_id="other")) == 1


class TestChat:
    def test_user_message_no_actions(self, db_path):
        msg = db.insert_chat_message("user", "hello")
        assert msg["role"] == "user"
        assert msg["content"] == "hello"
        assert msg["actions"] is None
        assert set(msg) == {"id", "role", "content", "actions", "created_at"}
        assert db.get_chat_messages() == [msg]

    def test_actions_json_round_trip(self, db_path):
        actions = {
            "trades": [
                {"ticker": "AAPL", "side": "buy", "quantity": 1.5, "price": 190.25,
                 "status": "executed", "error": None}
            ],
            "watchlist_changes": [
                {"ticker": "PYPL", "action": "add", "status": "failed", "error": "dup"}
            ],
        }
        db.insert_chat_message("assistant", "Done", actions)
        [stored] = db.get_chat_messages()
        assert stored["actions"] == actions

    def test_empty_actions_dict_preserved(self, db_path):
        db.insert_chat_message("assistant", "ok", {})
        assert db.get_chat_messages()[0]["actions"] == {}

    def test_order_and_limit(self, db_path):
        for i in range(25):
            db.insert_chat_message("user" if i % 2 == 0 else "assistant", f"m{i}")
        default = db.get_chat_messages()
        assert len(default) == 20
        assert [m["content"] for m in default] == [f"m{i}" for i in range(5, 25)]
        assert [m["content"] for m in db.get_chat_messages(limit=3)] == ["m22", "m23", "m24"]

    def test_user_isolation(self, db_path):
        db.insert_chat_message("user", "hi", user_id="other")
        assert db.get_chat_messages() == []
