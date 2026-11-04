"""Main menu, /start and /help."""

from telegram import Update
from telegram.ext import ContextTypes

import database
import messages
from keyboards import help_keyboard, main_menu_keyboard


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start command: save the user and show the welcome message."""
    user = update.effective_user
    database.save_user(update.effective_chat.id, user.first_name)
    await update.message.reply_text(
        messages.menu_text(user.first_name),
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/help command."""
    await update.message.reply_text(
        messages.help_text(), reply_markup=help_keyboard(), parse_mode="HTML"
    )


async def help_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The '❓ Help' button on the main menu."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        messages.help_text(), reply_markup=help_keyboard(), parse_mode="HTML"
    )


async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The '🏠 Menu' button."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        messages.menu_text(update.effective_user.first_name),
        reply_markup=main_menu_keyboard(),
        parse_mode="HTML",
    )
