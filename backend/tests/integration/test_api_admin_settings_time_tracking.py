"""
The /admin/settings/time-tracking surface end to end: reading and writing
the service settings (URL rules, the write-only API key, the audit entries
naming a service change and an API key change, a changed service clearing
the confirmed key), the connection test, the key confirmation, the list of
users with stored credentials, the purge of every stored credential, and
the time tracking flags on /host/capabilities. No service is contacted; a
fake provider is swapped in through app.dependency_overrides, with
synthetic values only.
"""

import pytest

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.bootstrap.main import app
from src.modules.operations.adapters.inbound.api.deps.services import (
    get_time_tracking_provider_factory,
)
from src.modules.operations.adapters.outbound.persistence.repositories.time_tracking_credentials_repository import (
    SqlAlchemyUserTimeTrackingCredentialsRepository,
)
from src.modules.operations.domain.errors import TimeTrackingUnavailableError
from src.modules.platform.domain.entities.admin_settings.features import AdminFeatureSettings
from src.modules.platform.domain.entities.admin_settings.mail import AdminMailSettings
from src.modules.platform.domain.entities.admin_settings.security import AdminSecuritySettings
from src.modules.platform.domain.value_objects.permission import Permission
from tests.unit.time_tracking._helpers import API_KEY
from tests.unit.time_tracking._helpers import KEY_ID
from tests.unit.time_tracking._helpers import PUBLIC_KEY
from tests.unit.time_tracking._helpers import SERVICE_URL
from tests.unit.time_tracking._helpers import make_credentials
from tests.unit.time_tracking.fakes import FakeProvider

BASE = "/api/v1/web/admin/settings/time-tracking"
AUDIT = "/api/v1/web/admin/settings/audit"


@pytest.fixture
def provider():
    fake = FakeProvider()
    app.dependency_overrides[get_time_tracking_provider_factory] = lambda: fake.factory
    yield fake
    app.dependency_overrides.pop(get_time_tracking_provider_factory, None)


async def configure(client) -> None:
    resp = await client.put(BASE, json={"service_url": SERVICE_URL, "api_key": API_KEY})
    assert resp.status_code == 200, resp.text


async def test_get_returns_the_disabled_defaults(auth_client) -> None:
    client = await auth_client(permissions=[Permission.READ_SETTINGS])

    resp = await client.get(BASE)

    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is False
    assert body["service_url"] == ""
    assert body["api_key_configured"] is False
    assert body["is_configured"] is False and body["is_ready"] is False
    assert body["credential_holders"] == []


async def test_reading_and_writing_need_their_permissions(auth_client) -> None:
    nobody = await auth_client(permissions=[])
    reader = await auth_client(
        permissions=[Permission.READ_SETTINGS], username="reader", email="reader@example.com"
    )

    assert (await nobody.get(BASE)).status_code == 403
    assert (await reader.put(BASE, json={"enabled": False})).status_code == 403
    assert (await reader.post(f"{BASE}/test", json={})).status_code == 403
    assert (
        await reader.post(f"{BASE}/confirm-key", json={"credential_key_id": KEY_ID})
    ).status_code == 403
    assert (await reader.delete(f"{BASE}/credentials")).status_code == 403


async def test_put_stores_the_api_key_write_only_and_audits_the_change(auth_client) -> None:
    client = await auth_client(permissions=Permission.ALL)

    resp = await client.put(
        BASE,
        json={
            "enabled": True,
            "service_url": " http://time-tracking.example.test:3100/ ",
            "api_key": API_KEY,
            "privacy_policy_url": "https://intranet.example.test/privacy",
        },
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["service_url"] == SERVICE_URL
    assert body["api_key_configured"] is True
    assert body["enabled"] is True and body["is_configured"] is True
    assert body["is_ready"] is False
    assert API_KEY not in resp.text
    assert API_KEY not in (await client.get(BASE)).text
    audit = (await client.get(AUDIT, params={"settings_domain": "time_tracking"})).json()
    assert audit["total"] == 1
    summary = audit["items"][0]["summary"]
    assert f"(none) to {SERVICE_URL}" in summary and "API key changed" in summary
    assert API_KEY not in summary


async def test_an_empty_api_key_clears_it_and_an_omitted_one_keeps_it(auth_client) -> None:
    client = await auth_client(permissions=Permission.ALL)
    await configure(client)

    kept = await client.put(BASE, json={"privacy_policy_url": ""})
    cleared = await client.put(BASE, json={"api_key": ""})

    assert kept.json()["api_key_configured"] is True
    assert cleared.json()["api_key_configured"] is False


async def test_enabling_without_url_or_key_is_refused(auth_client) -> None:
    client = await auth_client(permissions=Permission.ALL)

    resp = await client.put(BASE, json={"enabled": True, "service_url": SERVICE_URL})

    assert resp.status_code == 400
    assert resp.json()["code"] == "TimeTrackingNotConfiguredError"


async def test_a_validation_error_never_echoes_the_api_key(auth_client) -> None:
    client = await auth_client(permissions=Permission.ALL)

    resp = await client.put(BASE, json={"api_key": API_KEY, "service_url": "ftp://x"})

    assert resp.status_code == 422
    assert API_KEY not in resp.text


@pytest.mark.parametrize(
    "payload",
    [
        {"service_url": "https://user:pw@time.example.test"},
        {"service_url": "https://time.example.test/?x=1"},
        {"service_url": "ftp://time.example.test"},
        {"privacy_policy_url": "javascript:alert(1)"},
    ],
)
async def test_invalid_values_are_rejected(auth_client, payload: dict[str, str]) -> None:
    client = await auth_client(permissions=Permission.ALL)

    assert (await client.put(BASE, json=payload)).status_code == 422


async def test_connection_test_reports_the_service_and_its_key(auth_client, provider) -> None:
    client = await auth_client(permissions=Permission.ALL)

    resp = await client.post(f"{BASE}/test", json={"service_url": SERVICE_URL, "api_key": API_KEY})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["provider_label"] == "Example Time"
    assert body["contract_supported"] is True and body["credential_fields_supported"] is True
    assert (body["credential_key_id"], body["credential_public_key"]) == (KEY_ID, PUBLIC_KEY)
    assert body["key_confirmed"] is False
    assert (body["server_version"], body["default_project"]) == ("1.200.0.1", "DEMO")
    assert provider.names() == ["info", "status"]
    assert provider.connections[0].service_url == SERVICE_URL
    # Nothing was saved.
    assert (await client.get(BASE)).json()["service_url"] == ""


async def test_connection_test_warns_about_an_unsupported_contract(auth_client, provider) -> None:
    client = await auth_client(permissions=Permission.ALL)
    provider.contract_version = "9.0"
    await configure(client)

    body = (await client.post(f"{BASE}/test", json={})).json()

    assert body["contract_supported"] is False


async def test_connection_test_needs_url_and_key(auth_client, provider) -> None:
    client = await auth_client(permissions=Permission.ALL)

    resp = await client.post(f"{BASE}/test", json={"service_url": SERVICE_URL})

    assert resp.json()["code"] == "TimeTrackingNotConfiguredError"
    assert provider.calls == []


async def test_unreachable_service_is_a_503(auth_client, provider) -> None:
    client = await auth_client(permissions=Permission.ALL)
    provider.fail_on = {"info": TimeTrackingUnavailableError("down")}

    resp = await client.post(f"{BASE}/test", json={"service_url": SERVICE_URL, "api_key": API_KEY})

    assert resp.status_code == 503
    assert resp.json()["code"] == "TimeTrackingUnavailableError"


async def test_confirming_the_key_makes_time_tracking_ready_and_is_audited(
    auth_client, provider
) -> None:
    client = await auth_client(permissions=Permission.ALL)
    await configure(client)
    await client.put(BASE, json={"enabled": True})

    resp = await client.post(f"{BASE}/confirm-key", json={"credential_key_id": KEY_ID})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert (body["credential_key_id"], body["credential_public_key"]) == (KEY_ID, PUBLIC_KEY)
    assert body["provider_label"] == "Example Time"
    assert body["is_ready"] is True
    assert (await client.post(f"{BASE}/test", json={})).json()["key_confirmed"] is True
    audit = (await client.get(AUDIT, params={"settings_domain": "time_tracking"})).json()
    assert f"credential key {KEY_ID} confirmed" in audit["items"][0]["summary"]


async def test_a_key_that_changed_since_the_test_is_not_confirmed(auth_client, provider) -> None:
    client = await auth_client(permissions=Permission.ALL)
    await configure(client)

    resp = await client.post(f"{BASE}/confirm-key", json={"credential_key_id": "another-key-id"})

    assert resp.status_code == 409
    assert resp.json()["code"] == "TimeTrackingKeyChangedError"
    assert (await client.get(BASE)).json()["credential_key_id"] is None


async def test_a_changed_service_url_clears_the_confirmed_key(auth_client, provider) -> None:
    client = await auth_client(permissions=Permission.ALL)
    await configure(client)
    await client.post(f"{BASE}/confirm-key", json={"credential_key_id": KEY_ID})

    body = (await client.put(BASE, json={"service_url": "http://other.example.test"})).json()

    assert body["credential_key_id"] is None and body["credential_public_key"] is None
    assert body["is_ready"] is False


async def test_the_holders_list_names_users_and_their_state_only(
    auth_client, create_user, db
) -> None:
    client = await auth_client(permissions=Permission.ALL)
    repo = SqlAlchemyUserTimeTrackingCredentialsRepository(db)
    user = await create_user(username="worker", email="w@example.com")
    await repo.save(make_credentials(user_id=user.id, id=0, time_tracking_user="secret.name"))
    await db.commit()

    resp = await client.get(BASE)

    holders = resp.json()["credential_holders"]
    assert [(h["user_id"], h["username"]) for h in holders] == [(user.id, "worker")]
    # No confirmed key yet, so the stored credentials cannot be used.
    assert holders[0]["credentials_valid"] is False
    assert holders[0]["credentials_invalid_reason"] == "binding_changed"
    assert "secret.name" not in resp.text


async def test_purge_deletes_every_stored_credential_and_audits_the_count(
    auth_client, create_user, db
) -> None:
    client = await auth_client(permissions=Permission.ALL)
    repo = SqlAlchemyUserTimeTrackingCredentialsRepository(db)
    for index in range(2):
        user = await create_user(username=f"worker{index}", email=f"w{index}@example.com")
        await repo.save(
            make_credentials(user_id=user.id, id=0, time_tracking_user_fingerprint=f"fp-{index}")
        )
    await db.commit()
    assert len((await client.get(BASE)).json()["credential_holders"]) == 2

    resp = await client.delete(f"{BASE}/credentials")

    assert resp.status_code == 200
    assert resp.json() == {"deleted": 2}
    assert await repo.get_count() == 0
    audit = (await client.get(AUDIT, params={"settings_domain": "time_tracking"})).json()
    assert "(2 removed)" in audit["items"][0]["summary"]


async def _seed_capability_domains(db) -> None:
    """/host/capabilities also reads mail, features and security, which the
    integration conftest does not seed."""
    repo = SqlAlchemyAdminSettingsRepository(db)
    await repo.save_mail(
        AdminMailSettings(
            id=1,
            enabled=False,
            host="",
            port=587,
            user="",
            password=None,
            from_address=None,
            use_tls=True,
            use_ssl=False,
            verify_certificate=True,
            from_display_name="",
            reply_to=None,
            send_limit_per_hour=20,
            send_lock_minutes=60,
            alert_recipients=[],
        )
    )
    await repo.save_features(
        AdminFeatureSettings(
            id=1,
            enable_email_notifications=True,
            enable_production_planning=True,
            allow_private_webhooks=False,
        )
    )
    await repo.save_security(
        AdminSecuritySettings(
            id=1,
            enforce_totp=False,
            allow_rfid_login=True,
            allow_local_login=True,
            enable_api_key_auth=False,
            min_password_length=8,
            session_timeout_minutes=1440,
            totp_trusted_device_days=30,
            max_login_attempts=5,
            lockout_duration_minutes=15,
            token_max_lifetime_days=3650,
        )
    )
    await db.commit()


async def test_capabilities_report_time_tracking_once_ready(auth_client, db, provider) -> None:
    await _seed_capability_domains(db)
    admin = await auth_client(permissions=Permission.ALL)
    plain = await auth_client(permissions=[], username="plain", email="plain@example.com")

    before = (await plain.get("/api/v1/web/host/capabilities")).json()["features"]
    await admin.put(BASE, json={"enabled": True, "service_url": SERVICE_URL, "api_key": API_KEY})
    enabled = (await plain.get("/api/v1/web/host/capabilities")).json()["features"]
    await admin.post(f"{BASE}/confirm-key", json={"credential_key_id": KEY_ID})
    ready = (await plain.get("/api/v1/web/host/capabilities")).json()["features"]

    assert before["time_tracking"] is False and before["time_tracking_provider_label"] is None
    assert enabled["time_tracking"] is False
    assert ready["time_tracking"] is True
    assert ready["time_tracking_provider_label"] == "Example Time"
