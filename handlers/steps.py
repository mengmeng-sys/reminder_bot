"""Step handlers: the steps screen, add, edit and delete steps."""

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
from handlers.tasks import cancel
from keyboards import step_pick_keyboard, steps_screen_keyboard
from utils import escape_html

# Conversation states.
AS_TEXT, ES_TEXT = range(2)


async def _render_steps(query, task) -> None:
    """Draw the steps screen on the current message."""
    steps = database.get_steps(task.id)
    await query.edit_message_text(
        messages.steps_text(task, steps),
        reply_markup=steps_screen_keyboard(task.id, steps),
        parse_mode="HTML",
    )


def _get_task(task_id: int, chat_id: int):
    task = database.get_task(task_id)
    if not task or task.chat_id != chat_id:
        return None
    return task


async def _render_steps_after_text(update, context, task, notice: str) -> None:
    """Show the steps screen by editing the wizard message."""
    steps = database.get_steps(task.id)
    await cleanup.edit_wizard(
        context,
        update.effective_chat.id,
        f"{notice}\n\n{messages.steps_text(task, steps)}",
        steps_screen_keyboard(task.id, steps),
    )


# --- Open the steps screen ---------------------------------------------------


async def open_steps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The user tapped '🪜 All steps' or '⬅ Back'."""
    query = update.callback_query
    await query.answer()

    task_id = query.data.split(":")[1]
    task = _get_task(task_id, update.effective_chat.id)
    if not task:
        await query.answer("Task not found.", show_alert=True)
        return

    await _render_steps(query, task)


async def toggle_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The user tapped a step to mark it done / not done."""
    query = update.callback_query
    await query.answer()

    step_id = query.data.split(":")[1]
    step = database.get_step(step_id)
    if not step:
        await query.answer("Step not found.", show_alert=True)
        return

    task = _get_task(step.task_id, update.effective_chat.id)
    if not task:
        await query.answer("Task not found.", show_alert=True)
        return

    database.toggle_step(step_id)

    # If all steps are now done, complete the task.
    steps = database.get_steps(task.id)
    if steps and all(s.is_done for s in steps):
        database.mark_task_done(task.id)
        database.delete_alerts(task.id)
        await query.edit_message_text(
            "🎉 <b>Task completed! Great job.</b>\n\n"
            f"{messages.motivate_text()}\n\n"
            f"{messages.task_card(task, steps)}",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🏠 Menu", callback_data="menu")]]
            ),
            parse_mode="HTML",
        )
        return

    await _render_steps(query, task)


# --- Add steps ---------------------------------------------------------------


async def add_step_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The user tapped '➕ Add step'."""
    query = update.callback_query
    await query.answer()

    task_id = query.data.split(":")[1]
    task = _get_task(task_id, update.effective_chat.id)
    if not task:
        await query.answer("Task not found.", show_alert=True)
        return ConversationHandler.END

    context.user_data["step_task_id"] = task_id
    await query.edit_message_text(
        "➕ <b>Add steps</b>\n\nSend me the steps, one per line.",
        parse_mode="HTML",
    )
    cleanup.set_wizard(context, query.message)
    return AS_TEXT


async def add_step_from_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The '➕ Add step' button on a task card. Same flow as the steps screen."""
    return await add_step_start(update, context)


async def add_step_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The user sent one or more new steps."""
    lines = [line.strip() for line in update.message.text.splitlines() if line.strip()]
    if not lines:
        await update.message.reply_text("Please send at least one step per line.")
        return AS_TEXT

    task_id = context.user_data["step_task_id"]
    task = _get_task(task_id, update.effective_chat.id)
    if not task:
        await update.message.reply_text("Task not found.")
        return ConversationHandler.END

    for line in lines:
        database.add_step(task_id, line)

    await cleanup.delete_user_message(update, context)
    await _render_steps_after_text(
        update, context, task, f"✅ Added {len(lines)} step(s)."
    )
    return ConversationHandler.END


# --- Edit a step -------------------------------------------------------------


async def edit_step_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The user tapped '✏️ Edit'."""
    query = update.callback_query
    await query.answer()

    task_id = query.data.split(":")[1]
    task = _get_task(task_id, update.effective_chat.id)
    if not task:
        await query.answer("Task not found.", show_alert=True)
        return

    steps = database.get_steps(task_id)
    if not steps:
        await query.answer("There are no steps to edit.", show_alert=True)
        return

    await query.edit_message_text(
        "✏️ <b>Edit a step</b>\n\nWhich step do you want to change?",
        reply_markup=step_pick_keyboard(task_id, steps, "edit"),
        parse_mode="HTML",
    )


async def edit_step_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The user picked a step to edit."""
    query = update.callback_query
    await query.answer()

    step_id = query.data.split(":")[1]
    step = database.get_step(step_id)
    if not step:
        await query.answer("Step not found.", show_alert=True)
        return ConversationHandler.END

    context.user_data["edit_step_id"] = step_id
    await query.edit_message_text(
        f"✏️ <b>Edit step</b>\n\nCurrent text:\n{escape_html(step.text)}\n\n"
        "Send me the new text.",
        parse_mode="HTML",
    )
    cleanup.set_wizard(context, query.message)
    return ES_TEXT


async def edit_step_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The user sent the new step text."""
    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("Please send some text.")
        return ES_TEXT

    step_id = context.user_data["edit_step_id"]
    step = database.get_step(step_id)
    if not step:
        await update.message.reply_text("Step not found.")
        return ConversationHandler.END

    database.update_step_text(step_id, text)
    task = _get_task(step.task_id, update.effective_chat.id)
    if not task:
        await update.message.reply_text("Task not found.")
        return ConversationHandler.END

    await cleanup.delete_user_message(update, context)
    await _render_steps_after_text(update, context, task, "✅ Step updated.")
    return ConversationHandler.END


# --- Delete a step -----------------------------------------------------------


async def delete_step_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The user tapped '🗑 Delete'."""
    query = update.callback_query
    await query.answer()

    task_id = query.data.split(":")[1]
    task = _get_task(task_id, update.effective_chat.id)
    if not task:
        await query.answer("Task not found.", show_alert=True)
        return

    steps = database.get_steps(task_id)
    if not steps:
        await query.answer("There are no steps to delete.", show_alert=True)
        return

    await query.edit_message_text(
        "🗑 <b>Delete a step</b>\n\nWhich step do you want to remove?",
        reply_markup=step_pick_keyboard(task_id, steps, "del"),
        parse_mode="HTML",
    )


async def delete_step_ask(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The user picked a step to delete."""
    query = update.callback_query
    await query.answer()

    step_id = query.data.split(":")[1]
    step = database.get_step(step_id)
    if not step:
        await query.answer("Step not found.", show_alert=True)
        return

    await query.edit_message_text(
        f"🗑 <b>Delete this step?</b>\n\n{escape_html(step.text)}",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✅ Yes, delete", callback_data=f"step_del_yes:{step_id}"
                    ),
                    InlineKeyboardButton(
                        "🔙 Keep it", callback_data=f"steps_open:{step.task_id}"
                    ),
                ]
            ]
        ),
        parse_mode="HTML",
    )


async def delete_step_yes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    step_id = query.data.split(":")[1]
    step = database.get_step(step_id)
    if not step:
        await query.answer("Step not found.", show_alert=True)
        return

    task_id = step.task_id
    database.delete_step(step_id)

    task = _get_task(task_id, update.effective_chat.id)
    if not task:
        await query.answer("Task not found.", show_alert=True)
        return

    await query.answer("Step deleted.")
    await _render_steps(query, task)


# --- Fallbacks ---------------------------------------------------------------


async def send_text_please(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Please send the step as text, or type /cancel."
    )


# --- Conversation ------------------------------------------------------------


def step_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(add_step_start, pattern="^step_add:"),
            CallbackQueryHandler(add_step_from_task, pattern="^task_add_step:"),
            CallbackQueryHandler(edit_step_start, pattern="^step_edit:"),
        ],
        states={
            AS_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_step_receive),
            ],
            ES_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_step_receive),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            MessageHandler(filters.ALL, send_text_please),
        ],
        allow_reentry=True,
    )
