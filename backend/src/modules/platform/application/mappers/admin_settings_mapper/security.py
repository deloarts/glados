"""
Maps the security policy settings entity to its result DTO.
"""

from src.modules.platform.application.dto.admin_settings_dto.security import (
    AdminSecuritySettingsResult,
)
from src.modules.platform.domain.entities.admin_settings.security import AdminSecuritySettings


class SecuritySettingsMapper:
    @staticmethod
    def security_to_result(e: AdminSecuritySettings) -> AdminSecuritySettingsResult:
        return AdminSecuritySettingsResult(
            id=e.id,
            public_id=e.public_id,
            enforce_totp=e.enforce_totp,
            allow_rfid_login=e.allow_rfid_login,
            allow_local_login=e.allow_local_login,
            enable_api_key_auth=e.enable_api_key_auth,
            min_password_length=e.min_password_length,
            session_timeout_minutes=e.session_timeout_minutes,
            totp_trusted_device_days=e.totp_trusted_device_days,
            max_login_attempts=e.max_login_attempts,
            lockout_duration_minutes=e.lockout_duration_minutes,
            token_max_lifetime_days=e.token_max_lifetime_days,
            session_max_lifetime_days=e.session_max_lifetime_days,
            enable_terminals=e.enable_terminals,
            enable_infoscreen_weather=e.enable_infoscreen_weather,
            terminal_allowed_ips=list(e.terminal_allowed_ips),
        )
