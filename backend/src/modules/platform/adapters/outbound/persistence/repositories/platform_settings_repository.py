"""SQLAlchemy implementation of Platform's settings sections and the settings
audit log. Every settings table is a singleton row (id=1); the column mapping
lives per group under _admin_settings_mappers. Each module's settings store
extends this one with its own sections, and admin_settings_repository.py
assembles them into the store the composition root wires.

get_maintenance() is read on every authenticated request, so it is cached
per process for MAINTENANCE_CACHE_TTL_S. Saving invalidates this worker's
cache; other workers see the change once their copy expires, which is
acceptable for a rare, operator-initiated toggle.
"""

import threading
import time
from datetime import UTC
from datetime import tzinfo
from typing import Any

from sqlalchemy import event
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from src.modules.platform.adapters.outbound.persistence.date_range import day_after_utc
from src.modules.platform.adapters.outbound.persistence.date_range import day_start_utc
from src.modules.platform.adapters.outbound.persistence.like_escape import contains_ci
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.agents import (
    AdminAgentSettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.audit import (
    AdminSettingsAuditOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.auth import (
    AdminAuthSettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.banner import (
    AdminBannerSettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.branding import (
    AdminBrandingSettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.features import (
    AdminFeatureSettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.general import (
    AdminGeneralSettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.host import (
    AdminHostSettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.mail import (
    AdminMailSettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.mail import (
    AdminMailTemplateOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.maintenance import (
    AdminMaintenanceSettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.notifications import (
    AdminNotificationSettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.retention import (
    AdminRetentionSettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.security import (
    AdminSecuritySettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.storage import (
    AdminStorageSettingsOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.repositories._admin_settings_mappers import (
    agents,
)
from src.modules.platform.adapters.outbound.persistence.repositories._admin_settings_mappers import (
    audit,
)
from src.modules.platform.adapters.outbound.persistence.repositories._admin_settings_mappers import (
    auth,
)
from src.modules.platform.adapters.outbound.persistence.repositories._admin_settings_mappers import (
    banner,
)
from src.modules.platform.adapters.outbound.persistence.repositories._admin_settings_mappers import (
    branding,
)
from src.modules.platform.adapters.outbound.persistence.repositories._admin_settings_mappers import (
    features,
)
from src.modules.platform.adapters.outbound.persistence.repositories._admin_settings_mappers import (
    general,
)
from src.modules.platform.adapters.outbound.persistence.repositories._admin_settings_mappers import (
    host,
)
from src.modules.platform.adapters.outbound.persistence.repositories._admin_settings_mappers import (
    mail,
)
from src.modules.platform.adapters.outbound.persistence.repositories._admin_settings_mappers import (
    maintenance,
)
from src.modules.platform.adapters.outbound.persistence.repositories._admin_settings_mappers import (
    notifications,
)
from src.modules.platform.adapters.outbound.persistence.repositories._admin_settings_mappers import (
    retention,
)
from src.modules.platform.adapters.outbound.persistence.repositories._admin_settings_mappers import (
    security,
)
from src.modules.platform.adapters.outbound.persistence.repositories._admin_settings_mappers import (
    storage,
)
from src.modules.platform.adapters.outbound.persistence.statements import fetch_page
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
from src.modules.platform.domain.services.datetime_filters import resolve_actor_timezone
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.mail_template_kind import MailTemplateKind
from src.modules.platform.ports.outbound.platform_settings_repository import (
    AdminSettingsAuditFilterDto,
)
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)

SINGLETON_ID = 1

MAINTENANCE_CACHE_TTL_S = 5.0

_maintenance_cache_lock = threading.Lock()
_maintenance_cache_value: AdminMaintenanceSettings | None = None
_maintenance_cache_expires_at: float = 0.0


def clear_maintenance_cache() -> None:
    """Drops the cached maintenance row, so the next read queries again."""
    global _maintenance_cache_value, _maintenance_cache_expires_at
    with _maintenance_cache_lock:
        _maintenance_cache_value = None
        _maintenance_cache_expires_at = 0.0


def _clear_cache_on_commit(session: Session) -> None:
    clear_maintenance_cache()


# ── Helper: generic singleton upsert ─────────────────────────────────


async def upsert_singleton(db: AsyncSession, model_class: type[Any], data: dict[str, Any]) -> Any:
    """Upserts the singleton row and flushes without committing."""
    orm = await db.get(model_class, SINGLETON_ID)
    if orm is None:
        orm = model_class(id=SINGLETON_ID, **data)
        db.add(orm)
    else:
        for key, value in data.items():
            setattr(orm, key, value)
    await db.flush()
    await db.refresh(orm)
    return orm


async def upsert_by_keys(
    db: AsyncSession, model_class: type[Any], keys: dict[str, Any], data: dict[str, Any]
) -> Any:
    """Upserts a row identified by `keys`, such as a mail template's (kind,
    language). The keys are only used for lookup and insert, never written
    on update.
    """
    orm = await db.scalar(select(model_class).filter_by(**keys).limit(1))
    if orm is None:
        orm = model_class(**keys, **data)
        db.add(orm)
    else:
        for key, value in data.items():
            setattr(orm, key, value)
    await db.flush()
    await db.refresh(orm)
    return orm


# ── Repository ────────────────────────────────────────────────────────


class SqlAlchemyPlatformSettingsRepository(IPlatformSettingsRepository):
    def __init__(self, db: AsyncSession) -> None:
        """Writes only flush; the caller's unit of work commits them."""
        self._db = db

    # ── Host ──────────────────────────────────────────────────────────

    async def get_host(self) -> AdminHostSettings:
        orm = await self._db.get(AdminHostSettingsOrmModel, SINGLETON_ID)
        if not orm:
            raise RuntimeError("Admin host settings not seeded, run InitDatabase first.")
        return host.to_entity(orm)

    async def save_host(self, s: AdminHostSettings) -> AdminHostSettings:
        # No business columns to write yet; the upsert exists so the singleton
        # row is created on a fresh install (see InitDatabase).
        orm = await upsert_singleton(self._db, AdminHostSettingsOrmModel, {})
        return host.to_entity(orm)

    # ── Mail ──────────────────────────────────────────────────────────

    async def get_mail(self) -> AdminMailSettings:
        orm = await self._db.get(AdminMailSettingsOrmModel, SINGLETON_ID)
        if not orm:
            raise RuntimeError("Admin mail settings not seeded, run InitDatabase first.")
        return mail.to_entity(orm)

    async def save_mail(self, s: AdminMailSettings) -> AdminMailSettings:
        orm = await upsert_singleton(self._db, AdminMailSettingsOrmModel, mail.to_dict(s))
        return mail.to_entity(orm)

    # ── Mail templates ───────────────────────────────────────────────

    async def list_mail_templates(self) -> list[AdminMailTemplate]:
        rows = (await self._db.scalars(select(AdminMailTemplateOrmModel))).all()
        return [mail.template_to_entity(o) for o in rows]

    async def get_mail_template(
        self, kind: MailTemplateKind, language: Language
    ) -> AdminMailTemplate | None:
        orm = await self._db.scalar(
            select(AdminMailTemplateOrmModel)
            .filter_by(kind=kind.value, language=language.value)
            .limit(1)
        )
        return mail.template_to_entity(orm) if orm else None

    async def save_mail_template(self, t: AdminMailTemplate) -> AdminMailTemplate:
        orm = await upsert_by_keys(
            self._db,
            AdminMailTemplateOrmModel,
            {"kind": t.kind.value, "language": t.language.value},
            {"subject": t.subject, "body": t.body},
        )
        return mail.template_to_entity(orm)

    # ── Auth ──────────────────────────────────────────────────────────

    async def get_auth(self) -> AdminAuthSettings:
        orm = await self._db.get(AdminAuthSettingsOrmModel, SINGLETON_ID)
        if not orm:
            raise RuntimeError("Admin auth settings not seeded, run InitDatabase first.")
        return auth.to_entity(orm)

    async def save_auth(self, s: AdminAuthSettings) -> AdminAuthSettings:
        orm = await upsert_singleton(self._db, AdminAuthSettingsOrmModel, auth.to_dict(s))
        return auth.to_entity(orm)

    # ── Storage ───────────────────────────────────────────────────────

    async def get_storage(self) -> AdminStorageSettings:
        orm = await self._db.get(AdminStorageSettingsOrmModel, SINGLETON_ID)
        if not orm:
            raise RuntimeError("Admin storage settings not seeded, run InitDatabase first.")
        return storage.to_entity(orm)

    async def save_storage(self, s: AdminStorageSettings) -> AdminStorageSettings:
        orm = await upsert_singleton(self._db, AdminStorageSettingsOrmModel, storage.to_dict(s))
        return storage.to_entity(orm)

    # ── Security ──────────────────────────────────────────────────────

    async def get_security(self) -> AdminSecuritySettings:
        orm = await self._db.get(AdminSecuritySettingsOrmModel, SINGLETON_ID)
        if not orm:
            raise RuntimeError("Admin security settings not seeded, run InitDatabase first.")
        return security.to_entity(orm)

    async def save_security(self, s: AdminSecuritySettings) -> AdminSecuritySettings:
        orm = await upsert_singleton(self._db, AdminSecuritySettingsOrmModel, security.to_dict(s))
        return security.to_entity(orm)

    # ── Features ──────────────────────────────────────────────────────

    async def get_features(self) -> AdminFeatureSettings:
        orm = await self._db.get(AdminFeatureSettingsOrmModel, SINGLETON_ID)
        if not orm:
            raise RuntimeError("Admin feature settings not seeded, run InitDatabase first.")
        return features.to_entity(orm)

    async def save_features(self, s: AdminFeatureSettings) -> AdminFeatureSettings:
        orm = await upsert_singleton(self._db, AdminFeatureSettingsOrmModel, features.to_dict(s))
        return features.to_entity(orm)

    # ── General ───────────────────────────────────────────────────────

    async def get_general(self) -> AdminGeneralSettings:
        orm = await self._db.get(AdminGeneralSettingsOrmModel, SINGLETON_ID)
        if not orm:
            raise RuntimeError("Admin general settings not seeded, run InitDatabase first.")
        return general.to_entity(orm)

    async def save_general(self, s: AdminGeneralSettings) -> AdminGeneralSettings:
        orm = await upsert_singleton(self._db, AdminGeneralSettingsOrmModel, general.to_dict(s))
        return general.to_entity(orm)

    # ── Branding ──────────────────────────────────────────────────────

    async def get_branding(self) -> AdminBrandingSettings:
        orm = await self._db.get(AdminBrandingSettingsOrmModel, SINGLETON_ID)
        if not orm:
            raise RuntimeError("Admin branding settings not seeded, run InitDatabase first.")
        return branding.to_entity(orm)

    async def save_branding(self, s: AdminBrandingSettings) -> AdminBrandingSettings:
        orm = await upsert_singleton(self._db, AdminBrandingSettingsOrmModel, branding.to_dict(s))
        return branding.to_entity(orm)

    # ── Notifications ─────────────────────────────────────────────────

    async def get_notifications(self) -> AdminNotificationSettings:
        orm = await self._db.get(AdminNotificationSettingsOrmModel, SINGLETON_ID)
        if not orm:
            raise RuntimeError("Admin notification settings not seeded, run InitDatabase first.")
        return notifications.to_entity(orm)

    async def save_notifications(self, s: AdminNotificationSettings) -> AdminNotificationSettings:
        orm = await upsert_singleton(
            self._db, AdminNotificationSettingsOrmModel, notifications.to_dict(s)
        )
        return notifications.to_entity(orm)

    # ── Banner ────────────────────────────────────────────────────────

    async def get_banner(self) -> AdminBannerSettings:
        orm = await self._db.get(AdminBannerSettingsOrmModel, SINGLETON_ID)
        if not orm:
            raise RuntimeError("Admin banner settings not seeded, run InitDatabase first.")
        return banner.to_entity(orm)

    async def save_banner(self, s: AdminBannerSettings) -> AdminBannerSettings:
        orm = await upsert_singleton(self._db, AdminBannerSettingsOrmModel, banner.to_dict(s))
        return banner.to_entity(orm)

    # ── Agents ────────────────────────────────────────────────────────

    async def get_agents(self) -> AdminAgentSettings:
        orm = await self._db.get(AdminAgentSettingsOrmModel, SINGLETON_ID)
        if not orm:
            raise RuntimeError("Admin agent settings not seeded, run InitDatabase first.")
        return agents.to_entity(orm)

    async def save_agents(self, s: AdminAgentSettings) -> AdminAgentSettings:
        orm = await upsert_singleton(self._db, AdminAgentSettingsOrmModel, agents.to_dict(s))
        return agents.to_entity(orm)

    # ── Maintenance ───────────────────────────────────────────────────

    async def get_maintenance(self) -> AdminMaintenanceSettings:
        global _maintenance_cache_value, _maintenance_cache_expires_at
        with _maintenance_cache_lock:
            cached = _maintenance_cache_value
            if cached is not None and time.monotonic() < _maintenance_cache_expires_at:
                return cached

        orm = await self._db.get(AdminMaintenanceSettingsOrmModel, SINGLETON_ID)
        if not orm:
            raise RuntimeError("Admin maintenance settings not seeded, run InitDatabase first.")
        entity = maintenance.to_entity(orm)

        with _maintenance_cache_lock:
            _maintenance_cache_value = entity
            _maintenance_cache_expires_at = time.monotonic() + MAINTENANCE_CACHE_TTL_S
        return entity

    async def save_maintenance(self, s: AdminMaintenanceSettings) -> AdminMaintenanceSettings:
        orm = await upsert_singleton(
            self._db, AdminMaintenanceSettingsOrmModel, maintenance.to_dict(s)
        )
        entity = maintenance.to_entity(orm)
        clear_maintenance_cache()
        # Cleared again once the caller commits, so a read this worker makes
        # between the flush and that commit cannot cache the old row.
        event.listen(self._db.sync_session, "after_commit", _clear_cache_on_commit, once=True)
        return entity

    # ── Retention ─────────────────────────────────────────────────────

    async def get_retention(self) -> AdminRetentionSettings:
        orm = await self._db.get(AdminRetentionSettingsOrmModel, SINGLETON_ID)
        if not orm:
            raise RuntimeError("Admin retention settings not seeded, run InitDatabase first.")
        return retention.to_entity(orm)

    async def save_retention(self, s: AdminRetentionSettings) -> AdminRetentionSettings:
        orm = await upsert_singleton(self._db, AdminRetentionSettingsOrmModel, retention.to_dict(s))
        return retention.to_entity(orm)

    # ── Audit log ─────────────────────────────────────────────────────

    async def append_audit(self, entry: AdminSettingsAuditEntry) -> AdminSettingsAuditEntry:
        orm = AdminSettingsAuditOrmModel(
            changed_at=entry.changed_at,
            changed_by_id=entry.changed_by_id,
            changed_by_username=entry.changed_by_username,
            settings_domain=entry.settings_domain,
            summary=entry.summary,
        )
        self._db.add(orm)
        await self._db.flush()
        await self._db.refresh(orm)
        return audit.to_entity(orm)

    async def get_audit(
        self, filters: AdminSettingsAuditFilterDto
    ) -> tuple[int, list[AdminSettingsAuditEntry]]:
        # The days are the tenant's, read from the general settings this
        # repository owns, and only when a day bound is set.
        zone: tzinfo = UTC
        if filters.changed_from or filters.changed_to:
            zone = resolve_actor_timezone((await self.get_general()).default_timezone)
        q = select(AdminSettingsAuditOrmModel).order_by(
            AdminSettingsAuditOrmModel.changed_at.desc()
        )

        if filters.settings_domain:
            q = q.where(AdminSettingsAuditOrmModel.settings_domain == filters.settings_domain)
        if filters.changed_by:
            q = q.where(
                contains_ci(AdminSettingsAuditOrmModel.changed_by_username, filters.changed_by)
            )
        if filters.changed_by_id is not None:
            q = q.where(AdminSettingsAuditOrmModel.changed_by_id == filters.changed_by_id)
        if filters.summary:
            q = q.where(contains_ci(AdminSettingsAuditOrmModel.summary, filters.summary))
        if filters.changed_from:
            q = q.where(
                AdminSettingsAuditOrmModel.changed_at >= day_start_utc(filters.changed_from, zone)
            )
        if filters.changed_to:
            q = q.where(
                AdminSettingsAuditOrmModel.changed_at < day_after_utc(filters.changed_to, zone)
            )

        total, rows = await fetch_page(self._db, q, filters.skip, filters.limit)
        return total, [audit.to_entity(o) for o in rows]
