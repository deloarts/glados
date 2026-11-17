"""
Abstract directory authentication. The application layer calls this, never
ldap3 directly. Implementations live in src/modules/platform/adapters/outbound/external/ldap/.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.platform.domain.entities.admin_settings.auth import AdminAuthSettings


@runtime_checkable
class ILdapAuthenticator(Protocol):
    async def authenticate(self, username: str, password: str) -> bool:
        """Bind to the directory as `username`, a bare sAMAccountName; the
        implementation prefixes the configured NetBIOS domain.

        Returns True when the directory accepted the credentials, and False
        when the directory was reached and said no. Raises
        LdapUnavailableError when the directory could not be asked at all
        (DNS, TCP, TLS, timeout, misconfiguration).

        The distinction is security-critical: a caller may fall back to a
        locally cached password on LdapUnavailableError; it must never fall
        back on a False, or a stale local hash would outlive a disabled
        directory account.
        """
        ...


@runtime_checkable
class ILdapAuthenticatorFactory(Protocol):
    def __call__(self, settings: AdminAuthSettings) -> ILdapAuthenticator:
        """Build an authenticator for the given settings.

        A factory rather than a single injected ILdapAuthenticator because the
        admin test-connection endpoint must bind against settings that are not
        the persisted, active ones.
        """
        ...
