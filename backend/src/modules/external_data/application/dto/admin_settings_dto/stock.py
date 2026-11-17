"""
Commands and results for the stock service settings and the connection
test. Validators mirror the request schemas; None in an update keeps the
stored value. The API key is a SecretStr in commands and never part of a
result.
"""

from pydantic import BaseModel
from pydantic import SecretStr
from pydantic import field_validator

from src.modules.platform.application.dto.base import ResultBase
from src.shared_kernel.domain.services.service_url import normalize_service_url


class UpdateStockSettingsCommand(BaseModel):
    enabled: bool | None = None
    service_url: str | None = None
    # None keeps the stored key, an empty value clears it.
    api_key: SecretStr | None = None

    @field_validator("service_url")
    @classmethod
    def _service_url(cls, value: str | None) -> str | None:
        return None if value is None else normalize_service_url(value)


class VerifyStockServiceCommand(BaseModel):
    """The service to probe; None for a field uses the stored value."""

    service_url: str | None = None
    api_key: SecretStr | None = None

    @field_validator("service_url")
    @classmethod
    def _service_url(cls, value: str | None) -> str | None:
        return None if value is None else normalize_service_url(value)


class AdminStockSettingsResult(ResultBase):
    enabled: bool
    service_url: str
    api_key_configured: bool
    is_configured: bool
    is_ready: bool


class StockServiceTestResult(BaseModel):
    """What a connection test found."""

    service: str
    service_version: str
    contract_version: str
    contract_supported: bool
    provider_label: str
    server_version: str
