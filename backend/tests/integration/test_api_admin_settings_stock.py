"""
The /admin/settings/stock surface end to end: reading and writing the
service settings (URL rules, the write-only API key, the audit entries
naming a service change and an API key change), the permissions, and the
connection test. No service is contacted; a fake stock service is swapped
in through app.dependency_overrides, with synthetic values only.
"""

import pytest

from src.bootstrap.main import app
from src.modules.external_data.adapters.inbound.api.deps.services import get_stock_service_factory
from src.modules.external_data.domain.errors import StockServiceUnavailableError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.unit.stock_service.fakes import FakeStockService

BASE = "/api/v1/web/admin/settings/stock"
AUDIT = "/api/v1/web/admin/settings/audit"
SERVICE_URL = "http://stock.example.test:3200"
API_KEY = "test-stock-api-key"


@pytest.fixture
def service():
    fake = FakeStockService()
    app.dependency_overrides[get_stock_service_factory] = lambda: fake.factory
    yield fake
    app.dependency_overrides.pop(get_stock_service_factory, None)


async def test_get_returns_the_disabled_defaults(auth_client) -> None:
    client = await auth_client(permissions=[Permission.READ_SETTINGS])

    resp = await client.get(BASE)

    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is False
    assert body["service_url"] == ""
    assert body["api_key_configured"] is False
    assert body["is_configured"] is False and body["is_ready"] is False


async def test_reading_and_writing_need_their_permissions(auth_client) -> None:
    nobody = await auth_client(permissions=[])
    reader = await auth_client(
        permissions=[Permission.READ_SETTINGS], username="reader", email="reader@example.com"
    )

    assert (await nobody.get(BASE)).status_code == 403
    assert (await reader.put(BASE, json={"enabled": False})).status_code == 403
    assert (await reader.post(f"{BASE}/test", json={})).status_code == 403


async def test_put_stores_the_api_key_write_only_and_audits_the_change(auth_client) -> None:
    client = await auth_client(permissions=Permission.ALL)

    resp = await client.put(
        BASE,
        json={"enabled": True, "service_url": f" {SERVICE_URL}/ ", "api_key": API_KEY},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["service_url"] == SERVICE_URL
    assert body["api_key_configured"] is True
    assert body["is_ready"] is True
    assert API_KEY not in resp.text
    assert API_KEY not in (await client.get(BASE)).text
    audit = (await client.get(AUDIT, params={"settings_domain": "stock"})).json()
    assert audit["total"] == 1
    summary = audit["items"][0]["summary"]
    assert f"(none) to {SERVICE_URL}" in summary and "API key changed" in summary
    assert API_KEY not in summary


async def test_an_empty_api_key_clears_it_and_an_omitted_one_keeps_it(auth_client) -> None:
    client = await auth_client(permissions=Permission.ALL)
    await client.put(BASE, json={"service_url": SERVICE_URL, "api_key": API_KEY})

    kept = await client.put(BASE, json={"service_url": SERVICE_URL})
    cleared = await client.put(BASE, json={"api_key": ""})

    assert kept.json()["api_key_configured"] is True
    assert cleared.json()["api_key_configured"] is False


async def test_enabling_without_url_or_key_is_refused(auth_client) -> None:
    client = await auth_client(permissions=Permission.ALL)

    resp = await client.put(BASE, json={"enabled": True, "service_url": SERVICE_URL})

    assert resp.status_code == 400
    assert resp.json()["code"] == "StockServiceNotConfiguredError"


async def test_a_validation_error_never_echoes_the_api_key(auth_client) -> None:
    client = await auth_client(permissions=Permission.ALL)

    resp = await client.put(BASE, json={"api_key": API_KEY, "service_url": "ftp://x"})

    assert resp.status_code == 422
    assert API_KEY not in resp.text


@pytest.mark.parametrize(
    "service_url",
    [
        "https://user:pw@stock.example.test",
        "https://stock.example.test/?x=1",
        "ftp://stock.example.test",
    ],
)
async def test_invalid_service_urls_are_rejected(auth_client, service_url: str) -> None:
    client = await auth_client(permissions=Permission.ALL)

    assert (await client.put(BASE, json={"service_url": service_url})).status_code == 422


async def test_connection_test_reports_the_service(auth_client, service) -> None:
    client = await auth_client(permissions=Permission.ALL)

    resp = await client.post(f"{BASE}/test", json={"service_url": SERVICE_URL, "api_key": API_KEY})

    assert resp.status_code == 200, resp.text
    assert resp.json() == {
        "service": "stock-service-fake",
        "service_version": "0.1.0",
        "contract_version": "0.1",
        "contract_supported": True,
        "provider_label": "Example Stock",
        "server_version": "1.2.3",
    }
    assert service.calls == ["info", "status"]
    assert service.connections[0].service_url == SERVICE_URL
    assert (await client.get(BASE)).json()["service_url"] == ""


async def test_connection_test_uses_the_stored_settings(auth_client, service) -> None:
    client = await auth_client(permissions=Permission.ALL)
    await client.put(BASE, json={"service_url": SERVICE_URL, "api_key": API_KEY})

    resp = await client.post(f"{BASE}/test", json={})

    assert resp.status_code == 200, resp.text
    assert service.connections[0].service_url == SERVICE_URL
    assert service.connections[0].api_key == API_KEY


async def test_connection_test_warns_about_an_unsupported_contract(auth_client, service) -> None:
    client = await auth_client(permissions=Permission.ALL)
    service.contract_version = "9.0"

    resp = await client.post(f"{BASE}/test", json={"service_url": SERVICE_URL, "api_key": API_KEY})

    assert resp.status_code == 200
    assert resp.json()["contract_supported"] is False


async def test_connection_test_needs_url_and_key(auth_client, service) -> None:
    client = await auth_client(permissions=Permission.ALL)

    resp = await client.post(f"{BASE}/test", json={"service_url": SERVICE_URL})

    assert resp.status_code == 400
    assert resp.json()["code"] == "StockServiceNotConfiguredError"
    assert service.calls == []


async def test_unreachable_service_is_a_503(auth_client, service) -> None:
    client = await auth_client(permissions=Permission.ALL)
    service.fail_on = {"info": StockServiceUnavailableError("down")}

    resp = await client.post(f"{BASE}/test", json={"service_url": SERVICE_URL, "api_key": API_KEY})

    assert resp.status_code == 503
    assert resp.json()["code"] == "StockServiceUnavailableError"
