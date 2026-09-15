"""Turning conflicts into something you can answer with "yes".

The assistant never writes to your calendar on its own. For each conflict it
builds a Proposal: a human sentence plus the exact change it would make. The
bot shows the sentence; if you tap yes, `action` is what gets executed.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from .config import Profile
from .models import Conflict, ConflictKind, Event, Interval
from .planner import free_intervals


@dataclass
class Proposal:
    """One suggested fix, pending your confirmation."""

    id: str
    summary: str  # what the bot says to you
    action: dict  # what happens on "yes": {"op": "move_event", "event_id":..., ...}
    conflict: Conflict
    confidence: str = "medium"  # low | medium | high
    alternatives: list[str] = field(default_factory=list)

    @staticmethod
    def new(summary: str, action: dict, conflict: Conflict, **kw) -> "Proposal":
        return Proposal(id=uuid.uuid4().hex[:8], summary=summary, action=action,
                        conflict=conflict, **kw)


def _fmt(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def _nearest_slot(
    duration: timedelta,
    free: list[Interval],
    after: datetime | None = None,
    avoid: list[Interval] | None = None,
) -> datetime | None:
    """Earliest start in `free` that fits `duration`, optionally after a time.

    A candidate that lands on an `avoid` window steps past that window and keeps
    looking inside the same span, rather than giving up on the span.
    """
    blocked = sorted(avoid or [], key=lambda i: i.start)
    for span in sorted(free, key=lambda i: i.start):
        start = max(span.start, after) if after else span.start
        while start + duration <= span.end:
            clash = next(
                (a for a in blocked if Interval(start, start + duration).overlaps(a)),
                None,
            )
            if clash is None:
                return start
            start = clash.end  # always advances: an overlap means clash.end > start
    return None


def _options(conflict: Conflict) -> list[str]:
    """Realistic ways out when nothing is ours to move, by conflict kind."""
    asks = [f"Ask to move “{e.title}”" for e in conflict.events]
    if conflict.kind is ConflictKind.TRAVEL:
        return asks + ["Take the second one from the road",
                       "Ask to make one of them a call"]
    if conflict.kind is ConflictKind.DEEP_WORK:
        return asks + ["Let it through just this once",
                       "Shift your block later today"]
    return asks + ["Join the first one late", "Send someone else"]


def _movable_side(conflict: Conflict) -> Event | None:
    """Of the events in a conflict, the one that is ours to move.

    If both are movable we move the later one — it is the one that most likely
    got added on top of an existing commitment.
    """
    movable = [e for e in conflict.events if e.is_movable]
    if not movable:
        return None
    return max(movable, key=lambda e: e.start)


def propose(
    conflict: Conflict,
    events: list[Event],
    profile: Profile,
    day: date,
    now: datetime | None = None,
) -> Proposal:
    """Build the best available fix for one conflict."""
    target = _movable_side(conflict)

    if target is None:
        # Everything involved has other people on it. Hand it back with options.
        whose = ("That one has other people on it"
                 if len(conflict.events) == 1
                 else "Both have other people on them")
        return Proposal.new(
            summary=f"{conflict.message}. {whose}, so this one is yours to call.",
            action={"op": "none"},
            conflict=conflict,
            confidence="high",
            alternatives=_options(conflict),
        )

    # Free time on the day, ignoring the event we are about to move.
    others = [e for e in events if e.id != target.id]
    free = free_intervals(others, profile, day, now)

    # Never resolve a conflict by dropping the event into a protected block —
    # that just trades one conflict for another.
    avoid = [
        Interval(
            datetime.combine(day, w.start, tzinfo=profile.tz),
            datetime.combine(day, w.end, tzinfo=profile.tz),
        )
        for w in profile.deep_windows_on(day)
    ]

    slot = _nearest_slot(target.duration, free, avoid=avoid)

    if slot is None:
        return Proposal.new(
            summary=(
                f"{conflict.message}. Nothing free today fits “{target.title}” — "
                f"move it to tomorrow?"
            ),
            action={"op": "move_event", "event_id": target.id, "to": None,
                    "hint": "next_day"},
            conflict=conflict,
            confidence="low",
            alternatives=["Shorten it", "Make it a call", "Drop it this week"],
        )

    verb = {
        ConflictKind.OVERLAP: "clashes",
        ConflictKind.TRAVEL: "is too tight",
        ConflictKind.DEEP_WORK: "is in your protected block",
    }[conflict.kind]

    return Proposal.new(
        summary=(
            f"{conflict.message}.\nMove “{target.title}” to "
            f"{_fmt(slot)}–{_fmt(slot + target.duration)}?"
        ),
        action={
            "op": "move_event",
            "event_id": target.id,
            "to": slot.isoformat(),
            "duration_minutes": int(target.duration.total_seconds() // 60),
        },
        conflict=conflict,
        confidence="high" if conflict.kind is not ConflictKind.TRAVEL else "medium",
        alternatives=[f"Keep it, it {verb} but that is fine", "Pick another time"],
    )


def propose_all(
    conflicts: list[Conflict],
    events: list[Event],
    profile: Profile,
    day: date,
    now: datetime | None = None,
) -> list[Proposal]:
    return [propose(c, events, profile, day, now) for c in conflicts]
