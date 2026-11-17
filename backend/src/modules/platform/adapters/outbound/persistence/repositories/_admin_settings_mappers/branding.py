"""
Row mapping for the admin_branding_settings singleton. Converts the ORM row to
the domain entity and the entity to the column dict
SqlAlchemyAdminSettingsRepository upserts.
"""

from typing import Any

from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.branding import (
    AdminBrandingSettingsOrmModel,
)
from src.modules.platform.domain.entities.admin_settings.branding import AdminBrandingSettings


def to_entity(o: AdminBrandingSettingsOrmModel) -> AdminBrandingSettings:
    return AdminBrandingSettings(
        id=o.id,
        public_id=o.public_id,
        app_name=o.app_name,
        app_description=o.app_description,
        footer_text=o.footer_text,
        logo_url=o.logo_url,
        favicon_url=o.favicon_url,
        logo_key=o.logo_key,
        favicon_key=o.favicon_key,
        login_background_video_key=o.login_background_video_key,
    )


def to_dict(s: AdminBrandingSettings) -> dict[str, Any]:
    return {
        "app_name": s.app_name,
        "app_description": s.app_description,
        "footer_text": s.footer_text,
        "logo_url": s.logo_url,
        "favicon_url": s.favicon_url,
        "logo_key": s.logo_key,
        "favicon_key": s.favicon_key,
        "login_background_video_key": s.login_background_video_key,
    }
