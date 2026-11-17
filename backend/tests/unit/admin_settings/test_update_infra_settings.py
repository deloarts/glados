"""
Unit tests for the infrastructure-facing admin settings domains:
TestUpdateProductionSettings, TestUpdateStorageSettings,
TestUpdateMailSettings, TestUpdateAuthSettings and
TestUpdateBrandingSettings. No database, no HTTP. All dependencies
replaced with in-memory fakes.
"""

from datetime import UTC
from datetime import datetime

import pytest
from pydantic import ValidationError

from src.modules.catalogue.domain.entities.inspection_method import InspectionMethod
from src.modules.catalogue.domain.errors import InspectionMethodConfigurationError
from src.modules.fulfillment.application.dto.admin_settings_dto.production import (
    UpdateProductionSettingsCommand,
)
from src.modules.fulfillment.application.use_cases.admin_settings.update_production_settings import (
    UpdateProductionSettings,
)
from src.modules.platform.application.dto.admin_settings_dto.auth import UpdateAuthSettingsCommand
from src.modules.platform.application.dto.admin_settings_dto.branding import (
    UpdateBrandingSettingsCommand,
)
from src.modules.platform.application.dto.admin_settings_dto.mail import UpdateMailSettingsCommand
from src.modules.platform.application.dto.admin_settings_dto.storage import (
    UpdateStorageSettingsCommand,
)
from src.modules.platform.application.use_cases.admin_settings.update_auth_settings import (
    UpdateAuthSettings,
)
from src.modules.platform.application.use_cases.admin_settings.update_branding_settings import (
    UpdateBrandingSettings,
)
from src.modules.platform.application.use_cases.admin_settings.update_mail_settings import (
    UpdateMailSettings,
)
from src.modules.platform.application.use_cases.admin_settings.update_storage_settings import (
    UpdateStorageSettings,
)
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.exceptions import StorageProviderInvalidError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.admin_settings.fakes import FakeAdminSettingsRepository
from tests.unit.admin_settings.fakes import FakeInspectionMethodRepository
from tests.unit.fakes import FakeUnitOfWork


def make_inspection_method(id: int = 1, archived: bool = False) -> InspectionMethod:
    return InspectionMethod(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        name=f"Inspection Method {id}",
        label_color="#999999",
        label_font_color="#000000",
        description="",
        creator_id=1,
        requires_evidence=False,
        archived=archived,
    )


class FakeLotRepo:
    """The source approval backfill, which these tests never trigger."""

    async def reset_source_approval_for_setting_change(self, enabled: bool) -> int:
        return 0


class TestUpdateProductionSettings:
    def setup_method(self):
        self.repo = FakeAdminSettingsRepository()
        self.inspection_method_repo = FakeInspectionMethodRepository([make_inspection_method(1)])
        self.actor = make_user(permissions=[Permission.WRITE_SETTINGS])
        self.use_case = UpdateProductionSettings(
            self.repo, self.inspection_method_repo, FakeLotRepo(), uow=FakeUnitOfWork()
        )

    async def test_updates_successfully(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdateProductionSettingsCommand(
                production_order_number_format="PO-{year}-{seq:03d}"
            ),
        )
        assert result.production_order_number_format == "PO-{year}-{seq:03d}"

    async def test_invalid_format_raises(self):
        with pytest.raises(ValueError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=UpdateProductionSettingsCommand(production_order_number_format="NOSEQ"),
            )

    async def test_unprivileged_cannot_update(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, cmd=UpdateProductionSettingsCommand())

    async def test_provided_response_time_days_replaces_existing(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdateProductionSettingsCommand(response_time_days=3),
        )
        assert result.response_time_days == 3

    async def test_omitted_response_time_days_keeps_existing(self):
        await self.use_case.execute(
            actor=self.actor,
            cmd=UpdateProductionSettingsCommand(response_time_days=3),
        )
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdateProductionSettingsCommand(
                production_order_number_format="PO-{year}-{seq:03d}"
            ),
        )
        assert result.response_time_days == 3

    async def test_require_qa_defaults_false(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdateProductionSettingsCommand(
                production_order_number_format="PO-{year}-{seq:03d}"
            ),
        )
        assert result.require_qa is False

    async def test_provided_require_qa_replaces_existing(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdateProductionSettingsCommand(require_qa=True, default_inspection_method_id=1),
        )
        assert result.require_qa is True

    async def test_omitted_require_qa_keeps_existing(self):
        await self.use_case.execute(
            actor=self.actor,
            cmd=UpdateProductionSettingsCommand(require_qa=True, default_inspection_method_id=1),
        )
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=UpdateProductionSettingsCommand(
                production_order_number_format="PO-{year}-{seq:03d}"
            ),
        )
        assert result.require_qa is True

    async def test_require_qa_without_default_inspection_method_raises(self):
        with pytest.raises(InspectionMethodConfigurationError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=UpdateProductionSettingsCommand(require_qa=True),
            )

    async def test_require_qa_with_archived_default_inspection_method_raises(self):
        self.inspection_method_repo = FakeInspectionMethodRepository(
            [make_inspection_method(1, archived=True)]
        )
        self.use_case = UpdateProductionSettings(
            self.repo, self.inspection_method_repo, FakeLotRepo(), uow=FakeUnitOfWork()
        )
        with pytest.raises(InspectionMethodConfigurationError):
            await self.use_case.execute(
                actor=self.actor,
                cmd=UpdateProductionSettingsCommand(
                    require_qa=True, default_inspection_method_id=1
                ),
            )


class TestUpdateStorageSettings:
    def setup_method(self):
        self.repo = FakeAdminSettingsRepository()
        self.actor = make_user(permissions=[Permission.WRITE_SETTINGS])
        self.use_case = UpdateStorageSettings(self.repo, uow=FakeUnitOfWork())

    def _cmd(self, **kwargs) -> UpdateStorageSettingsCommand:
        defaults = dict(provider="s3", enabled=True)
        defaults.update(kwargs)
        return UpdateStorageSettingsCommand(**defaults)

    async def test_updates_successfully(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.provider == "s3"

    async def test_accepts_seaweedfs(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd(provider="seaweedfs"))
        assert result.provider == "seaweedfs"

    async def test_invalid_provider_raises(self):
        with pytest.raises(StorageProviderInvalidError, match="Invalid storage provider"):
            await self.use_case.execute(actor=self.actor, cmd=self._cmd(provider="dropbox"))

    async def test_omitted_secret_key_keeps_existing(self):
        await self.use_case.execute(actor=self.actor, cmd=self._cmd(secret_key=None))
        assert self.repo.storage.secret_key == "original-secret"

    async def test_provided_secret_key_replaces_existing(self):
        await self.use_case.execute(actor=self.actor, cmd=self._cmd(secret_key="new-secret"))
        assert self.repo.storage.secret_key == "new-secret"

    async def test_unprivileged_cannot_update(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, cmd=self._cmd())

    async def test_secret_key_result_never_carries_the_secret(self):
        """F1 guardrail: plaintext-at-rest is an accepted risk for these
        three columns (mail password, storage secret key, TOTP secret,
        never encrypted), the API never echoing them back is what keeps
        that acceptable. Pinned so a future change cannot regress it."""
        result = await self.use_case.execute(
            actor=self.actor, cmd=self._cmd(secret_key="s3-secret")
        )
        assert not hasattr(result, "secret_key")
        assert result.secret_key_configured is True

    def test_disk_warning_percent_defaults_to_90(self):
        """Matches InitDatabase's own seed."""
        cmd = UpdateStorageSettingsCommand(provider="local", enabled=True)
        assert cmd.disk_warning_percent == 90

    async def test_disk_warning_percent_is_saved(self):
        result = await self.use_case.execute(
            actor=self.actor, cmd=self._cmd(disk_warning_percent=75)
        )
        assert result.disk_warning_percent == 75
        assert self.repo.storage.disk_warning_percent == 75

    async def test_disk_warning_percent_zero_is_valid_and_disables_the_check(self):
        result = await self.use_case.execute(
            actor=self.actor, cmd=self._cmd(disk_warning_percent=0)
        )
        assert result.disk_warning_percent == 0

    def test_disk_warning_percent_above_100_is_rejected(self):
        with pytest.raises(ValidationError):
            self._cmd(disk_warning_percent=101)

    def test_disk_warning_percent_below_0_is_rejected(self):
        with pytest.raises(ValidationError):
            self._cmd(disk_warning_percent=-1)


class TestUpdateMailSettings:
    def setup_method(self):
        self.repo = FakeAdminSettingsRepository()
        self.repo.mail.password = "original-password"
        self.actor = make_user(permissions=[Permission.WRITE_SETTINGS])
        self.use_case = UpdateMailSettings(self.repo, uow=FakeUnitOfWork())

    def _cmd(self, **kwargs) -> UpdateMailSettingsCommand:
        defaults = dict(enabled=True, host="smtp.example.com", port=587, user="noreply")
        defaults.update(kwargs)
        return UpdateMailSettingsCommand(**defaults)

    async def test_updates_successfully(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.host == "smtp.example.com"

    async def test_omitted_password_keeps_existing(self):
        await self.use_case.execute(actor=self.actor, cmd=self._cmd(password=None))
        assert self.repo.mail.password == "original-password"

    async def test_provided_password_replaces_existing(self):
        await self.use_case.execute(actor=self.actor, cmd=self._cmd(password="new-password"))
        assert self.repo.mail.password == "new-password"

    async def test_verify_certificate_round_trips(self):
        result = await self.use_case.execute(
            actor=self.actor, cmd=self._cmd(verify_certificate=False)
        )
        assert self.repo.mail.verify_certificate is False
        assert result.verify_certificate is False

    async def test_alert_recipients_round_trip(self):
        result = await self.use_case.execute(
            actor=self.actor, cmd=self._cmd(alert_recipients=["ops@example.com"])
        )
        assert self.repo.mail.alert_recipients == ["ops@example.com"]
        assert result.alert_recipients == ["ops@example.com"]

    def test_verify_certificate_defaults_to_true_when_omitted(self):
        """DECISION A-2: omitting the field on a command lands on the secure
        value, not silently on whatever an opted-out relay needed."""
        cmd = UpdateMailSettingsCommand(
            enabled=True, host="smtp.example.com", port=587, user="noreply"
        )
        assert cmd.verify_certificate is True

    async def test_mail_result_never_carries_the_password(self):
        """F1 guardrail, see the matching test on TestUpdateStorageSettings."""
        result = await self.use_case.execute(
            actor=self.actor, cmd=self._cmd(password="new-password")
        )
        assert not hasattr(result, "password")
        assert result.password_configured is True

    async def test_unprivileged_cannot_update(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, cmd=self._cmd())

    # ── Mail identity + rate limit ──────────────────────────────────────

    async def test_from_display_name_and_reply_to_round_trip(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=self._cmd(from_display_name="Glados", reply_to="support@example.com"),
        )
        assert result.from_display_name == "Glados"
        assert result.reply_to == "support@example.com"
        assert self.repo.mail.from_display_name == "Glados"
        assert self.repo.mail.reply_to == "support@example.com"

    async def test_from_display_name_defaults_to_empty_when_omitted(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.from_display_name == ""

    async def test_reply_to_defaults_to_none_when_omitted(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.reply_to is None

    async def test_send_limit_per_hour_and_lock_minutes_round_trip(self):
        result = await self.use_case.execute(
            actor=self.actor,
            cmd=self._cmd(send_limit_per_hour=5, send_lock_minutes=15),
        )
        assert result.send_limit_per_hour == 5
        assert result.send_lock_minutes == 15
        assert self.repo.mail.send_limit_per_hour == 5
        assert self.repo.mail.send_lock_minutes == 15

    async def test_send_limit_per_hour_defaults_to_20_when_omitted(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.send_limit_per_hour == 20

    async def test_send_lock_minutes_defaults_to_60_when_omitted(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.send_lock_minutes == 60

    def test_send_limit_per_hour_rejects_zero(self):
        with pytest.raises(ValidationError):
            self._cmd(send_limit_per_hour=0)

    def test_send_lock_minutes_rejects_zero(self):
        with pytest.raises(ValidationError):
            self._cmd(send_lock_minutes=0)


class TestUpdateAuthSettings:
    def setup_method(self):
        self.repo = FakeAdminSettingsRepository()
        self.actor = make_user(permissions=[Permission.WRITE_SETTINGS])
        self.use_case = UpdateAuthSettings(self.repo, uow=FakeUnitOfWork())

    def _cmd(self, **kwargs) -> UpdateAuthSettingsCommand:
        defaults = dict(
            ldap_enabled=True,
            ldap_host="dc-01.example.com",
            ldap_port=636,
            ldap_use_ssl=True,
            ldap_start_tls=False,
            ldap_verify_certificate=False,
            ldap_domain="EXAMPLE",
            ldap_timeout_seconds=5,
        )
        defaults.update(kwargs)
        return UpdateAuthSettingsCommand(**defaults)

    async def test_updates_successfully(self):
        result = await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert result.ldap_enabled is True
        assert result.ldap_host == "dc-01.example.com"
        assert result.ldap_domain == "EXAMPLE"

    async def test_persists_every_field(self):
        await self.use_case.execute(
            actor=self.actor,
            cmd=self._cmd(
                ldap_port=389,
                ldap_use_ssl=False,
                ldap_start_tls=True,
                ldap_verify_certificate=True,
                ldap_timeout_seconds=12,
            ),
        )
        stored = self.repo.auth
        assert stored.ldap_port == 389
        assert stored.ldap_use_ssl is False
        assert stored.ldap_start_tls is True
        assert stored.ldap_verify_certificate is True
        assert stored.ldap_timeout_seconds == 12

    async def test_host_and_domain_are_trimmed(self):
        await self.use_case.execute(
            actor=self.actor, cmd=self._cmd(ldap_host="  dc.example.com  ", ldap_domain=" CORP ")
        )
        assert self.repo.auth.ldap_host == "dc.example.com"
        assert self.repo.auth.ldap_domain == "CORP"

    def test_rejects_out_of_range_port(self):
        """Enforced by the command's Field constraints, so it surfaces as a
        422 rather than an unmapped ValueError (there is no ValueError
        handler, a raise in the use case would be a 500)."""
        with pytest.raises(ValidationError):
            self._cmd(ldap_port=70000)

    def test_rejects_zero_timeout(self):
        with pytest.raises(ValidationError):
            self._cmd(ldap_timeout_seconds=0)

    async def test_appends_audit_entry(self):
        await self.use_case.execute(actor=self.actor, cmd=self._cmd())
        assert len(self.repo.audit_log) == 1
        assert self.repo.audit_log[0].settings_domain == "auth"

    def test_auth_command_defaults_to_verifying_certificates(self):
        """A bare command (a client PUTting without the field, the
        full-replace hazard) writes True, the secure value, not the insecure
        False."""
        assert UpdateAuthSettingsCommand().ldap_verify_certificate is True

    async def test_unprivileged_cannot_update(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, cmd=self._cmd())


class TestUpdateBrandingSettings:
    def setup_method(self):
        self.repo = FakeAdminSettingsRepository()
        self.actor = make_user(permissions=[Permission.WRITE_SETTINGS])
        self.use_case = UpdateBrandingSettings(self.repo, uow=FakeUnitOfWork())

    async def test_updates_name_and_description(self):
        result = await self.use_case.execute(
            actor=self.actor, cmd=UpdateBrandingSettingsCommand(app_name="Renamed App")
        )
        assert result.app_name == "Renamed App"

    async def test_does_not_touch_storage_keys(self):
        await self.use_case.execute(
            actor=self.actor, cmd=UpdateBrandingSettingsCommand(app_name="Renamed App")
        )
        assert self.repo.branding.logo_key == "original-logo-key"
        assert self.repo.branding.favicon_key == "original-favicon-key"
        assert self.repo.branding.login_background_video_key == "original-video-key"

    async def test_unprivileged_cannot_update(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(
                actor=actor, cmd=UpdateBrandingSettingsCommand(app_name="X")
            )
