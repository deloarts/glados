"""
Row mapping for the admin_security_settings singleton. Converts the ORM row to
the domain entity and the entity to the column dict
SqlAlchemyAdminSettingsRepository upserts.
"""

from typing import Any

from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.security import (
    AdminSecuritySettingsOrmModel,
)
from src.modules.platform.domain.entities.admin_settings.security import AdminSecuritySettings


def to_entity(o: AdminSecuritySettingsOrmModel) -> AdminSecuritySettings:
    return AdminSecuritySettings(
        id=o.id,
        public_id=o.public_id,
        enforce_totp=o.enforce_totp,
        allow_rfid_login=o.allow_rfid_login,
        allow_local_login=o.allow_local_login,
        enable_api_key_auth=o.enable_api_key_auth,
        min_password_length=o.min_password_length,
        session_timeout_minutes=o.session_timeout_minutes,
        totp_trusted_device_days=o.totp_trusted_device_days,
        max_login_attempts=o.max_login_attempts,
        lockout_duration_minutes=o.lockout_duration_minutes,
        token_max_lifetime_days=o.token_max_lifetime_days,
        session_max_lifetime_days=o.session_max_lifetime_days,
        enable_terminals=o.enable_terminals,
        enable_infoscreen_weather=o.enable_infoscreen_weather,
        terminal_allowed_ips=list(o.terminal_allowed_ips or []),
    )


def to_dict(s: AdminSecuritySettings) -> dict[str, Any]:
    return {
        "enforce_totp": s.enforce_totp,
        "allow_rfid_login": s.allow_rfid_login,
        "allow_local_login": s.allow_local_login,
        "enable_api_key_auth": s.enable_api_key_auth,
        "min_password_length": s.min_password_length,
        "session_timeout_minutes": s.session_timeout_minutes,
        "totp_trusted_device_days": s.totp_trusted_device_days,
        "max_login_attempts": s.max_login_attempts,
        "lockout_duration_minutes": s.lockout_duration_minutes,
        "token_max_lifetime_days": s.token_max_lifetime_days,
        "session_max_lifetime_days": s.session_max_lifetime_days,
        "enable_terminals": s.enable_terminals,
        "enable_infoscreen_weather": s.enable_infoscreen_weather,
        "terminal_allowed_ips": list(s.terminal_allowed_ips),
    }
