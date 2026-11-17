"""
Domain entity for the authentication and security policy settings singleton.
"""

from dataclasses import dataclass
from dataclasses import field

from src.modules.platform.domain.services.session_rules import DEFAULT_SESSION_MAX_LIFETIME_DAYS
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class AdminSecuritySettings(Entity):
    """Authentication and security policy settings."""

    enforce_totp: bool  # if True all users must enrol 2FA
    allow_rfid_login: bool
    allow_local_login: bool  # username + password login
    # Whether a request may authenticate with an API key at all (auth_deps).
    # It is an authentication policy, so it sits here, not in the feature flags.
    enable_api_key_auth: bool
    min_password_length: int
    # Idle timeout of a web session. The settings refuse 0; a stored 0 from
    # before that rule still means no idle expiry (session_rules.py).
    session_timeout_minutes: int
    totp_trusted_device_days: int  # "trust this device" TOTP skip; 0 = disabled
    max_login_attempts: int  # 0 = unlimited
    lockout_duration_minutes: int
    # Ceiling on the lifetime of a new API key or PAT, applied to every
    # caller, the system user included, on top of the schema's own limit.
    # Above 0 every new token needs an expiry; 0 lifts the cap
    # (domain/services/token_lifetime.py).
    token_max_lifetime_days: int
    # Absolute lifetime of a web session, counted from sign-in however
    # active the session stays (session_rules.py).
    session_max_lifetime_days: int = DEFAULT_SESSION_MAX_LIFETIME_DAYS
    # Whether terminals may sign in at all, independent of
    # enable_api_key_auth: a terminal key is only checked on a device's
    # first session, and an enrolled device needs no key afterwards.
    enable_terminals: bool = True
    # Whether the weather widget of infoscreens may call the public weather
    # service; off keeps the backend from reaching it at all.
    enable_infoscreen_weather: bool = True
    # Client addresses or CIDR networks terminals may connect from; empty
    # allows any address. Behind a reverse proxy the address is the
    # proxy's unless it forwards the client's.
    terminal_allowed_ips: list[str] = field(default_factory=list)
