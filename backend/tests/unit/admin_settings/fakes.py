"""
In-memory fake repositories shared by the admin_settings test modules
(and, for FakeAdminSettingsRepository and FakeInspectionMethodRepository,
by a few unit test modules elsewhere that reuse them directly).
"""

from datetime import UTC
from datetime import datetime

from src.modules.catalogue.domain.entities.admin_settings.made_items import AdminMadeItemSettings
from src.modules.catalogue.domain.entities.admin_settings.orders import AdminOrderSettings
from src.modules.catalogue.domain.entities.inspection_method import InspectionMethod
from src.modules.catalogue.domain.policies.item_field_ownership import default_policy
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.entities.pdm_file_snapshot import PdmFileSnapshot
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.admin_settings.auth import AdminAuthSettings
from src.modules.platform.domain.entities.admin_settings.banner import AdminBannerSettings
from src.modules.platform.domain.entities.admin_settings.branding import AdminBrandingSettings
from src.modules.platform.domain.entities.admin_settings.features import AdminFeatureSettings
from src.modules.platform.domain.entities.admin_settings.general import AdminGeneralSettings
from src.modules.platform.domain.entities.admin_settings.host import AdminHostSettings
from src.modules.platform.domain.entities.admin_settings.mail import AdminMailSettings
from src.modules.platform.domain.entities.admin_settings.mail import AdminMailTemplate
from src.modules.platform.domain.entities.admin_settings.maintenance import AdminMaintenanceSettings
from src.modules.platform.domain.entities.admin_settings.notifications import (
    AdminNotificationSettings,
)
from src.modules.platform.domain.entities.admin_settings.retention import AdminRetentionSettings
from src.modules.platform.domain.entities.admin_settings.security import AdminSecuritySettings
from src.modules.platform.domain.entities.admin_settings.storage import AdminStorageSettings
from src.modules.platform.domain.value_objects.announcement_severity import AnnouncementSeverity
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.read.ports.outbound.repositories.admin_settings_repository import (
    AdminSettingsAuditFilterDto,
)


class FakeAdminSettingsRepository:
    def __init__(self) -> None:
        self.host = AdminHostSettings(id=1)
        self.mail = AdminMailSettings(
            id=1,
            enabled=False,
            host="",
            port=587,
            user="",
            password=None,
            from_address=None,
            use_tls=True,
            use_ssl=False,
            verify_certificate=True,
            from_display_name="",
            reply_to=None,
            send_limit_per_hour=20,
            send_lock_minutes=60,
            alert_recipients=[],
        )
        self.auth = AdminAuthSettings(
            id=1,
            ldap_enabled=False,
            ldap_host="",
            ldap_port=636,
            ldap_use_ssl=True,
            ldap_start_tls=False,
            ldap_verify_certificate=False,
            ldap_domain="",
            ldap_timeout_seconds=5,
        )
        self.storage = AdminStorageSettings(
            id=1,
            provider="local",
            enabled=True,
            endpoint_url=None,
            public_endpoint_url=None,
            bucket_name=None,
            access_key=None,
            secret_key="original-secret",
            region=None,
            use_ssl=True,
            backup_enabled=False,
            backup_path=None,
            backup_cron=None,
            backup_retention_count=7,
        )
        self.security = AdminSecuritySettings(
            id=1,
            enforce_totp=False,
            allow_rfid_login=True,
            allow_local_login=True,
            enable_api_key_auth=False,
            min_password_length=8,
            session_timeout_minutes=0,
            totp_trusted_device_days=0,
            max_login_attempts=0,
            lockout_duration_minutes=15,
            token_max_lifetime_days=3650,
        )
        self.features = AdminFeatureSettings(
            id=1,
            enable_email_notifications=True,
            enable_production_planning=True,
            allow_private_webhooks=True,
        )
        self.general = AdminGeneralSettings(
            id=1,
            company_name=None,
            company_legal_name=None,
            company_logo_key=None,
            contact_email=None,
            imprint_url=None,
            privacy_url=None,
            support_url=None,
            product_number_pattern="",
            project_number_pattern="",
            allow_headless_projects=True,
            empty_value_placeholder="-",
            office_launcher_enabled=False,
            office_sharepoint_url="",
            currency="EUR",
            default_language=Language.enGB,
            default_timezone="Europe/Vienna",
            default_date_format=DateFormat.ISO,
        )
        self.branding = AdminBrandingSettings(
            id=1,
            app_name="Glados",
            app_description=None,
            footer_text=None,
            logo_url=None,
            favicon_url=None,
            logo_key="original-logo-key",
            favicon_key="original-favicon-key",
            login_background_video_key="original-video-key",
        )
        self.notifications = AdminNotificationSettings(
            id=1,
            webhook_timeout_seconds=10,
        )
        self.maintenance = AdminMaintenanceSettings(id=1, enabled=False, message=None)
        self.retention = AdminRetentionSettings(
            id=1, log_retention_days=90, audit_retention_days=365, soft_delete_cleanup_days=0
        )
        self.orders = AdminOrderSettings(
            id=1,
            order_number_format="ORD-{year}-{seq:04d}",
            part_number_format="PN-{year}-{seq:04d}",
            part_number_auto=False,
            part_number_editable=True,
            web_creation_allowed=True,
            pdm_part_number_pattern="",
        )
        self.made_items = AdminMadeItemSettings(
            id=1,
            item_number_format="MADE-{year}-{seq:04d}",
            lot_number_format="LOT-{year}-{seq:04d}",
            part_number_auto=False,
            part_number_editable=True,
            revision_start="0",
            revision_separator=":",
            revision_skip_ambiguous_letters=False,
            revision_only_newest_editable=True,
            revision_predecessor_status_web="ask",
            revision_predecessor_status_pdm="replaced",
            revision_field_policy=default_policy(),
            web_creation_allowed=True,
            pdm_part_number_pattern="",
        )
        self.pdm = AdminPdmSettings(
            id=1,
            made_item_variable_map={"part_number": "PDM.PartNumber", "revision": "PDM.Revision"},
            bought_item_variable_map={
                "part_number": "PDM.PartNumber",
                "revision": "PDM.Revision",
            },
            enabled=False,
            base_url="",
            vault_name="",
            username="",
            password=None,
            verify_certificate=True,
            timeout_seconds=15,
            session_token=None,
            session_user_id=None,
            session_obtained_at=None,
            watched_folders=[],
            made_released_state_ids=[],
            made_obsolete_state_ids=[],
            made_replaced_state_ids=[],
            bought_released_state_ids=[],
            bought_obsolete_state_ids=[],
            bought_replaced_state_ids=[],
            poll_interval_minutes=15,
            vault_id="",
            cad_items_read_only=True,
            last_poll_at=None,
            last_poll_error=None,
            last_poll_summary=None,
            writeback_enabled=False,
            made_item_extensions=["sldprt"],
            bought_item_extensions=["sldprt", "sldasm"],
            document_categories={"pdf": "drawing", "dxf": "dxf", "step": "step", "stp": "step"},
            thumbnails_enabled=False,
            stuck_after_days=7,
            reconcile_requested_deep=None,
            required_fields={"made": [], "bought": []},
        )
        self.production = AdminProductionSettings(
            id=1,
            production_order_number_format="PO-{year}-{seq:04d}",
            default_weekly_hours={0: 480, 1: 480, 2: 480, 3: 480, 4: 480, 5: 0, 6: 0},
            default_external_lead_days=0,
            response_time_days=1,
            require_qa=False,
            require_source_item_approval=False,
        )
        self.banner = AdminBannerSettings(
            id=1,
            enabled=False,
            text="",
            severity=AnnouncementSeverity.INFO,
            shows_from=None,
            shows_until=None,
            dismissable=True,
            updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        self.audit_log: list[AdminSettingsAuditEntry] = []
        self._next_audit_id = 1
        self.mail_templates: list[AdminMailTemplate] = []
        self._next_mail_template_id = 1

    async def get_host(self) -> AdminHostSettings:
        return self.host

    async def save_host(self, settings: AdminHostSettings) -> AdminHostSettings:
        self.host = settings
        return settings

    async def get_mail(self) -> AdminMailSettings:
        return self.mail

    async def save_mail(self, settings: AdminMailSettings) -> AdminMailSettings:
        self.mail = settings
        return settings

    async def list_mail_templates(self) -> list[AdminMailTemplate]:
        return list(self.mail_templates)

    async def get_mail_template(self, kind: str, language: str) -> AdminMailTemplate | None:
        return next(
            (t for t in self.mail_templates if t.kind == kind and t.language == language), None
        )

    async def save_mail_template(self, template: AdminMailTemplate) -> AdminMailTemplate:
        existing = await self.get_mail_template(template.kind, template.language)
        if existing is not None:
            existing.subject = template.subject
            existing.body = template.body
            return existing
        template.id = self._next_mail_template_id
        self._next_mail_template_id += 1
        self.mail_templates.append(template)
        return template

    async def get_auth(self) -> AdminAuthSettings:
        return self.auth

    async def save_auth(self, settings: AdminAuthSettings) -> AdminAuthSettings:
        self.auth = settings
        return settings

    async def get_storage(self) -> AdminStorageSettings:
        return self.storage

    async def save_storage(self, settings: AdminStorageSettings) -> AdminStorageSettings:
        self.storage = settings
        return settings

    async def get_security(self) -> AdminSecuritySettings:
        return self.security

    async def save_security(self, settings: AdminSecuritySettings) -> AdminSecuritySettings:
        self.security = settings
        return settings

    async def get_features(self) -> AdminFeatureSettings:
        return self.features

    async def save_features(self, settings: AdminFeatureSettings) -> AdminFeatureSettings:
        self.features = settings
        return settings

    async def get_general(self) -> AdminGeneralSettings:
        return self.general

    async def save_general(self, settings: AdminGeneralSettings) -> AdminGeneralSettings:
        self.general = settings
        return settings

    async def get_branding(self) -> AdminBrandingSettings:
        return self.branding

    async def save_branding(self, settings: AdminBrandingSettings) -> AdminBrandingSettings:
        self.branding = settings
        return settings

    async def get_notifications(self) -> AdminNotificationSettings:
        return self.notifications

    async def save_notifications(
        self, settings: AdminNotificationSettings
    ) -> AdminNotificationSettings:
        self.notifications = settings
        return settings

    async def get_maintenance(self) -> AdminMaintenanceSettings:
        return self.maintenance

    async def save_maintenance(
        self, settings: AdminMaintenanceSettings
    ) -> AdminMaintenanceSettings:
        self.maintenance = settings
        return settings

    async def get_retention(self) -> AdminRetentionSettings:
        return self.retention

    async def save_retention(self, settings: AdminRetentionSettings) -> AdminRetentionSettings:
        self.retention = settings
        return settings

    async def get_orders(self) -> AdminOrderSettings:
        return self.orders

    async def save_orders(self, settings: AdminOrderSettings) -> AdminOrderSettings:
        self.orders = settings
        return settings

    async def get_made_items(self) -> AdminMadeItemSettings:
        return self.made_items

    async def save_made_items(self, settings: AdminMadeItemSettings) -> AdminMadeItemSettings:
        self.made_items = settings
        return settings

    async def get_pdm(self) -> AdminPdmSettings:
        return self.pdm

    async def save_pdm(self, settings: AdminPdmSettings) -> AdminPdmSettings:
        self.pdm = settings
        return settings

    async def get_production(self) -> AdminProductionSettings:
        return self.production

    async def save_production(self, settings: AdminProductionSettings) -> AdminProductionSettings:
        self.production = settings
        return settings

    async def get_banner(self) -> AdminBannerSettings:
        return self.banner

    async def save_banner(self, settings: AdminBannerSettings) -> AdminBannerSettings:
        self.banner = settings
        return settings

    async def append_audit(self, entry: AdminSettingsAuditEntry) -> AdminSettingsAuditEntry:
        entry.id = self._next_audit_id
        self._next_audit_id += 1
        self.audit_log.append(entry)
        return entry

    async def get_audit(
        self, filters: AdminSettingsAuditFilterDto
    ) -> tuple[int, list[AdminSettingsAuditEntry]]:
        results = self.audit_log
        if filters.settings_domain:
            results = [e for e in results if e.settings_domain == filters.settings_domain]
        total = len(results)
        skip = filters.skip or 0
        limit = filters.limit
        return total, results[skip : skip + limit if limit else None]


class FakePdmFileSnapshotRepository:
    """Minimal fake: GetPdmSettings only calls counts_by_state(), and
    UpdatePdmSettings calls get_all_for_vault(), upsert_many() and
    reset_skipped_to_pending()."""

    def __init__(
        self,
        counts: dict[str, int] | None = None,
        reset_count: int = 0,
        rows: list[PdmFileSnapshot] | None = None,
    ) -> None:
        self.counts = counts or {}
        self.counts_by_state_calls: list[str] = []
        self.reset_count = reset_count
        self.reset_skipped_to_pending_calls: list[str] = []
        self.rows = rows or []
        self.upserted: list[PdmFileSnapshot] = []

    async def counts_by_state(self, vault_id: str) -> dict[str, int]:
        self.counts_by_state_calls.append(vault_id)
        return self.counts

    async def get_all_for_vault(self, vault_id: str) -> list[PdmFileSnapshot]:
        return [r for r in self.rows if r.vault_id == vault_id]

    async def upsert_many(self, items: list[PdmFileSnapshot]) -> None:
        self.upserted.extend(items)

    async def reset_skipped_to_pending(self, vault_id: str) -> int:
        self.reset_skipped_to_pending_calls.append(vault_id)
        return self.reset_count


class FakeInspectionMethodRepository:
    def __init__(self, methods: list[InspectionMethod] | None = None) -> None:
        self._methods: dict[int, InspectionMethod] = {m.id: m for m in (methods or [])}

    async def get_by_id(self, id: int) -> InspectionMethod | None:
        return self._methods.get(id)

    async def get_live_names(self) -> list[tuple[int, LocalizedText]]:
        raise NotImplementedError

    async def get_multi(self, filters):
        raise NotImplementedError

    async def save(self, inspection_method: InspectionMethod) -> InspectionMethod:
        raise NotImplementedError

    async def delete(self, inspection_method: InspectionMethod) -> None:
        raise NotImplementedError
