"""Handlers for the buttons on alert messages."""

from datetime import timedelta

from telegram import Update
from telegram.ext import CallbackQueryHandler, ContextTypes

import database
import messages
from handlers.tasks import render_task_card
from keyboards import focus_length_keyboard, main_menu_keyboard
from utils import utc_now


def _get_task(task_id: int, chat_id: int):
    task = database.get_task(task_id)
    if not task or task.chat_id != chat_id:
        return None
    return task


async def alert_start_focus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The user tapped '▶ Start focus' on an alert."""
    query = update.callback_query
    await query.answer()

    task_id = query.data.split(":")[1]
    task = _get_task(task_id, update.effective_chat.id)
    if not task:
        await query.answer("Task not found.", show_alert=True)
        return

    await query.edit_message_text(
        messages.focus_length_text(task.title),
        reply_markup=focus_length_keyboard(task_id),
        parse_mode="HTML",
    )


async def alert_finish_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The user tapped '✅ Finish next step' on an alert."""
    query = update.callback_query
    await query.answer()

    task_id = query.data.split(":")[1]
    task = _get_task(task_id, update.effective_chat.id)
    if not task or task.status != "active":
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


async def alert_snooze(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The user tapped '⏭ Snooze 30 min' on an alert."""
    query = update.callback_query
    await query.answer()

    task_id = query.data.split(":")[1]
    task = _get_task(task_id, update.effective_chat.id)
    if not task:
        await query.answer("Task not found.", show_alert=True)
        return

    # Add a one-off reminder in 30 minutes.
    database.add_alert(task_id, "snooze", utc_now() + timedelta(minutes=30))

    await query.edit_message_text(
        "⏭ <b>Snoozed for 30 minutes.</b>\n\n"
        + messages.task_card(task, database.get_steps(task_id)),
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )


def alert_handlers():
    """Return the callback handlers for alert buttons."""
    return [
        CallbackQueryHandler(alert_start_focus, pattern="^alert_focus:"),
        CallbackQueryHandler(alert_finish_step, pattern="^alert_finish_step:"),
        CallbackQueryHandler(alert_snooze, pattern="^alert_snooze:"),
    ]
