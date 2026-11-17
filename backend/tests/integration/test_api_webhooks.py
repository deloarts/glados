"""
HTTP-level coverage of /api/v1/web/admin/webhooks: admin
outbound-egress config (signed webhook subscriptions). Reads require
read:settings, writes require write:settings, both enforced inline in
manage_webhook_subscriptions.py rather than a dedicated *Rules class. The
signing secret is generated on create and appears exactly once, in the
create response; every other read path (list, update) omits it.

CreateWebhookSubscription/UpdateWebhookSubscription read
AdminFeatureSettings.allow_private_webhooks for every URL. That settings
domain isn't in conftest's autouse `_seed_admin_settings` fixture (only
General/Storage), so it's seeded here, with private targets off so the
tests can see that refusal. The target guard resolves hosts through a fake
resolver, so no test depends on real DNS.
"""

import pytest
from sqlalchemy.orm import Session

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.bootstrap.main import app
from src.modules.platform.adapters.inbound.api.deps.services import get_webhook_target_guard
from src.modules.platform.adapters.outbound.external.webhook.webhook_target_guard import (
    WebhookTargetGuard,
)
from src.modules.platform.domain.entities.admin_settings.features import AdminFeatureSettings

_ANSWERS = {"example.com": ["93.184.215.14"], "erp.corp.example": ["10.20.30.40"]}


async def _fake_resolve(host: str, port: int) -> list[str]:
    if host not in _ANSWERS:
        raise OSError(f"{host} does not resolve")
    return _ANSWERS[host]


@pytest.fixture(autouse=True)
def _fake_dns():
    app.dependency_overrides[get_webhook_target_guard] = lambda: WebhookTargetGuard(
        (), resolver=_fake_resolve
    )
    yield
    app.dependency_overrides.pop(get_webhook_target_guard, None)


@pytest.fixture(autouse=True)
async def _seed_feature_settings(db: Session) -> None:
    await SqlAlchemyAdminSettingsRepository(db).save_features(
        AdminFeatureSettings(
            id=1,
            enable_email_notifications=True,
            enable_production_planning=True,
            allow_private_webhooks=False,
        )
    )
    await db.commit()


async def _create(client, **overrides: object) -> dict:
    body = {
        "name": "Order events",
        "url": "https://example.com/hooks/glados",
        "event_types": ["*"],
        "is_active": True,
    } | overrides
    resp = await client.post("/api/v1/web/admin/webhooks/", json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def test_create_webhook_requires_write_settings(auth_client) -> None:
    client = await auth_client(permissions=["read:settings"])
    resp = await client.post(
        "/api/v1/web/admin/webhooks/",
        json={
            "name": "Order events",
            "url": "https://example.com/hooks",
            "event_types": ["*"],
        },
    )
    assert resp.status_code == 403


async def test_create_webhook_rejects_missing_url(auth_client) -> None:
    client = await auth_client(permissions=["write:settings"])
    resp = await client.post(
        "/api/v1/web/admin/webhooks/", json={"name": "Order events", "event_types": ["*"]}
    )
    assert resp.status_code == 422


async def test_create_and_list_webhook(auth_client) -> None:
    client = await auth_client(permissions=["write:settings", "read:settings"])
    created = await _create(client)
    # The secret is present exactly once, on the create response.
    assert "secret" in created
    assert created["name"] == "Order events"

    resp = await client.get("/api/v1/web/admin/webhooks/")
    assert resp.status_code == 200
    subs = resp.json()
    assert any(s["name"] == "Order events" for s in subs)
    assert all("secret" not in s for s in subs)


async def test_list_webhooks_requires_read_settings(auth_client) -> None:
    client = await auth_client(permissions=[])
    resp = await client.get("/api/v1/web/admin/webhooks/")
    assert resp.status_code == 403


async def test_update_missing_webhook_404(auth_client) -> None:
    client = await auth_client(permissions=["write:settings"])
    resp = await client.put(
        "/api/v1/web/admin/webhooks/999999",
        json={
            "name": "Renamed",
            "url": "https://example.com/hooks",
            "event_types": ["*"],
            "is_active": True,
        },
    )
    assert resp.status_code == 404


async def test_update_webhook(auth_client) -> None:
    client = await auth_client(permissions=["write:settings"])
    created = await _create(client)
    resp = await client.put(
        f"/api/v1/web/admin/webhooks/{created['id']}",
        json={
            "name": "Renamed",
            "url": "https://example.com/hooks/glados",
            "event_types": ["*"],
            "is_active": False,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Renamed"
    assert body["is_active"] is False
    assert "secret" not in body


async def test_update_webhook_is_persisted(auth_client) -> None:
    """Reads the edit back through a separate request, so an update that is
    never committed fails here."""
    client = await auth_client(permissions=["write:settings", "read:settings"])
    created = await _create(client)
    resp = await client.put(
        f"/api/v1/web/admin/webhooks/{created['id']}",
        json={
            "name": "Renamed",
            "url": "https://example.com/hooks/glados",
            "event_types": ["*"],
            "is_active": False,
        },
    )
    assert resp.status_code == 200

    listed = (await client.get("/api/v1/web/admin/webhooks/")).json()
    row = next(s for s in listed if s["id"] == created["id"])
    assert (row["name"], row["is_active"]) == ("Renamed", False)


async def test_create_webhook_rejects_private_network_url(auth_client) -> None:
    """A loopback literal is refused whatever the private target setting
    says."""
    client = await auth_client(permissions=["write:settings"])
    resp = await client.post(
        "/api/v1/web/admin/webhooks/",
        json={
            "name": "Internal",
            "url": "http://127.0.0.1:9999/hook",
            "event_types": ["*"],
            "is_active": True,
        },
    )
    assert resp.status_code == 400


@pytest.mark.parametrize("url", ["http://redis:6379/", "http://169.254.169.254/latest/meta-data/"])
async def test_create_webhook_refuses_stack_services_and_metadata(db, auth_client, url) -> None:
    await _allow_private(db)
    client = await auth_client(permissions=["write:settings"])
    resp = await client.post(
        "/api/v1/web/admin/webhooks/",
        json={"name": "Internal", "url": url, "event_types": ["*"], "is_active": True},
    )
    assert resp.status_code == 400
    assert "never sends webhooks to" in resp.text


async def test_a_private_host_follows_the_setting(db, auth_client) -> None:
    client = await auth_client(permissions=["write:settings", "read:settings"])
    body = {"name": "ERP", "url": "https://erp.corp.example/hook", "event_types": ["*"]}

    refused = await client.post("/api/v1/web/admin/webhooks/", json=body)
    assert refused.status_code == 400
    assert "private network" in refused.text

    await _allow_private(db)
    accepted = await client.post("/api/v1/web/admin/webhooks/", json=body)
    assert accepted.status_code == 201, accepted.text
    assert accepted.json()["secret"].startswith("whsec_")


async def _allow_private(db: Session) -> None:
    await SqlAlchemyAdminSettingsRepository(db).save_features(
        AdminFeatureSettings(
            id=1,
            enable_email_notifications=True,
            enable_production_planning=True,
            allow_private_webhooks=True,
        )
    )
    await db.commit()


async def test_delete_webhook(auth_client) -> None:
    client = await auth_client(permissions=["write:settings", "read:settings"])
    created = await _create(client)
    resp = await client.delete(f"/api/v1/web/admin/webhooks/{created['id']}")
    assert resp.status_code == 204

    remaining = (await client.get("/api/v1/web/admin/webhooks/")).json()
    assert all(s["id"] != created["id"] for s in remaining)
