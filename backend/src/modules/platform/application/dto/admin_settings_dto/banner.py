"""
Commands and results for the signed-in banner settings.
"""

from datetime import datetime

from pydantic import BaseModel
from pydantic import Field
from pydantic import model_validator

from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.domain.value_objects.announcement_severity import AnnouncementSeverity


class UpdateBannerSettingsCommand(BaseModel):
    enabled: bool = False
    text: str = Field(default="", max_length=500)
    severity: AnnouncementSeverity = AnnouncementSeverity.INFO
    shows_from: datetime | None = None
    shows_until: datetime | None = None
    dismissable: bool = True

    @model_validator(mode="after")
    def validate_banner(self) -> "UpdateBannerSettingsCommand":
        """Mirrored on UpdateBannerSettingsRequest per that module's
        docstring convention. Raising ValueError here (inside a
        model_validator) becomes a 422 through Pydantic/FastAPI's own
        validation-error handling, same reasoning as
        UpdateGeneralSettingsCommand.validate_office_sharepoint_url_scheme
        (general.py); a bare `raise ValueError` inside the use case would not be
        caught by exception_handlers.py, which only registers a handler
        for DomainError, and would fall through to an unhandled 500.
        """
        if self.enabled and not self.text.strip():
            raise ValueError("text is required while the banner is enabled.")
        if (
            self.shows_from is not None
            and self.shows_until is not None
            and self.shows_until < self.shows_from
        ):
            raise ValueError("shows_until must not be before shows_from.")
        return self


class AdminBannerSettingsResult(ResultBase):
    enabled: bool
    text: str
    severity: AnnouncementSeverity
    shows_from: datetime | None
    shows_until: datetime | None
    dismissable: bool
    updated_at: datetime
