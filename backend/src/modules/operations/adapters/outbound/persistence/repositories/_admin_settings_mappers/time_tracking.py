"""
Row mapping for the admin_time_tracking_settings singleton. Converts the ORM
row to the domain entity and the entity to the column dict the settings
repository upserts. An API key no configured key can decrypt loads as None,
which reads as "not configured".
"""

from typing import Any

from src.modules.operations.adapters.outbound.persistence.models.admin_settings_model.time_tracking import (
    AdminTimeTrackingSettingsOrmModel,
)
from src.modules.operations.domain.entities.admin_settings.time_tracking import (
    AdminTimeTrackingSettings,
)


def to_entity(o: AdminTimeTrackingSettingsOrmModel) -> AdminTimeTrackingSettings:
    return AdminTimeTrackingSettings(
        id=o.id,
        public_id=o.public_id,
        enabled=o.enabled,
        service_url=o.service_url,
        api_key=o.api_key or None,
        credential_public_key=o.credential_public_key,
        credential_key_id=o.credential_key_id,
        provider_label=o.provider_label,
        privacy_policy_url=o.privacy_policy_url,
    )


def to_dict(s: AdminTimeTrackingSettings) -> dict[str, Any]:
    return {
        "enabled": s.enabled,
        "service_url": s.service_url,
        "api_key": s.api_key,
        "credential_public_key": s.credential_public_key,
        "credential_key_id": s.credential_key_id,
        "provider_label": s.provider_label,
        "privacy_policy_url": s.privacy_policy_url,
    }


def disabled_defaults() -> AdminTimeTrackingSettings:
    """The settings a database without the row reads as: switched off,
    nothing configured."""
    return AdminTimeTrackingSettings(
        id=1,
        enabled=False,
        service_url="",
        api_key=None,
        credential_public_key=None,
        credential_key_id=None,
        provider_label=None,
        privacy_policy_url=None,
    )
