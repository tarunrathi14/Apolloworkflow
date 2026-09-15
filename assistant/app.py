"""FastAPI service: the Telegram webhook plus a couple of inspection routes."""

from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta

from fastapi import FastAPI, Header, HTTPException, Request

from .config import load_profile
from .integrations import gcal
from .integrations.telegram import TelegramChannel
from .models import Event
from .service import Assistant
from .store import Store

log = logging.getLogger(__name__)
app = FastAPI(title="Personal assistant")


class GoogleCalendar:
    """Adapter binding the Calendar API to the port the service expects."""

    def __init__(self, service, profile):
        self.service, self.profile = service, profile

    def fetch(self, day: date, days: int = 1) -> list[Event]:
        return gcal.fetch_events(self.service, self.profile, day, days)

    def create(self, event: Event) -> str:
        return gcal.create_event(self.service, self.profile, event)

    def move(self, event_id: str, new_start: datetime, duration_minutes: int) -> None:
        gcal.move_event(self.service, self.profile, event_id, new_start,
                        duration_minutes)


def build_assistant() -> Assistant:
    profile = load_profile()
    return Assistant(
        profile=profile,
        store=Store(os.environ.get("ASSISTANT_DB", "assistant.db")),
        calendar=GoogleCalendar(gcal.get_service(), profile),
        channel=TelegramChannel(chat_id=profile.telegram_chat_id
                                or os.environ.get("TELEGRAM_CHAT_ID")),
    )


@app.on_event("startup")
def startup() -> None:
    app.state.assistant = build_assistant()
    if os.environ.get("RUN_SCHEDULER", "1") == "1":
        from .scheduler import start_scheduler
        app.state.scheduler = start_scheduler(app.state.assistant)


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> dict:
    """Telegram calls this on every message. Only your chat is answered."""
    secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET")
    if secret and x_telegram_bot_api_secret_token != secret:
        raise HTTPException(status_code=403, detail="bad secret")

    payload = await request.json()
    assistant: Assistant = app.state.assistant

    # Inline button taps.
    if callback := payload.get("callback_query"):
        data = callback.get("data", "")
        verb, _, proposal_id = data.partition(":")
        reply = (assistant.accept(proposal_id) if verb == "yes"
                 else assistant.reject(proposal_id))
        assistant.channel.answer_callback(callback["id"])
        assistant.channel.send(reply)
        return {"ok": True}

    message = payload.get("message") or payload.get("edited_message")
    if not message or "text" not in message:
        return {"ok": True}

    # This is a personal tool: ignore anyone who is not you.
    allowed = str(assistant.channel.chat_id)
    if str(message["chat"]["id"]) != allowed:
        log.warning("ignored message from chat %s", message["chat"]["id"])
        return {"ok": True}

    try:
        reply = assistant.handle_message(message["text"])
    except Exception:
        log.exception("failed to handle message")
        reply = "Something broke on my side — try rephrasing that?"
    assistant.channel.send(reply)
    return {"ok": True}


@app.get("/plan/today")
def plan_today() -> dict:
    """Plain-text plan, handy for debugging without opening Telegram."""
    assistant: Assistant = app.state.assistant
    return {"brief": assistant.brief()}


@app.get("/plan/{day}")
def plan_for_day(day: str) -> dict:
    assistant: Assistant = app.state.assistant
    return {"brief": assistant.brief(date.fromisoformat(day))}
