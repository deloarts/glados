"""
ldap3-backed directory authentication: a direct simple bind as the end user.

There is deliberately no post-bind search. Users are never auto-created and no
directory attribute is ever read, so the bind alone is a complete proof of
credentials, Active Directory already refuses binds for disabled (error 49
data 533), locked (775) and expired-password (532/773) accounts. Skipping the
search also avoids a second round trip per login and the LDAP-filter escaping
that a username-in-a-filter would otherwise require.

ldap3 is blocking, so the async `authenticate` runs the bind on a worker
thread.
"""

import contextlib
import ssl

from anyio import to_thread
from ldap3 import AUTO_BIND_NO_TLS
from ldap3 import AUTO_BIND_TLS_BEFORE_BIND
from ldap3 import NONE
from ldap3 import SIMPLE
from ldap3 import Connection
from ldap3 import Server
from ldap3 import Tls
from ldap3.core.exceptions import LDAPBindError
from ldap3.core.exceptions import LDAPException
from ldap3.core.exceptions import LDAPInvalidCredentialsResult
from ldap3.core.exceptions import LDAPPasswordIsMandatoryError
from ldap3.core.exceptions import LDAPUserNameIsMandatoryError

from src.modules.platform.domain.entities.admin_settings.auth import AdminAuthSettings
from src.modules.platform.domain.exceptions import LdapNotConfiguredError
from src.modules.platform.domain.exceptions import LdapUnavailableError
from src.modules.platform.infrastructure.logging.logger import log


class Ldap3Authenticator:
    def __init__(self, settings: AdminAuthSettings) -> None:
        self._s = settings

    async def authenticate(self, username: str, password: str) -> bool:
        return await to_thread.run_sync(self._authenticate_blocking, username, password)

    def _authenticate_blocking(self, username: str, password: str) -> bool:
        # An empty password is never a valid credential, and the guard has to
        # be here rather than only in the caller: ldap3 2.9.1 raises
        # LDAPPasswordIsMandatoryError for it, which is an LDAPExceptionError
        # but neither an LDAPBindError nor an LDAPCommunicationError, so the
        # catch-all below would otherwise classify it as "directory
        # unreachable" and let the caller fall back to the local password.
        # A raw LDAP client would instead send an RFC 4513 5.1.2
        # unauthenticated bind, which AD answers with success. Both roads lead
        # somewhere wrong; neither is taken.
        if not password or not username:
            return False

        # A backslash would let the username rewrite the domain half of the
        # bind name. `username` comes from our own database, so this is
        # belt-and-braces rather than a live hole.
        if "\\" in username or "\x00" in username:
            log.warning("Refusing LDAP bind for a username containing a separator: %r", username)
            return False

        bind_name = f"{self._s.ldap_domain}\\{username}"
        conn = None
        try:
            conn = Connection(
                self._server(),
                user=bind_name,
                password=password,
                authentication=SIMPLE,
                auto_bind=(
                    AUTO_BIND_TLS_BEFORE_BIND if self._s.ldap_start_tls else AUTO_BIND_NO_TLS
                ),
                raise_exceptions=False,
                read_only=True,
                receive_timeout=self._s.ldap_timeout_seconds,
            )
            # auto_bind raises rather than returning on failure; checking
            # `bound` too guards against a future ldap3 changing that.
            return bool(conn.bound)
        except (LDAPBindError, LDAPInvalidCredentialsResult) as exc:
            # WARNING, not info: a rejected credential is the same
            # class of event as the malformed-request branch below and as
            # authenticate_user.py:97's own log line for the same
            # rejection; all three should be filterable together at the
            # log viewer's WARNING level. Message unchanged: username only,
            # no credential material.
            log.warning("LDAP rejected the bind for %r: %s", username, exc)
            return False
        except (LDAPPasswordIsMandatoryError, LDAPUserNameIsMandatoryError) as exc:
            # Unreachable given the guard above; classified explicitly so it
            # can never be mistaken for a transport failure.
            log.warning("Malformed LDAP bind request for %r: %s", username, exc)
            return False
        except LDAPException as exc:
            raise LdapUnavailableError(f"{type(exc).__name__}: {exc}") from exc
        except OSError as exc:  # ssl.SSLError, socket.gaierror, ...
            raise LdapUnavailableError(f"{type(exc).__name__}: {exc}") from exc
        finally:
            if conn is not None:
                # Teardown must not mask the verdict already returned/raised above.
                with contextlib.suppress(Exception):
                    conn.unbind()

    def _server(self) -> Server:
        if not self._s.ldap_host:
            raise LdapNotConfiguredError("LDAP host is not configured.")
        if not self._s.ldap_domain:
            raise LdapNotConfiguredError("LDAP domain is not configured.")
        tls = Tls(
            validate=ssl.CERT_REQUIRED if self._s.ldap_verify_certificate else ssl.CERT_NONE,
            version=ssl.PROTOCOL_TLS_CLIENT,
        )
        return Server(
            self._s.ldap_host,
            port=self._s.ldap_port,
            use_ssl=self._s.ldap_use_ssl,
            tls=tls,
            # get_info=ALL would fetch the RootDSE and the entire schema on
            # every open. Nothing here reads server.info.
            get_info=NONE,
            connect_timeout=self._s.ldap_timeout_seconds,
        )
