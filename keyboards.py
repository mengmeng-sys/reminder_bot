"""Every inline keyboard used by the bot, in one place."""

import calendar
from datetime import date

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from utils import MONTHS, shorten, urgency_icon

# The calendar week starts on Monday.
_cal = calendar.Calendar(firstweekday=0)
WEEKDAY_LABELS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]


# --- Main menu ---------------------------------------------------------------


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("➕ New task", callback_data="new_task"),
                InlineKeyboardButton("📋 My tasks", callback_data="my_tasks"),
            ],
            [
                InlineKeyboardButton("🎯 Focus", callback_data="focus_menu"),
                InlineKeyboardButton("❓ Help", callback_data="help"),
            ],
        ]
    )


def help_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("➕ New task", callback_data="new_task")],
            [InlineKeyboardButton("🏠 Menu", callback_data="menu")],
        ]
    )


def back_menu_keyboard(back_to: str = "menu") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("⬅ Back", callback_data=back_to),
                InlineKeyboardButton("🏠 Menu", callback_data="menu"),
            ]
        ]
    )


# --- New task flow -----------------------------------------------------------


def deadline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Today 20:00", callback_data="dl_today_20"),
                InlineKeyboardButton("Tomorrow 09:00", callback_data="dl_tomorrow_9"),
            ],
            [
                InlineKeyboardButton("In 3 days", callback_data="dl_3days"),
                InlineKeyboardButton("📅 Pick date", callback_data="dl_pick"),
            ],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
        ]
    )


def estimate_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("30 min", callback_data="est_30"),
                InlineKeyboardButton("1 h", callback_data="est_60"),
            ],
            [
                InlineKeyboardButton("2 h", callback_data="est_120"),
                InlineKeyboardButton("4 h", callback_data="est_240"),
            ],
            [
                InlineKeyboardButton("✏️ Custom", callback_data="est_custom"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
            ],
        ]
    )


def steps_prompt_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Skip, add steps later", callback_data="steps_skip")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
        ]
    )


# --- Task card ---------------------------------------------------------------


def task_card_keyboard(task_id: int, has_next_step: bool) -> InlineKeyboardMarkup:
    rows = []
    if has_next_step:
        rows.append(
            [
                InlineKeyboardButton(
                    "✅ Finish next step",
                    callback_data=f"task_finish_step:{task_id}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton("🪜 All steps", callback_data=f"task_steps:{task_id}"),
            InlineKeyboardButton(
                "🎯 Focus on this", callback_data=f"task_focus:{task_id}"
            ),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton("➕ Add step", callback_data=f"task_add_step:{task_id}"),
            InlineKeyboardButton("🗑 Delete task", callback_data=f"task_delete:{task_id}"),
        ]
    )
    rows.append([InlineKeyboardButton("🏠 Menu", callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def delete_task_confirm_keyboard(task_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "✅ Yes, delete", callback_data=f"task_delete_yes:{task_id}"
                ),
                InlineKeyboardButton("🔙 Keep it", callback_data=f"task_open:{task_id}"),
            ],
            [InlineKeyboardButton("🏠 Menu", callback_data="menu")],
        ]
    )


# --- My tasks ----------------------------------------------------------------


def my_tasks_keyboard(tasks) -> InlineKeyboardMarkup:
    rows = []
    for task in tasks:
        icon = urgency_icon(task.deadline_utc, task.estimate_minutes)
        rows.append(
            [
                InlineKeyboardButton(
                    f"{icon} {shorten(task.title, 40)}",
                    callback_data=f"task_open:{task.id}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton("➕ New task", callback_data="new_task"),
            InlineKeyboardButton("🏠 Menu", callback_data="menu"),
        ]
    )
    return InlineKeyboardMarkup(rows)


# --- Steps -------------------------------------------------------------------


def steps_screen_keyboard(task_id: int, steps) -> InlineKeyboardMarkup:
    rows = []
    for step in steps:
        mark = "☑" if step.is_done else "☐"
        rows.append(
            [
                InlineKeyboardButton(
                    f"{mark} {shorten(step.text, 40)}",
                    callback_data=f"step_toggle:{step.id}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton("➕ Add step", callback_data=f"step_add:{task_id}"),
            InlineKeyboardButton("✏️ Edit", callback_data=f"step_edit_pick:{task_id}"),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton("🗑 Delete", callback_data=f"step_del_pick:{task_id}"),
            InlineKeyboardButton("⬅ Back", callback_data=f"task_open:{task_id}"),
        ]
    )
    rows.append([InlineKeyboardButton("🏠 Menu", callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def step_pick_keyboard(task_id: int, steps, action: str) -> InlineKeyboardMarkup:
    """Buttons for choosing a step to edit or delete."""
    rows = []
    for index, step in enumerate(steps, start=1):
        rows.append(
            [
                InlineKeyboardButton(
                    f"{index}. {shorten(step.text, 40)}",
                    callback_data=f"step_{action}:{step.id}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton("⬅ Back", callback_data=f"steps_open:{task_id}"),
            InlineKeyboardButton("🏠 Menu", callback_data="menu"),
        ]
    )
    return InlineKeyboardMarkup(rows)


# --- Focus -------------------------------------------------------------------


def focus_task_keyboard(tasks) -> InlineKeyboardMarkup:
    rows = []
    for task in tasks:
        rows.append(
            [
                InlineKeyboardButton(
                    f"📝 {shorten(task.title, 40)}",
                    callback_data=f"focus_task:{task.id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton("🚫 No task", callback_data="focus_none")])
    rows.append([InlineKeyboardButton("🏠 Menu", callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def focus_length_keyboard(task_id) -> InlineKeyboardMarkup:
    data = f"focus_len:{task_id}"
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("15 min", callback_data=f"{data}:15"),
                InlineKeyboardButton("25 min", callback_data=f"{data}:25"),
                InlineKeyboardButton("45 min", callback_data=f"{data}:45"),
            ],
            [
                InlineKeyboardButton("⬅ Back", callback_data="focus_menu"),
                InlineKeyboardButton("🏠 Menu", callback_data="menu"),
            ],
        ]
    )


def focus_running_keyboard(session_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⏹ Stop", callback_data=f"focus_stop:{session_id}")],
            [InlineKeyboardButton("🏠 Menu", callback_data="menu")],
        ]
    )


def focus_checkin_keyboard(session_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("👍 Yes", callback_data=f"focus_yes:{session_id}"),
                InlineKeyboardButton(
                    "😴 I need a break", callback_data=f"focus_break:{session_id}"
                ),
            ],
            [InlineKeyboardButton("⏹ Stop", callback_data=f"focus_stop:{session_id}")],
        ]
    )


def focus_done_keyboard(task_id: int) -> InlineKeyboardMarkup:
    data = task_id or 0
    rows = []
    if task_id:
        rows.append(
            [
                InlineKeyboardButton(
                    "✅ Finish next step",
                    callback_data=f"focus_finish_step:{task_id}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                "☕ Take a 5 min break", callback_data=f"focus_break_start:{data}"
            ),
            InlineKeyboardButton("▶ Another round", callback_data=f"focus_another:{data}"),
        ]
    )
    rows.append([InlineKeyboardButton("⏹ Finish", callback_data=f"focus_finish:{data}")])
    rows.append([InlineKeyboardButton("🏠 Menu", callback_data="menu")])
    return InlineKeyboardMarkup(rows)


def break_end_keyboard(task_id: int) -> InlineKeyboardMarkup:
    data = task_id or 0
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "▶ Start next round", callback_data=f"focus_another:{data}"
                ),
                InlineKeyboardButton("⏹ Finish", callback_data=f"focus_finish:{data}"),
            ],
            [InlineKeyboardButton("🏠 Menu", callback_data="menu")],
        ]
    )


# --- Alerts ------------------------------------------------------------------


def alert_keyboard(task_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "▶ Start focus", callback_data=f"alert_focus:{task_id}"
                ),
                InlineKeyboardButton(
                    "✅ Finish next step",
                    callback_data=f"alert_finish_step:{task_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "⏭ Snooze 30 min", callback_data=f"alert_snooze:{task_id}"
                ),
                InlineKeyboardButton(
                    "📅 Change deadline",
                    callback_data=f"alert_change_deadline:{task_id}",
                ),
            ],
            [InlineKeyboardButton("🏠 Menu", callback_data="menu")],
        ]
    )


# --- Calendar ----------------------------------------------------------------


def calendar_keyboard(year: int, month: int, today: date):
    """A month calendar. Returns (header_text, keyboard)."""
    weeks = _cal.monthdayscalendar(year, month)
    rows = []

    # Previous month is only useful if we are not in the current month.
    if (year, month) > (today.year, today.month):
        prev_button = InlineKeyboardButton(
            "◀", callback_data=f"cal_prev:{year}:{month}"
        )
    else:
        prev_button = InlineKeyboardButton(" ", callback_data="cal_noop")

    rows.append(
        [
            prev_button,
            InlineKeyboardButton(
                f"{MONTHS[month - 1]} {year}", callback_data="cal_noop"
            ),
            InlineKeyboardButton("▶", callback_data=f"cal_next:{year}:{month}"),
        ]
    )
    rows.append(
        [InlineKeyboardButton(label, callback_data="cal_noop") for label in WEEKDAY_LABELS]
    )

    for week in weeks:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(" ", callback_data="cal_noop"))
            elif (year, month, day) < (today.year, today.month, today.day):
                row.append(InlineKeyboardButton(str(day), callback_data="cal_past"))
            else:
                row.append(
                    InlineKeyboardButton(
                        str(day), callback_data=f"cal_day:{year}:{month}:{day}"
                    )
                )
        rows.append(row)

    rows.append([InlineKeyboardButton("❌ Cancel", callback_data="cancel")])
    return f"📅 Pick a day in {MONTHS[month - 1]} {year}", InlineKeyboardMarkup(rows)


def hour_keyboard(year, month, day, now_local) -> InlineKeyboardMarkup:
    """24 hour buttons. Hours that already passed today are disabled."""
    buttons = []
    for hour in range(24):
        label = f"{hour:02d}:00"
        is_today = (year, month, day) == (
            now_local.year,
            now_local.month,
            now_local.day,
        )
        if is_today and hour <= now_local.hour:
            buttons.append(InlineKeyboardButton(label, callback_data="cal_past_hour"))
        else:
            buttons.append(
                InlineKeyboardButton(
                    label, callback_data=f"cal_hour:{year}:{month}:{day}:{hour}"
                )
            )

    rows = [buttons[i : i + 6] for i in range(0, 24, 6)]
    rows.append(
        [
            InlineKeyboardButton("⬅ Back", callback_data="cal_back_days"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
        ]
    )
    return InlineKeyboardMarkup(rows)


def minute_keyboard(year, month, day, hour, now_local) -> InlineKeyboardMarkup:
    """Four minute buttons. Minutes that already passed are disabled."""
    buttons = []
    for minute in (0, 15, 30, 45):
        label = f"{hour:02d}:{minute:02d}"
        is_now = (
            (year, month, day) == (now_local.year, now_local.month, now_local.day)
            and hour == now_local.hour
            and minute <= now_local.minute
        )
        if is_now:
            buttons.append(InlineKeyboardButton(label, callback_data="cal_past_min"))
        else:
            buttons.append(
                InlineKeyboardButton(
                    label,
                    callback_data=f"cal_min:{year}:{month}:{day}:{hour}:{minute}",
                )
            )

    rows = [buttons[i : i + 2] for i in range(0, 4, 2)]
    rows.append(
        [
            InlineKeyboardButton("⬅ Back", callback_data="cal_back_hours"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
        ]
    )
    return InlineKeyboardMarkup(rows)
