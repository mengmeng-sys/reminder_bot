"""Settings for the task coach bot.

Secrets are read from a .env file so they never have to be hard-coded.
Copy .env.example to .env and fill in your values.
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

MONGO_URI = os.getenv("MONGO_URI")
if not MONGO_URI:
    raise SystemExit(
        "MONGO_URI is missing!\n"
        "Add it to .env, for example:\n"
        "MONGO_URI=mongodb+srv://user:password@cluster0.xxxxx.mongodb.net/"
    )

# --- Time zone ---------------------------------------------------------------

# Every time is stored in UTC in the database and shown to users in this zone.
LOCAL_TZ = ZoneInfo("Asia/Phnom_Penh")  # UTC+7

# --- Database ----------------------------------------------------------------

MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "task_coach")

# --- Render (webhook mode) ---------------------------------------------------

# Render sets this automatically. When present, the bot uses webhooks
# instead of polling, so it works on Render's free tier.
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")
PORT = int(os.getenv("PORT", "10000"))
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "task-coach-secret")

# --- Optional proxy ----------------------------------------------------------
# Only needed if Telegram is blocked by your internet provider.
# Example: PROXY_URL=http://127.0.0.1:7890
PROXY_URL = os.getenv("PROXY_URL") or None
