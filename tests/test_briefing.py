from assistant.briefing import render_capture, render_conflicts, render_day
from assistant.conflicts import detect_conflicts
from assistant.models import Energy
from assistant.planner import build_day_plan

from .conftest import DAY, at, ev, task


class TestBriefing:
    def test_an_empty_day_says_so(self, profile):
        plan = build_day_plan([], [], profile, DAY)
        assert "whole day is yours" in render_day(plan)

    def test_events_and_times_appear(self, profile):
        plan = build_day_plan([ev("a", "Standup", 11, 0, 30)], [], profile, DAY)
        out = render_day(plan)
        assert "Standup" in out and "11:00–11:30" in out

    def test_free_time_is_reported(self, profile):
        plan = build_day_plan([], [], profile, DAY)
        assert "10h 00m unbooked" in render_day(plan)

    def test_conflicts_are_surfaced_in_the_brief(self, profile):
        events = [ev("a", "A", 11, 0, 60), ev("b", "B", 11, 30, 60)]
        plan = build_day_plan(events, [], profile, DAY)
        assert "to look at" in render_day(plan)

    def test_unplaced_tasks_are_listed(self, profile):
        plan = build_day_plan([], [task("big", "Huge job", 900)], profile, DAY)
        assert "Did not fit today" in render_day(plan)
        assert "Huge job" in render_day(plan)

    def test_html_in_a_title_cannot_break_the_message(self, profile):
        plan = build_day_plan([ev("a", "Review <b>draft</b> & sign", 11, 0, 30)],
                              [], profile, DAY)
        out = render_day(plan)
        assert "&lt;b&gt;draft&lt;/b&gt;" in out and "&amp; sign" in out

    def test_a_clean_day_reports_no_clashes(self):
        assert "No clashes" in render_conflicts([])

    def test_capture_confirms_what_was_understood(self, profile):
        from assistant.models import Task
        events = [ev("a", "Lunch with Rahul", 13, 0, 60, location="Bandra")]
        tasks = [Task(id="t", title="Write plan", estimate_minutes=90,
                      energy=Energy.DEEP)]
        out = render_capture(events, tasks, [])
        assert "Lunch with Rahul" in out and "Bandra" in out
        assert "Write plan" in out and "90m" in out

    def test_capture_asks_back_when_told_to(self):
        assert "Which Thursday" in render_capture([], [], [], "Which Thursday?")

    def test_capture_handles_understanding_nothing(self):
        assert render_capture([], [], [])
