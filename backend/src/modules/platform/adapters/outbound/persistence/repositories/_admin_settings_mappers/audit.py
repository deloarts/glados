"""
Row mapping for the admin_settings_audit log. Converts the ORM row to the
domain entity and the entity to the column dict
SqlAlchemyAdminSettingsRepository upserts.
"""

from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.audit import (
    AdminSettingsAuditOrmModel,
)
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry


def to_entity(o: AdminSettingsAuditOrmModel) -> AdminSettingsAuditEntry:
    return AdminSettingsAuditEntry(
        id=o.id,
        public_id=o.public_id,
        changed_at=o.changed_at,
        changed_by_id=o.changed_by_id,
        changed_by_username=o.changed_by_username,
        settings_domain=o.settings_domain,
        summary=o.summary,
    )
