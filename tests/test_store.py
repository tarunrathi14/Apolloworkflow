from datetime import timedelta

from assistant.models import Energy, Reminder, Task
from assistant.store import Store

from .conftest import at


class TestStore:
    def setup_method(self):
        self.store = Store(":memory:")

    def teardown_method(self):
        self.store.close()

    def test_a_task_survives_a_round_trip(self, profile):
        self.store.add_task(Task(id="t1", title="Write plan", estimate_minutes=90,
                                 due=at(17, 0), energy=Energy.DEEP, priority=1))
        (got,) = self.store.open_tasks(profile)
        assert got.title == "Write plan"
        assert got.energy is Energy.DEEP
        assert got.due == at(17, 0)

    def test_completing_a_task_removes_it_from_the_backlog(self, profile):
        self.store.add_task(Task(id="t1", title="Thing"))
        assert self.store.complete_task("t1") is True
        assert self.store.open_tasks(profile) == []

    def test_completing_twice_is_reported_as_a_no_op(self, profile):
        self.store.add_task(Task(id="t1", title="Thing"))
        self.store.complete_task("t1")
        assert self.store.complete_task("t1") is False

    def test_only_due_reminders_come_back(self, profile):
        self.store.add_reminder(Reminder(id="r1", title="Now", remind_at=at(10, 0)))
        self.store.add_reminder(Reminder(id="r2", title="Later", remind_at=at(18, 0)))
        due = self.store.due_reminders(at(12, 0), profile)
        assert [r.id for r in due] == ["r1"]

    def test_a_sent_reminder_is_not_resent(self, profile):
        self.store.add_reminder(Reminder(id="r1", title="Now", remind_at=at(10, 0)))
        self.store.mark_sent("r1")
        assert self.store.due_reminders(at(12, 0), profile) == []

    def test_a_proposal_can_be_accepted_exactly_once(self):
        self.store.save_proposal("p1", "Move it?", {"op": "move_event", "id": "x"})
        assert self.store.take_proposal("p1")["op"] == "move_event"
        assert self.store.take_proposal("p1") is None

    def test_a_rejected_proposal_cannot_then_be_accepted(self):
        self.store.save_proposal("p1", "Move it?", {"op": "move_event"})
        assert self.store.reject_proposal("p1") is True
        assert self.store.take_proposal("p1") is None

    def test_an_unknown_proposal_is_not_an_error(self):
        assert self.store.take_proposal("nope") is None
