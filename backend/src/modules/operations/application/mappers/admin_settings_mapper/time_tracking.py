"""
Maps the time tracking settings entity to its result DTO. The API key never
leaves the server; the result only says whether one is stored.
"""

from src.modules.operations.application.dto.admin_settings_dto.time_tracking import (
    AdminTimeTrackingSettingsResult,
)
from src.modules.operations.application.dto.admin_settings_dto.time_tracking import (
    TimeTrackingCredentialHolderResult,
)
from src.modules.operations.domain.entities.admin_settings.time_tracking import (
    AdminTimeTrackingSettings,
)


class TimeTrackingSettingsMapper:
    @staticmethod
    def time_tracking_to_result(
        e: AdminTimeTrackingSettings,
        *,
        credential_holders: list[TimeTrackingCredentialHolderResult],
    ) -> AdminTimeTrackingSettingsResult:
        return AdminTimeTrackingSettingsResult(
            id=e.id,
            public_id=e.public_id,
            enabled=e.enabled,
            service_url=e.service_url,
            api_key_configured=bool(e.api_key),
            credential_public_key=e.credential_public_key,
            credential_key_id=e.credential_key_id,
            provider_label=e.provider_label,
            privacy_policy_url=e.privacy_policy_url,
            is_configured=e.is_configured,
            is_ready=e.is_ready,
            credential_holders=credential_holders,
        )
