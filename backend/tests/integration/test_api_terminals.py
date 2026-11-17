"""HTTP coverage of terminals end to end: terminal keys, the device sign-in
with its every refusal, approval and the admin actions, the device state and
feed, the separation of terminal and web credentials, and the terminal
fields of the security settings."""

from collections.abc import AsyncIterator
from collections.abc import Awaitable
from collections.abc import Callable
from datetime import UTC
from datetime import datetime
from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.main import app
from src.modules.operations.adapters.inbound.api.deps.services import get_terminal_auth_rate_limiter
from src.modules.operations.adapters.outbound.persistence.models.terminal_model import (
    TerminalOrmModel,
)
from src.modules.operations.application.services.terminal_auth_rate_limiter import (
    TerminalAuthRateLimiter,
)
from src.modules.platform.adapters.outbound.persistence.models.admin_settings_model.audit import (
    AdminSettingsAuditOrmModel,
)
from src.modules.platform.adapters.outbound.persistence.models.api_key_model import ApiKeyOrmModel
from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import TEST_PASSWORD
from tests.integration._terminal_helpers import DEVICE
from tests.integration._terminal_helpers import INFOSCREENS
from tests.integration._terminal_helpers import TERMINAL_KEYS
from tests.integration._terminal_helpers import TERMINALS
from tests.integration._terminal_helpers import Device
from tests.integration._terminal_helpers import device_client
from tests.integration._terminal_helpers import seed_production
from tests.integration._terminal_helpers import seed_security

ADMIN_PERMISSIONS = [
    Permission.MANAGE_API_KEYS,
    Permission.MANAGE_TERMINALS,
    Permission.WRITE_INFOSCREENS,
]


@pytest.fixture(autouse=True)
async def _settings(db: AsyncSession) -> None:
    await seed_security(db)
    await seed_production(db)


@pytest.fixture(autouse=True)
def _fresh_rate_limiter() -> AsyncIterator[None]:
    """The process-wide limiter would carry hits from test to test."""
    limiter = TerminalAuthRateLimiter()
    app.dependency_overrides[get_terminal_auth_rate_limiter] = lambda: limiter
    yield
    app.dependency_overrides.pop(get_terminal_auth_rate_limiter, None)


@pytest.fixture
async def admin(auth_client: Callable[..., Awaitable[httpx.AsyncClient]]) -> httpx.AsyncClient:
    return await auth_client(
        permissions=ADMIN_PERMISSIONS, username="admin", email="admin@example.com"
    )


@pytest.fixture
async def device_http() -> AsyncIterator[httpx.AsyncClient]:
    async with device_client() as client:
        yield client


@pytest.fixture
async def terminal_key(admin: httpx.AsyncClient) -> str:
    expires_at = (datetime.now(UTC) + timedelta(days=30)).isoformat()
    response = await admin.post(
        TERMINAL_KEYS, json={"name": "Hall displays", "expires_at": expires_at}
    )
    assert response.status_code == 201, response.text
    key: str = response.json()["key"]
    return key


async def _register(device: Device, client: httpx.AsyncClient, terminal_key: str) -> dict:
    response = await device.start_session(client, terminal_key)
    assert response.status_code == 200, response.text
    body: dict = response.json()
    return body


async def _screen(admin: httpx.AsyncClient, name: str = "Hall 1") -> int:
    response = await admin.post(
        INFOSCREENS,
        json={
            "name": name,
            "pages": [
                {"layout": "full", "slots": [{"type": "message", "text": "Hello hall"}]},
                {"layout": "two_columns", "slots": [{"type": "clock"}, None]},
            ],
        },
    )
    assert response.status_code == 201, response.text
    screen_id: int = response.json()["id"]
    return screen_id


async def _approve(admin: httpx.AsyncClient, state: dict, infoscreen_id: int | None) -> dict:
    response = await admin.post(
        f"{TERMINALS}/{state['terminal_id']}/approve",
        json={
            "pairing_code": state["pairing_code"],
            "name": "Hall display",
            "mode": "infoscreen",
            "infoscreen_id": infoscreen_id,
        },
    )
    assert response.status_code == 200, response.text
    body: dict = response.json()
    return body


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ── Terminal keys ─────────────────────────────────────────────────────


async def test_terminal_key_creation_grants_exactly_connect_terminals(
    admin: httpx.AsyncClient, db: AsyncSession
) -> None:
    response = await admin.post(
        TERMINAL_KEYS,
        json={"name": "Hall", "expires_at": (datetime.now(UTC) + timedelta(days=30)).isoformat()},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["permissions"] == [Permission.CONNECT_TERMINALS]
    assert body["kind"] == "terminal"
    assert body["key"]

    key = await db.scalar(select(ApiKeyOrmModel).where(ApiKeyOrmModel.id == body["id"]))
    assert key is not None
    user = await db.scalar(select(UserOrmModel).where(UserOrmModel.id == key.user_id))
    assert user is not None and user.permissions == [Permission.CONNECT_TERMINALS]
    audits = (await db.scalars(select(AdminSettingsAuditOrmModel))).all()
    assert any(a.settings_domain == "terminals" and "Hall" in a.summary for a in audits)

    listed = (await admin.get("/api/v1/web/admin/api-keys/")).json()["items"]
    assert [k["kind"] for k in listed] == ["terminal"]


async def test_terminal_key_needs_manage_api_keys(
    auth_client: Callable[..., Awaitable[httpx.AsyncClient]],
) -> None:
    client = await auth_client(permissions=[Permission.MANAGE_TERMINALS])
    response = await client.post(TERMINAL_KEYS, json={"name": "Hall"})
    assert response.status_code == 403


async def test_terminal_key_expiry_in_the_past_is_refused(admin: httpx.AsyncClient) -> None:
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    response = await admin.post(TERMINAL_KEYS, json={"name": "Hall", "expires_at": past})
    assert response.status_code == 422
    assert response.json()["code"] == "TokenExpiryInPastError"


async def test_terminal_connect_permission_cannot_go_on_a_normal_key_or_pat(
    auth_client: Callable[..., Awaitable[httpx.AsyncClient]],
) -> None:
    client = await auth_client(permissions=[*ADMIN_PERMISSIONS, Permission.CONNECT_TERMINALS])
    response = await client.post(
        "/api/v1/web/admin/api-keys/",
        json={"permissions": [Permission.CONNECT_TERMINALS], "name": "x"},
    )
    assert response.status_code == 403
    pat = await client.post(
        "/api/v1/web/users/me/personal-access-tokens/",
        json={
            "name": "x",
            "permissions": [Permission.CONNECT_TERMINALS],
            "password": TEST_PASSWORD,
        },
    )
    assert pat.status_code in (403, 422)


async def test_terminal_connect_permission_cannot_go_on_a_user(
    auth_client: Callable[..., Awaitable[httpx.AsyncClient]],
    create_user: Callable[..., Awaitable[object]],
) -> None:
    client = await auth_client(permissions=[Permission.WRITE_SETTINGS])
    person = await create_user(username="person", email="person@example.com")
    response = await client.put(
        f"/api/v1/web/users/{person.id}",  # type: ignore[attr-defined]
        json={"permissions": [Permission.WRITE_ORDERS, Permission.CONNECT_TERMINALS]},
    )
    assert response.status_code == 422, response.text
    assert response.json()["code"] == "TerminalPermissionNotAssignableError"


async def test_terminal_key_is_refused_on_the_key_router(terminal_key: str) -> None:
    async with device_client() as client:
        for method, path, body in (
            ("GET", "/api/v1/key/products/1", None),
            ("GET", "/api/v1/key/projects/1", None),
            ("POST", "/api/v1/key/users/rfid", {"rfid": "00000000"}),
        ):
            response = await client.request(
                method, path, json=body, headers={"X-Api-Key": terminal_key}
            )
            assert response.status_code == 403, (path, response.text)


# ── Device sign-in ────────────────────────────────────────────────────


async def test_terminal_unknown_device_registers_as_pending_with_a_terminal_key(
    device_http: httpx.AsyncClient, terminal_key: str, admin: httpx.AsyncClient
) -> None:
    body = await _register(Device(), device_http, terminal_key)
    state = body["state"]
    assert state["status"] == "pending"
    assert state["mode"] == "infoscreen"
    assert len(state["pairing_code"]) == 6
    assert body["access_token"]

    listed = (await admin.get(f"{TERMINALS}/")).json()
    assert len(listed) == 1
    assert listed[0]["api_key_name"] == "Hall displays"
    assert listed[0]["last_ip"] == "10.0.0.5"
    assert listed[0]["screen_width"] == 1920
    assert len(listed[0]["public_key_fingerprint"]) == 16


async def test_terminal_unknown_device_without_a_key_is_refused(
    device_http: httpx.AsyncClient,
) -> None:
    response = await Device().start_session(device_http)
    assert response.status_code == 401
    assert response.json()["code"] == "TerminalKeyRequiredError"


async def test_terminal_unknown_device_with_a_wrong_or_normal_key_is_refused(
    device_http: httpx.AsyncClient, admin: httpx.AsyncClient
) -> None:
    wrong = await Device().start_session(device_http, "glados_ak_not-a-key")
    assert wrong.status_code == 401
    assert wrong.json()["code"] == "InvalidTerminalKeyError"

    normal = await admin.post(
        "/api/v1/web/admin/api-keys/",
        json={"name": "normal", "permissions": [], "expires_in_days": 30},
    )
    assert normal.status_code == 201, normal.text
    refused = await Device().start_session(device_http, normal.json()["key"])
    assert refused.status_code == 403
    assert refused.json()["code"] == "NotATerminalKeyError"


async def test_terminal_known_device_needs_no_key_even_after_the_key_is_revoked(
    device_http: httpx.AsyncClient, terminal_key: str, admin: httpx.AsyncClient
) -> None:
    device = Device()
    await _register(device, device_http, terminal_key)
    key_id = (await admin.get("/api/v1/web/admin/api-keys/")).json()["items"][0]["id"]
    assert (await admin.post(f"/api/v1/web/admin/api-keys/{key_id}/revoke")).status_code == 200
    response = await device.start_session(device_http)
    assert response.status_code == 200, response.text


async def test_terminal_challenge_is_single_use(
    device_http: httpx.AsyncClient, terminal_key: str
) -> None:
    device = Device()
    nonce = await device.challenge(device_http)
    headers = {"X-Api-Key": terminal_key}
    first = await device_http.post(
        f"{DEVICE}/session", json=device.session_body(nonce), headers=headers
    )
    assert first.status_code == 200, first.text
    again = await device_http.post(
        f"{DEVICE}/session", json=device.session_body(nonce), headers=headers
    )
    assert again.status_code == 401
    assert again.json()["code"] == "TerminalChallengeError"


async def test_terminal_challenge_expires(
    device_http: httpx.AsyncClient, terminal_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.modules.operations.application.use_cases.terminal_device import start_session

    device = Device()
    nonce = await device.challenge(device_http)
    later = datetime.now(UTC) + timedelta(seconds=61)
    monkeypatch.setattr(start_session, "now_utc", lambda: later)
    response = await device_http.post(
        f"{DEVICE}/session", json=device.session_body(nonce), headers={"X-Api-Key": terminal_key}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "TerminalChallengeError"


async def test_terminal_challenge_of_another_key_and_a_bad_signature_are_refused(
    device_http: httpx.AsyncClient, terminal_key: str
) -> None:
    device, other = Device(), Device()
    headers = {"X-Api-Key": terminal_key}
    foreign_nonce = await other.challenge(device_http)
    response = await device_http.post(
        f"{DEVICE}/session", json=device.session_body(foreign_nonce), headers=headers
    )
    assert response.status_code == 401
    assert response.json()["code"] == "TerminalChallengeError"

    nonce = await device.challenge(device_http)
    forged = device.session_body(nonce, signature=other.sign(nonce))
    response = await device_http.post(f"{DEVICE}/session", json=forged, headers=headers)
    assert response.status_code == 401
    assert response.json()["code"] == "TerminalSignatureError"


async def test_terminal_challenge_refuses_a_malformed_public_key(
    device_http: httpx.AsyncClient,
) -> None:
    response = await device_http.post(f"{DEVICE}/challenge", json={"public_key": "abc"})
    assert response.status_code == 401
    assert response.json()["code"] == "TerminalChallengeError"


async def test_terminal_sign_in_refused_while_terminals_are_disabled(
    device_http: httpx.AsyncClient, db: AsyncSession
) -> None:
    await seed_security(db, enable_terminals=False)
    response = await device_http.post(
        f"{DEVICE}/challenge", json={"public_key": Device().public_key}
    )
    assert response.status_code == 403
    assert response.json()["code"] == "TerminalsDisabledError"


async def test_terminal_ip_allowlist(
    device_http: httpx.AsyncClient, db: AsyncSession, terminal_key: str
) -> None:
    device = Device()
    token = await device.token(device_http, terminal_key)
    await seed_security(db, terminal_allowed_ips=["192.168.0.0/16"])
    response = await device_http.post(f"{DEVICE}/challenge", json={"public_key": device.public_key})
    assert response.status_code == 403
    assert response.json()["code"] == "TerminalIpNotAllowedError"
    state = await device_http.get(f"{DEVICE}/state", headers=_bearer(token))
    assert state.status_code == 403

    async with device_client("192.168.4.20") as allowed:
        assert (await allowed.get(f"{DEVICE}/state", headers=_bearer(token))).status_code == 200


async def test_terminal_sign_in_is_rate_limited_per_address(
    device_http: httpx.AsyncClient,
) -> None:
    limiter = TerminalAuthRateLimiter(max_requests=2)
    app.dependency_overrides[get_terminal_auth_rate_limiter] = lambda: limiter
    body = {"public_key": Device().public_key}
    assert (await device_http.post(f"{DEVICE}/challenge", json=body)).status_code == 200
    assert (await device_http.post(f"{DEVICE}/challenge", json=body)).status_code == 200
    refused = await device_http.post(f"{DEVICE}/challenge", json=body)
    assert refused.status_code == 429
    assert refused.json()["code"] == "TerminalAuthRateLimitedError"
    async with device_client("10.0.0.6") as other:
        assert (await other.post(f"{DEVICE}/challenge", json=body)).status_code == 200


async def test_terminal_pending_cap(
    device_http: httpx.AsyncClient, terminal_key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from src.modules.operations.domain.services import terminal_rules

    monkeypatch.setattr(terminal_rules, "MAX_PENDING_TERMINALS", 1)
    await _register(Device(), device_http, terminal_key)
    response = await Device().start_session(device_http, terminal_key)
    assert response.status_code == 409
    assert response.json()["code"] == "PendingTerminalLimitError"


# ── Tokens ────────────────────────────────────────────────────────────


async def test_terminal_device_endpoints_refuse_missing_and_web_tokens(
    device_http: httpx.AsyncClient, admin: httpx.AsyncClient
) -> None:
    missing = await device_http.get(f"{DEVICE}/state")
    assert missing.status_code == 401
    assert missing.json()["code"] == "TerminalTokenInvalidError"
    web = await device_http.get(f"{DEVICE}/state", headers=dict(admin.headers))
    assert web.status_code == 401


async def test_terminal_token_is_no_web_session(
    device_http: httpx.AsyncClient, terminal_key: str
) -> None:
    token = await Device().token(device_http, terminal_key)
    for path in (f"{TERMINALS}/", f"{INFOSCREENS}/", "/api/v1/web/users/me"):
        response = await device_http.get(path, headers=_bearer(token))
        assert response.status_code == 401, path


async def test_terminal_token_stops_working_once_the_terminal_is_deleted(
    device_http: httpx.AsyncClient, terminal_key: str, admin: httpx.AsyncClient
) -> None:
    body = await _register(Device(), device_http, terminal_key)
    token = body["access_token"]
    assert (await device_http.get(f"{DEVICE}/state", headers=_bearer(token))).status_code == 200
    deleted = await admin.delete(f"{TERMINALS}/{body['state']['terminal_id']}")
    assert deleted.status_code == 204
    assert (await device_http.get(f"{DEVICE}/state", headers=_bearer(token))).status_code == 401


# ── Approval, state and feed ──────────────────────────────────────────


async def test_terminal_approval_needs_the_matching_code(
    device_http: httpx.AsyncClient, terminal_key: str, admin: httpx.AsyncClient
) -> None:
    state = (await _register(Device(), device_http, terminal_key))["state"]
    wrong_code = "".join("A" if c != "A" else "B" for c in state["pairing_code"])
    response = await admin.post(
        f"{TERMINALS}/{state['terminal_id']}/approve",
        json={"pairing_code": wrong_code, "name": "Hall", "mode": "infoscreen"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "PairingCodeMismatchError"
    kiosk = await admin.post(
        f"{TERMINALS}/{state['terminal_id']}/approve",
        json={"pairing_code": state["pairing_code"], "name": "Hall", "mode": "kiosk"},
    )
    assert kiosk.status_code == 422
    assert kiosk.json()["code"] == "TerminalModeNotSupportedError"


async def test_terminal_actions_need_manage_terminals(
    device_http: httpx.AsyncClient,
    terminal_key: str,
    auth_client: Callable[..., Awaitable[httpx.AsyncClient]],
) -> None:
    state = (await _register(Device(), device_http, terminal_key))["state"]
    reader = await auth_client(permissions=[], username="reader", email="reader@example.com")
    assert (await reader.get(f"{TERMINALS}/")).status_code == 200
    terminal_id = state["terminal_id"]
    for method, path, body in (
        ("post", f"{TERMINALS}/{terminal_id}/approve", {"pairing_code": "X", "name": "n"}),
        ("patch", f"{TERMINALS}/{terminal_id}", {"name": "n"}),
        ("post", f"{TERMINALS}/{terminal_id}/revoke", None),
        ("post", f"{TERMINALS}/{terminal_id}/reload", None),
        ("post", f"{TERMINALS}/{terminal_id}/identify", None),
        ("delete", f"{TERMINALS}/{terminal_id}", None),
    ):
        kwargs = {"json": body} if body is not None else {}
        response = await getattr(reader, method)(path, **kwargs)
        assert response.status_code == 403, (method, path, response.text)


async def test_terminal_full_lifecycle(
    device_http: httpx.AsyncClient,
    terminal_key: str,
    admin: httpx.AsyncClient,
    db: AsyncSession,
) -> None:
    device = Device()
    registered = await _register(device, device_http, terminal_key)
    token = registered["access_token"]
    state = registered["state"]
    terminal_id = state["terminal_id"]

    pending_feed = await device_http.get(f"{DEVICE}/feed", headers=_bearer(token))
    assert pending_feed.status_code == 409
    assert pending_feed.json()["code"] == "TerminalNotReadyError"

    approved = await _approve(admin, state, None)
    assert approved["status"] == "approved"
    assert approved["approved_by"]["username"] == "admin"
    assert approved["pairing_code"] is None
    device_state = (await device_http.get(f"{DEVICE}/state", headers=_bearer(token))).json()
    assert device_state["status"] == "approved"
    assert device_state["pairing_code"] is None
    assert (await device_http.get(f"{DEVICE}/feed", headers=_bearer(token))).status_code == 409

    screen_id = await _screen(admin)
    patched = await admin.patch(f"{TERMINALS}/{terminal_id}", json={"infoscreen_id": screen_id})
    assert patched.status_code == 200, patched.text
    assert patched.json()["infoscreen_name"] == "Hall 1"
    shown_on = (await admin.get(f"{INFOSCREENS}/{screen_id}")).json()["shown_on"]
    assert shown_on == [{"id": terminal_id, "name": "Hall display"}]

    feed = await device_http.get(f"{DEVICE}/feed", headers=_bearer(token))
    assert feed.status_code == 200, feed.text
    assert feed.json()["infoscreen"]["id"] == screen_id

    renamed = await admin.patch(f"{TERMINALS}/{terminal_id}", json={"name": "Hall west"})
    assert renamed.json()["infoscreen_id"] == screen_id
    unassigned = await admin.patch(f"{TERMINALS}/{terminal_id}", json={"infoscreen_id": None})
    assert unassigned.json()["infoscreen_id"] is None

    reload = (await admin.post(f"{TERMINALS}/{terminal_id}/reload")).json()
    identify = (await admin.post(f"{TERMINALS}/{terminal_id}/identify")).json()
    device_state = (await device_http.get(f"{DEVICE}/state", headers=_bearer(token))).json()
    assert device_state["reload_requested_at"] == reload["reload_requested_at"]
    assert device_state["identify_requested_at"] == identify["identify_requested_at"]

    revoked = await admin.post(f"{TERMINALS}/{terminal_id}/revoke")
    assert revoked.json()["status"] == "revoked"
    device_state = (await device_http.get(f"{DEVICE}/state", headers=_bearer(token))).json()
    assert device_state["status"] == "revoked"
    assert (await device_http.get(f"{DEVICE}/feed", headers=_bearer(token))).status_code == 409

    back = await device.start_session(device_http)
    assert back.status_code == 200, back.text
    assert back.json()["state"]["status"] == "pending"
    assert back.json()["state"]["terminal_id"] == terminal_id
    assert back.json()["state"]["pairing_code"]

    summaries = [a.summary for a in (await db.scalars(select(AdminSettingsAuditOrmModel))).all()]
    for verb in ("Approved", "Reassigned", "Revoked"):
        assert any(s.startswith(verb) for s in summaries), verb


async def test_terminal_clone_detection(
    terminal_key: str, admin: httpx.AsyncClient, db: AsyncSession, glados_caplog
) -> None:
    device = Device()
    async with device_client("10.0.0.5") as first, device_client("10.0.0.99") as second:
        await device.token(first, terminal_key)
        await device.token(first)
        listed = (await admin.get(f"{TERMINALS}/")).json()
        assert listed[0]["duplicate_detected_at"] is None
        await device.token(second)
    listed = (await admin.get(f"{TERMINALS}/")).json()
    assert listed[0]["duplicate_detected_at"] is not None
    assert listed[0]["status"] == "pending"
    assert any("may have been copied" in r.getMessage() for r in glados_caplog.records)
    audits = (await db.scalars(select(AdminSettingsAuditOrmModel))).all()
    assert any(a.summary.startswith("Possible clone") and a.changed_by_id is None for a in audits)


async def test_terminal_expired_pending_entries_are_left_out_of_the_list(
    device_http: httpx.AsyncClient, terminal_key: str, admin: httpx.AsyncClient, db: AsyncSession
) -> None:
    await _register(Device(), device_http, terminal_key)
    row = await db.scalar(select(TerminalOrmModel))
    assert row is not None
    row.pairing_expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db.commit()
    assert (await admin.get(f"{TERMINALS}/")).json() == []


# ── Security settings ─────────────────────────────────────────────────


async def test_terminal_security_settings_round_trip(
    auth_client: Callable[..., Awaitable[httpx.AsyncClient]],
) -> None:
    client = await auth_client(permissions=[Permission.READ_SETTINGS, Permission.WRITE_SETTINGS])
    current = (await client.get("/api/v1/web/admin/settings/security")).json()
    assert current["enable_terminals"] is True
    assert current["terminal_allowed_ips"] == []
    body = {
        **current,
        "enable_terminals": False,
        "terminal_allowed_ips": [" 10.0.0.0/8 ", "10.0.0.0/8"],
    }
    saved = await client.put("/api/v1/web/admin/settings/security", json=body)
    assert saved.status_code == 200, saved.text
    assert saved.json()["enable_terminals"] is False
    assert saved.json()["terminal_allowed_ips"] == ["10.0.0.0/8"]
    bad = await client.put(
        "/api/v1/web/admin/settings/security", json={**body, "terminal_allowed_ips": ["nope"]}
    )
    assert bad.status_code == 422
