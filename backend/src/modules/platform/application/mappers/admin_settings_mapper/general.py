"""
Maps the general settings entity to its result DTO.
"""

from src.modules.platform.application.dto.admin_settings_dto.general import (
    AdminGeneralSettingsResult,
)
from src.modules.platform.domain.entities.admin_settings.general import AdminGeneralSettings


class GeneralSettingsMapper:
    @staticmethod
    def general_to_result(e: AdminGeneralSettings) -> AdminGeneralSettingsResult:
        return AdminGeneralSettingsResult(
            id=e.id,
            public_id=e.public_id,
            company_name=e.company_name,
            company_legal_name=e.company_legal_name,
            has_company_logo=e.company_logo_key is not None,
            contact_email=e.contact_email,
            imprint_url=e.imprint_url,
            privacy_url=e.privacy_url,
            support_url=e.support_url,
            product_number_pattern=e.product_number_pattern,
            project_number_pattern=e.project_number_pattern,
            allow_headless_projects=e.allow_headless_projects,
            empty_value_placeholder=e.empty_value_placeholder,
            office_launcher_enabled=e.office_launcher_enabled,
            office_sharepoint_url=e.office_sharepoint_url,
            currency=e.currency,
            default_language=e.default_language,
            default_timezone=e.default_timezone,
            default_date_format=e.default_date_format,
        )
