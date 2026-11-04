"""Background jobs: the alert checker and the focus timer."""

from datetime import timedelta

from telegram.error import TelegramError
from telegram.ext import ContextTypes

import database
import messages
from keyboards import (
    alert_keyboard,
    break_end_keyboard,
    focus_checkin_keyboard,
    focus_done_keyboard,
)
from utils import utc_now

# How often the alert checker runs (seconds).
ALERT_CHECK_INTERVAL = 30

# Urgency rank for alert kinds. Higher = more urgent.
URGENCY = {
    "snooze": 6,
    "overdue": 5,
    "1h_before": 4,
    "latest_start": 3,
    "3h_before": 2,
    "day_before": 1,
}


# --- Alert checker -----------------------------------------------------------


async def alert_checker(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Runs every 30 seconds and sends any alerts that are due."""
    due = database.get_due_alerts(utc_now())

    # Group the due alerts by task.
    by_task: dict[int, list] = {}
    for alert in due:
        by_task.setdefault(alert.task_id, []).append(alert)

    for task_id, alerts in by_task.items():
        task = database.get_task(task_id)

        # Never send alerts for completed or deleted tasks.
        if not task or task.status != "active":
            database.mark_alerts_sent([a.id for a in alerts])
            continue

        # If several alerts were missed, send only the most urgent one.
        most_urgent = max(alerts, key=lambda a: URGENCY.get(a.kind, 0))
        await send_alert(context, task, most_urgent.kind)

        # Mark all of them as sent so the user is not flooded.
        database.mark_alerts_sent([a.id for a in alerts])


async def send_alert(context: ContextTypes.DEFAULT_TYPE, task, kind: str) -> None:
    """Send one alert message. Never crash if the user blocked the bot."""
    steps = database.get_steps(task.id)
    try:
        await context.bot.send_message(
            chat_id=task.chat_id,
            text=messages.alert_text(task, steps, kind),
            reply_markup=alert_keyboard(task.id),
            parse_mode="HTML",
        )
    except TelegramError:
        # For example, the user blocked the bot.
        return


# --- Focus session helpers ---------------------------------------------------


def start_session(application, chat_id: int, task_id, kind: str, minutes: int):
    """Create a focus/break session and schedule its jobs."""
    now = utc_now()
    ends_at = now + timedelta(minutes=minutes)
    session_id = database.create_focus_session(
        chat_id, task_id, kind, now, ends_at, minutes
    )
    session = database.get_focus_session(session_id)
    schedule_session_jobs(application, session)
    return session


def end_session(session_id: int, status: str):
    """Mark a session as finished/stopped and save the focus minutes."""
    session = database.get_focus_session(session_id)
    if not session or session.status != "running":
        return None

    database.finish_focus_session(session_id, status)
    add_session_minutes(session)
    return session


def add_session_minutes(session) -> None:
    """Add the elapsed focus time to the task (capped at the planned length)."""
    if not session.task_id:
        return
    elapsed = (utc_now() - session.started_at).total_seconds() / 60
    minutes = max(0, min(round(elapsed), session.minutes))
    if minutes:
        database.add_focus_minutes(session.task_id, minutes)


def schedule_session_jobs(application, session) -> None:
    """Schedule the end job (and the halfway check-in for focus sessions)."""
    remaining = (session.ends_at - utc_now()).total_seconds()

    if remaining <= 0:
        # The session already ended while the bot was down.
        database.set_halfway_sent(session.id)
        application.job_queue.run_once(
            focus_end, when=0.1, data=session.id, name=f"focus_end_{session.id}"
        )
        return

    application.job_queue.run_once(
        focus_end, when=remaining, data=session.id, name=f"focus_end_{session.id}"
    )

    if session.kind == "focus" and not session.halfway_sent:
        halfway = remaining / 2
        if halfway > 0:
            application.job_queue.run_once(
                focus_halfway,
                when=halfway,
                data=session.id,
                name=f"focus_half_{session.id}",
            )


# --- Focus jobs --------------------------------------------------------------


async def focus_halfway(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Halfway check-in during a focus session."""
    session = database.get_focus_session(context.job.data)
    if not session or session.status != "running" or session.halfway_sent:
        return

    database.set_halfway_sent(session.id)
    task = database.get_task(session.task_id) if session.task_id else None
    title = task.title if task else None

    try:
        await context.bot.send_message(
            chat_id=session.chat_id,
            text=messages.focus_checkin_text(session, title),
            reply_markup=focus_checkin_keyboard(session.id),
            parse_mode="HTML",
        )
    except TelegramError:
        pass


async def focus_end(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Called when a focus session or a break ends."""
    session = database.get_focus_session(context.job.data)
    if not session or session.status != "running":
        return

    if session.kind == "break":
        await _end_break(context, session)
    else:
        await _end_focus(context, session)


async def _end_focus(context: ContextTypes.DEFAULT_TYPE, session) -> None:
    end_session(session.id, "finished")

    task = database.get_task(session.task_id) if session.task_id else None
    title = task.title if task else None

    try:
        await context.bot.send_message(
            chat_id=session.chat_id,
            text=messages.focus_done_text(title),
            reply_markup=focus_done_keyboard(session.task_id),
            parse_mode="HTML",
        )
    except TelegramError:
        pass


async def _end_break(context: ContextTypes.DEFAULT_TYPE, session) -> None:
    end_session(session.id, "finished")

    try:
        await context.bot.send_message(
            chat_id=session.chat_id,
            text=messages.break_done_text(),
            reply_markup=break_end_keyboard(session.task_id),
            parse_mode="HTML",
        )
    except TelegramError:
        pass


# --- Startup -----------------------------------------------------------------


def rebuild_jobs(application) -> None:
    """Rebuild all background jobs when the bot starts."""
    application.job_queue.run_repeating(
        alert_checker,
        interval=ALERT_CHECK_INTERVAL,
        first=1.0,
        name="alert_checker",
    )

    # Re-arm any focus sessions that were running before the restart.
    for session in database.get_running_sessions():
        schedule_session_jobs(application, session)
