"""Entry point for the task coach bot.

Run it with:
    python bot.py
"""

import logging
import warnings

from telegram import BotCommand
from telegram.error import NetworkError
from telegram.ext import Application, CallbackQueryHandler, CommandHandler
from telegram.request import HTTPXRequest
from telegram.warnings import PTBUserWarning

import database
import jobs
from config import BOT_TOKEN, PROXY_URL
from handlers.alerts import alert_handlers
from handlers.focus import focus_command, focus_handlers
from handlers.menu import help_button, help_command, show_menu, start
from handlers.steps import (
    delete_step_ask,
    delete_step_pick,
    delete_step_yes,
    edit_step_pick,
    open_steps,
    step_conversation,
    toggle_step,
)
from handlers.tasks import (
    change_deadline_conversation,
    delete_task_ask,
    delete_task_no,
    delete_task_yes,
    finish_next_step,
    my_tasks_command,
    new_task_conversation,
    open_task,
    show_my_tasks,
)

logger = logging.getLogger(__name__)

# The conversations use both buttons and typed text, so per_message=False is
# required. PTB warns about this even though it is intentional, so we hide it.
warnings.filterwarnings(
    "ignore", category=PTBUserWarning, message=".*per_message=False.*"
)

# The command list shown in the Telegram menu.
COMMANDS = [
    BotCommand("start", "🏠 Open the main menu"),
    BotCommand("new", "➕ Create a new task"),
    BotCommand("tasks", "📋 View my tasks"),
    BotCommand("focus", "🎯 Start a focus session"),
    BotCommand("help", "❓ How to use the bot"),
]


async def post_init(application: Application) -> None:
    """Runs once when the bot starts."""
    await application.bot.set_my_commands(COMMANDS)
    # Rebuild the alert checker and any focus sessions that were running.
    jobs.rebuild_jobs(application)


async def error_handler(update, context) -> None:
    """Log errors instead of crashing the bot."""
    logger.error("Exception while handling an update:", exc_info=context.error)


def build_application() -> Application:
    """Create the Application and register every handler."""
    # The default 5-second timeout is too short for slow internet connections.
    request_kwargs = {
        "read_timeout": 30.0,
        "write_timeout": 30.0,
        "connect_timeout": 15.0,
        "pool_timeout": 10.0,
    }
    if PROXY_URL:
        request_kwargs["proxy"] = PROXY_URL

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .request(HTTPXRequest(**request_kwargs))
        .post_init(post_init)
        .build()
    )

    if application.job_queue is None:
        raise SystemExit(
            "The job queue is not available.\n"
            "Install it with: pip install 'python-telegram-bot[job-queue]'"
        )

    # --- Conversations (added first so their buttons are handled first) ------
    application.add_handler(new_task_conversation())
    application.add_handler(change_deadline_conversation())
    application.add_handler(step_conversation())

    # --- Commands ------------------------------------------------------------
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("tasks", my_tasks_command))
    application.add_handler(CommandHandler("focus", focus_command))

    # --- Menu ---------------------------------------------------------------
    application.add_handler(CallbackQueryHandler(show_menu, pattern="^menu$"))
    application.add_handler(CallbackQueryHandler(help_button, pattern="^help$"))

    # --- Tasks --------------------------------------------------------------
    application.add_handler(CallbackQueryHandler(show_my_tasks, pattern="^my_tasks$"))
    application.add_handler(CallbackQueryHandler(open_task, pattern="^task_open:"))
    application.add_handler(
        CallbackQueryHandler(finish_next_step, pattern="^task_finish_step:")
    )
    application.add_handler(
        CallbackQueryHandler(delete_task_ask, pattern="^task_delete:")
    )
    application.add_handler(
        CallbackQueryHandler(delete_task_yes, pattern="^task_delete_yes:")
    )
    application.add_handler(
        CallbackQueryHandler(delete_task_no, pattern="^task_delete_no:")
    )

    # --- Steps --------------------------------------------------------------
    application.add_handler(
        CallbackQueryHandler(open_steps, pattern="^steps_open:|^task_steps:")
    )
    application.add_handler(CallbackQueryHandler(toggle_step, pattern="^step_toggle:"))
    application.add_handler(
        CallbackQueryHandler(edit_step_pick, pattern="^step_edit_pick:")
    )
    application.add_handler(
        CallbackQueryHandler(delete_step_pick, pattern="^step_del_pick:")
    )
    application.add_handler(CallbackQueryHandler(delete_step_ask, pattern="^step_del:"))
    application.add_handler(
        CallbackQueryHandler(delete_step_yes, pattern="^step_del_yes:")
    )

    # --- Focus --------------------------------------------------------------
    for handler in focus_handlers():
        application.add_handler(handler)

    # --- Alert buttons ------------------------------------------------------
    for handler in alert_handlers():
        application.add_handler(handler)

    application.add_error_handler(error_handler)

    return application


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO,
    )
    # httpx logs every request URL, and the URL contains the bot token.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    database.init_db()

    application = build_application()
    logger.info("Bot is running...")

    try:
        application.run_polling(bootstrap_retries=3)
    except NetworkError as exc:
        logger.error(
            "Could not connect to Telegram: %s\n"
            "Please check your internet connection. If Telegram is blocked "
            "in your country, set PROXY_URL in .env.",
            exc,
        )


if __name__ == "__main__":
    main()
