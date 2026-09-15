"""Orchestration: what actually happens when a message arrives or a job fires.

Every external dependency (calendar, channel, LLM, clock) is injected, so the
whole flow is testable without credentials.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Callable, Protocol

from .briefing import render_capture, render_day, render_proposals
from .config import Profile
from .models import Event, Reminder, Task
from .nlp.extract import parse_message, to_domain
from .planner import build_day_plan
from .proposals import propose_all
from .store import Store

# Minutes before an event that the nudge goes out.
DEFAULT_LEAD_MINUTES = 15


class CalendarPort(Protocol):
    def fetch(self, day: date, days: int = 1) -> list[Event]: ...
    def create(self, event: Event) -> str: ...
    def move(self, event_id: str, new_start: datetime, duration_minutes: int) -> None: ...


class Assistant:
    def __init__(
        self,
        profile: Profile,
        store: Store,
        calendar: CalendarPort,
        channel,
        parser: Callable[..., object] = parse_message,
        clock: Callable[[], datetime] | None = None,
    ):
        self.profile = profile
        self.store = store
        self.calendar = calendar
        self.channel = channel
        self.parser = parser
        self.clock = clock or (lambda: datetime.now(profile.tz))

    # --- inbound -------------------------------------------------------

    def handle_message(self, text: str) -> str:
        """Parse a message, store what it found, and reply with what it understood."""
        command = text.strip().lower()
        if command in {"/today", "today"}:
            return self.brief(self.clock().date())
        if command in {"/tomorrow", "tomorrow"}:
            return self.brief(self.clock().date() + timedelta(days=1))
        if command.startswith("/yes "):
            return self.accept(text.split(maxsplit=1)[1].strip())
        if command.startswith("/no "):
            return self.reject(text.split(maxsplit=1)[1].strip())
        if command.startswith("/done "):
            task_id = text.split(maxsplit=1)[1].strip()
            ok = self.store.complete_task(task_id)
            return "✅ Marked done." if ok else "I have no open task with that id."

        now = self.clock()
        extraction = self.parser(text, self.profile, now)
        events, tasks, reminders = to_domain(extraction, self.profile)

        for task in tasks:
            self.store.add_task(task)
        for reminder in reminders:
            self.store.add_reminder(reminder)

        # Events are proposed, not written: nothing reaches the calendar
        # without a confirmation.
        for event in events:
            self.store.save_proposal(
                event.id,
                f"Add “{event.title}” to your calendar?",
                {
                    "op": "create_event",
                    "title": event.title,
                    "start": event.start.isoformat(),
                    "end": event.end.isoformat(),
                    "location": event.location,
                    "attendees": list(event.attendees),
                },
            )
            self._auto_reminder(event)

        reply = render_capture(
            events, tasks, reminders, extraction.needs_clarification
        )
        if events:
            confirm = "\n".join(
                f"<code>/yes {e.id}</code> to put “{e.title}” on the calendar"
                for e in events
            )
            reply += "\n\n" + confirm
            # Show what adding them would do to the day.
            reply += self._impact(events)
        return reply

    def _auto_reminder(self, event: Event) -> None:
        remind_at = event.start - timedelta(minutes=DEFAULT_LEAD_MINUTES)
        if remind_at <= self.clock():
            return
        self.store.add_reminder(
            Reminder(
                id=f"r-{event.id}", title=f"{event.title} in {DEFAULT_LEAD_MINUTES} min",
                remind_at=remind_at, event_id=event.id,
            )
        )

    def _impact(self, new_events: list[Event]) -> str:
        """What these events would do to the day they land on."""
        from .conflicts import detect_conflicts
        from .briefing import render_conflicts

        out = []
        for day in sorted({e.start.astimezone(self.profile.tz).date()
                           for e in new_events}):
            existing = self.calendar.fetch(day)
            same_day = [e for e in new_events
                        if e.start.astimezone(self.profile.tz).date() == day]
            conflicts = detect_conflicts(existing + same_day, self.profile, day)
            # Only report conflicts the new events are actually part of.
            new_ids = {e.id for e in same_day}
            relevant = [c for c in conflicts
                        if any(e.id in new_ids for e in c.events)]
            if relevant:
                out.append(f"\n\n<b>Heads up for {day:%a %d %b}</b>\n"
                           + render_conflicts(relevant))
        return "".join(out)

    # --- confirmations -------------------------------------------------

    def accept(self, proposal_id: str) -> str:
        action = self.store.take_proposal(proposal_id)
        if action is None:
            return "That suggestion has expired or was already answered."
        return self.apply(action)

    def reject(self, proposal_id: str) -> str:
        ok = self.store.reject_proposal(proposal_id)
        return "Left as is." if ok else "Nothing pending with that id."

    def apply(self, action: dict) -> str:
        op = action.get("op")
        if op == "create_event":
            event = Event(
                id="", title=action["title"],
                start=self.profile.localize(datetime.fromisoformat(action["start"])),
                end=self.profile.localize(datetime.fromisoformat(action["end"])),
                location=action.get("location"),
                attendees=tuple(action.get("attendees") or ()),
            )
            self.calendar.create(event)
            return f"📅 Added “{event.title}”."
        if op == "move_event":
            if not action.get("to"):
                return "Nothing free today — tell me a day and I will move it."
            self.calendar.move(
                action["event_id"],
                self.profile.localize(datetime.fromisoformat(action["to"])),
                action["duration_minutes"],
            )
            return "📅 Moved."
        if op == "none":
            return "Understood — leaving that one to you."
        return f"I do not know how to do that ({op})."

    # --- outbound ------------------------------------------------------

    def plan_for(self, day: date):
        events = self.calendar.fetch(day)
        tasks = self.store.open_tasks(self.profile)
        now = self.clock()
        return build_day_plan(events, tasks, self.profile, day,
                              now=now if now.date() == day else None)

    def brief(self, day: date | None = None, greeting: str | None = None) -> str:
        """The daily brief, with a confirmable fix for anything broken."""
        day = day or self.clock().date()
        plan = self.plan_for(day)
        text = render_day(plan, greeting)

        if plan.conflicts:
            events = self.calendar.fetch(day)
            proposals = propose_all(plan.conflicts, events, self.profile, day,
                                    self.clock())
            for p in proposals:
                self.store.save_proposal(p.id, p.summary, p.action)
            text += "\n" + render_proposals(proposals)
        return text

    def send_brief(self, day: date | None = None) -> None:
        self.channel.send(self.brief(day, greeting="<b>Good morning ☀️</b>"))

    def dispatch_reminders(self) -> int:
        """Send anything now due. Returns how many went out."""
        now = self.clock()
        due = self.store.due_reminders(now, self.profile)
        for reminder in due:
            self.channel.send(f"⏰ <b>{reminder.title}</b>")
            self.store.mark_sent(reminder.id)
        return len(due)

    def watch_for_conflicts(self) -> int:
        """Re-check today and tomorrow; message only if something is newly wrong."""
        sent = 0
        for offset in (0, 1):
            day = self.clock().date() + timedelta(days=offset)
            plan = self.plan_for(day)
            if not plan.conflicts:
                continue
            fresh = [c for c in plan.conflicts
                     if self.store.is_new_conflict(c.fingerprint)]
            if not fresh:
                continue  # already told you about these
            events = self.calendar.fetch(day)
            proposals = propose_all(fresh, events, self.profile, day, self.clock())
            for proposal in proposals:
                self.store.save_proposal(proposal.id, proposal.summary,
                                         proposal.action)
            from .briefing import render_conflicts
            self.channel.send(
                f"<b>{day:%a %d %b}</b>\n" + render_conflicts(fresh)
                + render_proposals(proposals)
            )
            sent += 1
        return sent
