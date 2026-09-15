"""Turning "lunch with Rahul Thursday 1pm at Bandra" into structured objects.

The system prompt is deliberately static so it caches; everything that varies
per message (the current time, the text itself) goes in the user turn.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import anthropic

from ..config import Profile
from ..models import Energy, Event, Reminder, Task
from .schema import Extraction, ExtractedItem

MODEL = "claude-opus-5"

SYSTEM = """You read short, informal messages from one person about their schedule \
and turn them into structured items. You are the parsing layer of their personal \
assistant, not the assistant itself — do not reply conversationally.

Classify each thing mentioned as exactly one of:
  event    — happens at a specific time, occupies a block (meetings, calls, lunches, flights)
  task     — work that must get done and needs time found for it (write, review, prepare)
  reminder — a nudge at a moment, occupying no real time (take medication, call back)

Rules:
- One message may contain several items. Emit one entry per item.
- Resolve all relative dates ("tomorrow", "next Thursday", "in an hour") against \
the current time given in the message. Emit ISO 8601 local times with no timezone.
- If a duration was not stated, infer a sensible one: coffee 30m, lunch 60m, \
1:1 30m, interview 45m, workshop 120m. Set duration_minutes rather than guessing an end.
- Anything on Zoom/Meet/Teams/phone gets that as the location. A named place gets \
the place. Leave location null if genuinely unknown.
- For tasks, always set estimate_minutes, energy and priority. Writing, designing, \
analysis and planning are deep; email, admin, scheduling and quick calls are shallow.
- Mark confidence "low" whenever you inferred a date, time or duration that the \
user did not actually state.
- Use needs_clarification only when guessing wrong would genuinely cost the user \
something — a missing day for a real meeting, not a missing duration you can infer. \
Ask at most one question."""


def parse_message(
    text: str,
    profile: Profile,
    now: datetime | None = None,
    client: anthropic.Anthropic | None = None,
) -> Extraction:
    """Read one inbound message into structured items."""
    client = client or anthropic.Anthropic()
    now = profile.localize(now or datetime.now(profile.tz))

    response = client.messages.parse(
        model=MODEL,
        max_tokens=16000,
        system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[
            {
                "role": "user",
                "content": (
                    f"Current time: {now:%Y-%m-%d %H:%M} ({now:%A}), "
                    f"timezone {profile.timezone}.\n\n"
                    f"Message:\n{text}"
                ),
            }
        ],
        output_format=Extraction,
    )
    return response.parsed_output


def _dt(value: str | None, profile: Profile) -> datetime | None:
    if not value:
        return None
    try:
        return profile.localize(datetime.fromisoformat(value))
    except ValueError:
        return None


def to_domain(
    extraction: Extraction, profile: Profile
) -> tuple[list[Event], list[Task], list[Reminder]]:
    """Convert the model's output into the objects the planner understands.

    Items that cannot be made sense of — an event with no start time, a reminder
    with no moment — are dropped here rather than poisoning the plan. The caller
    should surface `needs_clarification` when that happens.
    """
    events: list[Event] = []
    tasks: list[Task] = []
    reminders: list[Reminder] = []

    for item in extraction.items:
        new_id = uuid.uuid4().hex[:12]
        if item.kind == "event":
            start = _dt(item.start, profile)
            if start is None:
                continue
            end = _dt(item.end, profile)
            if end is None or end <= start:
                end = start + timedelta(minutes=item.duration_minutes or 30)
            events.append(
                Event(
                    id=new_id, title=item.title, start=start, end=end,
                    location=item.location, attendees=tuple(item.attendees),
                    source="local",
                )
            )
        elif item.kind == "task":
            tasks.append(
                Task(
                    id=new_id, title=item.title,
                    estimate_minutes=item.estimate_minutes or 30,
                    due=_dt(item.due, profile),
                    priority=item.priority or 2,
                    energy=Energy(item.energy or "shallow"),
                )
            )
        elif item.kind == "reminder":
            remind_at = _dt(item.remind_at, profile)
            if remind_at is None:
                continue
            reminders.append(
                Reminder(id=new_id, title=item.title, remind_at=remind_at)
            )

    return events, tasks, reminders
