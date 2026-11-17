"""
Unit tests for the banner settings use cases (GetBannerSettings,
UpdateBannerSettings) and UpdateBannerSettingsCommand's validators. No
database, no HTTP: FakeAdminSettingsRepository (imported from
tests/unit/admin_settings/fakes.py, same pattern as
test_admin_settings_get_use_cases.py) stands in for the real repository.
"""

from datetime import UTC
from datetime import datetime

import pytest
from pydantic import ValidationError

from src.modules.platform.application.dto.admin_settings_dto.banner import (
    UpdateBannerSettingsCommand,
)
from src.modules.platform.application.use_cases.admin_settings.get_banner_settings import (
    GetBannerSettings,
)
from src.modules.platform.application.use_cases.admin_settings.update_banner_settings import (
    UpdateBannerSettings,
)
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.announcement_severity import AnnouncementSeverity
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.admin_settings.fakes import FakeAdminSettingsRepository
from tests.unit.fakes import FakeUnitOfWork

# ── UpdateBannerSettingsCommand validators ───────────────────────────────


class TestUpdateBannerSettingsCommandValidators:
    def test_enabled_with_blank_text_raises(self):
        with pytest.raises(ValidationError, match="text is required"):
            UpdateBannerSettingsCommand(enabled=True, text="   ")

    def test_enabled_with_text_is_valid(self):
        cmd = UpdateBannerSettingsCommand(enabled=True, text="We upgrade at 18:00")
        assert cmd.text == "We upgrade at 18:00"

    def test_disabled_with_blank_text_is_valid(self):
        cmd = UpdateBannerSettingsCommand(enabled=False, text="")
        assert cmd.enabled is False

    def test_shows_until_before_shows_from_raises(self):
        with pytest.raises(ValidationError, match="shows_until must not be before shows_from"):
            UpdateBannerSettingsCommand(
                shows_from=datetime(2026, 1, 2, tzinfo=UTC),
                shows_until=datetime(2026, 1, 1, tzinfo=UTC),
            )

    def test_shows_until_equal_to_shows_from_is_valid(self):
        same = datetime(2026, 1, 1, tzinfo=UTC)
        cmd = UpdateBannerSettingsCommand(shows_from=same, shows_until=same)
        assert cmd.shows_from == cmd.shows_until

    def test_open_ended_window_is_valid(self):
        cmd = UpdateBannerSettingsCommand(shows_from=None, shows_until=None)
        assert cmd.shows_from is None
        assert cmd.shows_until is None


# ── GetBannerSettings ─────────────────────────────────────────────────────


class TestGetBannerSettings:
    def setup_method(self):
        self.repo = FakeAdminSettingsRepository()
        self.use_case = GetBannerSettings(self.repo)

    async def test_returns_current_settings(self):
        actor = make_user(permissions=[Permission.READ_SETTINGS])
        result = await self.use_case.execute(actor=actor)
        assert result.enabled is False
        assert result.text == ""
        assert result.severity == AnnouncementSeverity.INFO

    async def test_unprivileged_cannot_read(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor)


# ── UpdateBannerSettings ──────────────────────────────────────────────────


class TestUpdateBannerSettings:
    def setup_method(self):
        self.repo = FakeAdminSettingsRepository()
        self.actor = make_user(permissions=[Permission.WRITE_SETTINGS])
        self.use_case = UpdateBannerSettings(self.repo, uow=FakeUnitOfWork())

    async def test_updates_successfully(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdateBannerSettingsCommand(
                enabled=True, text="We upgrade at 18:00", severity=AnnouncementSeverity.WARNING
            ),
        )
        assert result.enabled is True
        assert result.text == "We upgrade at 18:00"
        assert result.severity == AnnouncementSeverity.WARNING

    async def test_updated_at_is_bumped_on_every_save(self):
        first = await self.use_case.execute(actor=self.actor, cmd=UpdateBannerSettingsCommand())
        second = await self.use_case.execute(
            actor=self.actor, cmd=UpdateBannerSettingsCommand(text="still nothing to see")
        )
        assert second.updated_at > first.updated_at

    async def test_unprivileged_cannot_update(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, cmd=UpdateBannerSettingsCommand())

    async def test_audit_summary_says_enabled_on_off_to_on_flip(self):
        await self.use_case.execute(
            actor=self.actor, cmd=UpdateBannerSettingsCommand(enabled=False)
        )
        self.repo.audit_log.clear()
        await self.use_case.execute(
            actor=self.actor,
            cmd=UpdateBannerSettingsCommand(enabled=True, text="Down for maintenance"),
        )
        assert self.repo.audit_log[-1].summary == f"Banner enabled by {self.actor.username}."
        assert self.repo.audit_log[-1].settings_domain == "banner"

    async def test_audit_summary_says_disabled_on_on_to_off_flip(self):
        await self.use_case.execute(
            actor=self.actor, cmd=UpdateBannerSettingsCommand(enabled=True, text="Hello")
        )
        self.repo.audit_log.clear()
        await self.use_case.execute(
            actor=self.actor, cmd=UpdateBannerSettingsCommand(enabled=False)
        )
        assert self.repo.audit_log[-1].summary == f"Banner disabled by {self.actor.username}."

    async def test_audit_summary_says_updated_when_enabled_state_is_unchanged(self):
        await self.use_case.execute(
            actor=self.actor, cmd=UpdateBannerSettingsCommand(enabled=True, text="Hello")
        )
        self.repo.audit_log.clear()
        await self.use_case.execute(
            actor=self.actor, cmd=UpdateBannerSettingsCommand(enabled=True, text="Hello again")
        )
        assert self.repo.audit_log[-1].summary == f"Banner updated by {self.actor.username}."
