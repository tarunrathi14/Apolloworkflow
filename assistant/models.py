"""Core domain objects.

Everything the assistant reasons about is one of four things: an Event (a block
of time that exists), a Task (work that needs a block of time), a Reminder (a
nudge at a point in time), or a Conflict (a reason the day does not work).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, IntEnum


class Energy(str, Enum):
    """How much focus a task needs. Deep tasks are the ones worth protecting."""

    DEEP = "deep"
    SHALLOW = "shallow"


class TaskStatus(str, Enum):
    OPEN = "open"
    DONE = "done"
    DROPPED = "dropped"


@dataclass(frozen=True)
class Event:
    """A committed block of time.

    `attendees` drives movability: anything with other people on it is not ours
    to move unilaterally, which is what keeps the assistant from proposing that
    you reschedule a client call around your own admin block.
    """

    id: str
    title: str
    start: datetime
    end: datetime
    location: str | None = None
    attendees: tuple[str, ...] = ()
    source: str = "local"  # "gcal" | "local"
    external_id: str | None = None
    movable: bool | None = None  # explicit override; None means infer

    @property
    def is_movable(self) -> bool:
        if self.movable is not None:
            return self.movable
        return not self.attendees

    @property
    def duration(self) -> timedelta:
        return self.end - self.start

    def overlaps(self, other: Event) -> bool:
        return self.start < other.end and other.start < self.end


@dataclass
class Task:
    """Work that still needs a slot. `estimate_minutes` is what the planner books."""

    id: str
    title: str
    estimate_minutes: int = 30
    due: datetime | None = None
    priority: int = 2  # 1 = highest, 3 = lowest
    energy: Energy = Energy.SHALLOW
    status: TaskStatus = TaskStatus.OPEN
    source_note: str | None = None  # e.g. "from Plaud transcript, 12 Sep standup"

    @property
    def duration(self) -> timedelta:
        return timedelta(minutes=self.estimate_minutes)


@dataclass(frozen=True)
class Reminder:
    id: str
    title: str
    remind_at: datetime
    event_id: str | None = None
    task_id: str | None = None
    sent: bool = False


class ConflictKind(str, Enum):
    OVERLAP = "overlap"
    TRAVEL = "travel"
    DEEP_WORK = "deep_work"


class Severity(IntEnum):
    INFO = 1
    WARNING = 2
    CRITICAL = 3


@dataclass(frozen=True)
class Conflict:
    kind: ConflictKind
    severity: Severity
    message: str
    events: tuple[Event, ...]
    detail: dict = field(default_factory=dict, compare=False)

    @property
    def fingerprint(self) -> str:
        """Stable identity for this conflict, so it is announced only once.

        Built from the kind and the events' ids and times: if you move one of
        them and it still clashes, that is a new conflict worth telling you about.
        """
        parts = [self.kind.value] + sorted(
            f"{e.id}@{e.start.isoformat()}-{e.end.isoformat()}" for e in self.events
        )
        return hashlib.sha1("|".join(parts).encode()).hexdigest()[:16]


@dataclass(frozen=True)
class Interval:
    start: datetime
    end: datetime

    @property
    def minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)

    def overlaps(self, other: Interval) -> bool:
        return self.start < other.end and other.start < self.end


@dataclass(frozen=True)
class PlanItem:
    start: datetime
    end: datetime
    title: str
    kind: str  # "event" | "task" | "travel" | "deep_work"
    ref_id: str | None = None
    note: str | None = None


@dataclass
class DayPlan:
    date: datetime
    items: list[PlanItem] = field(default_factory=list)
    conflicts: list[Conflict] = field(default_factory=list)
    unplaced: list[tuple[Task, str]] = field(default_factory=list)  # (task, why)
    free_minutes: int = 0
