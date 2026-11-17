"""
The /admin/settings/auth surface: read, write, and the LDAP connection probe.

The probe's three verdicts must stay distinguishable end-to-end, "wrong
password" and "cannot reach the server" call for completely different fixes,
and collapsing them into one status is the easiest way to make this endpoint
useless.
"""

import pytest
from sqlalchemy import text

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.bootstrap.main import app
from src.modules.platform.adapters.inbound.api.deps.services import get_ldap_authenticator_factory
from src.modules.platform.domain.entities.admin_settings.auth import AdminAuthSettings
from src.modules.platform.domain.exceptions import LdapUnavailableError
from src.modules.platform.domain.value_objects.permission import Permission

BASE = "/api/v1/web/admin/settings/auth"


class FakeLdapAuthenticator:
    def __init__(self, verdict: bool | Exception = True) -> None:
        self.verdict = verdict

    async def authenticate(self, username: str, password: str) -> bool:
        if isinstance(self.verdict, Exception):
            raise self.verdict
        return self.verdict


@pytest.fixture
async def seeded_auth(db):
    """get_auth() raises when unseeded, and the integration schema is built
    from ORM metadata without ever running InitDatabase."""
    await db.execute(text("DELETE FROM admin_auth_settings"))
    await db.commit()
    await SqlAlchemyAdminSettingsRepository(db).save_auth(
        AdminAuthSettings(
            id=1,
            ldap_enabled=False,
            ldap_host="",
            ldap_port=636,
            ldap_use_ssl=True,
            ldap_start_tls=False,
            ldap_verify_certificate=False,
            ldap_domain="",
            ldap_timeout_seconds=5,
        )
    )
    await db.commit()


@pytest.fixture
def directory():
    fake = FakeLdapAuthenticator()
    app.dependency_overrides[get_ldap_authenticator_factory] = lambda: lambda settings: fake
    yield fake
    app.dependency_overrides.pop(get_ldap_authenticator_factory, None)


def _payload(**kwargs) -> dict:
    body = {
        "ldap_enabled": True,
        "ldap_host": "dc-01.example.com",
        "ldap_port": 636,
        "ldap_use_ssl": True,
        "ldap_start_tls": False,
        "ldap_verify_certificate": False,
        "ldap_domain": "EXAMPLE",
        "ldap_timeout_seconds": 5,
    }
    body.update(kwargs)
    return body


# ── Access control ────────────────────────────────────────────────────


class TestAccessControl:
    async def test_read_requires_authentication(self, client, seeded_auth):
        assert (await client.get(BASE)).status_code == 401

    async def test_read_requires_read_settings(self, auth_client, seeded_auth):
        assert (await (await auth_client(permissions=[])).get(BASE)).status_code == 403

    async def test_write_requires_write_settings(self, auth_client, seeded_auth):
        client = await auth_client(permissions=[Permission.READ_SETTINGS])
        assert (await client.put(BASE, json=_payload())).status_code == 403

    async def test_probe_requires_write_settings(self, auth_client, seeded_auth, directory):
        client = await auth_client(permissions=[Permission.READ_SETTINGS])
        body = _payload(username="admin", password="secret")
        assert (await client.post(f"{BASE}/ldap/test", json=body)).status_code == 403


# ── Read / write round trip ───────────────────────────────────────────


class TestReadWrite:
    async def test_reads_the_seeded_defaults(self, auth_client, seeded_auth):
        client = await auth_client(permissions=[Permission.READ_SETTINGS])
        body = (await client.get(BASE)).json()

        assert body["ldap_enabled"] is False
        assert body["ldap_port"] == 636

    async def test_put_then_get_round_trips_every_field(self, auth_client, seeded_auth):
        client = await auth_client(permissions=Permission.ALL)
        sent = _payload(ldap_port=389, ldap_use_ssl=False, ldap_start_tls=True)

        assert (await client.put(BASE, json=sent)).status_code == 200

        got = (await client.get(BASE)).json()
        for key, value in sent.items():
            assert got[key] == value, key

    async def test_no_secret_field_is_exposed(self, auth_client, seeded_auth):
        """Binding as the end user means this domain stores no secret at all,
        so unlike mail and storage there is no *_configured flag to leak."""
        client = await auth_client(permissions=[Permission.READ_SETTINGS])
        body = (await client.get(BASE)).json()

        assert not [k for k in body if "password" in k or "secret" in k]

    async def test_rejects_an_out_of_range_port(self, auth_client, seeded_auth):
        client = await auth_client(permissions=Permission.ALL)
        assert (await client.put(BASE, json=_payload(ldap_port=70000))).status_code == 422

    async def test_rejects_a_zero_timeout(self, auth_client, seeded_auth):
        """An unreachable DC holds a worker thread for this long on every
        login attempt, so it must stay bounded and non-zero."""
        client = await auth_client(permissions=Permission.ALL)
        assert (await client.put(BASE, json=_payload(ldap_timeout_seconds=0))).status_code == 422

    async def test_settings_change_is_audited(self, auth_client, seeded_auth):
        client = await auth_client(permissions=Permission.ALL)
        await client.put(BASE, json=_payload())

        audit = await client.get(
            "/api/v1/web/admin/settings/audit", params={"settings_domain": "auth"}
        )
        assert audit.status_code == 200
        assert audit.json()["total"] >= 1


# ── The probe's three verdicts ────────────────────────────────────────


class TestConnectionProbe:
    async def _post(self, client, **kwargs):
        body = _payload(username="admin", password="secret")
        body.update(kwargs)
        return await client.post(f"{BASE}/ldap/test", json=body)

    async def test_successful_bind_is_204(self, auth_client, seeded_auth, directory):
        directory.verdict = True
        client = await auth_client(permissions=Permission.ALL)

        assert (await self._post(client)).status_code == 204

    async def test_rejected_credentials_are_400(self, auth_client, seeded_auth, directory):
        directory.verdict = False
        client = await auth_client(permissions=Permission.ALL)

        assert (await self._post(client)).status_code == 400

    async def test_unreachable_directory_is_503(self, auth_client, seeded_auth, directory):
        """Distinct from 400 on purpose: "fix the password" and "fix the
        network" are different jobs."""
        directory.verdict = LdapUnavailableError("dc unreachable")
        client = await auth_client(permissions=Permission.ALL)

        assert (await self._post(client)).status_code == 503

    async def test_missing_password_is_400(self, auth_client, seeded_auth, directory):
        client = await auth_client(permissions=Permission.ALL)

        assert (await self._post(client, password="")).status_code == 400

    async def test_probing_does_not_persist_the_settings(self, auth_client, seeded_auth, directory):
        """The probe validates a candidate configuration; it must not enable
        LDAP as a side effect."""
        directory.verdict = True
        client = await auth_client(permissions=Permission.ALL)

        await self._post(client)

        assert (await client.get(BASE)).json()["ldap_enabled"] is False
