"""
Row mapping for the admin_notification_settings singleton. Converts the ORM row
to the domain entity and the entity to the column dict
SqlAlchemyAdminSettingsRepository upserts.
"""

from typing import Any

from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.notifications import (
    AdminNotificationSettingsOrmModel,
)
from src.modules.platform.domain.entities.admin_settings.notifications import (
    AdminNotificationSettings,
)


def to_entity(o: AdminNotificationSettingsOrmModel) -> AdminNotificationSettings:
    return AdminNotificationSettings(
        id=o.id,
        public_id=o.public_id,
        webhook_timeout_seconds=o.webhook_timeout_seconds,
    )


def to_dict(s: AdminNotificationSettings) -> dict[str, Any]:
    return {
        "webhook_timeout_seconds": s.webhook_timeout_seconds,
    }
