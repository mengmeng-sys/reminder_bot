"""Time and text helpers for the task coach bot.

Keeping these in one place makes the handlers short and easy to read.
All times in the database are naive UTC; these helpers convert for display.
"""

from datetime import UTC, date, datetime, timedelta
from html import escape

from config import LOCAL_TZ

# Fixed English labels so the output looks the same on every computer.
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]

# Extra time added on top of the estimate when calculating the latest start.
BUFFER_PERCENT = 0.20


# --- Time helpers ------------------------------------------------------------


def utc_now() -> datetime:
    """Current time in UTC (naive, matching what we store in SQLite)."""
    return datetime.now(UTC).replace(tzinfo=None)


def to_local(dt_utc: datetime) -> datetime:
    """Convert a stored UTC datetime to Cambodia time."""
    return dt_utc.replace(tzinfo=UTC).astimezone(LOCAL_TZ)


def local_to_utc(day: date, hour: int, minute: int) -> datetime:
    """Combine a date and time in Cambodia time and return naive UTC."""
    local = datetime(day.year, day.month, day.day, hour, minute, tzinfo=LOCAL_TZ)
    return local.astimezone(UTC).replace(tzinfo=None)


def format_when(dt_utc: datetime) -> str:
    """Format a stored UTC time as 'Fri, 8 Nov · 18:00' in Cambodia time."""
    local = to_local(dt_utc)
    return (
        f"{WEEKDAYS[local.weekday()]}, {local.day} "
        f"{MONTHS[local.month - 1]} · {local:%H:%M}"
    )


def format_time(dt_utc: datetime) -> str:
    """Format only the clock time, e.g. '18:00'."""
    return f"{to_local(dt_utc):%H:%M}"


def format_duration(minutes: int) -> str:
    """Format minutes as '2 h', '1 h 15 min' or '30 min'."""
    minutes = int(minutes)
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"{hours} h {mins} min"
    if hours:
        return f"{hours} h"
    return f"{mins} min"


# --- Deadline maths ----------------------------------------------------------


def latest_start_time(deadline_utc: datetime, estimate_minutes: int) -> datetime:
    """The latest moment you can start and still finish on time.

    latest start = deadline - estimate - 20% buffer
    """
    buffer_minutes = estimate_minutes * BUFFER_PERCENT
    return deadline_utc - timedelta(minutes=estimate_minutes + buffer_minutes)


def alert_schedule(deadline_utc: datetime, estimate_minutes: int):
    """Return the list of (kind, fire_at_utc) alerts for a task."""
    latest_start = latest_start_time(deadline_utc, estimate_minutes)
    return [
        ("day_before", deadline_utc - timedelta(days=1)),
        ("3h_before", deadline_utc - timedelta(hours=3)),
        ("latest_start", latest_start),
        ("1h_before", deadline_utc - timedelta(hours=1)),
        ("overdue", deadline_utc),
    ]


def time_left_text(deadline_utc: datetime) -> str:
    """Short human text such as '⏳ 2 days left' or '⚠️ Overdue by 3 h'."""
    delta = deadline_utc - utc_now()
    seconds = int(delta.total_seconds())

    if seconds < 0:
        return f"⚠️ Overdue by {format_duration(-seconds // 60)}"
    if delta.days >= 1:
        day_word = "day" if delta.days == 1 else "days"
        return f"⏳ {delta.days} {day_word} left"

    hours, remainder = divmod(delta.seconds, 3600)
    minutes = remainder // 60
    if hours:
        return f"⏳ {hours} h left"
    return f"⏳ {minutes} min left"


def urgency_icon(deadline_utc: datetime, estimate_minutes: int) -> str:
    """🟢 plenty of time, 🟡 start soon, 🔴 start now / overdue."""
    now = utc_now()
    if now > deadline_utc:
        return "🔴"

    latest_start = latest_start_time(deadline_utc, estimate_minutes)
    if now >= latest_start:
        return "🔴"
    if deadline_utc - now <= timedelta(days=2):
        return "🟡"
    return "🟢"


# --- Display helpers ---------------------------------------------------------


def progress_bar(done: int, total: int) -> str:
    """A 10-character progress bar, e.g. '▓▓▓░░░░░░░ 30%'."""
    if total == 0:
        return "░░░░░░░░░░ 0%"
    percent = round(done / total * 100)
    filled = round(done / total * 10)
    return f"{'▓' * filled}{'░' * (10 - filled)} {percent}%"


def escape_html(text: str) -> str:
    """Escape user text so it is safe to send with HTML parse mode."""
    return escape(text)


def shorten(text: str, limit: int = 40) -> str:
    """Collapse whitespace and cut long text for button labels."""
    text = " ".join(text.split())
    if len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text
