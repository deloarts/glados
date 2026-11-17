"""
Unit tests for the small, CRUD-shaped admin settings domains:
TestUpdateGeneralSettings, TestUpdateSecuritySettings,
TestUpdateFeatureSettings, TestUpdateMaintenanceSettings,
TestUpdateNotificationSettings and TestUpdateRetentionSettings. No
database, no HTTP. All dependencies replaced with in-memory fakes.
"""

import pytest
from pydantic import ValidationError

from src.modules.platform.application.dto.admin_settings_dto.features import (
    UpdateFeatureSettingsCommand,
)
from src.modules.platform.application.dto.admin_settings_dto.general import (
    UpdateGeneralSettingsCommand,
)
from src.modules.platform.application.dto.admin_settings_dto.maintenance import (
    UpdateMaintenanceSettingsCommand,
)
from src.modules.platform.application.dto.admin_settings_dto.notifications import (
    UpdateNotificationSettingsCommand,
)
from src.modules.platform.application.dto.admin_settings_dto.retention import (
    UpdateRetentionSettingsCommand,
)
from src.modules.platform.application.dto.admin_settings_dto.security import (
    UpdateSecuritySettingsCommand,
)
from src.modules.platform.application.use_cases.admin_settings.update_feature_settings import (
    UpdateFeatureSettings,
)
from src.modules.platform.application.use_cases.admin_settings.update_general_settings import (
    UpdateGeneralSettings,
)
from src.modules.platform.application.use_cases.admin_settings.update_maintenance_settings import (
    UpdateMaintenanceSettings,
)
from src.modules.platform.application.use_cases.admin_settings.update_notification_settings import (
    UpdateNotificationSettings,
)
from src.modules.platform.application.use_cases.admin_settings.update_retention_settings import (
    UpdateRetentionSettings,
)
from src.modules.platform.application.use_cases.admin_settings.update_security_settings import (
    UpdateSecuritySettings,
)
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.admin_settings.fakes import FakeAdminSettingsRepository
from tests.unit.fakes import FakeUnitOfWork


class TestUpdateGeneralSettings:
    def setup_method(self):
        self.repo = FakeAdminSettingsRepository()
        self.actor = make_user(permissions=[Permission.WRITE_SETTINGS])
        self.use_case = UpdateGeneralSettings(self.repo, uow=FakeUnitOfWork())

    async def test_updates_contact_details(self):
        """Contact details belong to the general settings, not the host
        domain, since they describe the organisation, not the machine."""
        result = await self.use_case.execute(
            actor=self.actor, cmd=UpdateGeneralSettingsCommand(contact_email="admin@example.com")
        )
        assert result.contact_email == "admin@example.com"

    async def test_omitted_fields_keep_their_stored_value(self):
        """Partial by design: the Numbering and General tabs each write a
        subset of this domain, so neither may clobber the other's fields."""
        self.repo.general.contact_email = "keep@example.com"

        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdateGeneralSettingsCommand(project_number_pattern=r"P-\d{3}"),
        )

        assert result.project_number_pattern == r"P-\d{3}"
        assert result.contact_email == "keep@example.com"

    async def test_rejects_an_uncompilable_pattern(self):
        with pytest.raises(ValueError, match="not a valid regular expression"):
            await self.use_case.execute(
                actor=self.actor, cmd=UpdateGeneralSettingsCommand(project_number_pattern="[")
            )

    async def test_appends_audit_entry(self):
        await self.use_case.execute(actor=self.actor, cmd=UpdateGeneralSettingsCommand())
        assert len(self.repo.audit_log) == 1
        assert self.repo.audit_log[0].settings_domain == "general"

    async def test_unprivileged_cannot_update(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, cmd=UpdateGeneralSettingsCommand())

    async def test_updates_office_launcher_enabled(self):
        result = await self.use_case.execute(
            actor=self.actor, cmd=UpdateGeneralSettingsCommand(office_launcher_enabled=True)
        )
        assert result.office_launcher_enabled is True

    def test_office_sharepoint_url_rejects_non_http_scheme(self):
        """The command's own field_validator must reject this at construction
        time, not the use case: exception_handlers.py has no handler for a
        bare ValueError raised from inside a use case, so that path would
        fall through to an unhandled 500 instead of a clean validation error.
        """
        with pytest.raises(ValidationError, match="http"):
            UpdateGeneralSettingsCommand(office_sharepoint_url="javascript:alert(1)")

    async def test_office_sharepoint_url_accepts_https(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdateGeneralSettingsCommand(
                office_sharepoint_url="https://contoso.sharepoint.com/sites/intranet"
            ),
        )
        assert result.office_sharepoint_url == "https://contoso.sharepoint.com/sites/intranet"

    async def test_office_sharepoint_url_empty_string_clears_a_previously_set_value(self):
        """ "" is a real, distinct value from None (which means "leave
        as-is"); this is the whole reason the column is non-nullable
        rather than str | None, see AdminGeneralSettings.office_sharepoint_url.
        """
        self.repo.general.office_sharepoint_url = "https://contoso.sharepoint.com/sites/intranet"

        result = await self.use_case.execute(
            actor=self.actor, cmd=UpdateGeneralSettingsCommand(office_sharepoint_url="")
        )

        assert result.office_sharepoint_url == ""

    async def test_office_sharepoint_url_omitted_keeps_stored_value(self):
        self.repo.general.office_sharepoint_url = "https://contoso.sharepoint.com/sites/intranet"

        result = await self.use_case.execute(
            actor=self.actor, cmd=UpdateGeneralSettingsCommand(office_launcher_enabled=True)
        )

        assert result.office_sharepoint_url == "https://contoso.sharepoint.com/sites/intranet"

    async def test_updating_only_default_timezone_leaves_language_and_date_format_untouched(self):
        """Partial update, same contract as every other field in this
        domain: the Locales section saves all three together today, but
        nothing stops a future caller sending just one."""
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdateGeneralSettingsCommand(default_timezone="America/New_York"),
        )

        assert result.default_timezone == "America/New_York"
        assert result.default_language == "enGB"
        assert result.default_date_format == "iso"

    async def test_all_three_locale_defaults_are_persisted(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdateGeneralSettingsCommand(
                default_language="deAT",
                default_timezone="Europe/London",
                default_date_format="dmy_dot",
            ),
        )

        assert result.default_language == "deAT"
        assert result.default_timezone == "Europe/London"
        assert result.default_date_format == "dmy_dot"
        # The stored entity holds plain str, not the enum's repr, see
        # update_general_settings.py's `.value` comment.
        assert self.repo.general.default_language == "deAT"
        assert self.repo.general.default_date_format == "dmy_dot"

    def test_default_timezone_rejects_an_invalid_iana_name(self):
        """Rejected at command construction (a field_validator), not the use
        case: same 422-vs-500 reasoning as office_sharepoint_url's scheme
        check above."""
        with pytest.raises(ValidationError, match="not a valid IANA timezone"):
            UpdateGeneralSettingsCommand(default_timezone="Mars/Olympus")

    def test_default_language_rejects_an_unknown_code(self):
        with pytest.raises(ValidationError):
            UpdateGeneralSettingsCommand(default_language="frFR")

    def test_default_date_format_rejects_an_unknown_preset(self):
        with pytest.raises(ValidationError):
            UpdateGeneralSettingsCommand(default_date_format="not-a-format")

    # ── Currency ──────────────────────────────────────────────────────

    async def test_currency_round_trips(self):
        result = await self.use_case.execute(
            actor=self.actor, cmd=UpdateGeneralSettingsCommand(currency="USD")
        )
        assert result.currency == "USD"
        assert self.repo.general.currency == "USD"

    async def test_currency_omitted_keeps_stored_value(self):
        self.repo.general.currency = "GBP"

        result = await self.use_case.execute(
            actor=self.actor, cmd=UpdateGeneralSettingsCommand(contact_email="a@example.com")
        )

        assert result.currency == "GBP"

    def test_currency_rejects_lowercase(self):
        """Rejected at command construction (a field_validator), not the use
        case, same 422-vs-500 reasoning as office_sharepoint_url's scheme
        check above. No case normalisation: "eur" is rejected outright."""
        with pytest.raises(ValidationError):
            UpdateGeneralSettingsCommand(currency="eur")

    def test_currency_rejects_a_four_letter_code(self):
        with pytest.raises(ValidationError):
            UpdateGeneralSettingsCommand(currency="EURO")


class TestUpdateSecuritySettings:
    def setup_method(self):
        self.repo = FakeAdminSettingsRepository()
        self.actor = make_user(permissions=[Permission.WRITE_SETTINGS])
        self.use_case = UpdateSecuritySettings(self.repo, uow=FakeUnitOfWork())

    async def test_updates_successfully(self):
        result = await self.use_case.execute(
            actor=self.actor, cmd=UpdateSecuritySettingsCommand(min_password_length=12)
        )
        assert result.min_password_length == 12

    async def test_zero_min_password_length_raises(self):
        with pytest.raises(ValueError, match="at least 1"):
            await self.use_case.execute(
                actor=self.actor, cmd=UpdateSecuritySettingsCommand(min_password_length=0)
            )

    async def test_api_key_auth_lives_here_not_in_features(self):
        """It is an authentication policy, so it moved out of the feature flags."""
        result = await self.use_case.execute(
            actor=self.actor, cmd=UpdateSecuritySettingsCommand(enable_api_key_auth=True)
        )
        assert result.enable_api_key_auth is True
        assert self.repo.security.enable_api_key_auth is True

    async def test_security_command_defaults_to_a_login_limit(self):
        """A bare command lands on the shipped default, 5 attempts / 15
        minutes, matching the always-on TOTP throttle."""
        result = await self.use_case.execute(actor=self.actor, cmd=UpdateSecuritySettingsCommand())
        assert result.max_login_attempts == 5
        assert result.lockout_duration_minutes == 15

    async def test_unprivileged_cannot_update(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, cmd=UpdateSecuritySettingsCommand())

    async def test_token_max_lifetime_days_defaults_to_365_when_omitted(self):
        result = await self.use_case.execute(actor=self.actor, cmd=UpdateSecuritySettingsCommand())
        assert result.token_max_lifetime_days == 365

    async def test_token_max_lifetime_days_round_trips(self):
        result = await self.use_case.execute(
            actor=self.actor, cmd=UpdateSecuritySettingsCommand(token_max_lifetime_days=365)
        )
        assert result.token_max_lifetime_days == 365
        assert self.repo.security.token_max_lifetime_days == 365

    def test_token_max_lifetime_days_rejects_a_negative_value(self):
        with pytest.raises(ValidationError):
            UpdateSecuritySettingsCommand(token_max_lifetime_days=-1)

    async def test_token_max_lifetime_days_accepts_zero_which_lifts_the_cap(self):
        result = await self.use_case.execute(
            actor=self.actor, cmd=UpdateSecuritySettingsCommand(token_max_lifetime_days=0)
        )
        assert result.token_max_lifetime_days == 0

    def test_token_max_lifetime_days_rejects_above_36500(self):
        with pytest.raises(ValidationError):
            UpdateSecuritySettingsCommand(token_max_lifetime_days=36501)

    async def test_token_max_lifetime_days_accepts_the_36500_boundary(self):
        result = await self.use_case.execute(
            actor=self.actor, cmd=UpdateSecuritySettingsCommand(token_max_lifetime_days=36500)
        )
        assert result.token_max_lifetime_days == 36500


class TestUpdateFeatureSettings:
    def setup_method(self):
        self.repo = FakeAdminSettingsRepository()
        self.actor = make_user(permissions=[Permission.WRITE_SETTINGS])
        self.use_case = UpdateFeatureSettings(self.repo, uow=FakeUnitOfWork())

    async def test_updates_successfully(self):
        result = await self.use_case.execute(
            actor=self.actor, cmd=UpdateFeatureSettingsCommand(enable_production_planning=False)
        )
        assert result.enable_production_planning is False

    async def test_omitted_flags_keep_their_stored_value(self):
        """The command is partial: the admin tab only sends the flags it shows,
        so anything omitted must survive rather than snap back to a default."""
        self.repo.features.allow_private_webhooks = False

        result = await self.use_case.execute(
            actor=self.actor, cmd=UpdateFeatureSettingsCommand(enable_production_planning=False)
        )

        assert result.enable_production_planning is False
        assert result.allow_private_webhooks is False

    async def test_unprivileged_cannot_update(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, cmd=UpdateFeatureSettingsCommand())


class TestUpdateMaintenanceSettings:
    def setup_method(self):
        self.repo = FakeAdminSettingsRepository()
        self.actor = make_user(permissions=[Permission.WRITE_SETTINGS])
        self.use_case = UpdateMaintenanceSettings(self.repo, uow=FakeUnitOfWork())

    async def test_updates_successfully(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdateMaintenanceSettingsCommand(enabled=True, message="Down for maintenance"),
        )
        assert result.enabled is True
        assert result.message == "Down for maintenance"

    async def test_unprivileged_cannot_update(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, cmd=UpdateMaintenanceSettingsCommand())


class TestUpdateNotificationSettings:
    def setup_method(self):
        self.repo = FakeAdminSettingsRepository()
        self.actor = make_user(permissions=[Permission.WRITE_SETTINGS])
        self.use_case = UpdateNotificationSettings(self.repo, uow=FakeUnitOfWork())

    async def test_updates_successfully(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdateNotificationSettingsCommand(webhook_timeout_seconds=30),
        )
        assert result.webhook_timeout_seconds == 30

    async def test_unprivileged_cannot_update(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, cmd=UpdateNotificationSettingsCommand())

    async def test_webhook_timeout_seconds_defaults_to_10_when_omitted(self):
        result = await self.use_case.execute(
            actor=self.actor, cmd=UpdateNotificationSettingsCommand()
        )
        assert result.webhook_timeout_seconds == 10

    async def test_webhook_timeout_seconds_round_trips(self):
        result = await self.use_case.execute(
            actor=self.actor, cmd=UpdateNotificationSettingsCommand(webhook_timeout_seconds=30)
        )
        assert result.webhook_timeout_seconds == 30
        assert self.repo.notifications.webhook_timeout_seconds == 30

    def test_webhook_timeout_seconds_rejects_zero(self):
        with pytest.raises(ValidationError):
            UpdateNotificationSettingsCommand(webhook_timeout_seconds=0)

    def test_webhook_timeout_seconds_rejects_above_120(self):
        with pytest.raises(ValidationError):
            UpdateNotificationSettingsCommand(webhook_timeout_seconds=121)

    async def test_webhook_timeout_seconds_accepts_the_120_boundary(self):
        result = await self.use_case.execute(
            actor=self.actor, cmd=UpdateNotificationSettingsCommand(webhook_timeout_seconds=120)
        )
        assert result.webhook_timeout_seconds == 120


class TestUpdateRetentionSettings:
    def setup_method(self):
        self.repo = FakeAdminSettingsRepository()
        self.actor = make_user(permissions=[Permission.WRITE_SETTINGS])
        self.use_case = UpdateRetentionSettings(self.repo, uow=FakeUnitOfWork())

    async def test_updates_successfully(self):
        result = await self.use_case.execute(
            actor=self.actor, cmd=UpdateRetentionSettingsCommand(log_retention_days=30)
        )
        assert result.log_retention_days == 30

    async def test_negative_days_raises(self):
        with pytest.raises(ValueError, match=">= 0"):
            await self.use_case.execute(
                actor=self.actor, cmd=UpdateRetentionSettingsCommand(log_retention_days=-1)
            )

    async def test_unprivileged_cannot_update(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, cmd=UpdateRetentionSettingsCommand())
