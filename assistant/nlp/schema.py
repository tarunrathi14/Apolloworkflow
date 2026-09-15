"""The shape Claude must return when reading one of your messages.

A single flat model with a `kind` discriminator, rather than a union: strict
structured outputs handle a flat schema far more reliably, and the conversion
to real domain objects happens in `extract.to_domain`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ExtractedItem(BaseModel):
    kind: Literal["event", "task", "reminder"]
    title: str = Field(description="Short, how the user would recognise it")

    # event
    start: str | None = Field(default=None, description="ISO 8601 local time, no zone")
    end: str | None = Field(default=None, description="ISO 8601 local time, no zone")
    duration_minutes: int | None = Field(
        default=None, description="Use when an end time was not stated"
    )
    location: str | None = Field(
        default=None,
        description="A place name, or Zoom/Meet/Phone for anything remote",
    )
    attendees: list[str] = Field(
        default_factory=list, description="Other people involved, names or emails"
    )

    # task
    due: str | None = Field(default=None, description="ISO 8601 local deadline")
    estimate_minutes: int | None = Field(
        default=None, description="Your best guess at how long the work takes"
    )
    energy: Literal["deep", "shallow"] | None = Field(
        default=None,
        description="deep = needs uninterrupted focus; shallow = admin, calls, email",
    )
    priority: int | None = Field(default=None, description="1 highest, 2 normal, 3 low")

    # reminder
    remind_at: str | None = Field(default=None, description="ISO 8601 local time")

    confidence: Literal["high", "low"] = Field(
        default="high",
        description="low if you guessed at the time, date, or duration",
    )


class Extraction(BaseModel):
    items: list[ExtractedItem] = Field(default_factory=list)
    needs_clarification: str | None = Field(
        default=None,
        description=(
            "One short question to ask back, only when a detail is genuinely "
            "ambiguous and guessing wrong would matter. Otherwise null."
        ),
    )
