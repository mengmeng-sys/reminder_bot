"""All text templates for the bot.

Keeping the words in one file makes them easy to change later.
User text is always escaped before it is put into HTML.
"""

from database import Step, Task
from utils import (
    escape_html,
    format_duration,
    format_when,
    latest_start_time,
    progress_bar,
    time_left_text,
    urgency_icon,
)

# Short celebration / motivation messages. A random one is picked each time.
CELEBRATIONS = [
    "🎉 Task completed! Great job.",
    "🎉 Done! You should be proud of yourself.",
    "🎉 Finished! One more win in the books.",
    "🎉 Wow, you did it! Keep the momentum going.",
]

MOTIVATIONS = [
    "You're doing great — keep going! 💪",
    "Small steps add up. Well done! 🌟",
    "Another win! Consistency is the key. 🏆",
    "Focus paid off. Nice work! 🎯",
]


def menu_text(first_name: str) -> str:
    return (
        f"👋 Hi, <b>{escape_html(first_name)}</b>!\n\n"
        "I'm your <b>task coach</b>. I'll help you:\n"
        "🪜 break big tasks into small steps\n"
        "🚦 start on time\n"
        "🎯 stay focused until the work is done\n\n"
        "What would you like to do?"
    )


def help_text() -> str:
    return (
        "❓ <b>How to use me</b>\n\n"
        "➕ <b>New task</b> — create a task with a deadline, an estimate "
        "and small steps\n"
        "📋 <b>My tasks</b> — see all your tasks, sorted by deadline\n"
        "🎯 <b>Focus</b> — start a Pomodoro focus timer\n\n"
        "<b>What you will see</b>\n"
        "🗓 deadlines with a countdown\n"
        "🚦 the latest time you should start\n"
        "🪜 a progress bar for your steps\n"
        "🔥 alerts that get more urgent as the deadline comes closer\n\n"
        "You can also use these commands:\n"
        "/start · /new · /tasks · /focus · /help"
    )


def task_card(task: Task, steps: list[Step]) -> str:
    """The main task card. Shows only ONE next step."""
    done = sum(1 for step in steps if step.is_done)
    total = len(steps)
    next_step = next((step for step in steps if not step.is_done), None)
    latest_start = latest_start_time(task.deadline_utc, task.estimate_minutes)

    lines = [
        f"📝 <b>{escape_html(task.title)}</b>",
        f"🗓 {format_when(task.deadline_utc)}   ({time_left_text(task.deadline_utc)})",
        (
            f"⏱ Estimate: {format_duration(task.estimate_minutes)}  ·  "
            f"🚦 Start by: {format_when(latest_start)}"
        ),
    ]

    if total:
        lines.append(f"🪜 Progress: {progress_bar(done, total)} ({done}/{total} steps)")
    else:
        lines.append("🪜 No steps yet")

    if next_step:
        lines.append(f"👉 Next step: {escape_html(next_step.text)}")

    lines.append(f"🎯 Focus: {format_duration(task.focus_minutes)}")
    return "\n".join(lines)


def steps_text(task: Task, steps: list[Step]) -> str:
    """The list of steps with ☑ / ☐."""
    lines = [f"🪜 <b>Steps for</b> {escape_html(task.title)}\n"]
    if not steps:
        lines.append("No steps yet.")
        return "\n".join(lines)

    for index, step in enumerate(steps, start=1):
        mark = "☑" if step.is_done else "☐"
        text = escape_html(step.text)
        if step.is_done:
            text = f"<s>{text}</s>"  # strike through finished steps
        lines.append(f"{mark} {index}. {text}")
    return "\n".join(lines)


def my_tasks_text(tasks: list[Task]) -> str:
    """The list of active tasks with urgency icons."""
    if not tasks:
        return (
            "📋 <b>My tasks</b>\n\n"
            "You have no tasks yet.\n"
            "Tap ➕ New task to create one!"
        )

    lines = ["📋 <b>My tasks</b>\n"]
    for task in tasks:
        icon = _urgency(task)
        lines.append(f"{icon} 📝 <b>{escape_html(task.title)}</b>")
        lines.append(
            f"   🗓 {format_when(task.deadline_utc)}   ({time_left_text(task.deadline_utc)})"
        )
    return "\n".join(lines)


def _urgency(task: Task) -> str:
    return urgency_icon(task.deadline_utc, task.estimate_minutes)


# --- Alerts ------------------------------------------------------------------

ALERT_HEADERS = {
    "day_before": "📌 <b>1 day left</b>",
    "3h_before": "⏳ <b>3 hours left</b>",
    "latest_start": "🚦 <b>Time to start!</b>\nStart now to finish on time.",
    "1h_before": "🔥 <b>1 hour left!</b>",
    "overdue": "⚠️ <b>Overdue!</b>",
    "snooze": "⏭ <b>Snoozed</b>",
}


def alert_text(task: Task, steps: list[Step], kind: str) -> str:
    header = ALERT_HEADERS.get(kind, "⏰ <b>Reminder</b>")
    return f"{header}\n\n{task_card(task, steps)}"


# --- Focus -------------------------------------------------------------------


def focus_menu_text(tasks: list[Task]) -> str:
    return (
        "🎯 <b>Focus</b>\n\n"
        "Choose a task to focus on, then pick a timer.\n\n"
        "Tip: 25 minutes of focus beats 2 hours of distraction."
    )


def focus_length_text(task_title: str | None) -> str:
    if task_title:
        return f"🎯 Focusing on <b>{escape_html(task_title)}</b>\n\nPick a timer:"
    return "🎯 <b>Focus</b>\n\nPick a timer:"


def focus_running_text(session, task_title: str | None) -> str:
    """Shown while a focus session or a break is running."""
    from utils import format_time

    label = "🎯 Focus" if session.kind == "focus" else "☕ Break"
    return (
        f"{label} started.\n"
        f"⏰ Ends at <b>{format_time(session.ends_at)}</b>"
    )


def focus_checkin_text(session, task_title: str | None) -> str:
    label = "🎯 Focus" if session.kind == "focus" else "☕ Break"
    return f"{label} — <b>still working? 💪</b>"


def focus_done_text(task_title: str | None) -> str:
    return "⏰ <b>Time is up! Great focus.</b>"


def break_done_text() -> str:
    return "☕ <b>Break is over!</b>"


def celebrate_text() -> str:
    """Pick a random celebration message."""
    import random

    return random.choice(CELEBRATIONS)


def motivate_text() -> str:
    """Pick a random short motivation message."""
    import random

    return random.choice(MOTIVATIONS)
