"""Telegram — how the assistant reaches you and how you reply.

Kept behind a tiny interface so that swapping in WhatsApp later means writing
one new class, not touching the rest of the codebase.
"""

from __future__ import annotations

import os
from typing import Protocol

import httpx


class Channel(Protocol):
    """Anything that can carry a message to the user and offer buttons."""

    def send(self, text: str, buttons: list[tuple[str, str]] | None = None) -> None: ...


class TelegramChannel:
    def __init__(self, token: str | None = None, chat_id: str | None = None):
        self.token = token or os.environ["TELEGRAM_BOT_TOKEN"]
        self.chat_id = chat_id or os.environ["TELEGRAM_CHAT_ID"]
        self.base = f"https://api.telegram.org/bot{self.token}"

    def send(self, text: str, buttons: list[tuple[str, str]] | None = None) -> None:
        """Send one message. `buttons` are (label, callback_data) pairs."""
        payload: dict = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if buttons:
            payload["reply_markup"] = {
                "inline_keyboard": [
                    [{"text": label, "callback_data": data}] for label, data in buttons
                ]
            }
        with httpx.Client(timeout=15) as client:
            response = client.post(f"{self.base}/sendMessage", json=payload)
            response.raise_for_status()

    def answer_callback(self, callback_id: str, text: str = "") -> None:
        """Clear the spinner on a tapped inline button."""
        with httpx.Client(timeout=15) as client:
            client.post(
                f"{self.base}/answerCallbackQuery",
                json={"callback_query_id": callback_id, "text": text},
            )

    def set_webhook(self, url: str, secret: str | None = None) -> dict:
        payload = {"url": url}
        if secret:
            payload["secret_token"] = secret
        with httpx.Client(timeout=15) as client:
            return client.post(f"{self.base}/setWebhook", json=payload).json()


class ConsoleChannel:
    """Stand-in for local development and tests."""

    def __init__(self):
        self.sent: list[str] = []

    def send(self, text: str, buttons: list[tuple[str, str]] | None = None) -> None:
        self.sent.append(text)
        print(text)
        if buttons:
            print("  [" + "] [".join(label for label, _ in buttons) + "]")
