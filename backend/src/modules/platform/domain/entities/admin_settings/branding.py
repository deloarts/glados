"""
Domain entity for the UI branding settings singleton.
"""

from dataclasses import dataclass

from src.shared_kernel.domain.entities.base import Entity


@dataclass
class AdminBrandingSettings(Entity):
    """UI / white-label branding settings."""

    app_name: str
    app_description: str | None
    footer_text: str | None
    logo_url: str | None
    favicon_url: str | None
    logo_key: str | None  # storage key, not a URL
    favicon_key: str | None  # storage key, not a URL
    login_background_video_key: str | None  # storage key, not a URL
