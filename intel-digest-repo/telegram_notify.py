"""
Sends the generated digest to Telegram via the Bot API.

No Anthropic API usage here -- this is a plain HTTP call to Telegram's
servers, completely separate from the Claude summarization step. Free
to use regardless of message volume at this scale.

Requires environment variables:
    TELEGRAM_BOT_TOKEN   from @BotFather
    TELEGRAM_CHAT_ID     from the getUpdates step (see setup docs)

Usage:
    export TELEGRAM_BOT_TOKEN=123456789:ABCdef...
    export TELEGRAM_CHAT_ID=123456789
    python telegram_notify.py digest_20260825.md
"""

import os
import sys
import re
import requests

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Telegram caps messages at 4096 characters. Stay comfortably under that
# so we're not fighting off-by-one issues with multi-byte characters.
MAX_MESSAGE_LENGTH = 3800


def get_api_url() -> str:
    if not BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN must be set as an environment variable.")
    return f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"


def markdown_to_telegram_safe(text: str) -> str:
    """
    Telegram's Markdown parser is stricter/different from standard markdown
    (it chokes on unescaped underscores, unbalanced asterisks, etc. in
    MarkdownV2 mode). Simplest reliable approach: strip markdown formatting
    entirely and send as plain text rather than fighting escaping rules.
    """
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)   # headers
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)              # bold
    text = re.sub(r"^---$", "\n" + "-" * 30 + "\n", text, flags=re.MULTILINE)  # divider
    return text


def split_into_chunks(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """
    Split the digest into Telegram-sized chunks, breaking on the '---'
    section dividers between items rather than mid-item wherever possible.
    """
    sections = text.split("\n" + "-" * 30 + "\n")
    chunks = []
    current = ""

    for section in sections:
        candidate = current + section + "\n" + "-" * 30 + "\n"
        if len(candidate) > max_length and current:
            chunks.append(current.strip())
            current = section + "\n" + "-" * 30 + "\n"
        else:
            current = candidate

    if current.strip():
        chunks.append(current.strip())

    return chunks or [text[:max_length]]


def send_message(chunk: str) -> None:
    if not CHAT_ID:
        raise RuntimeError("TELEGRAM_CHAT_ID must be set as an environment variable.")

    response = requests.post(
        get_api_url(),
        data={"chat_id": CHAT_ID, "text": chunk, "disable_web_page_preview": True},
        timeout=15,
    )

    if response.status_code != 200:
        print(f"  [error] Telegram API returned {response.status_code}: {response.text}")
        response.raise_for_status()


def send_digest(digest_path: str) -> None:
    with open(digest_path) as f:
        raw_text = f.read()

    plain_text = markdown_to_telegram_safe(raw_text)
    chunks = split_into_chunks(plain_text)

    print(f"Sending digest as {len(chunks)} message(s) to Telegram...")
    for i, chunk in enumerate(chunks, start=1):
        send_message(chunk)
        print(f"  Sent message {i}/{len(chunks)}")

    print("Done.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python telegram_notify.py <path-to-digest.md>")
        sys.exit(1)

    send_digest(sys.argv[1])
