"""
Listens for incoming Telegram messages and responds to /latest by sending
the most recent digest file. Runs as a continuous long-polling loop --
this is a separate, always-on process from main.py (which runs on a
schedule to generate digests). Think of it as: main.py produces digests,
this script lets you pull the latest one on demand.

Only responds to messages from TELEGRAM_CHAT_ID -- messages from any other
chat are ignored, so a stranger who somehow finds your bot's username
can't use it to fish for your intel digests.

No Anthropic API usage -- pure Telegram Bot API polling, free at this scale.

Requires the same environment variables as telegram_notify.py:
    TELEGRAM_BOT_TOKEN
    TELEGRAM_CHAT_ID

Usage (runs until stopped with Ctrl+C):
    python telegram_bot_listener.py

For always-on use, run under systemd, tmux, or nohup rather than a bare
foreground terminal -- see README for a sample systemd unit.
"""

import os
import glob
import time
import requests

from telegram_notify import send_digest, get_api_url as get_send_url

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
OFFSET_FILE = "telegram_offset.txt"
POLL_TIMEOUT_SECONDS = 30  # long-poll duration; Telegram holds the connection open


def get_updates_url() -> str:
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN must be set as an environment variable.")
    return f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"


def load_offset() -> int:
    if os.path.exists(OFFSET_FILE):
        with open(OFFSET_FILE) as f:
            content = f.read().strip()
            return int(content) if content else 0
    return 0


def save_offset(offset: int) -> None:
    with open(OFFSET_FILE, "w") as f:
        f.write(str(offset))


def find_latest_digest() -> str | None:
    """Return the path to the most recently modified digest file, or None."""
    digests = glob.glob(os.path.join("digests", "digest_*.md"))
    if not digests:
        return None
    return max(digests, key=os.path.getmtime)


def send_plain_reply(text: str) -> None:
    """Send a short plain-text reply (for status/error messages, not full digests)."""
    requests.post(
        get_send_url(),
        data={"chat_id": CHAT_ID, "text": text},
        timeout=15,
    )


def handle_message(message: dict) -> None:
    incoming_chat_id = str(message.get("chat", {}).get("id", ""))
    text = (message.get("text") or "").strip().lower()

    if incoming_chat_id != str(CHAT_ID):
        print(f"  [ignored] message from unauthorized chat_id {incoming_chat_id}")
        return

    if text in ("/latest", "/digest"):
        latest = find_latest_digest()
        if latest is None:
            send_plain_reply("No digest has been generated yet. Run main.py first.")
            print("  Replied: no digest found")
        else:
            print(f"  Sending latest digest: {latest}")
            send_digest(latest)
    elif text == "/start":
        send_plain_reply("Intel digest bot is running. Send /latest to get the most recent digest.")
    else:
        send_plain_reply("Unrecognized command. Send /latest to get the most recent digest.")


def poll_loop() -> None:
    if not CHAT_ID:
        raise RuntimeError("TELEGRAM_CHAT_ID must be set as an environment variable.")

    offset = load_offset()
    print(f"Listening for Telegram messages (starting from offset {offset})... Ctrl+C to stop.")

    while True:
        try:
            response = requests.get(
                get_updates_url(),
                params={"offset": offset, "timeout": POLL_TIMEOUT_SECONDS},
                timeout=POLL_TIMEOUT_SECONDS + 10,
            )
            response.raise_for_status()
            data = response.json()

            for update in data.get("result", []):
                offset = update["update_id"] + 1
                message = update.get("message")
                if message:
                    handle_message(message)

            save_offset(offset)

        except requests.exceptions.Timeout:
            continue  # normal for long polling, just retry
        except requests.exceptions.RequestException as e:
            print(f"  [error] polling failed: {e}, retrying in 5s")
            time.sleep(5)


if __name__ == "__main__":
    poll_loop()
