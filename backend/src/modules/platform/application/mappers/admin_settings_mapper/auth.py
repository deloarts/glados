"""
Maps the LDAP authentication settings entity to its result DTO.
"""

from src.modules.platform.application.dto.admin_settings_dto.auth import AdminAuthSettingsResult
from src.modules.platform.domain.entities.admin_settings.auth import AdminAuthSettings


class AuthSettingsMapper:
    @staticmethod
    def auth_to_result(e: AdminAuthSettings) -> AdminAuthSettingsResult:
        # No *_configured flag: binding as the end user means this domain
        # stores no secret at all.
        return AdminAuthSettingsResult(
            id=e.id,
            public_id=e.public_id,
            ldap_enabled=e.ldap_enabled,
            ldap_host=e.ldap_host,
            ldap_port=e.ldap_port,
            ldap_use_ssl=e.ldap_use_ssl,
            ldap_start_tls=e.ldap_start_tls,
            ldap_verify_certificate=e.ldap_verify_certificate,
            ldap_domain=e.ldap_domain,
            ldap_timeout_seconds=e.ldap_timeout_seconds,
        )
