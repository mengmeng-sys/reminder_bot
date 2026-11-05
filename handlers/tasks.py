"""Task handlers: new task flow, task card, my tasks, change deadline."""

from datetime import date, timedelta

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import database
import messages
from handlers import cleanup
from keyboards import (
    calendar_keyboard,
    deadline_keyboard,
    delete_task_confirm_keyboard,
    estimate_keyboard,
    hour_keyboard,
    main_menu_keyboard,
    minute_keyboard,
    my_tasks_keyboard,
    steps_prompt_keyboard,
    task_card_keyboard,
)
from utils import (
    alert_schedule,
    escape_html,
    latest_start_time,
    local_to_utc,
    shorten,
    to_local,
    utc_now,
)

# --- Conversation states -----------------------------------------------------

(
    NT_TITLE,
    NT_DEADLINE,
    NT_DAY,
    NT_HOUR,
    NT_MINUTE,
    NT_ESTIMATE,
    NT_ESTIMATE_CUSTOM,
    NT_STEPS,
) = range(8)

(
    CD_DAY,
    CD_HOUR,
    CD_MINUTE,
    CD_CONFIRM,
) = range(8, 12)

# Which state to return to after the calendar, for each flow.
DAY_STATE = {"new_task": NT_DAY, "change_deadline": CD_DAY}
HOUR_STATE = {"new_task": NT_HOUR, "change_deadline": CD_HOUR}
MINUTE_STATE = {"new_task": NT_MINUTE, "change_deadline": CD_MINUTE}


# --- Small helpers -----------------------------------------------------------


def _task_of_user(task_id: int, chat_id: int):
    """Return the task only if it belongs to this user."""
    task = database.get_task(task_id)
    if not task or task.chat_id != chat_id:
        return None
    return task


def _rebuild_alerts(task) -> None:
    """Create the alert schedule for a task (only future alerts)."""
    schedule = [
        (kind, fire_at)
        for kind, fire_at in alert_schedule(task.deadline_utc, task.estimate_minutes)
        if fire_at > utc_now()
    ]
    database.rebuild_alerts(task.id, schedule)


async def render_task_card(query, task) -> None:
    """Draw the task card on the current message."""
    steps = database.get_steps(task.id)
    has_next = any(not step.is_done for step in steps)
    await query.edit_message_text(
        messages.task_card(task, steps),
        reply_markup=task_card_keyboard(task.id, has_next),
        parse_mode="HTML",
    )


# --- New task flow: step 1, title ---------------------------------------------


async def start_new_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point: the user tapped '➕ New task'."""
    query = update.callback_query
    await query.answer()
    # Clean up the wizard from a previous conversation, if any.
    await cleanup.clear_wizard(context, update.effective_chat.id)
    context.user_data.clear()
    context.user_data["flow"] = "new_task"

    await query.edit_message_text(
        "📝 <b>New task</b>\n\nWhat is the task? Send me a short title.",
        reply_markup=None,
        parse_mode="HTML",
    )
    cleanup.set_wizard(context, query.message)
    return NT_TITLE


async def new_task_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/new command: start the new task flow."""
    await cleanup.clear_wizard(context, update.effective_chat.id)
    context.user_data.clear()
    context.user_data["flow"] = "new_task"
    sent = await update.message.reply_text(
        "📝 <b>New task</b>\n\nWhat is the task? Send me a short title.",
        parse_mode="HTML",
    )
    cleanup.set_wizard(context, sent)
    return NT_TITLE


async def receive_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The user sent the task title."""
    title = update.message.text.strip()
    if not title:
        await update.message.reply_text("Please send a title, or tap ❌ Cancel.")
        return NT_TITLE

    context.user_data["title"] = title
    # Edit the wizard instead of sending a new message (keeps the chat clean).
    await cleanup.edit_wizard(
        context,
        update.effective_chat.id,
        f"📝 <b>{escape_html(shorten(title, 60))}</b>\n\n"
        "When is the deadline?",
        deadline_keyboard(),
    )
    return NT_DEADLINE


# --- New task flow: step 2, deadline ------------------------------------------


async def choose_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The user picked a quick deadline or asked for the calendar."""
    query = update.callback_query
    await query.answer()

    choice = query.data
    now = utc_now()
    local_now = to_local(now)

    if choice == "dl_today_20":
        deadline = local_to_utc(local_now.date(), 20, 0)
        if deadline <= now:
            deadline += timedelta(days=1)
    elif choice == "dl_tomorrow_9":
        tomorrow = local_now.date() + timedelta(days=1)
        deadline = local_to_utc(tomorrow, 9, 0)
    elif choice == "dl_3days":
        deadline = local_to_utc(local_now.date(), 20, 0) + timedelta(days=3)
    elif choice == "dl_pick":
        context.user_data["cal_year"] = local_now.year
        context.user_data["cal_month"] = local_now.month
        text, keyboard = calendar_keyboard(
            local_now.year, local_now.month, local_now.date()
        )
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")
        return NT_DAY
    else:
        return NT_DEADLINE

    return await ask_estimate(query, context, deadline)


async def ask_estimate(query, context, deadline):
    """Store the deadline and ask for the time estimate."""
    context.user_data["deadline"] = deadline
    await query.edit_message_text(
        "⏱ <b>Time estimate</b>\n\nHow long will this task take?",
        reply_markup=estimate_keyboard(),
        parse_mode="HTML",
    )
    return NT_ESTIMATE


# --- New task flow: step 3, estimate ------------------------------------------


async def choose_estimate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The user picked an estimate."""
    query = update.callback_query
    await query.answer()

    choice = query.data
    if choice == "est_custom":
        await query.edit_message_text(
            "✏️ <b>Custom estimate</b>\n\nSend me the number of minutes "
            "(for example: 90).",
            parse_mode="HTML",
        )
        return NT_ESTIMATE_CUSTOM

    minutes = int(choice.split("_")[1])
    return await ask_steps(query, context, minutes)


async def receive_custom_estimate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The user typed a custom estimate in minutes."""
    text = update.message.text.strip()
    try:
        minutes = int(text)
    except ValueError:
        await update.message.reply_text(
            "Please send a number of minutes, for example: 90"
        )
        return NT_ESTIMATE_CUSTOM

    if minutes <= 0 or minutes > 600:
        await update.message.reply_text("Please send a number between 1 and 600.")
        return NT_ESTIMATE_CUSTOM

    context.user_data["estimate"] = minutes
    await _send_steps_prompt(update, context)
    return NT_STEPS


async def ask_steps(query, context, minutes):
    """Store the estimate and ask for the steps."""
    context.user_data["estimate"] = minutes
    await query.edit_message_text(
        "🪜 <b>Break it into small steps</b>\n\n"
        "Send me the steps, one per line.\n"
        "<i>Example:\nWrite the introduction\nMake the chart\nProofread</i>",
        reply_markup=steps_prompt_keyboard(),
        parse_mode="HTML",
    )
    return NT_STEPS


async def _send_steps_prompt(update, context):
    """Same as ask_steps, but for a typed custom estimate."""
    await update.message.reply_text(
        "🪜 <b>Break it into small steps</b>\n\n"
        "Send me the steps, one per line.\n"
        "<i>Example:\nWrite the introduction\nMake the chart\nProofread</i>",
        reply_markup=steps_prompt_keyboard(),
        parse_mode="HTML",
    )


# --- New task flow: step 4, steps ---------------------------------------------


async def receive_steps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The user sent the steps (one per line)."""
    lines = [line.strip() for line in update.message.text.splitlines() if line.strip()]
    if not lines:
        await update.message.reply_text(
            "Please send at least one step per line, or tap ❌ Cancel."
        )
        return NT_STEPS

    await _create_task(update, context, lines)
    return ConversationHandler.END


async def skip_steps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The user tapped 'Skip, add steps later'."""
    query = update.callback_query
    await query.answer()
    await _create_task(update, context, [])
    return ConversationHandler.END


async def _create_task(update, context, step_lines):
    """Save the task, its steps and its alerts, then show the card."""
    chat_id = update.effective_chat.id
    title = context.user_data["title"]
    deadline = context.user_data["deadline"]
    estimate = context.user_data["estimate"]

    task_id = database.add_task(chat_id, title, deadline, estimate)
    for line in step_lines:
        database.add_step(task_id, line)

    task = database.get_task(task_id)
    _rebuild_alerts(task)

    steps = database.get_steps(task_id)
    text = messages.task_card(task, steps)

    # Warning if the user is already late to start.
    if latest_start_time(deadline, estimate) <= utc_now():
        text += "\n\n⚠️ <b>You are already late to start. Start now!</b>"

    # Show the card by editing the wizard message so the chat stays clean.
    await cleanup.edit_wizard(
        context, chat_id, text, task_card_keyboard(task.id, bool(step_lines))
    )

    context.user_data.clear()


# --- Calendar (shared by new task and change deadline) -----------------------


async def calendar_nav(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """◀ / ▶ month navigation."""
    query = update.callback_query
    await query.answer()

    action, year, month = query.data.split(":")
    year, month = int(year), int(month)

    if action == "cal_prev":
        month -= 1
        if month == 0:
            month, year = 12, year - 1
    else:
        month += 1
        if month == 13:
            month, year = 1, year + 1

    context.user_data["cal_year"] = year
    context.user_data["cal_month"] = month

    flow = context.user_data.get("flow", "new_task")
    text, keyboard = calendar_keyboard(year, month, to_local(utc_now()).date())
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")
    return DAY_STATE[flow]


async def choose_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The user tapped a day."""
    query = update.callback_query
    await query.answer()

    _, year, month, day = query.data.split(":")
    year, month, day = int(year), int(month), int(day)
    context.user_data.update(cal_year=year, cal_month=month, cal_day=day)

    flow = context.user_data.get("flow", "new_task")
    await query.edit_message_text(
        f"📅 Pick an hour for <b>{day}/{month}/{year}</b>:",
        reply_markup=hour_keyboard(year, month, day, to_local(utc_now())),
        parse_mode="HTML",
    )
    return HOUR_STATE[flow]


async def choose_hour(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The user tapped an hour."""
    query = update.callback_query
    await query.answer()

    _, year, month, day, hour = query.data.split(":")
    year, month, day, hour = int(year), int(month), int(day), int(hour)
    context.user_data.update(cal_year=year, cal_month=month, cal_day=day)

    flow = context.user_data.get("flow", "new_task")
    await query.edit_message_text(
        f"🕐 <b>{hour:02d}:00</b>\n\nPick minutes:",
        reply_markup=minute_keyboard(year, month, day, hour, to_local(utc_now())),
        parse_mode="HTML",
    )
    return MINUTE_STATE[flow]


async def choose_minute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The user tapped the minutes. The next step depends on the flow."""
    query = update.callback_query
    await query.answer()

    _, year, month, day, hour, minute = query.data.split(":")
    year, month, day, hour, minute = (
        int(year),
        int(month),
        int(day),
        int(hour),
        int(minute),
    )
    deadline = local_to_utc(date(year, month, day), hour, minute)

    flow = context.user_data.get("flow", "new_task")
    if flow == "change_deadline":
        return await show_change_deadline_confirm(query, context, deadline)
    return await ask_estimate(query, context, deadline)


async def back_to_days(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """⬅ Back from the hour screen."""
    query = update.callback_query
    await query.answer()

    now_local = to_local(utc_now())
    year = context.user_data.get("cal_year", now_local.year)
    month = context.user_data.get("cal_month", now_local.month)

    flow = context.user_data.get("flow", "new_task")
    text, keyboard = calendar_keyboard(year, month, now_local.date())
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")
    return DAY_STATE[flow]


async def back_to_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """⬅ Back from the minute screen."""
    query = update.callback_query
    await query.answer()

    year = context.user_data["cal_year"]
    month = context.user_data["cal_month"]
    day = context.user_data["cal_day"]

    flow = context.user_data.get("flow", "new_task")
    await query.edit_message_text(
        f"📅 Pick an hour for <b>{day}/{month}/{year}</b>:",
        reply_markup=hour_keyboard(year, month, day, to_local(utc_now())),
        parse_mode="HTML",
    )
    return HOUR_STATE[flow]


# --- Change deadline flow ----------------------------------------------------


async def start_change_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point: the user tapped '📅 Change deadline'."""
    query = update.callback_query
    await query.answer()

    task_id = query.data.split(":")[1]
    task = _task_of_user(task_id, update.effective_chat.id)
    if not task:
        await query.answer("Task not found.", show_alert=True)
        return ConversationHandler.END

    context.user_data.clear()
    context.user_data["flow"] = "change_deadline"
    context.user_data["task_id"] = task_id

    now_local = to_local(utc_now())
    context.user_data["cal_year"] = now_local.year
    context.user_data["cal_month"] = now_local.month

    text, keyboard = calendar_keyboard(
        now_local.year, now_local.month, now_local.date()
    )
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")
    return CD_DAY


async def show_change_deadline_confirm(query, context, new_deadline):
    """Show the new deadline and ask for confirmation."""
    context.user_data["new_deadline"] = new_deadline
    task_id = context.user_data["task_id"]
    task = database.get_task(task_id)

    await query.edit_message_text(
        f"📅 <b>Change deadline?</b>\n\n"
        f"📝 {escape_html(task.title)}\n"
        f"🗓 Old: {messages.format_when(task.deadline_utc)}\n"
        f"🗓 New: {messages.format_when(new_deadline)}",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✅ Yes, change", callback_data="cd_confirm"
                    ),
                    InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
                ]
            ]
        ),
        parse_mode="HTML",
    )
    return CD_CONFIRM


async def confirm_change_deadline(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save the new deadline and rebuild the alerts."""
    query = update.callback_query
    await query.answer()

    task_id = context.user_data["task_id"]
    new_deadline = context.user_data["new_deadline"]
    task = _task_of_user(task_id, update.effective_chat.id)
    if not task:
        await query.answer("Task not found.", show_alert=True)
        return ConversationHandler.END

    database.update_task_deadline(task_id, new_deadline)
    task = database.get_task(task_id)
    _rebuild_alerts(task)

    await query.answer("Deadline updated.")
    await render_task_card(query, task)
    context.user_data.clear()
    return ConversationHandler.END


# --- Task card actions -------------------------------------------------------


async def open_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The user opened a task from 'My tasks'."""
    query = update.callback_query
    await query.answer()

    task_id = query.data.split(":")[1]
    task = _task_of_user(task_id, update.effective_chat.id)
    if not task:
        await query.answer("Task not found.", show_alert=True)
        return

    await render_task_card(query, task)


async def finish_next_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The user tapped '✅ Finish next step'."""
    query = update.callback_query
    await query.answer()

    task_id = query.data.split(":")[1]
    task = _task_of_user(task_id, update.effective_chat.id)
    if not task or task.status != "active":
        await query.answer("Task not found.", show_alert=True)
        return

    step = database.get_next_step(task_id)
    if not step:
        await query.answer("No steps yet. Add a step first!", show_alert=True)
        return

    database.toggle_step(step.id)
    steps = database.get_steps(task_id)

    # All steps done -> complete the task.
    if steps and all(s.is_done for s in steps):
        database.mark_task_done(task_id)
        database.delete_alerts(task_id)
        await query.edit_message_text(
            "🎉 <b>Task completed! Great job.</b>\n\n"
            f"{messages.motivate_text()}\n\n"
            f"{messages.task_card(task, steps)}",
            reply_markup=task_card_keyboard(task.id, False),
            parse_mode="HTML",
        )
        return

    await render_task_card(query, task)


async def delete_task_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The user tapped '🗑 Delete task'."""
    query = update.callback_query
    await query.answer()

    task_id = query.data.split(":")[1]
    task = _task_of_user(task_id, update.effective_chat.id)
    if not task:
        await query.answer("Task not found.", show_alert=True)
        return

    await query.edit_message_text(
        f"🗑 <b>Delete this task?</b>\n\n📝 {escape_html(task.title)}",
        reply_markup=delete_task_confirm_keyboard(task_id),
        parse_mode="HTML",
    )


async def delete_task_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    task_id = query.data.split(":")[1]
    task = _task_of_user(task_id, update.effective_chat.id)
    if not task:
        await query.answer("Task not found.", show_alert=True)
        return

    database.mark_task_deleted(task_id)
    database.delete_alerts(task_id)

    await query.edit_message_text(
        "🗑 Task deleted.\n\nWhat would you like to do?",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )


async def delete_task_no(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    task_id = query.data.split(":")[1]
    task = _task_of_user(task_id, update.effective_chat.id)
    if not task:
        await query.answer("Task not found.", show_alert=True)
        return

    await render_task_card(query, task)


# --- My tasks ----------------------------------------------------------------


async def show_my_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The '📋 My tasks' button."""
    query = update.callback_query
    await query.answer()

    tasks = database.get_active_tasks(update.effective_chat.id)
    await query.edit_message_text(
        messages.my_tasks_text(tasks),
        reply_markup=my_tasks_keyboard(tasks),
        parse_mode="HTML",
    )


async def my_tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The /tasks command."""
    tasks = database.get_active_tasks(update.effective_chat.id)
    await update.message.reply_text(
        messages.my_tasks_text(tasks),
        reply_markup=my_tasks_keyboard(tasks),
        parse_mode="HTML",
    )


# --- Cancel / fallbacks ------------------------------------------------------


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel any flow."""
    await cleanup.clear_wizard(context, update.effective_chat.id)
    context.user_data.clear()
    text = "❌ Cancelled.\n\nWhat would you like to do?"
    query = update.callback_query
    if query:
        await query.answer()
        await query.edit_message_text(
            text, reply_markup=main_menu_keyboard(), parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            text, reply_markup=main_menu_keyboard(), parse_mode="HTML"
        )
    return ConversationHandler.END


async def use_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The user sent text while buttons were expected."""
    await update.message.reply_text(
        "Please tap one of the buttons above, or type /cancel to stop."
    )


async def send_text_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The user sent a non-text message while the title was expected."""
    await update.message.reply_text("Please send the task title as text.")


async def past_day(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer(
        "That day is in the past. Pick a future day 📅", show_alert=True
    )


async def past_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer(
        "That time has already passed today. Pick a later time ⏰", show_alert=True
    )


# --- Conversations -----------------------------------------------------------


def new_task_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(start_new_task, pattern="^new_task$"),
            CommandHandler("new", new_task_command),
        ],
        states={
            NT_TITLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_title),
                MessageHandler(
                    filters.ALL & ~filters.COMMAND, send_text_title
                ),
            ],
            NT_DEADLINE: [
                CallbackQueryHandler(choose_deadline, pattern="^dl_"),
            ],
            NT_DAY: [
                CallbackQueryHandler(calendar_nav, pattern="^cal_prev:|^cal_next:"),
                CallbackQueryHandler(choose_day, pattern="^cal_day:"),
                CallbackQueryHandler(back_to_days, pattern="^cal_back_days$"),
            ],
            NT_HOUR: [
                CallbackQueryHandler(choose_hour, pattern="^cal_hour:"),
                CallbackQueryHandler(back_to_days, pattern="^cal_back_days$"),
            ],
            NT_MINUTE: [
                CallbackQueryHandler(choose_minute, pattern="^cal_min:"),
                CallbackQueryHandler(back_to_hours, pattern="^cal_back_hours$"),
            ],
            NT_ESTIMATE: [
                CallbackQueryHandler(choose_estimate, pattern="^est_"),
            ],
            NT_ESTIMATE_CUSTOM: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND, receive_custom_estimate
                ),
            ],
            NT_STEPS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_steps),
                CallbackQueryHandler(skip_steps, pattern="^steps_skip$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel, pattern="^cancel$"),
            CallbackQueryHandler(past_day, pattern="^cal_past$"),
            CallbackQueryHandler(
                past_time, pattern="^cal_past_hour$|^cal_past_min$"
            ),
            MessageHandler(filters.ALL, use_buttons),
        ],
        allow_reentry=True,
    )


def change_deadline_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(
                start_change_deadline, pattern="^(alert_change_deadline|task_change_deadline):"
            )
        ],
        states={
            CD_DAY: [
                CallbackQueryHandler(calendar_nav, pattern="^cal_prev:|^cal_next:"),
                CallbackQueryHandler(choose_day, pattern="^cal_day:"),
                CallbackQueryHandler(back_to_days, pattern="^cal_back_days$"),
            ],
            CD_HOUR: [
                CallbackQueryHandler(choose_hour, pattern="^cal_hour:"),
                CallbackQueryHandler(back_to_days, pattern="^cal_back_days$"),
            ],
            CD_MINUTE: [
                CallbackQueryHandler(choose_minute, pattern="^cal_min:"),
                CallbackQueryHandler(back_to_hours, pattern="^cal_back_hours$"),
            ],
            CD_CONFIRM: [
                CallbackQueryHandler(confirm_change_deadline, pattern="^cd_confirm$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CallbackQueryHandler(cancel, pattern="^cancel$"),
            CallbackQueryHandler(past_day, pattern="^cal_past$"),
            CallbackQueryHandler(
                past_time, pattern="^cal_past_hour$|^cal_past_min$"
            ),
            MessageHandler(filters.ALL, use_buttons),
        ],
        allow_reentry=True,
    )
