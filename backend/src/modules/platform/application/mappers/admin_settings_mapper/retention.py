"""
Maps the data retention settings entity to its result DTO.
"""

from src.modules.platform.application.dto.admin_settings_dto.retention import (
    AdminRetentionSettingsResult,
)
from src.modules.platform.domain.entities.admin_settings.retention import AdminRetentionSettings


class RetentionSettingsMapper:
    @staticmethod
    def retention_to_result(e: AdminRetentionSettings) -> AdminRetentionSettingsResult:
        return AdminRetentionSettingsResult(
            id=e.id,
            public_id=e.public_id,
            log_retention_days=e.log_retention_days,
            audit_retention_days=e.audit_retention_days,
            soft_delete_cleanup_days=e.soft_delete_cleanup_days,
            meeting_retention_days=e.meeting_retention_days,
        )
