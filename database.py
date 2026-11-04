"""SQLite storage for the task coach bot.

All times are stored as naive UTC ISO strings. Converting to Cambodia time
happens only when we show a time to the user.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime

from config import DB_PATH
from utils import utc_now

# --- Data classes ------------------------------------------------------------


@dataclass
class Task:
    id: int
    chat_id: int
    title: str
    deadline_utc: datetime
    estimate_minutes: int
    status: str  # active | done | deleted
    created_at: datetime
    completed_at: datetime | None
    focus_minutes: int


@dataclass
class Step:
    id: int
    task_id: int
    position: int
    text: str
    is_done: bool
    done_at: datetime | None


@dataclass
class Alert:
    id: int
    task_id: int
    kind: str
    fire_at_utc: datetime
    sent: bool


@dataclass
class FocusSession:
    id: int
    chat_id: int
    task_id: int | None
    kind: str  # focus | break
    started_at: datetime
    ends_at: datetime
    halfway_sent: bool
    status: str  # running | finished | stopped
    minutes: int


# --- Connection helpers ------------------------------------------------------


def _connect() -> sqlite3.Connection:
    """Open a new connection (one per operation keeps things simple)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Needed so that "ON DELETE CASCADE" actually works.
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _task_from_row(row: sqlite3.Row) -> Task:
    return Task(
        id=row["id"],
        chat_id=row["chat_id"],
        title=row["title"],
        deadline_utc=datetime.fromisoformat(row["deadline_utc"]),
        estimate_minutes=row["estimate_minutes"],
        status=row["status"],
        created_at=datetime.fromisoformat(row["created_at"]),
        completed_at=(
            datetime.fromisoformat(row["completed_at"])
            if row["completed_at"]
            else None
        ),
        focus_minutes=row["focus_minutes"],
    )


def _step_from_row(row: sqlite3.Row) -> Step:
    return Step(
        id=row["id"],
        task_id=row["task_id"],
        position=row["position"],
        text=row["text"],
        is_done=bool(row["is_done"]),
        done_at=datetime.fromisoformat(row["done_at"]) if row["done_at"] else None,
    )


def _alert_from_row(row: sqlite3.Row) -> Alert:
    return Alert(
        id=row["id"],
        task_id=row["task_id"],
        kind=row["kind"],
        fire_at_utc=datetime.fromisoformat(row["fire_at_utc"]),
        sent=bool(row["sent"]),
    )


def _focus_from_row(row: sqlite3.Row) -> FocusSession:
    return FocusSession(
        id=row["id"],
        chat_id=row["chat_id"],
        task_id=row["task_id"],
        kind=row["kind"],
        started_at=datetime.fromisoformat(row["started_at"]),
        ends_at=datetime.fromisoformat(row["ends_at"]),
        halfway_sent=bool(row["halfway_sent"]),
        status=row["status"],
        minutes=row["minutes"],
    )


def _dt(value: datetime | None) -> str | None:
    """Format a datetime for SQLite, or None."""
    return value.isoformat(timespec="seconds") if value else None


# --- Setup -------------------------------------------------------------------


def init_db() -> None:
    """Create all tables if they do not exist yet."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                chat_id    INTEGER PRIMARY KEY,
                first_name TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id          INTEGER NOT NULL,
                title            TEXT NOT NULL,
                deadline_utc     TEXT NOT NULL,
                estimate_minutes INTEGER NOT NULL,
                status           TEXT NOT NULL DEFAULT 'active',
                created_at       TEXT NOT NULL,
                completed_at     TEXT,
                focus_minutes    INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tasks_chat ON tasks(chat_id)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS steps (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id  INTEGER NOT NULL,
                position INTEGER NOT NULL,
                text     TEXT NOT NULL,
                is_done  INTEGER NOT NULL DEFAULT 0,
                done_at  TEXT,
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_steps_task ON steps(task_id)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id     INTEGER NOT NULL,
                kind        TEXT NOT NULL,
                fire_at_utc TEXT NOT NULL,
                sent        INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_alerts_fire ON alerts(fire_at_utc)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS focus_sessions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id      INTEGER NOT NULL,
                task_id      INTEGER,
                kind         TEXT NOT NULL,
                started_at   TEXT NOT NULL,
                ends_at      TEXT NOT NULL,
                halfway_sent INTEGER NOT NULL DEFAULT 0,
                status       TEXT NOT NULL,
                minutes      INTEGER NOT NULL,
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE SET NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_focus_chat ON focus_sessions(chat_id)"
        )


# --- Users -------------------------------------------------------------------


def save_user(chat_id: int, first_name: str) -> None:
    """Add a user if they are not in the database yet."""
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO users (chat_id, first_name, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET first_name = excluded.first_name
            """,
            (chat_id, first_name, _dt(utc_now())),
        )


# --- Tasks -------------------------------------------------------------------


def add_task(
    chat_id: int,
    title: str,
    deadline_utc: datetime,
    estimate_minutes: int,
) -> int:
    """Save a task and return its new id."""
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO tasks
                (chat_id, title, deadline_utc, estimate_minutes, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                chat_id,
                title,
                _dt(deadline_utc),
                estimate_minutes,
                _dt(utc_now()),
            ),
        )
        return cursor.lastrowid


def get_task(task_id: int) -> Task | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return _task_from_row(row) if row else None


def get_active_tasks(chat_id: int) -> list[Task]:
    """All active tasks for a user, soonest deadline first."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM tasks
            WHERE chat_id = ? AND status = 'active'
            ORDER BY deadline_utc ASC
            """,
            (chat_id,),
        ).fetchall()
        return [_task_from_row(row) for row in rows]


def update_task_deadline(task_id: int, deadline_utc: datetime) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE tasks SET deadline_utc = ? WHERE id = ?",
            (_dt(deadline_utc), task_id),
        )


def update_task_estimate(task_id: int, estimate_minutes: int) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE tasks SET estimate_minutes = ? WHERE id = ?",
            (estimate_minutes, task_id),
        )


def mark_task_done(task_id: int) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE tasks SET status = 'done', completed_at = ? WHERE id = ?",
            (_dt(utc_now()), task_id),
        )


def mark_task_deleted(task_id: int) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE tasks SET status = 'deleted' WHERE id = ?", (task_id,)
        )


def add_focus_minutes(task_id: int, minutes: int) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE tasks SET focus_minutes = focus_minutes + ? WHERE id = ?",
            (int(minutes), task_id),
        )


# --- Steps -------------------------------------------------------------------


def add_step(task_id: int, text: str, position: int | None = None) -> int:
    """Add a step. If position is None, put it at the end."""
    with _connect() as conn:
        if position is None:
            row = conn.execute(
                "SELECT COALESCE(MAX(position), 0) AS max_pos FROM steps WHERE task_id = ?",
                (task_id,),
            ).fetchone()
            position = row["max_pos"] + 1

        cursor = conn.execute(
            "INSERT INTO steps (task_id, position, text) VALUES (?, ?, ?)",
            (task_id, position, text),
        )
        return cursor.lastrowid


def get_steps(task_id: int) -> list[Step]:
    """All steps for a task, in order."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM steps WHERE task_id = ? ORDER BY position, id",
            (task_id,),
        ).fetchall()
        return [_step_from_row(row) for row in rows]


def get_step(step_id: int) -> Step | None:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM steps WHERE id = ?", (step_id,)).fetchone()
        return _step_from_row(row) if row else None


def toggle_step(step_id: int) -> None:
    """Flip a step between done and not done."""
    with _connect() as conn:
        step = conn.execute(
            "SELECT is_done FROM steps WHERE id = ?", (step_id,)
        ).fetchone()
        if not step:
            return

        new_value = 0 if step["is_done"] else 1
        done_at = _dt(utc_now()) if new_value else None
        conn.execute(
            "UPDATE steps SET is_done = ?, done_at = ? WHERE id = ?",
            (new_value, done_at, step_id),
        )


def update_step_text(step_id: int, text: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE steps SET text = ? WHERE id = ?", (text, step_id))


def delete_step(step_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM steps WHERE id = ?", (step_id,))


def get_next_step(task_id: int) -> Step | None:
    """The first step that is not done yet."""
    for step in get_steps(task_id):
        if not step.is_done:
            return step
    return None


# --- Alerts ------------------------------------------------------------------


def delete_alerts(task_id: int) -> None:
    with _connect() as conn:
        conn.execute("DELETE FROM alerts WHERE task_id = ?", (task_id,))


def add_alert(task_id: int, kind: str, fire_at_utc: datetime) -> int:
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO alerts (task_id, kind, fire_at_utc) VALUES (?, ?, ?)",
            (task_id, kind, _dt(fire_at_utc)),
        )
        return cursor.lastrowid


def rebuild_alerts(task_id: int, schedule) -> None:
    """Replace all alerts for a task with a new schedule."""
    delete_alerts(task_id)
    for kind, fire_at in schedule:
        add_alert(task_id, kind, fire_at)


def get_due_alerts(now: datetime) -> list[Alert]:
    """All unsent alerts whose time has come."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM alerts
            WHERE sent = 0 AND fire_at_utc <= ?
            ORDER BY fire_at_utc
            """,
            (_dt(now),),
        ).fetchall()
        return [_alert_from_row(row) for row in rows]


def mark_alerts_sent(alert_ids: list[int]) -> None:
    if not alert_ids:
        return
    placeholders = ", ".join("?" for _ in alert_ids)
    with _connect() as conn:
        conn.execute(
            f"UPDATE alerts SET sent = 1 WHERE id IN ({placeholders})",
            alert_ids,
        )


# --- Focus sessions ----------------------------------------------------------


def create_focus_session(
    chat_id: int,
    task_id: int | None,
    kind: str,
    started_at: datetime,
    ends_at: datetime,
    minutes: int,
) -> int:
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO focus_sessions
                (chat_id, task_id, kind, started_at, ends_at, status, minutes)
            VALUES (?, ?, ?, ?, ?, 'running', ?)
            """,
            (chat_id, task_id, kind, _dt(started_at), _dt(ends_at), minutes),
        )
        return cursor.lastrowid


def get_focus_session(session_id: int) -> FocusSession | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM focus_sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return _focus_from_row(row) if row else None


def get_running_session(chat_id: int) -> FocusSession | None:
    """The one active focus/break session for a user, if any."""
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT * FROM focus_sessions
            WHERE chat_id = ? AND status = 'running'
            ORDER BY id DESC LIMIT 1
            """,
            (chat_id,),
        ).fetchone()
        return _focus_from_row(row) if row else None


def get_running_sessions() -> list[FocusSession]:
    """All running sessions (used on startup to rebuild jobs)."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM focus_sessions WHERE status = 'running'"
        ).fetchall()
        return [_focus_from_row(row) for row in rows]


def finish_focus_session(session_id: int, status: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE focus_sessions SET status = ? WHERE id = ?",
            (status, session_id),
        )


def set_halfway_sent(session_id: int) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE focus_sessions SET halfway_sent = 1 WHERE id = ?",
            (session_id,),
        )


def get_last_focus_minutes(chat_id: int) -> int | None:
    """The length of the user's most recent focus session (for 'Another round')."""
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT minutes FROM focus_sessions
            WHERE chat_id = ? AND kind = 'focus'
            ORDER BY id DESC LIMIT 1
            """,
            (chat_id,),
        ).fetchone()
        return row["minutes"] if row else None
