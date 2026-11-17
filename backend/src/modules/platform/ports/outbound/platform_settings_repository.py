"""
Abstract interface for admin settings persistence. All settings tables are
singletons (always one row with id=1), and their get_* methods always return
an entity, they never return None, because calling code can rely on defaults
being seeded at startup. The one exception is admin_mail_template: it is not
a singleton, holding one row per (kind, language) pair, so get_mail_template
legitimately returns None for a pair that has not been seeded/saved yet.

This port holds Platform's own sections and the audit log. Each module
extends it with its own sections in its settings port, so a module's code
sees its own settings and those of the modules it depends on.
"""

from dataclasses import dataclass
from datetime import date
from typing import Protocol
from typing import runtime_checkable

from src.modules.platform.domain.entities.admin_settings.agents import AdminAgentSettings
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
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.mail_template_kind import MailTemplateKind


@dataclass
class AdminSettingsAuditFilterDto:
    skip: int | None = None
    limit: int | None = None
    settings_domain: str | None = None
    changed_by: str | None = None  # substring of changed_by_username
    changed_by_id: int | None = None
    summary: str | None = None  # substring of summary
    changed_from: date | None = None  # inclusive calendar day
    changed_to: date | None = None  # inclusive calendar day


@runtime_checkable
class IPlatformSettingsRepository(Protocol):
    # ── Host ──────────────────────────────────────────────────────────

    async def get_host(self) -> AdminHostSettings: ...

    async def save_host(self, settings: AdminHostSettings) -> AdminHostSettings: ...

    # ── Mail ──────────────────────────────────────────────────────────

    async def get_mail(self) -> AdminMailSettings: ...

    async def save_mail(self, settings: AdminMailSettings) -> AdminMailSettings: ...

    # ── Mail templates ────────────────────────────────────────────────

    async def list_mail_templates(self) -> list[AdminMailTemplate]: ...

    async def get_mail_template(
        self, kind: MailTemplateKind, language: Language
    ) -> AdminMailTemplate | None: ...

    async def save_mail_template(self, template: AdminMailTemplate) -> AdminMailTemplate: ...

    # ── Auth ──────────────────────────────────────────────────────────

    async def get_auth(self) -> AdminAuthSettings: ...

    async def save_auth(self, settings: AdminAuthSettings) -> AdminAuthSettings: ...

    # ── Storage ───────────────────────────────────────────────────────

    async def get_storage(self) -> AdminStorageSettings: ...

    async def save_storage(self, settings: AdminStorageSettings) -> AdminStorageSettings: ...

    # ── Security ──────────────────────────────────────────────────────

    async def get_security(self) -> AdminSecuritySettings: ...

    async def save_security(self, settings: AdminSecuritySettings) -> AdminSecuritySettings: ...

    # ── Features ──────────────────────────────────────────────────────

    async def get_features(self) -> AdminFeatureSettings: ...

    async def save_features(self, settings: AdminFeatureSettings) -> AdminFeatureSettings: ...

    # ── General ───────────────────────────────────────────────────────

    async def get_general(self) -> AdminGeneralSettings: ...

    async def save_general(self, settings: AdminGeneralSettings) -> AdminGeneralSettings: ...

    # ── Branding ──────────────────────────────────────────────────────

    async def get_branding(self) -> AdminBrandingSettings: ...

    async def save_branding(self, settings: AdminBrandingSettings) -> AdminBrandingSettings: ...

    # ── Notifications ─────────────────────────────────────────────────

    async def get_notifications(self) -> AdminNotificationSettings: ...

    async def save_notifications(
        self, settings: AdminNotificationSettings
    ) -> AdminNotificationSettings: ...

    # ── Banner ────────────────────────────────────────────────────────

    async def get_banner(self) -> AdminBannerSettings: ...

    async def save_banner(self, settings: AdminBannerSettings) -> AdminBannerSettings: ...

    # ── Agents ────────────────────────────────────────────────────────

    async def get_agents(self) -> AdminAgentSettings: ...

    async def save_agents(self, settings: AdminAgentSettings) -> AdminAgentSettings: ...

    # ── Maintenance ───────────────────────────────────────────────────

    async def get_maintenance(self) -> AdminMaintenanceSettings: ...

    async def save_maintenance(
        self, settings: AdminMaintenanceSettings
    ) -> AdminMaintenanceSettings: ...

    # ── Retention ─────────────────────────────────────────────────────

    async def get_retention(self) -> AdminRetentionSettings: ...

    async def save_retention(self, settings: AdminRetentionSettings) -> AdminRetentionSettings: ...

    # ── Audit log ─────────────────────────────────────────────────────

    async def append_audit(self, entry: AdminSettingsAuditEntry) -> AdminSettingsAuditEntry: ...

    async def get_audit(
        self, filters: AdminSettingsAuditFilterDto
    ) -> tuple[int, list[AdminSettingsAuditEntry]]: ...
