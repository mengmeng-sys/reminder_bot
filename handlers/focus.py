"""Focus timer handlers (Pomodoro style)."""

from telegram import Update
from telegram.ext import CallbackQueryHandler, ContextTypes

import database
import jobs
import messages
from handlers.tasks import render_task_card
from keyboards import (
    focus_length_keyboard,
    focus_running_keyboard,
    focus_task_keyboard,
    main_menu_keyboard,
)


def _task_title(task_id):
    if not task_id:
        return None
    task = database.get_task(task_id)
    return task.title if task else None


async def _render_focus_menu(update, context, query) -> None:
    """Show the focus screen: the running session, or the task picker."""
    session = database.get_running_session(update.effective_chat.id)

    if session:
        text = messages.focus_running_text(session, _task_title(session.task_id))
        keyboard = focus_running_keyboard(session.id)
    else:
        tasks = database.get_active_tasks(update.effective_chat.id)
        text = messages.focus_menu_text(tasks)
        keyboard = focus_task_keyboard(tasks)

    if query:
        await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")
    else:
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode="HTML")


# --- Menu --------------------------------------------------------------------


async def focus_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The '🎯 Focus' button."""
    query = update.callback_query
    await query.answer()
    await _render_focus_menu(update, context, query)


async def focus_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The /focus command."""
    await _render_focus_menu(update, context, None)


async def focus_pick_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The user chose a task (or 'No task')."""
    query = update.callback_query
    await query.answer()

    # "focus_none" has no colon, so handle it separately.
    if query.data == "focus_none":
        task_id = None
    else:
        task_id = query.data.split(":")[1]

    title = _task_title(task_id)
    await query.edit_message_text(
        messages.focus_length_text(title),
        reply_markup=focus_length_keyboard(task_id or "0"),
        parse_mode="HTML",
    )


async def focus_on_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The '🎯 Focus on this' button on a task card."""
    query = update.callback_query
    await query.answer()

    task_id = query.data.split(":")[1]
    task = database.get_task(task_id)
    if not task or task.chat_id != update.effective_chat.id:
        await query.answer("Task not found.", show_alert=True)
        return

    await query.edit_message_text(
        messages.focus_length_text(task.title),
        reply_markup=focus_length_keyboard(task_id),
        parse_mode="HTML",
    )


async def focus_pick_length(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The user chose a timer length: start the focus session."""
    query = update.callback_query
    await query.answer()

    _, raw_task_id, raw_minutes = query.data.split(":")
    task_id = None if raw_task_id == "0" else raw_task_id
    minutes = int(raw_minutes)

    # Only one active session per user.
    if database.get_running_session(update.effective_chat.id):
        await query.answer("You already have a session running.", show_alert=True)
        return

    session = jobs.start_session(
        context.application, update.effective_chat.id, task_id, "focus", minutes
    )
    await query.edit_message_text(
        messages.focus_running_text(session, _task_title(task_id)),
        reply_markup=focus_running_keyboard(session.id),
        parse_mode="HTML",
    )


# --- While a session is running ----------------------------------------------


async def focus_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The user tapped '⏹ Stop'."""
    query = update.callback_query
    await query.answer()

    session_id = query.data.split(":")[1]
    session = jobs.end_session(session_id, "stopped")
    if not session:
        await query.answer("No active session.", show_alert=True)
        return

    await query.edit_message_text(
        "⏹ <b>Session stopped.</b>",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )


async def focus_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The user answered '👍 Yes' to the halfway check-in."""
    query = update.callback_query
    await query.answer()

    session_id = query.data.split(":")[1]
    session = database.get_focus_session(session_id)
    if not session:
        return

    await query.edit_message_text(
        "💪 <b>Great, keep going!</b>\n\n"
        + messages.focus_running_text(session, _task_title(session.task_id)),
        reply_markup=focus_running_keyboard(session_id),
        parse_mode="HTML",
    )


async def focus_break(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The user answered '😴 I need a break' to the check-in."""
    query = update.callback_query
    await query.answer()

    session_id = query.data.split(":")[1]
    session = jobs.end_session(session_id, "stopped")
    if not session:
        return

    # Start a 5 minute break.
    break_session = jobs.start_session(
        context.application, session.chat_id, session.task_id, "break", 5
    )
    await query.edit_message_text(
        "😴 <b>Okay, take a short break.</b>\n\n"
        + messages.focus_running_text(break_session, _task_title(session.task_id)),
        reply_markup=focus_running_keyboard(break_session.id),
        parse_mode="HTML",
    )


# --- After the timer ends ----------------------------------------------------


async def focus_finish_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The user tapped '✅ Finish next step' on the time-up screen."""
    query = update.callback_query
    await query.answer()

    task_id = query.data.split(":")[1]
    task = database.get_task(task_id)
    if not task or task.chat_id != update.effective_chat.id:
        await query.answer("Task not found.", show_alert=True)
        return

    step = database.get_next_step(task_id)
    if not step:
        await query.answer("No steps yet. Add a step first!", show_alert=True)
        return

    database.toggle_step(step.id)
    steps = database.get_steps(task_id)

    if steps and all(s.is_done for s in steps):
        database.mark_task_done(task_id)
        database.delete_alerts(task_id)
        await query.edit_message_text(
            "🎉 <b>Task completed! Great job.</b>\n\n"
            f"{messages.motivate_text()}",
            reply_markup=main_menu_keyboard(),
            parse_mode="HTML",
        )
        return

    await render_task_card(query, task)


async def focus_break_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The user tapped '☕ Take a 5 min break'."""
    query = update.callback_query
    await query.answer()

    raw_task_id = query.data.split(":")[1]
    task_id = None if raw_task_id == "0" else raw_task_id
    session = jobs.start_session(
        context.application, update.effective_chat.id, task_id, "break", 5
    )
    await query.edit_message_text(
        messages.focus_running_text(session, _task_title(task_id)),
        reply_markup=focus_running_keyboard(session.id),
        parse_mode="HTML",
    )


async def focus_another(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The user tapped '▶ Another round'."""
    query = update.callback_query
    await query.answer()

    raw_task_id = query.data.split(":")[1]
    task_id = None if raw_task_id == "0" else raw_task_id
    # Use the same length as the last focus session, or 25 minutes.
    minutes = database.get_last_focus_minutes(update.effective_chat.id) or 25

    session = jobs.start_session(
        context.application, update.effective_chat.id, task_id, "focus", minutes
    )
    await query.edit_message_text(
        messages.focus_running_text(session, _task_title(task_id)),
        reply_markup=focus_running_keyboard(session.id),
        parse_mode="HTML",
    )


async def focus_finish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The user tapped '⏹ Finish'."""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "✅ <b>Finished. Great work!</b>",
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )


def focus_handlers():
    """Return the callback handlers for the focus flow."""
    return [
        CallbackQueryHandler(focus_menu, pattern="^focus_menu$"),
        CallbackQueryHandler(focus_on_task, pattern="^task_focus:"),
        CallbackQueryHandler(focus_pick_task, pattern="^focus_task:|^focus_none$"),
        CallbackQueryHandler(focus_pick_length, pattern="^focus_len:"),
        CallbackQueryHandler(focus_stop, pattern="^focus_stop:"),
        CallbackQueryHandler(focus_yes, pattern="^focus_yes:"),
        CallbackQueryHandler(focus_break, pattern="^focus_break:"),
        CallbackQueryHandler(focus_finish_step, pattern="^focus_finish_step:"),
        CallbackQueryHandler(focus_break_start, pattern="^focus_break_start:"),
        CallbackQueryHandler(focus_another, pattern="^focus_another:"),
        CallbackQueryHandler(focus_finish, pattern="^focus_finish:"),
    ]
