"""
Row mapping for the admin_auth_settings singleton. Converts the ORM row to the
domain entity and the entity to the column dict
SqlAlchemyAdminSettingsRepository upserts.
"""

from typing import Any

from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.auth import (
    AdminAuthSettingsOrmModel,
)
from src.modules.platform.domain.entities.admin_settings.auth import AdminAuthSettings


def to_entity(o: AdminAuthSettingsOrmModel) -> AdminAuthSettings:
    return AdminAuthSettings(
        id=o.id,
        public_id=o.public_id,
        ldap_enabled=o.ldap_enabled,
        ldap_host=o.ldap_host,
        ldap_port=o.ldap_port,
        ldap_use_ssl=o.ldap_use_ssl,
        ldap_start_tls=o.ldap_start_tls,
        ldap_verify_certificate=o.ldap_verify_certificate,
        ldap_domain=o.ldap_domain,
        ldap_timeout_seconds=o.ldap_timeout_seconds,
    )


def to_dict(s: AdminAuthSettings) -> dict[str, Any]:
    return {
        "ldap_enabled": s.ldap_enabled,
        "ldap_host": s.ldap_host,
        "ldap_port": s.ldap_port,
        "ldap_use_ssl": s.ldap_use_ssl,
        "ldap_start_tls": s.ldap_start_tls,
        "ldap_verify_certificate": s.ldap_verify_certificate,
        "ldap_domain": s.ldap_domain,
        "ldap_timeout_seconds": s.ldap_timeout_seconds,
    }
