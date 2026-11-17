"""
HTTP request and response schemas for the time tracking settings, the
connection test, the confirmation of the credential key and the purge of
stored time tracking credentials. Request validators mirror the command
DTOs; None keeps a stored value, an empty string clears an optional one.
The API key is write-only: requests take it as a SecretStr, responses only
say whether one is stored.
"""

from datetime import datetime

from pydantic import BaseModel
from pydantic import Field
from pydantic import SecretStr
from pydantic import field_validator

from src.modules.operations.domain.entities.admin_settings.time_tracking import (
    normalize_privacy_policy_url,
)
from src.modules.operations.domain.entities.admin_settings.time_tracking import (
    normalize_service_url,
)
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel


class UpdateTimeTrackingSettingsRequest(BaseModel):
    enabled: bool | None = None
    service_url: str | None = Field(default=None, max_length=2048)
    api_key: SecretStr | None = Field(default=None, max_length=512)
    privacy_policy_url: str | None = Field(default=None, max_length=2048)

    @field_validator("service_url")
    @classmethod
    def _service_url(cls, value: str | None) -> str | None:
        return None if value is None else normalize_service_url(value)

    @field_validator("privacy_policy_url")
    @classmethod
    def _privacy_policy_url(cls, value: str | None) -> str | None:
        return None if value is None else (normalize_privacy_policy_url(value) or "")


class VerifyTimeTrackingServiceRequest(BaseModel):
    """Unsaved values to probe; omitted fields use the stored settings."""

    service_url: str | None = Field(default=None, max_length=2048)
    api_key: SecretStr | None = Field(default=None, max_length=512)

    @field_validator("service_url")
    @classmethod
    def _service_url(cls, value: str | None) -> str | None:
        return None if value is None else normalize_service_url(value)


class ConfirmTimeTrackingKeyRequest(BaseModel):
    credential_key_id: str = Field(min_length=1, max_length=64)


class TimeTrackingCredentialHolderResponse(ResponseModel):
    user_id: int
    username: str
    full_name: str
    saved_at: datetime
    credentials_valid: bool
    credentials_invalid_reason: str | None


class AdminTimeTrackingSettingsResponse(EntityResponse):
    enabled: bool
    service_url: str
    api_key_configured: bool
    credential_public_key: str | None
    credential_key_id: str | None
    provider_label: str | None
    privacy_policy_url: str | None
    is_configured: bool
    is_ready: bool
    credential_holders: list[TimeTrackingCredentialHolderResponse]


class TimeTrackingServiceTestResponse(ResponseModel):
    service: str
    service_version: str
    contract_version: str
    contract_supported: bool
    credential_fields_supported: bool
    provider_label: str
    credential_public_key: str
    credential_key_id: str
    key_confirmed: bool
    server_version: str
    default_project: str


class PurgeTimeTrackingCredentialsResponse(ResponseModel):
    deleted: int
