"""Conflict detection.

Three things can be wrong with a day:

  OVERLAP    two events claim the same minutes
  TRAVEL     the gap between two places is smaller than the time to cross it
  DEEP_WORK  something was booked into a window you said to protect

Severity is about recoverability, not annoyance. CRITICAL means the day as
scheduled is impossible; WARNING means it is possible but violates a rule you
set.
"""

from __future__ import annotations

from datetime import date, datetime

from .config import Profile
from .models import Conflict, ConflictKind, Event, Severity


def _fmt(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def detect_overlaps(events: list[Event]) -> list[Conflict]:
    """Every pair of events that share time.

    Two immovable events overlapping is CRITICAL: only you can resolve it. If at
    least one side is yours to move, it is a WARNING and the proposer can offer
    a fix.
    """
    out: list[Conflict] = []
    ordered = sorted(events, key=lambda e: (e.start, e.end))
    for i, a in enumerate(ordered):
        for b in ordered[i + 1:]:
            if b.start >= a.end:
                break  # sorted by start, so nothing later can overlap `a`
            if not a.overlaps(b):
                continue
            both_fixed = not a.is_movable and not b.is_movable
            overlap_min = int(
                (min(a.end, b.end) - max(a.start, b.start)).total_seconds() // 60
            )
            out.append(
                Conflict(
                    kind=ConflictKind.OVERLAP,
                    severity=Severity.CRITICAL if both_fixed else Severity.WARNING,
                    message=(
                        f"“{a.title}” ({_fmt(a.start)}–{_fmt(a.end)}) overlaps "
                        f"“{b.title}” ({_fmt(b.start)}–{_fmt(b.end)}) by {overlap_min} min"
                    ),
                    events=(a, b),
                    detail={"overlap_minutes": overlap_min, "both_fixed": both_fixed},
                )
            )
    return out


def detect_travel(events: list[Event], profile: Profile) -> list[Conflict]:
    """Back-to-backs that are physically impossible.

    Only consecutive pairs matter: if you cannot make the next one, the ones
    after it are a consequence, not a separate problem.
    """
    out: list[Conflict] = []
    ordered = sorted(events, key=lambda e: e.start)
    for a, b in zip(ordered, ordered[1:]):
        if a.overlaps(b):
            continue  # already reported as an overlap
        needed = profile.travel_minutes(a.location, b.location)
        if needed == 0:
            continue
        needed += profile.default_buffer_minutes
        gap = int((b.start - a.end).total_seconds() // 60)
        if gap >= needed:
            continue
        out.append(
            Conflict(
                kind=ConflictKind.TRAVEL,
                severity=Severity.CRITICAL,
                message=(
                    f"Only {gap} min between “{a.title}” ({a.location}) and "
                    f"“{b.title}” ({b.location}) — you need about {needed}"
                ),
                events=(a, b),
                detail={"gap_minutes": gap, "needed_minutes": needed,
                        "short_by": needed - gap},
            )
        )
    return out


def detect_deep_work(events: list[Event], profile: Profile, day: date) -> list[Conflict]:
    """Anything booked inside a protected window."""
    out: list[Conflict] = []
    for window in profile.deep_windows_on(day):
        w_start = datetime.combine(day, window.start, tzinfo=profile.tz)
        w_end = datetime.combine(day, window.end, tzinfo=profile.tz)
        for event in sorted(events, key=lambda e: e.start):
            if event.start < w_end and w_start < event.end:
                out.append(
                    Conflict(
                        kind=ConflictKind.DEEP_WORK,
                        severity=Severity.WARNING,
                        message=(
                            f"“{event.title}” ({_fmt(event.start)}–{_fmt(event.end)}) "
                            f"lands in your protected block “{window.label}” "
                            f"({_fmt(w_start)}–{_fmt(w_end)})"
                        ),
                        events=(event,),
                        detail={"window": window.label,
                                "window_start": w_start, "window_end": w_end},
                    )
                )
    return out


def detect_conflicts(events: list[Event], profile: Profile, day: date | None = None) -> list[Conflict]:
    """All conflicts for a set of events, worst first."""
    if not events:
        return []
    day = day or min(e.start for e in events).astimezone(profile.tz).date()
    found = (
        detect_overlaps(events)
        + detect_travel(events, profile)
        + detect_deep_work(events, profile, day)
    )
    return sorted(found, key=lambda c: (-c.severity, c.events[0].start))
