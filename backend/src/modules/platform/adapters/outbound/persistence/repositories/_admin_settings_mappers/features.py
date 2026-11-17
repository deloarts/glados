"""
Row mapping for the admin_feature_settings singleton. Converts the ORM row to
the domain entity and the entity to the column dict
SqlAlchemyAdminSettingsRepository upserts.
"""

from typing import Any

from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.features import (
    AdminFeatureSettingsOrmModel,
)
from src.modules.platform.domain.entities.admin_settings.features import AdminFeatureSettings


def to_entity(o: AdminFeatureSettingsOrmModel) -> AdminFeatureSettings:
    return AdminFeatureSettings(
        id=o.id,
        public_id=o.public_id,
        enable_email_notifications=o.enable_email_notifications,
        enable_production_planning=o.enable_production_planning,
        allow_private_webhooks=o.allow_private_webhooks,
        enable_calculations=o.enable_calculations,
        enable_checklists=o.enable_checklists,
        enable_devices=o.enable_devices,
        enable_sequences=o.enable_sequences,
        enable_todos=o.enable_todos,
    )


def to_dict(s: AdminFeatureSettings) -> dict[str, Any]:
    return {
        "enable_email_notifications": s.enable_email_notifications,
        "enable_production_planning": s.enable_production_planning,
        "allow_private_webhooks": s.allow_private_webhooks,
        "enable_calculations": s.enable_calculations,
        "enable_checklists": s.enable_checklists,
        "enable_devices": s.enable_devices,
        "enable_sequences": s.enable_sequences,
        "enable_todos": s.enable_todos,
    }
