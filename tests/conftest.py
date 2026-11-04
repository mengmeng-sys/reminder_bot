"""Make sure the tests can import the bot modules without a real token."""

import os

# config.py reads BOT_TOKEN on import; give it a dummy value for tests.
# The format matches a real token so Telegram's Bot class accepts it.
os.environ.setdefault("BOT_TOKEN", "123456789:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
