"""End-to-end flow with the calendar, channel and LLM replaced by fakes."""

from datetime import date, datetime, timedelta

import pytest

from assistant.integrations.telegram import ConsoleChannel
from assistant.models import Event
from assistant.nlp.schema import Extraction, ExtractedItem
from assistant.service import Assistant
from assistant.store import Store

from .conftest import DAY, at, ev


class FakeCalendar:
    def __init__(self, events=None):
        self.events = list(events or [])
        self.created: list[Event] = []
        self.moved: list[tuple] = []

    def fetch(self, day: date, days: int = 1) -> list[Event]:
        return [e for e in self.events if e.start.date() == day]

    def create(self, event: Event) -> str:
        self.created.append(event)
        self.events.append(event)
        return "new-id"

    def move(self, event_id, new_start, duration_minutes):
        self.moved.append((event_id, new_start, duration_minutes))


def fake_parser(*items, clarification=None):
    def parse(text, profile, now=None, client=None):
        return Extraction(items=list(items), needs_clarification=clarification)
    return parse


@pytest.fixture
def assistant(profile):
    def build(calendar=None, parser=None, now=at(10, 0)):
        return Assistant(
            profile=profile,
            store=Store(":memory:"),
            calendar=calendar or FakeCalendar(),
            channel=ConsoleChannel(),
            parser=parser or fake_parser(),
            clock=lambda: now,
        )
    return build


class TestCapture:
    def test_a_task_is_stored_and_confirmed(self, assistant, profile):
        a = assistant(parser=fake_parser(
            ExtractedItem(kind="task", title="Write Q4 plan",
                          estimate_minutes=120, energy="deep", priority=1)))
        reply = a.handle_message("need to write the Q4 plan")
        assert "Write Q4 plan" in reply
        assert [t.title for t in a.store.open_tasks(profile)] == ["Write Q4 plan"]

    def test_an_event_is_proposed_not_written(self, assistant):
        cal = FakeCalendar()
        a = assistant(calendar=cal, parser=fake_parser(
            ExtractedItem(kind="event", title="Lunch with Rahul",
                          start="2026-09-16T13:00", duration_minutes=60,
                          location="Bandra")))
        reply = a.handle_message("lunch with Rahul at 1")
        assert cal.created == []           # nothing hit the calendar
        assert "/yes" in reply             # it asked first

    def test_confirming_writes_the_event(self, assistant):
        cal = FakeCalendar()
        a = assistant(calendar=cal, parser=fake_parser(
            ExtractedItem(kind="event", title="Lunch with Rahul",
                          start="2026-09-16T13:00", duration_minutes=60)))
        reply = a.handle_message("lunch with Rahul at 1")
        proposal_id = reply.split("/yes ")[1].split("<")[0].strip()
        assert "Added" in a.accept(proposal_id)
        assert [e.title for e in cal.created] == ["Lunch with Rahul"]

    def test_a_proposal_cannot_be_confirmed_twice(self, assistant):
        cal = FakeCalendar()
        a = assistant(calendar=cal, parser=fake_parser(
            ExtractedItem(kind="event", title="Lunch",
                          start="2026-09-16T13:00", duration_minutes=60)))
        pid = a.handle_message("lunch").split("/yes ")[1].split("<")[0].strip()
        a.accept(pid)
        assert "expired" in a.accept(pid)
        assert len(cal.created) == 1

    def test_declining_leaves_the_calendar_alone(self, assistant):
        cal = FakeCalendar()
        a = assistant(calendar=cal, parser=fake_parser(
            ExtractedItem(kind="event", title="Lunch",
                          start="2026-09-16T13:00", duration_minutes=60)))
        pid = a.handle_message("lunch").split("/yes ")[1].split("<")[0].strip()
        assert "Left as is" in a.reject(pid)
        assert "expired" in a.accept(pid)
        assert cal.created == []

    def test_a_new_event_warns_about_the_clash_it_would_cause(self, assistant):
        cal = FakeCalendar([ev("existing", "Board call", 13, 0, 60,
                               attendees=("board@x.com",))])
        a = assistant(calendar=cal, parser=fake_parser(
            ExtractedItem(kind="event", title="Lunch with Rahul",
                          start="2026-09-16T13:30", duration_minutes=60)))
        reply = a.handle_message("lunch with Rahul at 1:30")
        assert "Heads up" in reply and "overlaps" in reply

    def test_a_clash_free_event_produces_no_warning(self, assistant):
        cal = FakeCalendar([ev("existing", "Board call", 11, 0, 60)])
        a = assistant(calendar=cal, parser=fake_parser(
            ExtractedItem(kind="event", title="Lunch",
                          start="2026-09-16T13:30", duration_minutes=60)))
        assert "Heads up" not in a.handle_message("lunch at 1:30")

    def test_an_ambiguous_message_asks_back(self, assistant):
        a = assistant(parser=fake_parser(clarification="Which Thursday?"))
        assert "Which Thursday" in a.handle_message("meet Sam Thursday")

    def test_an_event_schedules_its_own_nudge(self, assistant, profile):
        a = assistant(parser=fake_parser(
            ExtractedItem(kind="event", title="Lunch",
                          start="2026-09-16T13:00", duration_minutes=60)))
        a.handle_message("lunch at 1")
        due = a.store.due_reminders(at(12, 50), profile)
        assert [r.title for r in due] == ["Lunch in 15 min"]


class TestCommands:
    def test_today_returns_the_brief(self, assistant):
        a = assistant(calendar=FakeCalendar([ev("a", "Standup", 11, 0, 30)]))
        assert "Standup" in a.handle_message("/today")

    def test_tomorrow_looks_at_the_next_day(self, assistant):
        tomorrow = DAY + timedelta(days=1)
        a = assistant(calendar=FakeCalendar([
            ev("a", "Tomorrow thing", 11, 0, 30, day=tomorrow)]))
        assert "Tomorrow thing" in a.handle_message("/tomorrow")

    def test_done_closes_a_task(self, assistant, profile):
        a = assistant(parser=fake_parser(
            ExtractedItem(kind="task", title="Thing", estimate_minutes=30)))
        a.handle_message("do the thing")
        task_id = a.store.open_tasks(profile)[0].id
        assert "done" in a.handle_message(f"/done {task_id}").lower()
        assert a.store.open_tasks(profile) == []

    def test_done_with_a_bad_id_says_so(self, assistant):
        a = assistant()
        assert "no open task" in a.handle_message("/done nonsense")


class TestProactive:
    def test_the_brief_offers_fixes_for_clashes(self, assistant):
        cal = FakeCalendar([
            ev("client", "Client call", 13, 0, 60, attendees=("c@x.com",)),
            ev("mine", "Write proposal", 13, 30, 60),
        ])
        a = assistant(calendar=cal)
        brief = a.brief(DAY)
        assert "Suggested fixes" in brief and "/yes" in brief

    def test_a_fix_from_the_brief_can_be_confirmed(self, assistant):
        cal = FakeCalendar([
            ev("client", "Client call", 13, 0, 60, attendees=("c@x.com",)),
            ev("mine", "Write proposal", 13, 30, 60),
        ])
        a = assistant(calendar=cal)
        pid = a.brief(DAY).split("/yes ")[1].split("<")[0].strip()
        assert "Moved" in a.accept(pid)
        assert cal.moved[0][0] == "mine"

    def test_reminders_go_out_once(self, assistant):
        from assistant.models import Reminder
        a = assistant(now=at(13, 0))
        a.store.add_reminder(Reminder(id="r1", title="Call back", remind_at=at(12, 55)))
        assert a.dispatch_reminders() == 1
        assert a.dispatch_reminders() == 0
        assert "Call back" in a.channel.sent[0]

    def test_a_conflict_is_announced_once_not_every_check(self, assistant):
        cal = FakeCalendar([ev("a", "A", 13, 0, 60), ev("b", "B", 13, 30, 60)])
        a = assistant(calendar=cal)
        assert a.watch_for_conflicts() == 1
        assert a.watch_for_conflicts() == 0

    def test_a_clean_calendar_stays_quiet(self, assistant):
        a = assistant(calendar=FakeCalendar([ev("a", "A", 13, 0, 60)]))
        assert a.watch_for_conflicts() == 0
        assert a.channel.sent == []

    def test_the_morning_brief_is_sent_to_the_channel(self, assistant):
        a = assistant(calendar=FakeCalendar([ev("a", "Standup", 11, 0, 30)]))
        a.send_brief(DAY)
        assert "Good morning" in a.channel.sent[0]
