"""
Unit tests for the changelog service (src/shared_kernel/domain/services/changelog_service.py),
covering append_changelog's timestamp formatting and non-mutation of the
existing list, and diff_changes's dict-diffing behaviour, which shows an
enum member as its value.
"""

import re

from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.changelog_service import diff_changes
from src.shared_kernel.domain.services.changelog_service import shown_value

_TIMESTAMP_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}")


class TestAppendChangelog:
    def test_new_entry_is_prefixed_with_a_utc_timestamp(self):
        result = append_changelog([], "Jane Doe", "Item updated.")
        assert _TIMESTAMP_PREFIX.match(result[0])

    def test_new_entry_contains_the_user_and_changes(self):
        result = append_changelog([], "Jane Doe", "Item updated.")
        assert "Jane Doe" in result[0]
        assert "Item updated." in result[0]

    def test_does_not_mutate_the_existing_list(self):
        existing = ["first entry"]
        result = append_changelog(existing, "Jane Doe", "second entry")
        assert existing == ["first entry"]
        assert result == ["first entry", result[1]]

    def test_appends_after_existing_entries(self):
        existing = ["first entry"]
        result = append_changelog(existing, "Jane Doe", "second entry")
        assert len(result) == 2
        assert result[0] == "first entry"


class TestDiffChanges:
    def test_no_differences_returns_no_changes_message(self):
        assert diff_changes({"a": 1}, {"a": 1}) == "No changes."

    def test_skips_changed_and_changes_keys(self):
        old = {"changed": None, "changes": []}
        new = {"changed": "2026-01-01", "changes": ["entry"]}
        assert diff_changes(old, new) == "No changes."

    def test_reports_a_changed_field(self):
        result = diff_changes({"name": "old"}, {"name": "new"})
        assert "name" in result
        assert "'old'" in result
        assert "'new'" in result

    def test_uses_the_given_heading(self):
        result = diff_changes({"name": "old"}, {"name": "new"}, heading="Custom heading:")
        assert result.startswith("Custom heading:")


class TestChangelogShowsEnumValues:
    def test_diff_changes_shows_the_value(self) -> None:
        text = diff_changes({"priority": UrgencyClass.NORMAL}, {"priority": UrgencyClass.HIGH})
        assert text == "Item updated:\n  • priority: 'normal' → 'high'"

    def test_an_enum_equal_to_its_plain_value_is_no_change(self) -> None:
        assert diff_changes({"priority": "high"}, {"priority": UrgencyClass.HIGH}) == "No changes."

    def test_shown_value_shows_the_value(self) -> None:
        assert shown_value(LotStatus.ON_HOLD) == "on_hold"
