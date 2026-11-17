"""
HTTP request and response schemas for the maintenance mode settings.
"""

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator

from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.domain.services.maintenance_policy import normalise_allowed_ips


class UpdateMaintenanceSettingsRequest(BaseModel):
    enabled: bool = False
    message: str | None = Field(default=None, max_length=500)
    allowed_ips: list[str] = []

    @field_validator("allowed_ips")
    @classmethod
    def validate_allowed_ips(cls, v: list[str]) -> list[str]:
        """Trims, de-duplicates (order kept) and rejects anything that
        doesn't parse as an IP address or CIDR network, mirrored on
        UpdateMaintenanceSettingsCommand per the package's docstring.
        ValueError here (inside a field_validator) becomes a proper 422;
        see validate_office_sharepoint_url_scheme (general.py) for why that
        matters versus a bare ValueError inside the use case.
        """
        return normalise_allowed_ips(v)


class AdminMaintenanceSettingsResponse(EntityResponse):
    enabled: bool
    message: str | None
    allowed_ips: list[str]
