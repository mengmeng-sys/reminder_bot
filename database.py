"""MongoDB storage for the task coach bot (using pymongo).

All times are stored as UTC datetimes (BSON dates). Converting to Cambodia
time happens only when we show a time to the user.

The `id` of each object is the string form of MongoDB's ObjectId, for
example "507f1f77bcf86cd799439011". Keeping it as a string means it can be
used directly in callback data and URLs.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from bson import ObjectId
from pymongo import MongoClient

from config import MONGO_DB_NAME, MONGO_URI
from utils import utc_now

# One client for the whole app. pymongo manages a connection pool for us.
client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]

users = db.users
tasks = db.tasks
steps = db.steps
alerts = db.alerts
focus_sessions = db.focus_sessions


# --- Data classes ------------------------------------------------------------


@dataclass
class Task:
    id: str
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
    id: str
    task_id: str
    position: int
    text: str
    is_done: bool
    done_at: datetime | None


@dataclass
class Alert:
    id: str
    task_id: str
    kind: str
    fire_at_utc: datetime
    sent: bool


@dataclass
class FocusSession:
    id: str
    chat_id: int
    task_id: str | None
    kind: str  # focus | break
    started_at: datetime
    ends_at: datetime
    halfway_sent: bool
    status: str  # running | finished | stopped
    minutes: int


# --- Helpers -----------------------------------------------------------------


def to_object_id(value) -> ObjectId:
    """Convert a string (or ObjectId) into an ObjectId."""
    if isinstance(value, ObjectId):
        return value
    return ObjectId(str(value))


def _naive(value):
    """Make sure a datetime from MongoDB is naive UTC."""
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


def _task_from_doc(doc) -> Task:
    return Task(
        id=str(doc["_id"]),
        chat_id=doc["chat_id"],
        title=doc["title"],
        deadline_utc=_naive(doc["deadline_utc"]),
        estimate_minutes=doc["estimate_minutes"],
        status=doc["status"],
        created_at=_naive(doc["created_at"]),
        completed_at=_naive(doc.get("completed_at")),
        focus_minutes=doc.get("focus_minutes", 0),
    )


def _step_from_doc(doc) -> Step:
    return Step(
        id=str(doc["_id"]),
        task_id=str(doc["task_id"]),
        position=doc["position"],
        text=doc["text"],
        is_done=bool(doc.get("is_done")),
        done_at=_naive(doc.get("done_at")),
    )


def _alert_from_doc(doc) -> Alert:
    return Alert(
        id=str(doc["_id"]),
        task_id=str(doc["task_id"]),
        kind=doc["kind"],
        fire_at_utc=_naive(doc["fire_at_utc"]),
        sent=bool(doc.get("sent")),
    )


def _focus_from_doc(doc) -> FocusSession:
    return FocusSession(
        id=str(doc["_id"]),
        chat_id=doc["chat_id"],
        task_id=str(doc["task_id"]) if doc.get("task_id") else None,
        kind=doc["kind"],
        started_at=_naive(doc["started_at"]),
        ends_at=_naive(doc["ends_at"]),
        halfway_sent=bool(doc.get("halfway_sent")),
        status=doc["status"],
        minutes=doc["minutes"],
    )


# --- Setup -------------------------------------------------------------------


def init_db() -> None:
    """Create the indexes we need (safe to call more than once)."""
    users.create_index("chat_id", unique=True)
    tasks.create_index("chat_id")
    tasks.create_index("deadline_utc")
    steps.create_index("task_id")
    alerts.create_index("fire_at_utc")
    focus_sessions.create_index("chat_id")


# --- Users -------------------------------------------------------------------


def save_user(chat_id: int, first_name: str) -> None:
    """Add a user if they are not in the database yet."""
    users.update_one(
        {"chat_id": chat_id},
        {
            "$set": {"first_name": first_name},
            "$setOnInsert": {"created_at": utc_now()},
        },
        upsert=True,
    )


# --- Tasks -------------------------------------------------------------------


def add_task(
    chat_id: int,
    title: str,
    deadline_utc: datetime,
    estimate_minutes: int,
) -> str:
    """Save a task and return its new id."""
    result = tasks.insert_one(
        {
            "chat_id": chat_id,
            "title": title,
            "deadline_utc": deadline_utc,
            "estimate_minutes": estimate_minutes,
            "status": "active",
            "created_at": utc_now(),
            "completed_at": None,
            "focus_minutes": 0,
        }
    )
    return str(result.inserted_id)


def get_task(task_id) -> Task | None:
    doc = tasks.find_one({"_id": to_object_id(task_id)})
    return _task_from_doc(doc) if doc else None


def get_active_tasks(chat_id: int) -> list[Task]:
    """All active tasks for a user, soonest deadline first."""
    cursor = tasks.find({"chat_id": chat_id, "status": "active"}).sort(
        "deadline_utc", 1
    )
    return [_task_from_doc(doc) for doc in cursor]


def update_task_deadline(task_id, deadline_utc: datetime) -> None:
    tasks.update_one(
        {"_id": to_object_id(task_id)}, {"$set": {"deadline_utc": deadline_utc}}
    )


def update_task_estimate(task_id, estimate_minutes: int) -> None:
    tasks.update_one(
        {"_id": to_object_id(task_id)},
        {"$set": {"estimate_minutes": estimate_minutes}},
    )


def mark_task_done(task_id) -> None:
    tasks.update_one(
        {"_id": to_object_id(task_id)},
        {"$set": {"status": "done", "completed_at": utc_now()}},
    )


def mark_task_deleted(task_id) -> None:
    tasks.update_one(
        {"_id": to_object_id(task_id)}, {"$set": {"status": "deleted"}}
    )


def add_focus_minutes(task_id, minutes: int) -> None:
    tasks.update_one(
        {"_id": to_object_id(task_id)}, {"$inc": {"focus_minutes": int(minutes)}}
    )


# --- Steps -------------------------------------------------------------------


def add_step(task_id, text: str, position: int | None = None) -> str:
    """Add a step. If position is None, put it at the end."""
    if position is None:
        last = steps.find_one(
            {"task_id": to_object_id(task_id)}, sort=[("position", -1)]
        )
        position = (last["position"] + 1) if last else 1

    result = steps.insert_one(
        {
            "task_id": to_object_id(task_id),
            "position": position,
            "text": text,
            "is_done": False,
            "done_at": None,
        }
    )
    return str(result.inserted_id)


def get_steps(task_id) -> list[Step]:
    """All steps for a task, in order."""
    cursor = steps.find({"task_id": to_object_id(task_id)}).sort(
        [("position", 1), ("_id", 1)]
    )
    return [_step_from_doc(doc) for doc in cursor]


def get_step(step_id) -> Step | None:
    doc = steps.find_one({"_id": to_object_id(step_id)})
    return _step_from_doc(doc) if doc else None


def toggle_step(step_id) -> None:
    """Flip a step between done and not done."""
    step = steps.find_one({"_id": to_object_id(step_id)}, {"is_done": 1})
    if not step:
        return

    new_value = not step["is_done"]
    steps.update_one(
        {"_id": to_object_id(step_id)},
        {"$set": {"is_done": new_value, "done_at": utc_now() if new_value else None}},
    )


def update_step_text(step_id, text: str) -> None:
    steps.update_one({"_id": to_object_id(step_id)}, {"$set": {"text": text}})


def delete_step(step_id) -> None:
    steps.delete_one({"_id": to_object_id(step_id)})


def get_next_step(task_id) -> Step | None:
    """The first step that is not done yet."""
    for step in get_steps(task_id):
        if not step.is_done:
            return step
    return None


# --- Alerts ------------------------------------------------------------------


def delete_alerts(task_id) -> None:
    alerts.delete_many({"task_id": to_object_id(task_id)})


def add_alert(task_id, kind: str, fire_at_utc: datetime) -> str:
    result = alerts.insert_one(
        {
            "task_id": to_object_id(task_id),
            "kind": kind,
            "fire_at_utc": fire_at_utc,
            "sent": False,
        }
    )
    return str(result.inserted_id)


def rebuild_alerts(task_id, schedule) -> None:
    """Replace all alerts for a task with a new schedule."""
    delete_alerts(task_id)
    for kind, fire_at in schedule:
        add_alert(task_id, kind, fire_at)


def get_due_alerts(now: datetime) -> list[Alert]:
    """All unsent alerts whose time has come."""
    cursor = alerts.find({"sent": False, "fire_at_utc": {"$lte": now}}).sort(
        "fire_at_utc", 1
    )
    return [_alert_from_doc(doc) for doc in cursor]


def mark_alerts_sent(alert_ids: list) -> None:
    if not alert_ids:
        return
    alerts.update_many(
        {"_id": {"$in": [to_object_id(a) for a in alert_ids]}},
        {"$set": {"sent": True}},
    )


# --- Focus sessions ----------------------------------------------------------


def create_focus_session(
    chat_id: int,
    task_id,
    kind: str,
    started_at: datetime,
    ends_at: datetime,
    minutes: int,
) -> str:
    result = focus_sessions.insert_one(
        {
            "chat_id": chat_id,
            "task_id": to_object_id(task_id) if task_id else None,
            "kind": kind,
            "started_at": started_at,
            "ends_at": ends_at,
            "halfway_sent": False,
            "status": "running",
            "minutes": minutes,
        }
    )
    return str(result.inserted_id)


def get_focus_session(session_id) -> FocusSession | None:
    doc = focus_sessions.find_one({"_id": to_object_id(session_id)})
    return _focus_from_doc(doc) if doc else None


def get_running_session(chat_id: int) -> FocusSession | None:
    """The one active focus/break session for a user, if any."""
    doc = focus_sessions.find_one(
        {"chat_id": chat_id, "status": "running"}, sort=[("_id", -1)]
    )
    return _focus_from_doc(doc) if doc else None


def get_running_sessions() -> list[FocusSession]:
    """All running sessions (used on startup to rebuild jobs)."""
    return [
        _focus_from_doc(doc)
        for doc in focus_sessions.find({"status": "running"})
    ]


def finish_focus_session(session_id, status: str) -> None:
    focus_sessions.update_one(
        {"_id": to_object_id(session_id)}, {"$set": {"status": status}}
    )


def set_halfway_sent(session_id) -> None:
    focus_sessions.update_one(
        {"_id": to_object_id(session_id)}, {"$set": {"halfway_sent": True}}
    )


def get_last_focus_minutes(chat_id: int) -> int | None:
    """The length of the user's most recent focus session (for 'Another round')."""
    doc = focus_sessions.find_one(
        {"chat_id": chat_id, "kind": "focus"}, sort=[("_id", -1)]
    )
    return doc["minutes"] if doc else None
