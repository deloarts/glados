"""
Commands and results for the time tracking settings, the connection test,
the confirmation of the service's credential key and the purge of all stored
time tracking credentials. Validators mirror the request schemas; None in an
update keeps the stored value, an empty string clears an optional one. The
API key is a SecretStr in commands and never part of a result.
"""

from datetime import datetime

from pydantic import BaseModel
from pydantic import SecretStr
from pydantic import field_validator

from src.modules.operations.domain.entities.admin_settings.time_tracking import (
    normalize_privacy_policy_url,
)
from src.modules.operations.domain.entities.admin_settings.time_tracking import (
    normalize_service_url,
)
from src.modules.platform.application.dto.base import ResultBase


class UpdateTimeTrackingSettingsCommand(BaseModel):
    enabled: bool | None = None
    service_url: str | None = None
    # None keeps the stored key, an empty value clears it.
    api_key: SecretStr | None = None
    privacy_policy_url: str | None = None

    @field_validator("service_url")
    @classmethod
    def _service_url(cls, value: str | None) -> str | None:
        return None if value is None else normalize_service_url(value)

    @field_validator("privacy_policy_url")
    @classmethod
    def _privacy_policy_url(cls, value: str | None) -> str | None:
        return None if value is None else (normalize_privacy_policy_url(value) or "")


class VerifyTimeTrackingServiceCommand(BaseModel):
    """The service to probe; None for a field uses the stored value."""

    service_url: str | None = None
    api_key: SecretStr | None = None

    @field_validator("service_url")
    @classmethod
    def _service_url(cls, value: str | None) -> str | None:
        return None if value is None else normalize_service_url(value)


class ConfirmTimeTrackingKeyCommand(BaseModel):
    """The id of the key the admin saw in the connection test. The key is
    only stored when the service still serves exactly that key."""

    credential_key_id: str


class TimeTrackingCredentialHolderResult(BaseModel):
    """One user with stored credentials, for the admin's list. Never carries
    the time tracking user name or anything sealed."""

    user_id: int
    username: str
    full_name: str
    saved_at: datetime
    credentials_valid: bool
    credentials_invalid_reason: str | None


class AdminTimeTrackingSettingsResult(ResultBase):
    enabled: bool
    service_url: str
    api_key_configured: bool
    credential_public_key: str | None
    credential_key_id: str | None
    provider_label: str | None
    privacy_policy_url: str | None
    is_configured: bool
    is_ready: bool
    credential_holders: list[TimeTrackingCredentialHolderResult]


class TimeTrackingServiceTestResult(BaseModel):
    """What a connection test found. `key_confirmed` says whether the key
    the service serves is the confirmed one; the admin confirms it when not."""

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


class PurgeTimeTrackingCredentialsResult(BaseModel):
    deleted: int
