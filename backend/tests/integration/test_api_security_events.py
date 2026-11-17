"""
The security log through the API with the real repositories: logins and
their refusals, throttle locks, logout, account and permission changes,
groups and tokens are recorded once each, in a request of their own and
read back through the admin settings route in another; attempts refused
while a lock holds are not recorded; the route needs read:settings; the
log retention leaves the table alone.
"""

from collections.abc import AsyncIterator
from collections.abc import Awaitable
from collections.abc import Callable
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy import text

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.bootstrap.main import app
from src.modules.platform.adapters.inbound.api.deps.services import get_mail_service
from src.modules.platform.adapters.outbound.persistence.models.security_event_model import (
    SecurityEventOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.retention_purger import (
    SqlAlchemyRetentionPurger,
)
from src.modules.platform.const import API_WEB
from src.modules.platform.domain.entities.admin_settings.security import AdminSecuritySettings
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import TEST_PASSWORD
from tests.integration.conftest import _new_client
from tests.integration.conftest import auth_headers

EVENTS = f"{API_WEB}/admin/settings/security-events"
LOGIN_URL = "/api/v1/auth/login/access-token"
LOGOUT_URL = "/api/v1/auth/logout"
CSRF_HEADER = {"X-Requested-With": "glados"}
ADMIN_PERMISSIONS = [Permission.READ_SETTINGS, Permission.WRITE_SETTINGS]

CreateUser = Callable[..., Awaitable[User]]


class _SilentMailService:
    async def send_welcome(self, **_: Any) -> None:
        return None


@pytest.fixture(autouse=True)
async def _security_settings(db: Any) -> None:
    """Logins read the security settings, which these tests seed with 2FA
    off and the shipped lockout of five attempts."""
    await db.execute(text("DELETE FROM admin_security_settings"))
    await db.commit()
    await SqlAlchemyAdminSettingsRepository(db).save_security(
        AdminSecuritySettings(
            id=1,
            enforce_totp=False,
            allow_rfid_login=True,
            allow_local_login=True,
            enable_api_key_auth=False,
            min_password_length=8,
            session_timeout_minutes=0,
            totp_trusted_device_days=0,
            max_login_attempts=5,
            lockout_duration_minutes=15,
            token_max_lifetime_days=0,
        )
    )
    await db.commit()


@pytest.fixture
async def admin(create_user: CreateUser) -> AsyncIterator[httpx.AsyncClient]:
    user = await create_user(
        username="admin", email="admin@example.com", permissions=ADMIN_PERMISSIONS
    )
    async with _new_client() as c:
        c.headers.update(await auth_headers(user))
        yield c


@pytest.fixture
def silent_mail() -> AsyncIterator[None]:
    app.dependency_overrides[get_mail_service] = _SilentMailService
    yield None
    app.dependency_overrides.pop(get_mail_service, None)


async def _login(client: httpx.AsyncClient, username: str, password: str) -> httpx.Response:
    return await client.post(
        LOGIN_URL,
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )


async def _events(admin: httpx.AsyncClient, **params: Any) -> list[dict[str, Any]]:
    response = await admin.get(EVENTS, params=params)
    assert response.status_code == 200, response.text
    return list(response.json()["items"])


async def test_a_login_and_a_refused_login_are_recorded(
    client: httpx.AsyncClient, admin: httpx.AsyncClient, create_user: CreateUser
) -> None:
    tester = await create_user()

    assert (await _login(client, "tester", "wrong")).status_code == 401
    assert (await _login(client, "tester", TEST_PASSWORD)).status_code == 200

    success, failure = await _events(admin, event_type="login")
    assert success["outcome"] == "success"
    assert success["detail"] == {"method": "password"}
    assert success["actor_user_id"] == tester.id
    assert success["actor_username"] == "tester"
    assert success["client_ip"] == "testclient"
    assert failure["outcome"] == "failure"
    assert failure["detail"] == {"method": "password", "reason": "invalid_credentials"}
    assert failure["target_user_id"] == tester.id


async def test_a_refused_login_with_an_unknown_name_names_nobody(
    client: httpx.AsyncClient, admin: httpx.AsyncClient
) -> None:
    assert (await _login(client, "nobody", "wrong")).status_code == 401

    (event,) = await _events(admin, event_type="login", outcome="failure")
    assert event["actor_user_id"] is None
    assert event["actor_username"] is None


async def test_a_lock_is_recorded_once_and_refused_attempts_are_not(
    client: httpx.AsyncClient, admin: httpx.AsyncClient, create_user: CreateUser, db: Any
) -> None:
    await create_user()
    await db.execute(text("UPDATE admin_security_settings SET max_login_attempts = 2"))
    await db.commit()

    for _ in range(2):
        assert (await _login(client, "tester", "wrong")).status_code == 401
    for _ in range(5):
        assert (await _login(client, "tester", "wrong")).status_code == 429

    assert len(await _events(admin, event_type="login")) == 2
    throttled = await _events(admin, event_type="login_throttled")
    assert sorted(e["detail"]["scope"] for e in throttled) == ["account", "account_on_address"]


async def test_logout_is_recorded(
    admin: httpx.AsyncClient, create_user: CreateUser, db: Any
) -> None:
    tester = await create_user()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app, client=("testclient", 50000)),
        base_url="https://testserver",
    ) as browser:
        assert (await _login(browser, "tester", TEST_PASSWORD)).status_code == 200
        assert (await browser.post(LOGOUT_URL, headers=CSRF_HEADER)).status_code == 200
        # A second logout has no live session left to end.
        await browser.post(LOGOUT_URL, headers=CSRF_HEADER)

    (event,) = await _events(admin, event_type="logout")
    assert event["actor_user_id"] == tester.id
    assert event["target_id"] is not None


async def test_account_and_permission_changes_are_recorded(
    admin: httpx.AsyncClient, silent_mail: None
) -> None:
    created = await admin.post(
        f"{API_WEB}/users/",
        json={
            "username": "newcomer",
            "full_name": "New Comer",
            "email": "newcomer@example.com",
            "password": "a-long-password",
        },
    )
    assert created.status_code == 201, created.text
    user_id = created.json()["id"]

    granted = await admin.put(
        f"{API_WEB}/users/{user_id}", json={"permissions": [Permission.WRITE_PAT]}
    )
    assert granted.status_code == 200, granted.text
    assert (await admin.delete(f"{API_WEB}/users/{user_id}")).status_code == 200
    reactivated = await admin.put(f"{API_WEB}/users/{user_id}", json={"is_active": True})
    assert reactivated.status_code == 200, reactivated.text

    events = await _events(admin, user_id=user_id)
    assert [e["event_type"] for e in events] == [
        "user_reactivated",
        "user_deactivated",
        "user_permissions_changed",
        "user_created",
    ]
    assert events[2]["detail"] == {"added": [Permission.WRITE_PAT], "removed": []}
    assert all(e["actor_username"] == "admin" for e in events)
    assert all(e["target_username"] == "newcomer" for e in events)


async def test_a_group_is_recorded_but_not_a_rename(
    admin: httpx.AsyncClient, create_user: CreateUser
) -> None:
    member = await create_user(username="member", email="member@example.com")
    created = await admin.post(
        f"{API_WEB}/user-groups",
        json={"name": "Planning", "permissions": [Permission.WRITE_PAT], "member_ids": []},
    )
    assert created.status_code == 201, created.text
    group_id = created.json()["id"]

    renamed = await admin.put(
        f"{API_WEB}/user-groups/{group_id}",
        json={"name": "Planners", "permissions": [Permission.WRITE_PAT], "member_ids": []},
    )
    assert renamed.status_code == 200, renamed.text
    joined = await admin.put(
        f"{API_WEB}/user-groups/{group_id}",
        json={"name": "Planners", "permissions": [], "member_ids": [member.id]},
    )
    assert joined.status_code == 200, joined.text

    changed, created_event = await _events(admin)
    assert created_event["event_type"] == "group_created"
    assert created_event["target_id"] == group_id
    assert changed["event_type"] == "group_changed"
    assert changed["detail"] == {
        "name": "Planners",
        "permissions_removed": [Permission.WRITE_PAT],
        "members_added": [member.id],
    }


async def test_a_token_is_recorded_when_created_and_revoked(
    admin: httpx.AsyncClient, create_user: CreateUser
) -> None:
    owner = await create_user(
        username="owner", email="owner@example.com", permissions=[Permission.WRITE_PAT]
    )
    async with _new_client() as c:
        c.headers.update(await auth_headers(owner))
        created = await c.post(
            f"{API_WEB}/users/me/personal-access-tokens/",
            json={"name": "CI", "password": TEST_PASSWORD},
        )
        assert created.status_code == 201, created.text
        pat_id = created.json()["id"]
        revoked = await c.post(f"{API_WEB}/users/me/personal-access-tokens/{pat_id}/revoke")
        assert revoked.status_code == 200, revoked.text
        # Revoking a revoked token changes nothing and records nothing.
        await c.post(f"{API_WEB}/users/me/personal-access-tokens/{pat_id}/revoke")

    events = await _events(admin, user_id=owner.id)
    assert [(e["event_type"], e["target_id"]) for e in events] == [
        ("pat_revoked", pat_id),
        ("pat_created", pat_id),
    ]
    assert events[1]["detail"]["name"] == "CI"


async def test_reading_the_log_needs_read_settings(
    auth_client: Callable[..., Awaitable[httpx.AsyncClient]],
) -> None:
    reader = await auth_client(permissions=[Permission.WRITE_PAT])

    assert (await reader.get(EVENTS)).status_code == 403


async def test_the_log_retention_leaves_the_security_log_alone(
    client: httpx.AsyncClient, create_user: CreateUser, db: Any
) -> None:
    await create_user()
    await _login(client, "tester", "wrong")

    purger = SqlAlchemyRetentionPurger(db)
    future = datetime.now(UTC) + timedelta(days=1)
    await purger.purge_logs_before(future)
    await purger.purge_audit_before(future)

    assert await db.scalar(select(func.count()).select_from(SecurityEventOrmModel)) == 1


async def test_an_api_key_and_a_terminal_key_are_told_apart(
    admin: httpx.AsyncClient, create_user: CreateUser
) -> None:
    keys = f"{API_WEB}/admin/api-keys"
    manager = await create_user(
        username="keys", email="keys@example.com", permissions=[Permission.MANAGE_API_KEYS]
    )
    async with _new_client() as c:
        c.headers.update(await auth_headers(manager))
        api_key = await c.post(f"{keys}/", json={"name": "CI Key"})
        terminal_key = await c.post(f"{keys}/terminal", json={"name": "Hall"})
        assert api_key.status_code == 201, api_key.text
        assert terminal_key.status_code == 201, terminal_key.text
        terminal_key_id = terminal_key.json()["id"]
        revoked = await c.post(f"{keys}/{terminal_key_id}/revoke")
        assert revoked.status_code == 200, revoked.text

    events = await _events(admin)
    assert [(e["event_type"], e["target_id"]) for e in events[:3]] == [
        ("terminal_key_revoked", terminal_key_id),
        ("terminal_key_created", terminal_key_id),
        ("api_key_created", api_key.json()["id"]),
    ]


async def test_an_own_password_change_and_a_wrong_current_password_are_recorded(
    admin: httpx.AsyncClient, create_user: CreateUser
) -> None:
    tester = await create_user()
    async with _new_client() as c:
        c.headers.update(await auth_headers(tester))
        refused = await c.put(
            f"{API_WEB}/users/me",
            json={"password": "a-new-password", "current_password": "wrong"},
        )
        assert refused.status_code >= 400
        changed = await c.put(
            f"{API_WEB}/users/me",
            json={"password": "a-new-password", "current_password": TEST_PASSWORD},
        )
        assert changed.status_code == 200, changed.text

    changed_event, refused_event = await _events(admin, user_id=tester.id)
    assert changed_event["event_type"] == "password_changed"
    assert changed_event["detail"]["by_self"] is True
    assert refused_event["event_type"] == "password_confirmation"
    assert refused_event["outcome"] == "failure"
