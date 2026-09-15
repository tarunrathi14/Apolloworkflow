from datetime import time

import pytest

from assistant.conflicts import (detect_conflicts, detect_deep_work,
                                 detect_overlaps, detect_travel)
from assistant.config import DeepWorkWindow
from assistant.models import ConflictKind, Severity

from .conftest import DAY, at, ev


class TestOverlaps:
    def test_clean_day_has_no_conflicts(self, profile):
        events = [ev("a", "Standup", 11, 0, 30), ev("b", "1:1", 12, 0, 30)]
        assert detect_overlaps(events) == []

    def test_touching_events_do_not_overlap(self, profile):
        events = [ev("a", "A", 11, 0, 60), ev("b", "B", 12, 0, 30)]
        assert detect_overlaps(events) == []

    def test_partial_overlap_is_found(self, profile):
        events = [ev("a", "A", 11, 0, 60), ev("b", "B", 11, 30, 60)]
        (conflict,) = detect_overlaps(events)
        assert conflict.kind is ConflictKind.OVERLAP
        assert conflict.detail["overlap_minutes"] == 30

    def test_two_immovable_events_are_critical(self, profile):
        events = [
            ev("a", "Client call", 11, 0, 60, attendees=("client@x.com",)),
            ev("b", "Board review", 11, 30, 60, attendees=("board@x.com",)),
        ]
        (conflict,) = detect_overlaps(events)
        assert conflict.severity is Severity.CRITICAL

    def test_one_movable_event_is_only_a_warning(self, profile):
        events = [
            ev("a", "Client call", 11, 0, 60, attendees=("client@x.com",)),
            ev("b", "Write proposal", 11, 30, 60),  # no attendees -> mine
        ]
        (conflict,) = detect_overlaps(events)
        assert conflict.severity is Severity.WARNING

    def test_three_way_pileup_reports_every_pair(self, profile):
        events = [ev("a", "A", 11, 0, 90), ev("b", "B", 11, 30, 60),
                  ev("c", "C", 12, 0, 30)]
        assert len(detect_overlaps(events)) == 3

    def test_fully_contained_event_is_found(self, profile):
        events = [ev("a", "Long", 10, 0, 180), ev("b", "Short", 11, 0, 30)]
        (conflict,) = detect_overlaps(events)
        assert conflict.detail["overlap_minutes"] == 30


class TestTravel:
    def test_back_to_back_across_town_is_impossible(self, profile):
        events = [ev("a", "Standup", 11, 0, 30, location="Office"),
                  ev("b", "Pitch", 11, 30, 60, location="Client HQ")]
        (conflict,) = detect_travel(events, profile)
        assert conflict.kind is ConflictKind.TRAVEL
        assert conflict.severity is Severity.CRITICAL
        assert conflict.detail["needed_minutes"] == 50  # 45 travel + 5 buffer
        assert conflict.detail["short_by"] == 50

    def test_enough_gap_is_fine(self, profile):
        events = [ev("a", "Standup", 11, 0, 30, location="Office"),
                  ev("b", "Pitch", 12, 30, 60, location="Client HQ")]
        assert detect_travel(events, profile) == []

    def test_same_location_needs_no_travel(self, profile):
        events = [ev("a", "A", 11, 0, 30, location="Office"),
                  ev("b", "B", 11, 30, 30, location="Office")]
        assert detect_travel(events, profile) == []

    def test_location_matching_ignores_case(self, profile):
        events = [ev("a", "A", 11, 0, 30, location="OFFICE"),
                  ev("b", "B", 11, 30, 30, location="office")]
        assert detect_travel(events, profile) == []

    def test_virtual_meetings_cost_no_travel(self, profile):
        events = [ev("a", "Zoom sync", 11, 0, 30, location="Zoom"),
                  ev("b", "Client HQ", 11, 5, 30, location="Client HQ")]
        assert detect_travel(events, profile) == []

    def test_unknown_route_uses_the_default(self, profile):
        events = [ev("a", "A", 11, 0, 30, location="Airport"),
                  ev("b", "B", 11, 40, 30, location="Office")]
        (conflict,) = detect_travel(events, profile)
        assert conflict.detail["needed_minutes"] == 35  # 30 default + 5 buffer
        assert conflict.detail["gap_minutes"] == 10

    def test_overlapping_events_are_not_also_travel_conflicts(self, profile):
        events = [ev("a", "A", 11, 0, 60, location="Office"),
                  ev("b", "B", 11, 30, 60, location="Client HQ")]
        assert detect_travel(events, profile) == []


class TestDeepWork:
    def test_meeting_inside_protected_block_is_flagged(self, profile):
        events = [ev("a", "Sales sync", 9, 30, 30)]
        (conflict,) = detect_deep_work(events, profile, DAY)
        assert conflict.kind is ConflictKind.DEEP_WORK
        assert conflict.severity is Severity.WARNING

    def test_meeting_after_the_block_is_fine(self, profile):
        events = [ev("a", "Sales sync", 11, 30, 30)]
        assert detect_deep_work(events, profile, DAY) == []

    def test_meeting_ending_exactly_at_block_start_is_fine(self, profile):
        events = [ev("a", "Early call", 8, 30, 30)]
        assert detect_deep_work(events, profile, DAY) == []

    def test_meeting_straddling_the_block_edge_is_flagged(self, profile):
        events = [ev("a", "Overrun", 10, 30, 60)]
        assert len(detect_deep_work(events, profile, DAY)) == 1

    def test_weekday_scoped_block_does_not_apply_on_other_days(self, profile):
        from dataclasses import replace
        friday_only = replace(
            profile,
            deep_work=(DeepWorkWindow("Friday writing", time(9, 0), time(11, 0),
                                      weekdays=(4,)),),
        )
        events = [ev("a", "Sync", 9, 30, 30)]  # DAY is a Wednesday
        assert detect_deep_work(events, friday_only, DAY) == []


class TestCombined:
    def test_conflicts_are_ordered_worst_first(self, profile):
        events = [
            ev("a", "Deep block intruder", 9, 30, 30),        # WARNING
            ev("b", "Office", 12, 0, 30, location="Office"),
            ev("c", "Client HQ", 12, 30, 30, location="Client HQ"),  # CRITICAL
        ]
        conflicts = detect_conflicts(events, profile, DAY)
        assert [c.severity for c in conflicts] == sorted(
            [c.severity for c in conflicts], reverse=True
        )

    def test_empty_day_is_clean(self, profile):
        assert detect_conflicts([], profile, DAY) == []

    def test_a_single_event_can_still_break_a_rule(self, profile):
        (conflict,) = detect_conflicts([ev("a", "Sync", 9, 30, 30)], profile, DAY)
        assert conflict.kind is ConflictKind.DEEP_WORK
