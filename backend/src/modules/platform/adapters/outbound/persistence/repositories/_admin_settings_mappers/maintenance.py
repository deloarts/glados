"""
Row mapping for the admin_maintenance_settings singleton. Converts the ORM row
to the domain entity and the entity to the column dict
SqlAlchemyAdminSettingsRepository upserts.
"""

from typing import Any

from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.maintenance import (
    AdminMaintenanceSettingsOrmModel,
)
from src.modules.platform.domain.entities.admin_settings.maintenance import AdminMaintenanceSettings


def to_entity(o: AdminMaintenanceSettingsOrmModel) -> AdminMaintenanceSettings:
    return AdminMaintenanceSettings(
        id=o.id,
        public_id=o.public_id,
        enabled=o.enabled,
        message=o.message,
        allowed_ips=list(o.allowed_ips or []),
    )


def to_dict(s: AdminMaintenanceSettings) -> dict[str, Any]:
    return {
        "enabled": s.enabled,
        "message": s.message,
        "allowed_ips": list(s.allowed_ips),
    }
