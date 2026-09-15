from datetime import timedelta

from assistant.models import Energy, Interval, Task, TaskStatus
from assistant.planner import (build_day_plan, free_intervals, intersect,
                               subtract, travel_items)

from .conftest import DAY, at, ev, task


class TestIntervalMath:
    def test_subtract_a_middle_chunk_splits_the_span(self):
        free = [Interval(at(9), at(17))]
        out = subtract(free, Interval(at(12), at(13)))
        assert out == [Interval(at(9), at(12)), Interval(at(13), at(17))]

    def test_subtract_a_non_overlapping_chunk_changes_nothing(self):
        free = [Interval(at(9), at(11))]
        assert subtract(free, Interval(at(12), at(13))) == free

    def test_subtract_covering_everything_leaves_nothing(self):
        assert subtract([Interval(at(9), at(11))], Interval(at(8), at(12))) == []

    def test_subtract_trims_a_leading_edge(self):
        out = subtract([Interval(at(9), at(11))], Interval(at(8), at(10)))
        assert out == [Interval(at(10), at(11))]

    def test_intersect_keeps_only_shared_time(self):
        a = [Interval(at(9), at(12)), Interval(at(14), at(16))]
        b = [Interval(at(11), at(15))]
        assert intersect(a, b) == [Interval(at(11), at(12)), Interval(at(14), at(15))]


class TestFreeTime:
    def test_empty_day_is_entirely_free(self, profile):
        (free,) = free_intervals([], profile, DAY)
        assert free.minutes == 600  # 09:00-19:00

    def test_events_are_carved_out(self, profile):
        events = [ev("a", "Sync", 11, 0, 60, location="Zoom")]
        free = free_intervals(events, profile, DAY)
        assert sum(i.minutes for i in free) == 540

    def test_in_person_events_also_cost_their_buffer(self, profile):
        events = [ev("a", "Sync", 11, 0, 60, location="Office")]
        free = free_intervals(events, profile, DAY)
        assert sum(i.minutes for i in free) == 530  # 60 + 5 either side

    def test_travel_between_places_consumes_free_time(self, profile):
        events = [ev("a", "Standup", 11, 0, 30, location="Office"),
                  ev("b", "Pitch", 14, 0, 60, location="Client HQ")]
        free = free_intervals(events, profile, DAY)
        # 90 min of meetings, 20 min of buffers, and a 45 min drive — of which
        # 5 min runs concurrently with the buffer after the standup.
        assert sum(i.minutes for i in free) == 600 - 90 - 20 - 40

    def test_planning_midday_ignores_the_morning(self, profile):
        free = free_intervals([], profile, DAY, now=at(15, 0))
        assert sum(i.minutes for i in free) == 240  # 15:00-19:00

    def test_planning_after_hours_leaves_nothing(self, profile):
        assert free_intervals([], profile, DAY, now=at(22, 0)) == []


class TestTravelLegs:
    def test_a_leg_is_inserted_between_distant_events(self, profile):
        events = [ev("a", "Standup", 11, 0, 30, location="Office"),
                  ev("b", "Pitch", 14, 0, 60, location="Client HQ")]
        (leg,) = travel_items(events, profile)
        assert leg.kind == "travel"
        assert leg.start == at(11, 30)
        assert leg.end == at(12, 15)  # 45 minutes

    def test_no_leg_for_virtual_meetings(self, profile):
        events = [ev("a", "A", 11, 0, 30, location="Zoom"),
                  ev("b", "B", 12, 0, 30, location="Meet")]
        assert travel_items(events, profile) == []

    def test_a_leg_never_runs_past_the_next_event(self, profile):
        events = [ev("a", "A", 11, 0, 30, location="Office"),
                  ev("b", "B", 11, 40, 30, location="Client HQ")]
        (leg,) = travel_items(events, profile)
        assert leg.end == at(11, 40)


class TestDayPlan:
    def test_events_and_tasks_land_in_one_ordered_timeline(self, profile):
        events = [ev("a", "Standup", 11, 0, 30, location="Zoom")]
        tasks = [task("t1", "Write proposal", 60)]
        plan = build_day_plan(events, tasks, profile, DAY)
        starts = [i.start for i in plan.items]
        assert starts == sorted(starts)
        assert {i.kind for i in plan.items} >= {"event", "task", "deep_work"}

    def test_a_deep_task_claims_the_protected_block(self, profile):
        tasks = [task("t1", "Strategy memo", 90, energy=Energy.DEEP)]
        plan = build_day_plan([], tasks, profile, DAY)
        (placed,) = [i for i in plan.items if i.kind == "task"]
        assert placed.start == at(9, 0)  # the 09:00-11:00 deep window

    def test_shallow_work_stays_out_of_the_protected_block(self, profile):
        tasks = [task("t1", "Clear inbox", 30, energy=Energy.SHALLOW)]
        plan = build_day_plan([], tasks, profile, DAY)
        (placed,) = [i for i in plan.items if i.kind == "task"]
        assert placed.start >= at(11, 0)

    def test_shallow_work_falls_back_to_the_block_when_nothing_else_is_free(self, profile):
        events = [ev("a", "All-day offsite", 11, 0, 480, location="Zoom")]
        tasks = [task("t1", "Clear inbox", 30, energy=Energy.SHALLOW)]
        plan = build_day_plan(events, tasks, profile, DAY)
        (placed,) = [i for i in plan.items if i.kind == "task"]
        assert placed.start == at(9, 0)

    def test_the_soonest_deadline_is_scheduled_first(self, profile):
        tasks = [
            task("late", "Due Friday", 60, due=at(18, 0)),
            task("soon", "Due at noon", 60, due=at(12, 0)),
        ]
        plan = build_day_plan([], tasks, profile, DAY)
        placed = [i for i in plan.items if i.kind == "task"]
        assert placed[0].ref_id == "soon"

    def test_priority_breaks_a_deadline_tie(self, profile):
        tasks = [task("low", "Low", 60, priority=3), task("high", "High", 60, priority=1)]
        plan = build_day_plan([], tasks, profile, DAY)
        placed = sorted((i for i in plan.items if i.kind == "task"),
                        key=lambda i: i.start)
        assert placed[0].ref_id == "high"

    def test_tasks_never_double_book_each_other(self, profile):
        tasks = [task(f"t{n}", f"Task {n}", 120) for n in range(4)]
        plan = build_day_plan([], tasks, profile, DAY)
        placed = sorted((i for i in plan.items if i.kind == "task"),
                        key=lambda i: i.start)
        for a, b in zip(placed, placed[1:]):
            assert a.end <= b.start

    def test_a_task_that_does_not_fit_is_reported_not_dropped(self, profile):
        tasks = [task("big", "Ten hour job", 600)]
        plan = build_day_plan([ev("a", "Sync", 11, 0, 60)], tasks, profile, DAY)
        assert [t.id for t, _ in plan.unplaced] == ["big"]
        assert "no free block" in plan.unplaced[0][1]

    def test_tiny_tasks_are_batched_rather_than_booked(self, profile):
        tasks = [task("t1", "Reply to Sam", 5)]
        plan = build_day_plan([], tasks, profile, DAY)
        assert not [i for i in plan.items if i.kind == "task"]
        assert "batch" in plan.unplaced[0][1]

    def test_done_tasks_are_ignored(self, profile):
        tasks = [task("t1", "Already done", 60, status=TaskStatus.DONE)]
        plan = build_day_plan([], tasks, profile, DAY)
        assert not [i for i in plan.items if i.kind == "task"]
        assert plan.unplaced == []

    def test_nothing_is_scheduled_in_the_past(self, profile):
        tasks = [task("t1", "Afternoon job", 60)]
        plan = build_day_plan([], tasks, profile, DAY, now=at(15, 30))
        (placed,) = [i for i in plan.items if i.kind == "task"]
        assert placed.start >= at(15, 30)

    def test_tasks_do_not_collide_with_events(self, profile):
        events = [ev("a", "Standup", 11, 0, 60, location="Zoom")]
        tasks = [task("t1", "Deep work", 120, energy=Energy.DEEP),
                 task("t2", "Admin", 90)]
        plan = build_day_plan(events, tasks, profile, DAY)
        event_span = Interval(at(11, 0), at(12, 0))
        for item in (i for i in plan.items if i.kind == "task"):
            assert not Interval(item.start, item.end).overlaps(event_span)

    def test_the_plan_carries_its_conflicts(self, profile):
        events = [ev("a", "A", 11, 0, 60), ev("b", "B", 11, 30, 60)]
        plan = build_day_plan(events, [], profile, DAY)
        assert len(plan.conflicts) == 1

    def test_events_from_other_days_are_excluded(self, profile):
        from datetime import date
        other = date(2026, 9, 17)
        events = [ev("a", "Tomorrow", 11, 0, 60, day=other)]
        plan = build_day_plan(events, [], profile, DAY)
        assert not [i for i in plan.items if i.kind == "event"]

    def test_free_minutes_are_reported(self, profile):
        plan = build_day_plan([ev("a", "Sync", 11, 0, 60, location="Zoom")],
                              [], profile, DAY)
        assert plan.free_minutes == 540


class TestTravelNotes:
    def test_a_leg_that_fits_reports_its_duration(self, profile):
        events = [ev("a", "A", 11, 0, 30, location="Office"),
                  ev("b", "B", 14, 0, 30, location="Client HQ")]
        (leg,) = travel_items(events, profile)
        assert leg.note == "~45 min"

    def test_a_leg_that_does_not_fit_says_so(self, profile):
        events = [ev("a", "A", 11, 0, 30, location="Office"),
                  ev("b", "B", 11, 45, 30, location="Client HQ")]
        (leg,) = travel_items(events, profile)
        assert leg.note == "needs ~45 min, only 15 available"
