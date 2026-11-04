"""Test setup: dummy secrets and an in-memory MongoDB."""

import os

import mongomock
import pytest

# config.py reads these on import; give them dummy values for tests.
os.environ.setdefault("BOT_TOKEN", "123456789:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017")


@pytest.fixture
def mongo_db(monkeypatch):
    """Replace the real MongoDB with an in-memory mock for each test."""
    import database

    client = mongomock.MongoClient()
    test_db = client["test_task_coach"]

    monkeypatch.setattr(database, "client", client)
    monkeypatch.setattr(database, "db", test_db)
    monkeypatch.setattr(database, "users", test_db.users)
    monkeypatch.setattr(database, "tasks", test_db.tasks)
    monkeypatch.setattr(database, "steps", test_db.steps)
    monkeypatch.setattr(database, "alerts", test_db.alerts)
    monkeypatch.setattr(database, "focus_sessions", test_db.focus_sessions)

    database.init_db()
    return test_db
