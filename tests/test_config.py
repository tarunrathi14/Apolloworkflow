from datetime import date, time

from assistant.config import load_profile


class TestExampleConfig:
    """The shipped example must actually load — it is the onboarding path."""

    def setup_method(self):
        self.profile = load_profile("config.example.yaml")

    def test_basics_are_read(self):
        assert self.profile.timezone == "Asia/Kolkata"
        assert self.profile.work_start == time(9, 0)
        assert self.profile.work_end == time(19, 0)

    def test_named_routes_are_used(self):
        assert self.profile.travel_minutes("Home", "Office") == 30
        assert self.profile.travel_minutes("Office", "Home") == 30  # symmetric

    def test_unknown_routes_fall_back_to_the_default(self):
        assert self.profile.travel_minutes("Mars", "Office") == 30

    def test_virtual_locations_cost_nothing(self):
        assert self.profile.travel_minutes("Zoom", "Client HQ") == 0
        assert self.profile.travel_minutes(None, "Office") == 0

    def test_deep_work_windows_are_parsed_with_weekdays(self):
        wednesday = date(2026, 9, 16)
        friday = date(2026, 9, 18)
        saturday = date(2026, 9, 19)
        assert len(self.profile.deep_windows_on(wednesday)) == 1
        assert len(self.profile.deep_windows_on(friday)) == 2  # maker + planning
        assert self.profile.deep_windows_on(saturday) == []

    def test_a_missing_file_yields_working_defaults(self):
        profile = load_profile("does-not-exist.yaml")
        assert profile.work_start == time(9, 0)
        assert profile.default_travel_minutes == 30
