"""Your working rules, loaded from config.yaml.

This file is the assistant's model of how you work. The planner and the conflict
engine read nothing else about you, so tuning behaviour means editing YAML, not
code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

import yaml

# Locations that cost no travel time, whatever they are called.
DEFAULT_VIRTUAL = frozenset({"zoom", "meet", "google meet", "teams", "phone", "call", "online", "remote", ""})


@dataclass(frozen=True)
class DeepWorkWindow:
    """A recurring window that must stay unbooked.

    `weekdays` uses Python's Monday=0 convention. An empty tuple means every day.
    """

    label: str
    start: time
    end: time
    weekdays: tuple[int, ...] = ()

    def applies_on(self, day: date) -> bool:
        return not self.weekdays or day.weekday() in self.weekdays


@dataclass(frozen=True)
class Profile:
    timezone: str = "Asia/Kolkata"
    work_start: time = time(9, 0)
    work_end: time = time(19, 0)
    deep_work: tuple[DeepWorkWindow, ...] = ()
    # Travel time in minutes between two named places, symmetric.
    travel_matrix: dict[frozenset[str], int] = field(default_factory=dict)
    default_travel_minutes: int = 30
    virtual_locations: frozenset[str] = DEFAULT_VIRTUAL
    # Padding added around every in-person event, on top of travel.
    default_buffer_minutes: int = 5
    # A task shorter than this is not worth a calendar slot of its own.
    min_task_slot_minutes: int = 15
    telegram_chat_id: str | None = None
    calendar_id: str = "primary"

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)

    def is_virtual(self, location: str | None) -> bool:
        if location is None:
            return True
        return location.strip().lower() in self.virtual_locations

    def travel_minutes(self, a: str | None, b: str | None) -> int:
        """Minutes needed to get from `a` to `b`. Virtual legs are free."""
        if self.is_virtual(a) or self.is_virtual(b):
            return 0
        na, nb = a.strip().lower(), b.strip().lower()
        if na == nb:
            return 0
        return self.travel_matrix.get(frozenset({na, nb}), self.default_travel_minutes)

    def deep_windows_on(self, day: date) -> list[DeepWorkWindow]:
        return [w for w in self.deep_work if w.applies_on(day)]

    def localize(self, dt: datetime) -> datetime:
        """Attach the profile timezone to a naive datetime; convert an aware one."""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=self.tz)
        return dt.astimezone(self.tz)

    def day_bounds(self, day: date) -> tuple[datetime, datetime]:
        start = datetime.combine(day, self.work_start, tzinfo=self.tz)
        end = datetime.combine(day, self.work_end, tzinfo=self.tz)
        return start, end


def _parse_time(value: str | time) -> time:
    if isinstance(value, time):
        return value
    hh, _, mm = str(value).partition(":")
    return time(int(hh), int(mm or 0))


_WEEKDAY_NAMES = {
    "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
}


def _parse_weekdays(values) -> tuple[int, ...]:
    if not values:
        return ()
    out = []
    for v in values:
        if isinstance(v, int):
            out.append(v)
        else:
            out.append(_WEEKDAY_NAMES[str(v)[:3].lower()])
    return tuple(sorted(set(out)))


def load_profile(path: str | None = None) -> Profile:
    """Read config.yaml. Missing file means defaults, which are deliberately sane."""
    path = path or os.environ.get("ASSISTANT_CONFIG", "config.yaml")
    if not os.path.exists(path):
        return Profile()

    with open(path) as fh:
        raw = yaml.safe_load(fh) or {}

    hours = raw.get("working_hours", {})
    travel = {}
    for entry in raw.get("travel", {}).get("routes", []) or []:
        travel[frozenset({entry["from"].strip().lower(), entry["to"].strip().lower()})] = int(entry["minutes"])

    deep = tuple(
        DeepWorkWindow(
            label=w.get("label", "Deep work"),
            start=_parse_time(w["start"]),
            end=_parse_time(w["end"]),
            weekdays=_parse_weekdays(w.get("weekdays")),
        )
        for w in raw.get("deep_work", []) or []
    )

    virtual = raw.get("travel", {}).get("virtual_locations")
    return Profile(
        timezone=raw.get("timezone", "Asia/Kolkata"),
        work_start=_parse_time(hours.get("start", "09:00")),
        work_end=_parse_time(hours.get("end", "19:00")),
        deep_work=deep,
        travel_matrix=travel,
        default_travel_minutes=int(raw.get("travel", {}).get("default_minutes", 30)),
        virtual_locations=frozenset(v.lower() for v in virtual) if virtual else DEFAULT_VIRTUAL,
        default_buffer_minutes=int(raw.get("travel", {}).get("buffer_minutes", 5)),
        min_task_slot_minutes=int(raw.get("planning", {}).get("min_task_slot_minutes", 15)),
        telegram_chat_id=str(raw["telegram_chat_id"]) if raw.get("telegram_chat_id") else None,
        calendar_id=raw.get("calendar_id", "primary"),
    )
