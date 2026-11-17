"""
Maps the EPLAN Data Portal settings to their result; the token is replaced
with a presence flag.
"""

from src.modules.external_data.application.dto.admin_settings_dto.eplan_data_portal import (
    AdminEdpSettingsResult,
)
from src.modules.external_data.domain.entities.admin_settings.eplan_data_portal import (
    AdminEdpSettings,
)


class EdpSettingsMapper:
    @staticmethod
    def edp_to_result(e: AdminEdpSettings) -> AdminEdpSettingsResult:
        return AdminEdpSettingsResult(
            id=e.id,
            public_id=e.public_id,
            enabled=e.enabled,
            base_url=e.base_url,
            pat_configured=bool(e.pat),
            default_article_group_ids=list(e.default_article_group_ids),
            language=e.language,
            is_configured=e.is_configured,
        )
