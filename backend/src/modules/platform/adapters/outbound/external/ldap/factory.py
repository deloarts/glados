"""
Builds a directory authenticator from settings. Trivial today (one
implementation), but it is the seam ILdapAuthenticatorFactory names, and it
lets the admin test-connection use case bind against unsaved settings without
importing the concrete adapter into the application layer.
"""

from src.modules.platform.adapters.outbound.external.ldap.ldap3_authenticator import (
    Ldap3Authenticator,
)
from src.modules.platform.domain.entities.admin_settings.auth import AdminAuthSettings
from src.modules.platform.ports.outbound.ldap_authenticator_port import ILdapAuthenticator


def create_ldap_authenticator(settings: AdminAuthSettings) -> ILdapAuthenticator:
    """Return the authenticator for the given settings."""
    return Ldap3Authenticator(settings)
