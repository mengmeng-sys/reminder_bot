"""Tests for the SQLite storage layer."""

from datetime import timedelta

import database
from utils import alert_schedule, utc_now


def test_task_and_steps(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "test.sqlite"))
    database.init_db()

    deadline = utc_now() + timedelta(days=2)
    task_id = database.add_task(1, "Finish report", deadline, 120)

    database.add_step(task_id, "Write intro")
    database.add_step(task_id, "Make chart")

    steps = database.get_steps(task_id)
    assert [step.text for step in steps] == ["Write intro", "Make chart"]
    assert database.get_next_step(task_id).text == "Write intro"

    database.toggle_step(steps[0].id)
    assert database.get_next_step(task_id).text == "Make chart"


def test_alerts_rebuild_and_due(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "test.sqlite"))
    database.init_db()

    deadline = utc_now() + timedelta(days=2)
    task_id = database.add_task(1, "Task", deadline, 120)
    database.rebuild_alerts(task_id, alert_schedule(deadline, 120))

    # All alerts are in the future, so none are due yet.
    assert database.get_due_alerts(utc_now()) == []

    # Rebuild with an alert that is already in the past.
    database.rebuild_alerts(
        task_id, [("overdue", utc_now() - timedelta(minutes=1))]
    )
    due = database.get_due_alerts(utc_now())
    assert len(due) == 1
    assert due[0].kind == "overdue"

    database.mark_alerts_sent([due[0].id])
    assert database.get_due_alerts(utc_now()) == []


def test_focus_sessions(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "test.sqlite"))
    database.init_db()

    now = utc_now()
    session_id = database.create_focus_session(
        1, None, "focus", now, now + timedelta(minutes=25), 25
    )

    session = database.get_focus_session(session_id)
    assert session.status == "running"
    assert database.get_running_session(1).id == session_id
    assert database.get_last_focus_minutes(1) == 25

    database.finish_focus_session(session_id, "finished")
    assert database.get_running_session(1) is None


def test_only_own_tasks_are_returned(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "test.sqlite"))
    database.init_db()

    deadline = utc_now() + timedelta(days=1)
    database.add_task(1, "User 1 task", deadline, 60)
    database.add_task(2, "User 2 task", deadline, 60)

    titles = [task.title for task in database.get_active_tasks(1)]
    assert titles == ["User 1 task"]
