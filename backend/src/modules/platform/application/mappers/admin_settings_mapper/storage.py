"""
Maps the file storage settings entity to its result DTO. The secret key is
replaced with a boolean presence flag.
"""

from src.modules.platform.application.dto.admin_settings_dto.storage import (
    AdminStorageSettingsResult,
)
from src.modules.platform.domain.entities.admin_settings.storage import AdminStorageSettings


class StorageSettingsMapper:
    @staticmethod
    def storage_to_result(e: AdminStorageSettings) -> AdminStorageSettingsResult:
        return AdminStorageSettingsResult(
            id=e.id,
            public_id=e.public_id,
            provider=e.provider,
            enabled=e.enabled,
            endpoint_url=e.endpoint_url,
            public_endpoint_url=e.public_endpoint_url,
            bucket_name=e.bucket_name,
            access_key=e.access_key,
            secret_key_configured=e.secret_key is not None and e.secret_key != "",
            region=e.region,
            use_ssl=e.use_ssl,
            backup_enabled=e.backup_enabled,
            backup_path=e.backup_path,
            backup_cron=e.backup_cron,
            backup_retention_count=e.backup_retention_count,
            disk_warning_percent=e.disk_warning_percent,
        )
