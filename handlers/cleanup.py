"""Helpers to keep the chat clean during conversations.

Instead of sending a new message for every step, we edit ONE "wizard"
message. The user's messages are deleted after we read them, so the chat
stays tidy and shows only the current step.

Example of the result:

    Bot: 📝 What is the task?
    [user types "Finish report" -> deleted]
    Bot: When is the deadline?        (same message, edited)
    [user taps "Tomorrow 09:00"]
    Bot: ⏱ Time estimate               (same message, edited)
"""

from telegram.error import TelegramError
from telegram.ext import ContextTypes

# The key under which we store the wizard message id in user_data.
WIZARD_KEY = "wizard_message_id"


async def delete_message(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int) -> None:
    """Delete a message. Ignore errors (already deleted, too old, ...)."""
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except TelegramError:
        # The message may already be deleted or too old to delete.
        pass


def set_wizard(context: ContextTypes.DEFAULT_TYPE, message) -> None:
    """Remember which message is the wizard for this conversation."""
    context.user_data[WIZARD_KEY] = message.message_id


async def edit_wizard(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    text: str,
    keyboard=None,
) -> None:
    """Edit the wizard message. If it was deleted, send a new one."""
    wizard_id = context.user_data.get(WIZARD_KEY)
    if wizard_id:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=wizard_id,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
            return
        except TelegramError:
            # The message may have been deleted by the user.
            pass

    sent = await context.bot.send_message(
        chat_id=chat_id, text=text, reply_markup=keyboard, parse_mode="HTML"
    )
    context.user_data[WIZARD_KEY] = sent.message_id


async def clear_wizard(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    """Delete the wizard message (used when a conversation ends)."""
    wizard_id = context.user_data.pop(WIZARD_KEY, None)
    if wizard_id:
        await delete_message(context, chat_id, wizard_id)
