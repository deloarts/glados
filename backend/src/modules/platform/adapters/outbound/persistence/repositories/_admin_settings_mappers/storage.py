"""
Row mapping for the admin_storage_settings singleton. Converts the ORM row to
the domain entity and the entity to the column dict
SqlAlchemyAdminSettingsRepository upserts.
"""

from typing import Any

from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.storage import (
    AdminStorageSettingsOrmModel,
)
from src.modules.platform.domain.entities.admin_settings.storage import AdminStorageSettings


def to_entity(o: AdminStorageSettingsOrmModel) -> AdminStorageSettings:
    return AdminStorageSettings(
        id=o.id,
        public_id=o.public_id,
        provider=o.provider,
        enabled=o.enabled,
        endpoint_url=o.endpoint_url,
        public_endpoint_url=o.public_endpoint_url,
        bucket_name=o.bucket_name,
        access_key=o.access_key,
        secret_key=o.secret_key,
        region=o.region,
        use_ssl=o.use_ssl,
        backup_enabled=o.backup_enabled,
        backup_path=o.backup_path,
        backup_cron=o.backup_cron,
        backup_retention_count=o.backup_retention_count,
        disk_warning_percent=o.disk_warning_percent,
    )


def to_dict(s: AdminStorageSettings) -> dict[str, Any]:
    return {
        "provider": s.provider,
        "enabled": s.enabled,
        "endpoint_url": s.endpoint_url,
        "public_endpoint_url": s.public_endpoint_url,
        "bucket_name": s.bucket_name,
        "access_key": s.access_key,
        "secret_key": s.secret_key,
        "region": s.region,
        "use_ssl": s.use_ssl,
        "backup_enabled": s.backup_enabled,
        "backup_path": s.backup_path,
        "backup_cron": s.backup_cron,
        "backup_retention_count": s.backup_retention_count,
        "disk_warning_percent": s.disk_warning_percent,
    }
