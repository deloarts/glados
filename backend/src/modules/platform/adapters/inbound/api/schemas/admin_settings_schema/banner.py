"""
HTTP request and response schemas for the signed-in banner settings.
"""

from datetime import datetime

from pydantic import BaseModel
from pydantic import Field
from pydantic import model_validator

from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.domain.value_objects.announcement_severity import AnnouncementSeverity


class UpdateBannerSettingsRequest(BaseModel):
    enabled: bool = False
    text: str = Field(default="", max_length=500)
    severity: AnnouncementSeverity = AnnouncementSeverity.INFO
    shows_from: datetime | None = None
    shows_until: datetime | None = None
    dismissable: bool = True

    @model_validator(mode="after")
    def validate_banner(self) -> "UpdateBannerSettingsRequest":
        """Mirrored on UpdateBannerSettingsCommand per the package's
        docstring. See validate_office_sharepoint_url_scheme (general.py) for why
        this must raise ValueError inside the validator rather than inside
        the use case."""
        if self.enabled and not self.text.strip():
            raise ValueError("text is required while the banner is enabled.")
        if (
            self.shows_from is not None
            and self.shows_until is not None
            and self.shows_until < self.shows_from
        ):
            raise ValueError("shows_until must not be before shows_from.")
        return self


class AdminBannerSettingsResponse(EntityResponse):
    enabled: bool
    text: str
    severity: AnnouncementSeverity
    shows_from: datetime | None
    shows_until: datetime | None
    dismissable: bool
    updated_at: datetime
