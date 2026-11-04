"""Check that every button the bot shows is handled by some handler."""

from datetime import date, timedelta

from telegram.ext import CallbackQueryHandler

import bot
import database
from keyboards import (
    alert_keyboard,
    back_menu_keyboard,
    break_end_keyboard,
    calendar_keyboard,
    deadline_keyboard,
    delete_task_confirm_keyboard,
    estimate_keyboard,
    focus_checkin_keyboard,
    focus_done_keyboard,
    focus_length_keyboard,
    focus_running_keyboard,
    focus_task_keyboard,
    help_keyboard,
    hour_keyboard,
    main_menu_keyboard,
    minute_keyboard,
    my_tasks_keyboard,
    step_pick_keyboard,
    steps_prompt_keyboard,
    steps_screen_keyboard,
    task_card_keyboard,
)
from utils import to_local, utc_now


def _patterns(handlers):
    """Collect the regex patterns of all callback handlers in a list."""
    return [
        handler.pattern
        for handler in handlers
        if isinstance(handler, CallbackQueryHandler) and handler.pattern is not None
    ]


def _all_patterns():
    application = bot.build_application()
    patterns = []
    for group in application.handlers.values():
        for handler in group:
            if type(handler).__name__ == "ConversationHandler":
                patterns += _patterns(handler.entry_points)
                for handlers in handler.states.values():
                    patterns += _patterns(handlers)
                patterns += _patterns(handler.fallbacks)
            else:
                patterns += _patterns([handler])
    return patterns


def _all_callback_data():
    now = utc_now()
    now_local = to_local(now)
    task = database.Task(
        id=1,
        chat_id=1,
        title="Test",
        deadline_utc=now + timedelta(days=1),
        estimate_minutes=60,
        status="active",
        created_at=now,
        completed_at=None,
        focus_minutes=0,
    )
    step = database.Step(
        id=1, task_id=1, position=1, text="Step", is_done=False, done_at=None
    )
    _, calendar = calendar_keyboard(2026, 11, date(2026, 11, 3))

    keyboards = [
        main_menu_keyboard(),
        help_keyboard(),
        back_menu_keyboard(),
        deadline_keyboard(),
        estimate_keyboard(),
        steps_prompt_keyboard(),
        task_card_keyboard(1, True),
        task_card_keyboard(1, False),
        delete_task_confirm_keyboard(1),
        my_tasks_keyboard([task]),
        steps_screen_keyboard(1, [step]),
        step_pick_keyboard(1, [step], "edit"),
        step_pick_keyboard(1, [step], "del"),
        focus_task_keyboard([task]),
        focus_length_keyboard(1),
        focus_running_keyboard(1),
        focus_checkin_keyboard(1),
        focus_done_keyboard(1),
        focus_done_keyboard(0),
        break_end_keyboard(1),
        alert_keyboard(1),
        calendar,
        hour_keyboard(2026, 11, 5, now_local),
        minute_keyboard(2026, 11, 5, 14, now_local),
    ]

    data = set()
    for keyboard in keyboards:
        for row in keyboard.inline_keyboard:
            for button in row:
                data.add(button.callback_data)
    return data


def test_every_button_has_a_handler():
    patterns = _all_patterns()
    for data in _all_callback_data():
        if data == "cal_noop":
            continue  # label button, intentionally does nothing
        assert any(p.match(data) for p in patterns), f"No handler for {data!r}"
