"""
Row mapping for the admin_retention_settings singleton. Converts the ORM row to
the domain entity and the entity to the column dict
SqlAlchemyAdminSettingsRepository upserts.
"""

from typing import Any

from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.retention import (
    AdminRetentionSettingsOrmModel,
)
from src.modules.platform.domain.entities.admin_settings.retention import AdminRetentionSettings


def to_entity(o: AdminRetentionSettingsOrmModel) -> AdminRetentionSettings:
    return AdminRetentionSettings(
        id=o.id,
        public_id=o.public_id,
        log_retention_days=o.log_retention_days,
        audit_retention_days=o.audit_retention_days,
        soft_delete_cleanup_days=o.soft_delete_cleanup_days,
        meeting_retention_days=o.meeting_retention_days,
    )


def to_dict(s: AdminRetentionSettings) -> dict[str, Any]:
    return {
        "log_retention_days": s.log_retention_days,
        "audit_retention_days": s.audit_retention_days,
        "soft_delete_cleanup_days": s.soft_delete_cleanup_days,
        "meeting_retention_days": s.meeting_retention_days,
    }
