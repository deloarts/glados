"""
Row mapping for the admin_general_settings singleton. Converts the ORM row to
the domain entity and the entity to the column dict
SqlAlchemyAdminSettingsRepository upserts.
"""

from typing import Any

from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.general import (
    AdminGeneralSettingsOrmModel,
)
from src.modules.platform.domain.entities.admin_settings.general import AdminGeneralSettings
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language


def to_entity(o: AdminGeneralSettingsOrmModel) -> AdminGeneralSettings:
    return AdminGeneralSettings(
        id=o.id,
        public_id=o.public_id,
        company_name=o.company_name,
        company_legal_name=o.company_legal_name,
        company_logo_key=o.company_logo_key,
        contact_email=o.contact_email,
        imprint_url=o.imprint_url,
        privacy_url=o.privacy_url,
        support_url=o.support_url,
        product_number_pattern=o.product_number_pattern,
        project_number_pattern=o.project_number_pattern,
        allow_headless_projects=o.allow_headless_projects,
        empty_value_placeholder=o.empty_value_placeholder,
        office_launcher_enabled=o.office_launcher_enabled,
        office_sharepoint_url=o.office_sharepoint_url,
        currency=o.currency,
        default_language=Language(o.default_language),
        default_timezone=o.default_timezone,
        default_date_format=DateFormat(o.default_date_format),
    )


def to_dict(s: AdminGeneralSettings) -> dict[str, Any]:
    return {
        "company_name": s.company_name,
        "company_legal_name": s.company_legal_name,
        "company_logo_key": s.company_logo_key,
        "contact_email": s.contact_email,
        "imprint_url": s.imprint_url,
        "privacy_url": s.privacy_url,
        "support_url": s.support_url,
        "product_number_pattern": s.product_number_pattern,
        "project_number_pattern": s.project_number_pattern,
        "allow_headless_projects": s.allow_headless_projects,
        "empty_value_placeholder": s.empty_value_placeholder,
        "office_launcher_enabled": s.office_launcher_enabled,
        "office_sharepoint_url": s.office_sharepoint_url,
        "currency": s.currency,
        "default_language": s.default_language.value,
        "default_timezone": s.default_timezone,
        "default_date_format": s.default_date_format.value,
    }
