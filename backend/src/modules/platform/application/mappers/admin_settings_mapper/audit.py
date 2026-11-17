"""
Maps an admin settings audit entry to its result DTO.
"""

from src.modules.platform.application.dto.admin_settings_dto.audit import (
    AdminSettingsAuditEntryResult,
)
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry


class AuditEntryMapper:
    @staticmethod
    def audit_to_result(e: AdminSettingsAuditEntry) -> AdminSettingsAuditEntryResult:
        return AdminSettingsAuditEntryResult(
            id=e.id,
            public_id=e.public_id,
            changed_at=e.changed_at,
            changed_by_id=e.changed_by_id,
            changed_by_username=e.changed_by_username,
            settings_domain=e.settings_domain,
            summary=e.summary,
        )
