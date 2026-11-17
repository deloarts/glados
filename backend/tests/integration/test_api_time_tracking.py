"""
The /time-tracking/me/* surface and the user administration hooks end to
end, with the time tracking provider factory overridden by a fake so no
request leaves the process and all data is synthetic: time tracking not
available (409), saving credentials (the user name encrypted at rest, the
password only sealed for the service's key, verified first, never echoed,
not even in a 422 body), each user seeing only their own data, the re-entry
states (undecryptable, binding changed, rejected) answered without a 500
and without a call, the lockout after failed checks, the fetch cooldown, the
personal-account rule, and removal on deactivation or by an admin.
"""

from collections.abc import Iterator

import pytest
from sqlalchemy import text

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.bootstrap.main import app
from src.modules.operations.adapters.inbound.api.deps.services import (
    get_time_tracking_provider_factory,
)
from src.modules.operations.domain.errors import TimeTrackingBindingChangedError
from src.modules.operations.domain.services.time_tracking_rules import TIME_TRACKING_CONSENT_VERSION
from src.modules.operations.domain.services.time_tracking_rules import VERIFY_FAILURE_LIMIT
from src.modules.platform.adapters.inbound.api.deps.services import get_login_attempt_tracker
from src.modules.platform.adapters.outbound.persistence.repositories.user_repository import (
    SqlAlchemyUserRepository,
)
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.security.secret_box import ENCRYPTED_PREFIX
from tests.integration.conftest import auth_headers
from tests.unit.time_tracking._helpers import make_settings
from tests.unit.time_tracking._helpers import open_sealed
from tests.unit.time_tracking.fakes import FakeProvider
from tests.unit.time_tracking.fakes import FakeTracker

BASE = "/api/v1/web/time-tracking/me"
PASSWORD = "s3cret-Pw-ß"


@pytest.fixture
def provider() -> Iterator[FakeProvider]:
    fake = FakeProvider()
    app.dependency_overrides[get_time_tracking_provider_factory] = lambda: fake.factory
    yield fake
    app.dependency_overrides.pop(get_time_tracking_provider_factory, None)


@pytest.fixture(autouse=True)
def tracker(login_attempts) -> Iterator[FakeTracker]:
    """Replaces conftest's tracker fake with one that also claims, which
    the month and year cooldown needs."""
    fake = FakeTracker()
    app.dependency_overrides[get_login_attempt_tracker] = lambda: fake
    yield fake


@pytest.fixture
async def enabled(db) -> None:
    await SqlAlchemyAdminSettingsRepository(db).save_time_tracking(make_settings())
    await db.commit()


def payload(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "time_tracking_user": "jane.doe",
        "time_tracking_password": PASSWORD,
        "time_tracking_consent_version": TIME_TRACKING_CONSENT_VERSION,
    }
    values.update(overrides)
    return values


async def user_headers(create_user, name: str = "jane") -> tuple[int, dict[str, str]]:
    user = await create_user(username=name, email=f"{name}@example.com")
    return user.id, await auth_headers(user)


# ── time tracking not available ──────────────────────────────────────


async def test_every_route_answers_409_while_disabled(client, create_user, provider) -> None:
    _, headers = await user_headers(create_user)

    responses = [
        await client.get(f"{BASE}/account", headers=headers),
        await client.put(f"{BASE}/account", headers=headers, json=payload()),
        await client.post(f"{BASE}/account/check", headers=headers),
        await client.get(f"{BASE}/month", headers=headers, params={"month": "2026-09"}),
        await client.get(f"{BASE}/year", headers=headers, params={"year": 2026}),
    ]

    assert [r.status_code for r in responses] == [409] * 5
    assert {r.json()["code"] for r in responses} == {"TimeTrackingNotEnabledError"}
    assert provider.calls == []


# ── saving ───────────────────────────────────────────────────────────


async def test_save_verifies_stores_encrypted_and_never_returns_the_password(
    client, create_user, provider, enabled, db
) -> None:
    user_id, headers = await user_headers(create_user)

    resp = await client.put(f"{BASE}/account", headers=headers, json=payload())

    assert resp.status_code == 200, resp.text
    assert resp.headers["cache-control"] == "no-store"
    body = resp.json()
    assert PASSWORD not in resp.text
    assert body["time_tracking_user"] == "jane.doe"
    assert body["time_tracking_password_configured"] is True
    assert body["time_tracking_credentials_valid"] is True
    assert body["time_tracking_employee_name"] == "Doe, Jane"
    assert body["time_tracking_rights"] == {"days": False, "month": True, "year": True}
    assert body["time_tracking_provider_label"] == "Example Time"
    user, sealed = (
        await db.execute(
            text(
                "SELECT time_tracking_user, time_tracking_sealed_credentials "
                "FROM user_time_tracking_credentials WHERE user_id = :u"
            ),
            {"u": user_id},
        )
    ).one()
    assert user.startswith(ENCRYPTED_PREFIX) and "jane.doe" not in user
    assert PASSWORD not in sealed
    assert open_sealed(sealed) == {"user": "jane.doe", "password": PASSWORD}
    assert provider.calls == [("verify", (sealed,))]

    state = await client.get(f"{BASE}/account", headers=headers)
    assert state.json()["time_tracking_credentials_valid"] is True
    assert state.json()["time_tracking_employee_name"] is None
    assert state.json()["time_tracking_rights"] is None


async def test_rejected_credentials_store_nothing(client, create_user, provider, enabled) -> None:
    _, headers = await user_headers(create_user)
    provider.reject_credentials = True

    resp = await client.put(f"{BASE}/account", headers=headers, json=payload())

    assert resp.status_code == 400
    assert resp.json()["code"] == "TimeTrackingAuthenticationFailedError"
    state = (await client.get(f"{BASE}/account", headers=headers)).json()
    assert state["time_tracking_credentials_invalid_reason"] == "missing"


@pytest.mark.parametrize(
    "overrides",
    [
        {"time_tracking_user": "jane:doe"},
        {"time_tracking_password": PASSWORD + "\n"},
        {"time_tracking_password": PASSWORD * 40},
        {"time_tracking_consent_version": "not a number"},
    ],
)
async def test_a_422_never_echoes_the_password(
    client, create_user, provider, enabled, overrides: dict[str, object]
) -> None:
    _, headers = await user_headers(create_user)
    body = payload(**overrides)
    del body["time_tracking_user"]  # A missing field echoes the whole body by default.
    body.update({k: v for k, v in overrides.items() if k == "time_tracking_user"})

    resp = await client.put(f"{BASE}/account", headers=headers, json=body)

    assert resp.status_code == 422
    assert PASSWORD not in resp.text
    assert "s3cret" not in resp.text
    assert provider.calls == []


async def test_save_without_consent_is_refused(client, create_user, provider, enabled) -> None:
    _, headers = await user_headers(create_user)

    resp = await client.put(
        f"{BASE}/account", headers=headers, json=payload(time_tracking_consent_version=None)
    )

    assert resp.status_code == 400
    assert resp.json()["code"] == "TimeTrackingConsentRequiredError"
    assert provider.calls == []


async def test_one_time_tracking_user_per_glados_user(
    client, create_user, provider, enabled
) -> None:
    _, jane = await user_headers(create_user, "jane")
    _, john = await user_headers(create_user, "john")
    await client.put(f"{BASE}/account", headers=jane, json=payload())
    verifications = provider.names().count("verify")

    resp = await client.put(
        f"{BASE}/account", headers=john, json=payload(time_tracking_user="JANE.DOE")
    )

    assert resp.status_code == 409
    assert resp.json()["code"] == "TimeTrackingUserAlreadyLinkedError"
    assert "jane" not in resp.json()["detail"].replace("jane.doe", "")
    assert provider.names().count("verify") == verifications


async def test_failed_checks_lock_further_checks(client, create_user, provider, enabled) -> None:
    _, headers = await user_headers(create_user)
    provider.reject_credentials = True
    for _ in range(VERIFY_FAILURE_LIMIT):
        await client.put(f"{BASE}/account", headers=headers, json=payload())
    verifications = provider.names().count("verify")

    resp = await client.put(f"{BASE}/account", headers=headers, json=payload())

    assert resp.status_code == 429
    assert resp.json()["code"] == "TimeTrackingRateLimitedError"
    assert provider.names().count("verify") == verifications


async def test_shared_accounts_cannot_store_credentials(
    client, create_user, provider, enabled, db
) -> None:
    user = await create_user(username="floor", email="floor@example.com")
    user.is_shared_account = True
    await SqlAlchemyUserRepository(db).save(user)
    await db.commit()

    resp = await client.put(f"{BASE}/account", headers=await auth_headers(user), json=payload())

    assert resp.status_code == 409
    assert resp.json()["code"] == "TimeTrackingCredentialsNotAllowedError"
    assert provider.calls == []


# ── own data only ────────────────────────────────────────────────────


async def test_each_user_sees_only_their_own_data(client, create_user, provider, enabled) -> None:
    _, jane = await user_headers(create_user, "jane")
    _, john = await user_headers(create_user, "john")
    await client.put(f"{BASE}/account", headers=jane, json=payload())

    johns_state = (await client.get(f"{BASE}/account", headers=john)).json()
    johns_month = await client.get(f"{BASE}/month", headers=john, params={"month": "2026-09"})

    assert johns_state["time_tracking_user"] is None
    assert johns_state["time_tracking_credentials_invalid_reason"] == "missing"
    assert johns_month.status_code == 400
    assert johns_month.json()["code"] == "TimeTrackingCredentialsMissingError"
    verified = [args[0] for name, args in provider.calls if name == "verify"]
    assert len(verified) == 1
    assert open_sealed(str(verified[0]))["user"] == "jane.doe"


# ── month and year ───────────────────────────────────────────────────


async def test_month_and_year_are_fetched_live_and_not_cached(
    client, create_user, provider, enabled
) -> None:
    _, headers = await user_headers(create_user)
    await client.put(f"{BASE}/account", headers=headers, json=payload())

    month = await client.get(f"{BASE}/month", headers=headers, params={"month": "2026-09"})
    year = await client.get(f"{BASE}/year", headers=headers, params={"year": 2026})

    assert month.status_code == 200, month.text
    assert month.headers["cache-control"] == "no-store"
    body = month.json()
    assert body["month"] == "2026-09"
    assert [d["date"] for d in body["days"]] == ["2026-09-29", "2026-09-30"]
    assert body["days"][0]["worked_seconds"] == 30000
    assert body["accounts"][0]["short_name"] == "BAL"
    assert body["accounts"][0]["format"] == "duration_clock"
    assert body["rights"]["month"] is True
    assert year.status_code == 200, year.text
    assert year.json()["rights"]["year"] is True
    assert [name for name, _ in provider.calls] == ["verify", "month", "year"]


async def test_month_fetches_are_spaced(client, create_user, provider, enabled) -> None:
    _, headers = await user_headers(create_user)
    await client.put(f"{BASE}/account", headers=headers, json=payload())
    await client.get(f"{BASE}/month", headers=headers, params={"month": "2026-09"})

    again = await client.get(f"{BASE}/month", headers=headers, params={"month": "2026-08"})

    assert again.status_code == 429


@pytest.mark.parametrize("params", [{"month": "2026-13"}, {"month": "2026-9"}, {"month": "x"}, {}])
async def test_invalid_month_parameter_is_a_422(client, create_user, enabled, params) -> None:
    _, headers = await user_headers(create_user)

    assert (await client.get(f"{BASE}/month", headers=headers, params=params)).status_code == 422


async def test_future_month_is_refused(client, create_user, provider, enabled) -> None:
    _, headers = await user_headers(create_user)
    await client.put(f"{BASE}/account", headers=headers, json=payload())

    resp = await client.get(f"{BASE}/month", headers=headers, params={"month": "2099-01"})

    assert resp.status_code == 400
    assert resp.json()["code"] == "TimeTrackingPeriodInvalidError"


# ── re-entry states ──────────────────────────────────────────────────


async def test_undecryptable_credentials_ask_for_re_entry_instead_of_failing(
    client, create_user, provider, enabled, db
) -> None:
    user_id, headers = await user_headers(create_user)
    await client.put(f"{BASE}/account", headers=headers, json=payload())
    await db.execute(
        text(
            "UPDATE user_time_tracking_credentials SET time_tracking_user = :v WHERE user_id = :u"
        ),
        {"v": ENCRYPTED_PREFIX + "not-a-valid-token", "u": user_id},
    )
    await db.commit()
    calls = len(provider.calls)

    state = await client.get(f"{BASE}/account", headers=headers)
    month = await client.get(f"{BASE}/month", headers=headers, params={"month": "2026-09"})

    assert state.status_code == 200
    assert state.json()["time_tracking_credentials_valid"] is False
    assert state.json()["time_tracking_credentials_invalid_reason"] == "undecryptable"
    assert state.json()["time_tracking_user"] is None
    assert month.status_code == 400
    assert len(provider.calls) == calls


async def test_a_newly_confirmed_key_blocks_every_call_until_saved_again(
    client, create_user, provider, enabled, db
) -> None:
    _, headers = await user_headers(create_user)
    await client.put(f"{BASE}/account", headers=headers, json=payload())
    settings_repo = SqlAlchemyAdminSettingsRepository(db)
    await settings_repo.save_time_tracking(make_settings(credential_key_id="a-newer-key-id"))
    await db.commit()
    calls = len(provider.calls)

    state = (await client.get(f"{BASE}/account", headers=headers)).json()
    month = await client.get(f"{BASE}/month", headers=headers, params={"month": "2026-09"})
    keep_password = await client.put(
        f"{BASE}/account", headers=headers, json=payload(time_tracking_password=None)
    )

    assert state["time_tracking_credentials_invalid_reason"] == "binding_changed"
    assert month.status_code == 400 and "server or key has changed" in month.json()["detail"]
    assert keep_password.status_code == 400
    assert len(provider.calls) == calls

    resaved = await client.put(f"{BASE}/account", headers=headers, json=payload())
    assert resaved.json()["time_tracking_credentials_valid"] is True


async def test_a_binding_change_reported_by_the_service_drops_the_sealed_value(
    client, create_user, provider, enabled
) -> None:
    _, headers = await user_headers(create_user)
    await client.put(f"{BASE}/account", headers=headers, json=payload())
    provider.fail_on = {"month": TimeTrackingBindingChangedError("The binding changed.")}

    first = await client.get(f"{BASE}/month", headers=headers, params={"month": "2026-09"})
    calls = len(provider.calls)
    second = await client.post(f"{BASE}/account/check", headers=headers)
    state = (await client.get(f"{BASE}/account", headers=headers)).json()

    assert first.status_code == 400
    assert first.json()["code"] == "TimeTrackingBindingChangedError"
    assert second.status_code == 400
    assert len(provider.calls) == calls
    assert state["time_tracking_credentials_invalid_reason"] == "binding_changed"
    assert state["time_tracking_password_configured"] is False


async def test_a_rejection_stops_further_calls_until_saved_again(
    client, create_user, provider, enabled
) -> None:
    _, headers = await user_headers(create_user)
    await client.put(f"{BASE}/account", headers=headers, json=payload())
    provider.reject_credentials = True

    first = await client.get(f"{BASE}/month", headers=headers, params={"month": "2026-09"})
    calls = len(provider.calls)
    second = await client.post(f"{BASE}/account/check", headers=headers)
    state = (await client.get(f"{BASE}/account", headers=headers)).json()

    assert first.status_code == 400
    assert second.status_code == 400
    assert len(provider.calls) == calls
    assert state["time_tracking_credentials_invalid_reason"] == "auth_failed"


# ── removal ──────────────────────────────────────────────────────────


async def test_user_can_remove_their_credentials(client, create_user, provider, enabled) -> None:
    _, headers = await user_headers(create_user)
    await client.put(f"{BASE}/account", headers=headers, json=payload())

    resp = await client.delete(f"{BASE}/account", headers=headers)

    assert resp.status_code == 204
    state = (await client.get(f"{BASE}/account", headers=headers)).json()
    assert state["time_tracking_credentials_invalid_reason"] == "missing"


async def test_admin_conversion_needs_the_credentials_removed_first(
    client, create_user, auth_client, provider, enabled
) -> None:
    user_id, headers = await user_headers(create_user)
    await client.put(f"{BASE}/account", headers=headers, json=payload())
    admin = await auth_client(
        permissions=Permission.ALL, username="admin", email="admin@example.com"
    )

    refused = await admin.put(f"/api/v1/web/users/{user_id}", json={"is_shared_account": True})
    removed = await admin.delete(f"/api/v1/web/users/{user_id}/time-tracking-credentials")
    converted = await admin.put(f"/api/v1/web/users/{user_id}", json={"is_shared_account": True})

    assert refused.status_code == 409
    assert refused.json()["code"] == "TimeTrackingCredentialsNotAllowedError"
    assert removed.status_code == 204
    assert converted.status_code == 200


async def test_removing_another_users_credentials_needs_write_settings(
    client, create_user, provider, enabled
) -> None:
    jane_id, jane = await user_headers(create_user, "jane")
    _, john = await user_headers(create_user, "john")
    await client.put(f"{BASE}/account", headers=jane, json=payload())

    resp = await client.delete(
        f"/api/v1/web/users/{jane_id}/time-tracking-credentials", headers=john
    )

    assert resp.status_code == 403
    assert (await client.get(f"{BASE}/account", headers=jane)).json()[
        "time_tracking_credentials_valid"
    ]


async def test_deactivating_a_user_deletes_their_credentials(
    client, create_user, auth_client, provider, enabled, db
) -> None:
    user_id, headers = await user_headers(create_user)
    await client.put(f"{BASE}/account", headers=headers, json=payload())
    admin = await auth_client(
        permissions=Permission.ALL, username="admin", email="admin@example.com"
    )

    resp = await admin.delete(f"/api/v1/web/users/{user_id}")

    assert resp.status_code == 200
    remaining = (
        await db.execute(
            text("SELECT COUNT(*) FROM user_time_tracking_credentials WHERE user_id = :u"),
            {"u": user_id},
        )
    ).scalar()
    assert remaining == 0
