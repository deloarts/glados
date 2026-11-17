"""
Commands and results for the authentication and security policy settings.
"""

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator

from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.domain.services.maintenance_policy import normalise_allowed_ips


class UpdateSecuritySettingsCommand(BaseModel):
    enforce_totp: bool = False
    allow_rfid_login: bool = True
    allow_local_login: bool = True
    enable_api_key_auth: bool = False
    min_password_length: int = 8
    # Idle timeout in minutes; 0 (never) is refused, the absolute lifetime
    # below bounds a session either way.
    session_timeout_minutes: int = Field(default=1440, ge=1)
    totp_trusted_device_days: int = 30
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 15
    # Enforced cap on the lifetime of a newly created API key or PAT; while
    # it is above 0 such a token needs an expiry, and 0 lifts the cap (see
    # domain/services/token_lifetime.py). Full-replace like every other
    # field in this command, so the Security tab must send it on every save.
    token_max_lifetime_days: int = Field(default=365, ge=0, le=36500)
    session_max_lifetime_days: int = Field(default=30, ge=1, le=365)
    enable_terminals: bool = True
    enable_infoscreen_weather: bool = True
    terminal_allowed_ips: list[str] = []

    @field_validator("terminal_allowed_ips")
    @classmethod
    def validate_terminal_allowed_ips(cls, v: list[str]) -> list[str]:
        return normalise_allowed_ips(v)


class AdminSecuritySettingsResult(ResultBase):
    enforce_totp: bool
    allow_rfid_login: bool
    allow_local_login: bool
    enable_api_key_auth: bool
    min_password_length: int
    session_timeout_minutes: int
    totp_trusted_device_days: int
    max_login_attempts: int
    lockout_duration_minutes: int
    token_max_lifetime_days: int
    session_max_lifetime_days: int
    enable_terminals: bool
    enable_infoscreen_weather: bool
    terminal_allowed_ips: list[str]
