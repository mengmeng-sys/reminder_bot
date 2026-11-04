"""One-time setup: save your bot token to .env safely.

Run this once:
    python add_token.py

Then run the bot:
    python bot.py

The token is typed in the terminal, not in a chat, so it stays private.
"""

from pathlib import Path

ENV_FILE = Path(".env")


def main() -> None:
    print("=" * 55)
    print(" Task Coach Bot - setup")
    print("=" * 55)
    print()
    print("1. Open Telegram and message @BotFather")
    print("2. Send it: /newbot")
    print("3. Follow the steps and copy the token it gives you")
    print()

    token = input("Paste your bot token here: ").strip()

    if not token or ":" not in token:
        print()
        print("That does not look like a bot token. It should look like this:")
        print("   123456789:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        return

    ENV_FILE.write_text(
        "# Bot token from @BotFather\n"
        f"BOT_TOKEN={token}\n\n"
        "# Optional: only if Telegram is blocked by your internet provider\n"
        "# PROXY_URL=\n",
        encoding="utf-8",
    )

    print()
    print(f"Saved to {ENV_FILE}")
    print("Now run the bot with:  python bot.py")


if __name__ == "__main__":
    main()
