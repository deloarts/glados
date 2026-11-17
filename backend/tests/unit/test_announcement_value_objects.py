"""
Coverage for the two small `str, Enum` value objects introduced by the
announcements feature (admin banner + acknowledgements): their
`default()` / `values()` classmethods and wire values are a contract the
API schemas and the frontend rely on, same reasoning as
test_value_object_enums.py.
"""

from src.modules.platform.domain.value_objects.acknowledgement_show_when import (
    AcknowledgementShowWhen,
)
from src.modules.platform.domain.value_objects.announcement_severity import AnnouncementSeverity

# ── AnnouncementSeverity ─────────────────────────────────────────────────


class TestAnnouncementSeverity:
    def test_default_is_info(self):
        assert AnnouncementSeverity.default() == AnnouncementSeverity.INFO

    def test_values_lists_every_member_value(self):
        assert AnnouncementSeverity.values() == ["info", "warning", "danger"]

    def test_members_are_plain_strings(self):
        assert AnnouncementSeverity.INFO == "info"
        assert AnnouncementSeverity.WARNING == "warning"
        assert AnnouncementSeverity.DANGER == "danger"

    def test_default_is_a_member_of_values(self):
        assert AnnouncementSeverity.default().value in AnnouncementSeverity.values()


# ── AcknowledgementShowWhen ──────────────────────────────────────────────


class TestAcknowledgementShowWhen:
    def test_default_is_immediately(self):
        assert AcknowledgementShowWhen.default() == AcknowledgementShowWhen.IMMEDIATELY

    def test_values_lists_every_member_value(self):
        assert AcknowledgementShowWhen.values() == ["immediately", "next_login"]

    def test_members_are_plain_strings(self):
        assert AcknowledgementShowWhen.IMMEDIATELY == "immediately"
        assert AcknowledgementShowWhen.NEXT_LOGIN == "next_login"

    def test_default_is_a_member_of_values(self):
        assert AcknowledgementShowWhen.default().value in AcknowledgementShowWhen.values()
