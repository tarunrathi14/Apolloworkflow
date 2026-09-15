from assistant.conflicts import detect_conflicts
from assistant.models import ConflictKind
from assistant.proposals import propose_all

from .conftest import DAY, at, ev


def _for(events, profile, kind):
    conflicts = [c for c in detect_conflicts(events, profile, DAY) if c.kind is kind]
    return propose_all(conflicts, events, profile, DAY)


class TestProposals:
    def test_an_overlap_proposes_moving_the_event_that_is_mine(self, profile):
        events = [
            ev("client", "Client call", 11, 0, 60, attendees=("them@x.com",)),
            ev("mine", "Write proposal", 11, 30, 60),
        ]
        (p,) = _for(events, profile, ConflictKind.OVERLAP)
        assert p.action["op"] == "move_event"
        assert p.action["event_id"] == "mine"

    def test_the_proposed_slot_is_actually_free(self, profile):
        events = [
            ev("client", "Client call", 11, 0, 60, attendees=("them@x.com",)),
            ev("mine", "Write proposal", 11, 30, 60),
        ]
        (p,) = _for(events, profile, ConflictKind.OVERLAP)
        from datetime import datetime
        assert datetime.fromisoformat(p.action["to"]) >= at(12, 0)

    def test_two_immovable_events_are_handed_back_with_options(self, profile):
        events = [
            ev("a", "Client call", 11, 0, 60, attendees=("a@x.com",)),
            ev("b", "Board review", 11, 30, 60, attendees=("b@x.com",)),
        ]
        (p,) = _for(events, profile, ConflictKind.OVERLAP)
        assert p.action["op"] == "none"
        assert p.alternatives

    def test_a_deep_work_intruder_is_moved_out_of_the_block(self, profile):
        events = [ev("sync", "Sales sync", 9, 30, 30)]
        (p,) = _for(events, profile, ConflictKind.DEEP_WORK)
        from datetime import datetime
        assert datetime.fromisoformat(p.action["to"]) >= at(11, 0)

    def test_a_full_day_defers_to_tomorrow(self, profile):
        events = [
            ev("wall", "Offsite", 9, 0, 570, attendees=("team@x.com",)),  # 09:00-18:30
            ev("mine", "Write proposal", 11, 0, 120),
        ]
        (p,) = _for(events, profile, ConflictKind.OVERLAP)
        assert p.action["hint"] == "next_day"
        assert p.confidence == "low"

    def test_every_proposal_says_something_a_human_can_answer(self, profile):
        events = [ev("a", "A", 11, 0, 60), ev("b", "B", 11, 30, 60)]
        for p in propose_all(detect_conflicts(events, profile, DAY), events,
                             profile, DAY):
            assert p.summary and p.id


class TestWording:
    def test_a_single_immovable_event_is_not_called_both(self, profile):
        events = [ev("sync", "Sales sync", 9, 30, 30, attendees=("team@x.com",))]
        (p,) = _for(events, profile, ConflictKind.DEEP_WORK)
        assert "Both" not in p.summary
        assert "That one has other people" in p.summary

    def test_a_dead_proposal_offers_options_instead_of_a_button(self, profile):
        from assistant.briefing import render_proposals
        events = [ev("sync", "Sales sync", 9, 30, 30, attendees=("team@x.com",))]
        rendered = render_proposals(_for(events, profile, ConflictKind.DEEP_WORK))
        assert "/yes" not in rendered
        assert "Ask to move" in rendered

    def test_options_fit_the_kind_of_conflict(self, profile):
        travel = [ev("a", "A", 11, 0, 30, location="Office",
                     attendees=("x@y.com",)),
                  ev("b", "B", 11, 30, 30, location="Client HQ",
                     attendees=("z@y.com",))]
        (p,) = _for(travel, profile, ConflictKind.TRAVEL)
        assert any("from the road" in a for a in p.alternatives)

        deep = [ev("s", "Sync", 9, 30, 30, attendees=("t@y.com",))]
        (q,) = _for(deep, profile, ConflictKind.DEEP_WORK)
        assert any("just this once" in a for a in q.alternatives)
        assert not any("Send someone else" in a for a in q.alternatives)
