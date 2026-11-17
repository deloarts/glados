"""
Commands and results for the maintenance mode settings.
"""

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator

from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.domain.services.maintenance_policy import normalise_allowed_ips


class UpdateMaintenanceSettingsCommand(BaseModel):
    enabled: bool = False
    message: str | None = Field(default=None, max_length=500)
    allowed_ips: list[str] = []

    @field_validator("allowed_ips")
    @classmethod
    def validate_allowed_ips(cls, v: list[str]) -> list[str]:
        """Trims, de-duplicates (order kept) and rejects anything that
        doesn't parse as an IP address or CIDR network, mirrored on
        UpdateMaintenanceSettingsRequest per the schema package's docstring.
        ValueError here (inside a field_validator) becomes a 422 through
        Pydantic/FastAPI's own validation-error handling, same reasoning
        as UpdateGeneralSettingsCommand.validate_office_sharepoint_url_scheme
        (general.py); a bare `raise ValueError` inside the use case would not be
        caught by exception_handlers.py, which only registers a handler
        for DomainError, and would fall through to an unhandled 500.
        """
        return normalise_allowed_ips(v)


class AdminMaintenanceSettingsResult(ResultBase):
    enabled: bool
    message: str | None
    allowed_ips: list[str]
