"""
The EPLAN Data Portal settings end to end (the token is write-only and
audited without its value, enabling needs a token, default article groups
must exist), the connection test against a fake portal swapped in through
app.dependency_overrides, and the supplier's Data Portal code (stored upper
case, unique among live suppliers, web-only).
"""

from typing import Any

import pytest

from src.bootstrap.main import app
from src.modules.external_data.adapters.inbound.api.deps.services import (
    get_eplan_data_portal_factory,
)
from src.modules.external_data.domain.errors import EdpAuthenticationFailedError
from src.modules.external_data.domain.value_objects.eplan_data_portal import EdpConnectionInfo
from src.modules.external_data.ports.outbound.eplan_data_portal_port import EdpConnection
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration._edit_versions import row_version

BASE = "/api/v1/web/admin/settings/eplan-data-portal"
AUDIT = "/api/v1/web/admin/settings/audit"
SUPPLIERS = "/api/v1/web/suppliers"


class _FakePortal:
    def __init__(self) -> None:
        self.connections: list[EdpConnection] = []
        self.accept = True

    def factory(self, connection: EdpConnection) -> "_FakePortal":
        self.connections.append(connection)
        return self

    async def test_connection(self) -> EdpConnectionInfo:
        if not self.accept:
            raise EdpAuthenticationFailedError("refused")
        return EdpConnectionInfo(authenticated=True)


@pytest.fixture
def portal() -> Any:
    fake = _FakePortal()
    app.dependency_overrides[get_eplan_data_portal_factory] = lambda: fake.factory
    yield fake
    app.dependency_overrides.pop(get_eplan_data_portal_factory, None)


async def test_edp_settings_default_to_off(auth_client) -> None:
    client = await auth_client(permissions=[Permission.READ_SETTINGS])

    body = (await client.get(BASE)).json()

    assert body["enabled"] is False
    assert body["pat_configured"] is False
    assert body["base_url"] == "https://dataportal.eplan.com/api"
    assert body["language"] == "de_DE"


async def test_edp_settings_store_the_token_write_only_and_audit_it(auth_client) -> None:
    client = await auth_client(permissions=Permission.ALL)

    resp = await client.put(BASE, json={"enabled": True, "pat": " secret-token "})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["enabled"] is True
    assert body["pat_configured"] is True
    assert "secret-token" not in resp.text
    audit = (await client.get(AUDIT, params={"settings_domain": "eplan_data_portal"})).json()
    assert "replaced" in audit["items"][0]["summary"]
    assert "secret-token" not in str(audit)


async def test_edp_settings_clearing_the_token_switches_off(auth_client) -> None:
    client = await auth_client(permissions=Permission.ALL)
    await client.put(BASE, json={"enabled": True, "pat": "secret-token"})

    body = (await client.put(BASE, json={"pat": ""})).json()

    assert (body["enabled"], body["pat_configured"]) == (False, False)


async def test_edp_settings_refuse_enabling_without_a_token_and_bad_input(auth_client) -> None:
    client = await auth_client(permissions=Permission.ALL)

    no_token = await client.put(BASE, json={"enabled": True})
    http_url = await client.put(BASE, json={"base_url": "http://portal.example.test/api"})
    unknown_group = await client.put(BASE, json={"default_article_group_ids": [999]})

    assert no_token.json()["code"] == "EdpSettingsInvalidError"
    assert http_url.json()["code"] == "EdpSettingsInvalidError"
    assert unknown_group.status_code == 404


async def test_edp_settings_need_their_permissions(auth_client) -> None:
    reader = await auth_client(permissions=[Permission.READ_SETTINGS])

    assert (await reader.put(BASE, json={"enabled": False})).status_code == 403
    assert (await reader.post(f"{BASE}/test", json={})).status_code == 403


async def test_edp_connection_test_uses_the_given_or_stored_token(auth_client, portal) -> None:
    client = await auth_client(permissions=Permission.ALL)

    without = await client.post(f"{BASE}/test", json={})
    assert without.json()["code"] == "EdpNotConfiguredError"

    await client.put(BASE, json={"pat": "stored-token"})
    stored = await client.post(f"{BASE}/test", json={})
    given = await client.post(f"{BASE}/test", json={"pat": "new-token"})

    assert stored.json() == {"authenticated": True}
    assert given.json() == {"authenticated": True}
    assert [c.pat for c in portal.connections] == ["stored-token", "new-token"]


async def test_edp_connection_test_reports_a_refused_token(auth_client, portal) -> None:
    client = await auth_client(permissions=Permission.ALL)
    portal.accept = False

    resp = await client.post(f"{BASE}/test", json={"pat": "bad"})

    assert resp.status_code == 400
    assert resp.json()["code"] == "EdpAuthenticationFailedError"


async def test_supplier_edp_code_is_upper_case_and_unique(auth_client) -> None:
    client = await auth_client(permissions=[Permission.WRITE_SUPPLIERS])

    siemens = await client.post(f"{SUPPLIERS}/", json={"name": "Siemens", "edp_code": " sie "})
    clash = await client.post(f"{SUPPLIERS}/", json={"name": "Other", "edp_code": "SIE"})
    bad = await client.post(f"{SUPPLIERS}/", json={"name": "Bad", "edp_code": "S I E"})

    assert siemens.status_code == 201, siemens.text
    assert siemens.json()["edp_code"] == "SIE"
    assert clash.status_code == 409
    assert clash.json()["code"] == "SupplierEdpCodeInUseError"
    assert bad.status_code == 400

    festo = (await client.post(f"{SUPPLIERS}/", json={"name": "Festo"})).json()
    moved = await client.put(
        f"{SUPPLIERS}/{festo['id']}",
        json={
            "expected_edit_version": await row_version(client, f"{SUPPLIERS}/{festo['id']}"),
            "name": "Festo",
            "edp_code": "fes",
        },
    )
    assert moved.json()["edp_code"] == "FES"
