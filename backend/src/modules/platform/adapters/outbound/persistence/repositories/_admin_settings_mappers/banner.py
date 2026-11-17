"""
Row mapping for the admin_banner_settings singleton. Converts the ORM row to
the domain entity and the entity to the column dict
SqlAlchemyAdminSettingsRepository upserts.
"""

from typing import Any

from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.banner import (
    AdminBannerSettingsOrmModel,
)
from src.modules.platform.domain.entities.admin_settings.banner import AdminBannerSettings
from src.modules.platform.domain.value_objects.announcement_severity import AnnouncementSeverity


def to_entity(o: AdminBannerSettingsOrmModel) -> AdminBannerSettings:
    updated_at = utc_aware(o.updated_at)
    assert updated_at is not None  # non-null column
    return AdminBannerSettings(
        id=o.id,
        public_id=o.public_id,
        enabled=o.enabled,
        text=o.text,
        severity=AnnouncementSeverity(o.severity),
        shows_from=utc_aware(o.shows_from),
        shows_until=utc_aware(o.shows_until),
        dismissable=o.dismissable,
        updated_at=updated_at,
    )


def to_dict(s: AdminBannerSettings) -> dict[str, Any]:
    return {
        "enabled": s.enabled,
        "text": s.text,
        "severity": s.severity.value,
        "shows_from": s.shows_from,
        "shows_until": s.shows_until,
        "dismissable": s.dismissable,
        "updated_at": s.updated_at,
    }
