"""A walkthrough you can run with no credentials: python -m assistant.demo

Uses a fake calendar and a scripted parser so you can see exactly how the
assistant behaves on a messy day before wiring up Google or Telegram.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

from .config import load_profile
from .integrations.telegram import ConsoleChannel
from .models import Event
from .nlp.schema import Extraction, ExtractedItem
from .service import Assistant
from .store import Store

TAGS = re.compile(r"<[^>]+>")


def plain(text: str) -> str:
    """Strip the Telegram HTML so the terminal output stays readable."""
    return TAGS.sub("", text).replace("&amp;", "&").replace("&lt;", "<")


class DemoCalendar:
    def __init__(self, events):
        self.events = list(events)

    def fetch(self, day: date, days: int = 1) -> list[Event]:
        return [e for e in self.events if e.start.date() == day]

    def create(self, event: Event) -> str:
        self.events.append(event)
        return "demo-id"

    def move(self, event_id: str, new_start: datetime, duration_minutes: int) -> None:
        for i, e in enumerate(self.events):
            if e.id == event_id:
                self.events[i] = Event(
                    id=e.id, title=e.title, start=new_start,
                    end=new_start + timedelta(minutes=duration_minutes),
                    location=e.location, attendees=e.attendees,
                )


def main() -> None:
    profile = load_profile("config.example.yaml")
    tz = profile.tz
    day = datetime.now(tz).date()

    def at(h, m=0):
        return datetime.combine(day, datetime.min.time().replace(hour=h, minute=m),
                                tzinfo=tz)

    # A realistically annoying day.
    calendar = DemoCalendar([
        Event(id="standup", title="Team standup", start=at(9, 30), end=at(10, 0),
              location="Zoom", attendees=("team@acme.com",)),
        Event(id="review", title="Design review", start=at(11, 0), end=at(12, 0),
              location="Office", attendees=("design@acme.com",)),
        Event(id="pitch", title="Client pitch", start=at(12, 15), end=at(13, 15),
              location="Client HQ", attendees=("buyer@bigco.com",)),
        Event(id="notes", title="Write up pitch notes", start=at(12, 30),
              end=at(13, 0)),
    ])

    scripted = [
        ExtractedItem(kind="task", title="Draft Q4 strategy memo",
                      estimate_minutes=120, energy="deep", priority=1),
        ExtractedItem(kind="task", title="Reply to the vendor thread",
                      estimate_minutes=20, energy="shallow", priority=2),
        ExtractedItem(kind="reminder", title="Take the 6pm call from the airport",
                      remind_at=at(17, 45).replace(tzinfo=None).isoformat()),
    ]

    assistant = Assistant(
        profile=profile,
        store=Store(":memory:"),
        calendar=calendar,
        channel=ConsoleChannel(),
        parser=lambda *a, **k: Extraction(items=scripted),
        clock=lambda: at(8, 0),
    )

    print("=" * 68)
    print("1. You text the bot a brain-dump")
    print("=" * 68)
    print('  > "draft the Q4 strategy memo, reply to the vendor thread,')
    print('     and remind me about the 6pm call from the airport"\n')
    print(plain(assistant.handle_message("brain dump")))

    print("\n" + "=" * 68)
    print("2. It plans your day around what is already booked")
    print("=" * 68)
    print(plain(assistant.brief(day)))

    print("\n" + "=" * 68)
    print("3. You accept the first suggested fix")
    print("=" * 68)
    brief = assistant.brief(day)
    ids = re.findall(r"/yes (\w+)", brief)
    if ids:
        print(plain(assistant.accept(ids[0])))
        print("\nReplanned:\n")
        print(plain(assistant.brief(day)))
    else:
        print("Nothing to fix.")


if __name__ == "__main__":
    main()
