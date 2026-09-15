from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from assistant.config import DeepWorkWindow, Profile
from assistant.models import Event, Task

TZ = ZoneInfo("Asia/Kolkata")
DAY = datetime(2026, 9, 16, tzinfo=TZ).date()  # a Wednesday


@pytest.fixture
def profile() -> Profile:
    return Profile(
        timezone="Asia/Kolkata",
        work_start=time(9, 0),
        work_end=time(19, 0),
        deep_work=(DeepWorkWindow("Morning maker time", time(9, 0), time(11, 0)),),
        travel_matrix={
            frozenset({"home", "office"}): 30,
            frozenset({"office", "client hq"}): 45,
        },
        default_travel_minutes=30,
        default_buffer_minutes=5,
    )


def at(hour: int, minute: int = 0, day=DAY) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=TZ)


def ev(id_, title, start_h, start_m, dur_min, location=None, attendees=(),
       day=DAY, **kw) -> Event:
    start = at(start_h, start_m, day)
    return Event(
        id=id_, title=title, start=start,
        end=start + timedelta(minutes=dur_min),
        location=location, attendees=tuple(attendees), **kw
    )


def task(id_, title, minutes, **kw) -> Task:
    return Task(id=id_, title=title, estimate_minutes=minutes, **kw)
