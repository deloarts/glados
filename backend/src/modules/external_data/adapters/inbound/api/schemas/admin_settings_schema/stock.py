"""
HTTP request and response schemas for the stock service settings and the
connection test. Request validators mirror the command DTOs; None keeps a
stored value. The API key is write-only: requests take it as a SecretStr,
responses only say whether one is stored.
"""

from pydantic import BaseModel
from pydantic import Field
from pydantic import SecretStr
from pydantic import field_validator

from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.shared_kernel.domain.services.service_url import normalize_service_url


class UpdateStockSettingsRequest(BaseModel):
    enabled: bool | None = None
    service_url: str | None = Field(default=None, max_length=2048)
    api_key: SecretStr | None = Field(default=None, max_length=512)

    @field_validator("service_url")
    @classmethod
    def _service_url(cls, value: str | None) -> str | None:
        return None if value is None else normalize_service_url(value)


class VerifyStockServiceRequest(BaseModel):
    """Unsaved values to probe; omitted fields use the stored settings."""

    service_url: str | None = Field(default=None, max_length=2048)
    api_key: SecretStr | None = Field(default=None, max_length=512)

    @field_validator("service_url")
    @classmethod
    def _service_url(cls, value: str | None) -> str | None:
        return None if value is None else normalize_service_url(value)


class AdminStockSettingsResponse(EntityResponse):
    enabled: bool
    service_url: str
    api_key_configured: bool
    is_configured: bool
    is_ready: bool


class StockServiceTestResponse(ResponseModel):
    service: str
    service_version: str
    contract_version: str
    contract_supported: bool
    provider_label: str
    server_version: str
