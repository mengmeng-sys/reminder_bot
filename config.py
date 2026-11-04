"""Settings for the task coach bot.

The bot token is read from a .env file so it never has to be hard-coded.
Copy .env.example to .env and paste your token there.
"""

import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

# Load variables from .env into the environment.
load_dotenv()

# --- Required settings -------------------------------------------------------

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise SystemExit(
        "BOT_TOKEN is missing!\n"
        "Create a .env file in this folder with:\n"
        "BOT_TOKEN=123456789:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    )

# --- Time zone ---------------------------------------------------------------

# Every time is stored in UTC in the database and shown to users in this zone.
LOCAL_TZ = ZoneInfo("Asia/Phnom_Penh")  # UTC+7

# --- Database ----------------------------------------------------------------

DB_PATH = os.getenv("DB_PATH", "task_coach.sqlite")

# --- Optional proxy ----------------------------------------------------------
# Only needed if Telegram is blocked by your internet provider.
# Example: PROXY_URL=http://127.0.0.1:7890
PROXY_URL = os.getenv("PROXY_URL") or None
