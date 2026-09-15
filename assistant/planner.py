"""Day planning: turn events + a task backlog into an ordered timeline.

The planner never moves an event. It takes the calendar as given, works out
what time is actually left once travel is accounted for, and fits tasks into
that. Deep work windows are reserved for DEEP tasks — that is what "protected"
means here: shallow work is not allowed to eat the block either.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from .conflicts import detect_conflicts
from .config import Profile
from .models import DayPlan, Energy, Event, Interval, PlanItem, Task, TaskStatus

FAR_FUTURE = datetime.max.replace(tzinfo=None)


def subtract(free: list[Interval], busy: Interval) -> list[Interval]:
    """Remove `busy` from a list of free intervals."""
    out: list[Interval] = []
    for span in free:
        if not span.overlaps(busy):
            out.append(span)
            continue
        if span.start < busy.start:
            out.append(Interval(span.start, busy.start))
        if busy.end < span.end:
            out.append(Interval(busy.end, span.end))
    return out


def intersect(a: list[Interval], b: list[Interval]) -> list[Interval]:
    out: list[Interval] = []
    for x in a:
        for y in b:
            start, end = max(x.start, y.start), min(x.end, y.end)
            if start < end:
                out.append(Interval(start, end))
    return sorted(out, key=lambda i: i.start)


def event_footprint(event: Event, profile: Profile) -> Interval:
    """The event plus the padding an in-person event really costs."""
    if profile.is_virtual(event.location):
        return Interval(event.start, event.end)
    pad = timedelta(minutes=profile.default_buffer_minutes)
    return Interval(event.start - pad, event.end + pad)


def travel_items(events: list[Event], profile: Profile) -> list[PlanItem]:
    """A leg of travel between each consecutive pair that needs one."""
    out: list[PlanItem] = []
    ordered = sorted(events, key=lambda e: e.start)
    for a, b in zip(ordered, ordered[1:]):
        minutes = profile.travel_minutes(a.location, b.location)
        if minutes <= 0 or a.overlaps(b):
            continue
        wanted = a.end + timedelta(minutes=minutes)
        end = min(b.start, wanted)
        if end <= a.end:
            continue
        available = int((end - a.end).total_seconds() // 60)
        note = (f"~{minutes} min" if end == wanted
                else f"needs ~{minutes} min, only {available} available")
        out.append(
            PlanItem(
                start=a.end,
                end=end,
                title=f"Travel: {a.location} → {b.location}",
                kind="travel",
                note=note,
            )
        )
    return out


def free_intervals(
    events: list[Event],
    profile: Profile,
    day: date,
    now: datetime | None = None,
) -> list[Interval]:
    """Working-day time not consumed by events or the travel between them."""
    todays = sorted(
        (e for e in events if e.start.astimezone(profile.tz).date() == day),
        key=lambda e: e.start,
    )
    work_start, work_end = profile.day_bounds(day)
    if now is not None:
        now = profile.localize(now)
        if now.date() == day and now > work_start:
            work_start = now
    if work_start >= work_end:
        return []
    free = [Interval(work_start, work_end)]
    for event in todays:
        free = subtract(free, event_footprint(event, profile))
    for leg in travel_items(todays, profile):
        free = subtract(free, Interval(leg.start, leg.end))
    return free


def _urgency(task: Task) -> tuple:
    """Soonest deadline first, then priority, then longest job."""
    due = task.due.replace(tzinfo=None) if task.due else FAR_FUTURE
    return (due, task.priority, -task.estimate_minutes)


def build_day_plan(
    events: list[Event],
    tasks: list[Task],
    profile: Profile,
    day: date,
    now: datetime | None = None,
) -> DayPlan:
    """Build the plan for `day`.

    If `now` falls inside the day, the planner will not schedule anything in the
    past — a plan generated at 3pm starts at 3pm.
    """
    todays = sorted(
        (e for e in events if e.start.astimezone(profile.tz).date() == day),
        key=lambda e: e.start,
    )
    plan = DayPlan(date=datetime.combine(day, datetime.min.time(), tzinfo=profile.tz))
    plan.conflicts = detect_conflicts(todays, profile, day)

    items: list[PlanItem] = [
        PlanItem(
            start=e.start, end=e.end, title=e.title, kind="event",
            ref_id=e.id,
            note=e.location if not profile.is_virtual(e.location) else None,
        )
        for e in todays
    ]
    legs = travel_items(todays, profile)
    items.extend(legs)

    # What is left of the working day.
    work_start, work_end = profile.day_bounds(day)
    if now is not None:
        now = profile.localize(now)
        if now.date() == day and now > work_start:
            work_start = now
    if work_start >= work_end:
        plan.items = sorted(items, key=lambda i: i.start)
        plan.unplaced = [(t, "the working day is already over") for t in tasks
                         if t.status is TaskStatus.OPEN]
        return plan

    free = free_intervals(todays, profile, day, now)

    # Split free time into protected and ordinary.
    deep_windows = [
        Interval(
            datetime.combine(day, w.start, tzinfo=profile.tz),
            datetime.combine(day, w.end, tzinfo=profile.tz),
        )
        for w in profile.deep_windows_on(day)
    ]
    for window in deep_windows:
        items.append(
            PlanItem(start=window.start, end=window.end,
                     title="Protected: deep work", kind="deep_work")
        )
    protected = intersect(free, deep_windows)
    ordinary = list(free)
    for window in deep_windows:
        ordinary = subtract(ordinary, window)

    plan.free_minutes = sum(i.minutes for i in free)

    open_tasks = [t for t in tasks if t.status is TaskStatus.OPEN]
    for task in sorted(open_tasks, key=_urgency):
        if task.estimate_minutes < profile.min_task_slot_minutes:
            # Too small to book; it rides along with whatever else you are doing.
            plan.unplaced.append((task, "too short to book — batch it"))
            continue
        # Deep tasks get first claim on the protected block, then ordinary time.
        pools = ([protected, ordinary] if task.energy is Energy.DEEP
                 else [ordinary, protected])
        placed = False
        for pool in pools:
            slot = _first_fit(pool, task.duration)
            if slot is None:
                continue
            start = slot.start
            end = start + task.duration
            items.append(
                PlanItem(start=start, end=end, title=task.title, kind="task",
                         ref_id=task.id,
                         note=f"due {task.due:%d %b %H:%M}" if task.due else None)
            )
            busy = Interval(start, end)
            protected = subtract(protected, busy)
            ordinary = subtract(ordinary, busy)
            placed = True
            break
        if not placed:
            plan.unplaced.append(
                (task, f"no free block of {task.estimate_minutes} min left today")
            )

    plan.items = sorted(items, key=lambda i: (i.start, i.kind != "deep_work"))
    return plan


def _first_fit(pool: list[Interval], need: timedelta) -> Interval | None:
    for span in sorted(pool, key=lambda i: i.start):
        if span.end - span.start >= need:
            return span
    return None
