"""Fixtures for DB layer tests."""

import pytest

from app import db


@pytest.fixture
def db_path(tmp_path):
    """Initialize a fresh temporary database and make it active."""
    path = tmp_path / "test.db"
    db.init_db(path)
    return path
