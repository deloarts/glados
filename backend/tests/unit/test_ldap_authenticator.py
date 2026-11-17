"""
Unit tests for the ldap3-backed directory authenticator. No network: the
Connection and Server classes are monkeypatched inside the adapter module.

The exception mapping is the security-critical part of this adapter, and it is
counter-intuitive in ldap3 2.9.1:

  - LDAPBindError (a wrong password) is NOT an LDAPCommunicationError
  - LDAPPasswordIsMandatoryError (an empty password) is NOT one either
  - LDAPResponseTimeoutError, LDAPStartTLSError and LDAPCertificateError are
    NOT LDAPCommunicationError, despite all being transport-ish failures

So `except LDAPCommunicationError` would miss real outages, and a bare
`except LDAPException -> unavailable` would classify an empty password as
"directory unreachable", which lets the caller fall back to the local
password. Both mistakes are pinned by tests here.
"""

import logging
import socket
import ssl
from typing import ClassVar

import pytest
from ldap3.core.exceptions import LDAPBindError
from ldap3.core.exceptions import LDAPCertificateError
from ldap3.core.exceptions import LDAPPasswordIsMandatoryError
from ldap3.core.exceptions import LDAPResponseTimeoutError
from ldap3.core.exceptions import LDAPSocketOpenError
from ldap3.core.exceptions import LDAPStartTLSError

from src.modules.platform.adapters.outbound.external.ldap import ldap3_authenticator as mod
from src.modules.platform.adapters.outbound.external.ldap.ldap3_authenticator import (
    Ldap3Authenticator,
)
from src.modules.platform.domain.entities.admin_settings.auth import AdminAuthSettings
from src.modules.platform.domain.exceptions import LdapNotConfiguredError
from src.modules.platform.domain.exceptions import LdapUnavailableError

# ── Helpers ───────────────────────────────────────────────────────────


def make_settings(**kwargs) -> AdminAuthSettings:
    defaults = dict(
        id=1,
        ldap_enabled=True,
        ldap_host="dc-01.example.com",
        ldap_port=636,
        ldap_use_ssl=True,
        ldap_start_tls=False,
        ldap_verify_certificate=False,
        ldap_domain="EXAMPLE",
        ldap_timeout_seconds=5,
    )
    defaults.update(kwargs)
    return AdminAuthSettings(**defaults)


class FakeConnection:
    """Records construction kwargs and whether unbind() was called."""

    instances: ClassVar[list["FakeConnection"]] = []

    def __init__(self, server, **kwargs) -> None:
        self.server = server
        self.kwargs = kwargs
        self.bound = True
        self.unbound = False
        FakeConnection.instances.append(self)

    def unbind(self) -> None:
        self.unbound = True


class FakeServer:
    instances: ClassVar[list["FakeServer"]] = []

    def __init__(self, host, **kwargs) -> None:
        self.host = host
        self.kwargs = kwargs
        FakeServer.instances.append(self)


@pytest.fixture(autouse=True)
def _reset_fakes(monkeypatch):
    FakeConnection.instances = []
    FakeServer.instances = []
    monkeypatch.setattr(mod, "Connection", FakeConnection)
    monkeypatch.setattr(mod, "Server", FakeServer)
    yield


def raising_connection(exc: Exception):
    """A Connection replacement whose constructor raises."""

    def _factory(server, **kwargs):
        raise exc

    return _factory


# ── Credential rejection (must NOT be treated as unavailable) ─────────


class TestRejectsCredentials:
    async def test_bind_error_returns_false(self, monkeypatch):
        """A wrong password. The single most important mapping: returning
        False (not raising) is what stops the caller falling back to the
        local hash."""
        monkeypatch.setattr(mod, "Connection", raising_connection(LDAPBindError("bad creds")))
        assert await Ldap3Authenticator(make_settings()).authenticate("alice", "wrong") is False

    async def test_bind_error_logs_at_warning_not_info(self, monkeypatch, glados_caplog):
        """A rejected bind is the same class of event as the
        malformed-request branch (already WARNING) and as
        authenticate_user.py's own log line for the same rejection; all
        three should be filterable together at the log viewer's WARNING
        level, not split across INFO and WARNING."""
        monkeypatch.setattr(mod, "Connection", raising_connection(LDAPBindError("bad creds")))

        await Ldap3Authenticator(make_settings()).authenticate("alice", "wrong")

        (record,) = [r for r in glados_caplog.records if r.name == "glados"]
        assert record.levelno == logging.WARNING

    async def test_password_is_mandatory_returns_false(self, monkeypatch):
        """Regression guard: LDAPPasswordIsMandatoryError is an
        LDAPExceptionError but NOT an LDAPCommunicationError, so a naive
        catch-all would call this a transport failure and fall back."""
        monkeypatch.setattr(
            mod, "Connection", raising_connection(LDAPPasswordIsMandatoryError("no password"))
        )
        assert await Ldap3Authenticator(make_settings()).authenticate("alice", "pw") is False

    async def test_empty_password_never_opens_a_connection(self):
        assert await Ldap3Authenticator(make_settings()).authenticate("alice", "") is False
        assert FakeConnection.instances == []

    async def test_empty_username_never_opens_a_connection(self):
        assert await Ldap3Authenticator(make_settings()).authenticate("", "pw") is False
        assert FakeConnection.instances == []

    async def test_username_with_backslash_never_opens_a_connection(self):
        """A backslash would let the username rewrite the domain half of the
        bind name."""
        assert await Ldap3Authenticator(make_settings()).authenticate("OTHER\\alice", "pw") is False
        assert FakeConnection.instances == []

    async def test_username_with_null_byte_never_opens_a_connection(self):
        assert await Ldap3Authenticator(make_settings()).authenticate("ali\x00ce", "pw") is False
        assert FakeConnection.instances == []


# ── Transport failure (must NOT be treated as a rejection) ────────────


class TestUnavailable:
    @pytest.mark.parametrize(
        "exc",
        [
            LDAPSocketOpenError("refused"),
            LDAPResponseTimeoutError("timed out"),
            LDAPStartTLSError("starttls failed"),
            ssl.SSLError("handshake failed"),
            socket.gaierror("name resolution failed"),
        ],
        ids=["socket_open", "response_timeout", "start_tls", "ssl_error", "dns"],
    )
    async def test_transport_failures_raise_unavailable(self, monkeypatch, exc):
        monkeypatch.setattr(mod, "Connection", raising_connection(exc))
        with pytest.raises(LdapUnavailableError):
            await Ldap3Authenticator(make_settings()).authenticate("alice", "pw")

    async def test_certificate_error_is_unavailable_not_a_rejection(self, monkeypatch):
        """A bad certificate must never read as "wrong password", that would
        silently downgrade a MITM warning into a normal failed login."""
        monkeypatch.setattr(mod, "Connection", raising_connection(LDAPCertificateError("bad cert")))
        with pytest.raises(LdapUnavailableError):
            await Ldap3Authenticator(make_settings()).authenticate("alice", "pw")


# ── Configuration guards ──────────────────────────────────────────────


class TestConfiguration:
    async def test_missing_host_raises_not_configured(self):
        with pytest.raises(LdapNotConfiguredError):
            await Ldap3Authenticator(make_settings(ldap_host="")).authenticate("alice", "pw")

    async def test_missing_domain_raises_not_configured(self):
        with pytest.raises(LdapNotConfiguredError):
            await Ldap3Authenticator(make_settings(ldap_domain="")).authenticate("alice", "pw")


# ── Success path and wiring ───────────────────────────────────────────


class TestSuccess:
    async def test_successful_bind_returns_true(self):
        assert await Ldap3Authenticator(make_settings()).authenticate("alice", "pw") is True

    async def test_bind_name_is_domain_backslash_username(self):
        await Ldap3Authenticator(make_settings()).authenticate("alice", "pw")
        assert FakeConnection.instances[0].kwargs["user"] == "EXAMPLE\\alice"

    async def test_timeouts_are_applied_to_server_and_connection(self):
        await Ldap3Authenticator(make_settings(ldap_timeout_seconds=11)).authenticate("alice", "pw")
        assert FakeServer.instances[0].kwargs["connect_timeout"] == 11
        assert FakeConnection.instances[0].kwargs["receive_timeout"] == 11

    async def test_unbinds_on_success(self):
        await Ldap3Authenticator(make_settings()).authenticate("alice", "pw")
        assert FakeConnection.instances[0].unbound is True

    async def test_unbinds_on_rejection(self, monkeypatch):
        """A leaked socket per failed login is slow file-descriptor
        exhaustion; the previous implementation only unbinds on
        success."""
        calls: list[FakeConnection] = []

        class RejectingConnection(FakeConnection):
            def __init__(self, server, **kwargs):
                super().__init__(server, **kwargs)
                calls.append(self)
                self.bound = False

        monkeypatch.setattr(mod, "Connection", RejectingConnection)
        assert await Ldap3Authenticator(make_settings()).authenticate("alice", "pw") is False
        assert calls[0].unbound is True

    async def test_unbound_connection_reports_false(self, monkeypatch):
        class UnboundConnection(FakeConnection):
            def __init__(self, server, **kwargs):
                super().__init__(server, **kwargs)
                self.bound = False

        monkeypatch.setattr(mod, "Connection", UnboundConnection)
        assert await Ldap3Authenticator(make_settings()).authenticate("alice", "pw") is False

    async def test_verify_certificate_requires_a_valid_cert(self):
        await Ldap3Authenticator(make_settings(ldap_verify_certificate=True)).authenticate(
            "alice", "pw"
        )
        assert FakeServer.instances[0].kwargs["tls"].validate == ssl.CERT_REQUIRED

    async def test_verify_certificate_off_accepts_any_cert(self):
        await Ldap3Authenticator(make_settings(ldap_verify_certificate=False)).authenticate(
            "alice", "pw"
        )
        assert FakeServer.instances[0].kwargs["tls"].validate == ssl.CERT_NONE

    async def test_start_tls_selects_the_starttls_bind_mode(self):
        await Ldap3Authenticator(make_settings(ldap_start_tls=True)).authenticate("alice", "pw")
        assert FakeConnection.instances[0].kwargs["auto_bind"] == mod.AUTO_BIND_TLS_BEFORE_BIND

    async def test_without_start_tls_uses_the_plain_bind_mode(self):
        await Ldap3Authenticator(make_settings(ldap_start_tls=False)).authenticate("alice", "pw")
        assert FakeConnection.instances[0].kwargs["auto_bind"] == mod.AUTO_BIND_NO_TLS

    async def test_server_info_is_not_fetched(self):
        """get_info=ALL would pull the RootDSE and the whole schema on every
        login. Nothing here reads server.info."""
        await Ldap3Authenticator(make_settings()).authenticate("alice", "pw")
        assert FakeServer.instances[0].kwargs["get_info"] == mod.NONE

    async def test_connection_is_read_only(self):
        await Ldap3Authenticator(make_settings()).authenticate("alice", "pw")
        assert FakeConnection.instances[0].kwargs["read_only"] is True
