"""HTTP coverage of the terminal additions: device details on the session
call and who sees which of them, the location, the display schedule and
override in the device state, the actions on all terminals, messages to
terminals with their audiences, and the screen language in the feed."""

from collections.abc import AsyncIterator
from collections.abc import Awaitable
from collections.abc import Callable
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.bootstrap.main import app
from src.modules.operations.adapters.inbound.api.deps.services import get_terminal_auth_rate_limiter
from src.modules.operations.adapters.outbound.persistence.models.terminal_model import (
    TerminalOrmModel,
)
from src.modules.operations.application.services.terminal_auth_rate_limiter import (
    TerminalAuthRateLimiter,
)
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration._terminal_helpers import DEVICE
from tests.integration._terminal_helpers import INFOSCREENS
from tests.integration._terminal_helpers import TERMINAL_KEYS
from tests.integration._terminal_helpers import TERMINALS
from tests.integration._terminal_helpers import Device
from tests.integration._terminal_helpers import device_client
from tests.integration._terminal_helpers import seed_production
from tests.integration._terminal_helpers import seed_security

BROADCASTS = "/api/v1/web/terminal-broadcasts"
ADMIN_PERMISSIONS = [
    Permission.MANAGE_API_KEYS,
    Permission.MANAGE_TERMINALS,
    Permission.WRITE_INFOSCREENS,
]
DEVICE_DETAILS: dict[str, Any] = {
    "computer_model": "Raspberry Pi 4 Model B Rev 1.5",
    "computer_serial": "10000000abcdef01",
    "ram_mb": 3790,
    "cpu_temperature_c": 50.1,
    "uptime_seconds": 3600,
    "kernel": "6.18.50+rpt-rpi-v8",
    "os_name": "Debian GNU/Linux 13 (trixie)",
    "hostname": "IND-SBC-0001",
    "display_make": "SAM",
    "display_model": "S27D390",
    "display_serial": "H4ZH800000",
    "display_width_px": 1920,
    "display_height_px": 1080,
    "display_connected": True,
    "cec_available": True,
}
_PERSON_KEYS = ("created_by", "creator", "author", "username", "full_name", "email")


@pytest.fixture(autouse=True)
async def _settings(db: AsyncSession) -> None:
    await seed_security(db)
    await seed_production(db)


@pytest.fixture(autouse=True)
def _fresh_rate_limiter() -> AsyncIterator[None]:
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
async def reader(auth_client: Callable[..., Awaitable[httpx.AsyncClient]]) -> httpx.AsyncClient:
    return await auth_client(permissions=[], username="reader", email="reader@example.com")


@pytest.fixture
async def device_http() -> AsyncIterator[httpx.AsyncClient]:
    async with device_client() as client:
        yield client


@pytest.fixture
async def terminal_key(admin: httpx.AsyncClient) -> str:
    # Seeded security settings cap token lifetimes, so a key needs an expiry.
    expires_at = (datetime.now(UTC) + timedelta(days=30)).isoformat()
    response = await admin.post(
        TERMINAL_KEYS, json={"name": "Hall displays", "expires_at": expires_at}
    )
    assert response.status_code == 201, response.text
    key: str = response.json()["key"]
    return key


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _session(
    display: Device, client: httpx.AsyncClient, api_key: str | None = None, **body: Any
) -> httpx.Response:
    nonce = await display.challenge(client)
    headers = {"X-Api-Key": api_key} if api_key else {}
    return await client.post(
        f"{DEVICE}/session", json=display.session_body(nonce, **body), headers=headers
    )


async def _registered(
    client: httpx.AsyncClient, terminal_key: str, **body: Any
) -> tuple[Device, dict[str, Any]]:
    device = Device()
    response = await _session(device, client, terminal_key, **body)
    assert response.status_code == 200, response.text
    return device, response.json()


async def _screen(admin: httpx.AsyncClient, name: str, **fields: Any) -> int:
    response = await admin.post(
        INFOSCREENS,
        json={
            "name": name,
            "pages": [{"layout": "full", "slots": [{"type": "message", "text": "Hi"}]}],
            **fields,
        },
    )
    assert response.status_code == 201, response.text
    screen_id: int = response.json()["id"]
    return screen_id


async def _approved_terminal(
    admin: httpx.AsyncClient,
    client: httpx.AsyncClient,
    terminal_key: str,
    infoscreen_id: int | None,
    **approve: Any,
) -> tuple[int, str]:
    """Registers and approves a display; returns its id and token."""
    _, session = await _registered(client, terminal_key)
    state = session["state"]
    response = await admin.post(
        f"{TERMINALS}/{state['terminal_id']}/approve",
        json={
            "pairing_code": state["pairing_code"],
            "name": f"Display {state['terminal_id']}",
            "infoscreen_id": infoscreen_id,
            **approve,
        },
    )
    assert response.status_code == 200, response.text
    return state["terminal_id"], session["access_token"]


async def _state(client: httpx.AsyncClient, token: str) -> dict[str, Any]:
    response = await client.get(f"{DEVICE}/state", headers=_bearer(token))
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


def _soon(hours: int = 1) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).isoformat()


def _listed(terminals: list[dict[str, Any]], terminal_id: int) -> dict[str, Any]:
    return next(t for t in terminals if t["id"] == terminal_id)


# ── Device details and who sees them ──────────────────────────────────


async def test_terminal_device_details_are_stored_and_capped(
    device_http: httpx.AsyncClient, terminal_key: str, admin: httpx.AsyncClient
) -> None:
    long_hostname = "h" * 600
    _, session = await _registered(
        device_http, terminal_key, device={**DEVICE_DETAILS, "hostname": long_hostname}
    )
    terminal = _listed((await admin.get(f"{TERMINALS}/")).json(), session["state"]["terminal_id"])
    device = terminal["device"]
    assert device["computer_model"] == DEVICE_DETAILS["computer_model"]
    assert device["display_width_px"] == 1920
    assert device["hostname"] == "h" * 253
    assert device["reported_at"] is not None

    too_long = await _session(Device(), device_http, terminal_key, device={"kernel": "k" * 1025})
    assert too_long.status_code == 422


async def test_terminal_session_without_details_keeps_the_previous_ones(
    device_http: httpx.AsyncClient, terminal_key: str, admin: httpx.AsyncClient, db: AsyncSession
) -> None:
    device, session = await _registered(device_http, terminal_key, device=DEVICE_DETAILS)
    assert (await _session(device, device_http)).status_code == 200
    row = await db.scalar(
        select(TerminalOrmModel).where(TerminalOrmModel.id == session["state"]["terminal_id"])
    )
    assert row is not None
    assert row.device_os_name == DEVICE_DETAILS["os_name"]
    assert row.device_details is not None
    assert row.device_details["hostname"] == DEVICE_DETAILS["hostname"]


async def test_terminal_identifying_details_need_manage_terminals(
    device_http: httpx.AsyncClient,
    terminal_key: str,
    admin: httpx.AsyncClient,
    reader: httpx.AsyncClient,
) -> None:
    _, session = await _registered(device_http, terminal_key, device=DEVICE_DETAILS)
    terminal_id = session["state"]["terminal_id"]

    full = _listed((await admin.get(f"{TERMINALS}/")).json(), terminal_id)
    assert full["identifying_details_visible"] is True
    assert full["public_key_fingerprint"]
    assert full["last_ip"] == "10.0.0.5"
    assert full["last_session_ip"] == "10.0.0.5"
    assert full["device"]["computer_serial"] == DEVICE_DETAILS["computer_serial"]
    assert full["device"]["display_serial"] == DEVICE_DETAILS["display_serial"]
    assert full["device"]["hostname"] == DEVICE_DETAILS["hostname"]

    limited = _listed((await reader.get(f"{TERMINALS}/")).json(), terminal_id)
    assert limited["identifying_details_visible"] is False
    for key in ("public_key_fingerprint", "last_ip", "last_session_ip"):
        assert limited[key] is None, key
    for key in ("computer_serial", "display_serial", "hostname"):
        assert limited["device"][key] is None, key
    assert limited["device"]["computer_model"] == DEVICE_DETAILS["computer_model"]


# ── Location ──────────────────────────────────────────────────────────


async def test_terminal_location_is_set_capped_cleared_and_sent_to_the_device(
    device_http: httpx.AsyncClient, terminal_key: str, admin: httpx.AsyncClient
) -> None:
    terminal_id, token = await _approved_terminal(
        admin, device_http, terminal_key, None, location="  Hall 2, north wall  "
    )
    assert (await _state(device_http, token))["location"] == "Hall 2, north wall"

    too_long = await admin.patch(f"{TERMINALS}/{terminal_id}", json={"location": "x" * 201})
    assert too_long.status_code == 422
    renamed = await admin.patch(f"{TERMINALS}/{terminal_id}", json={"name": "Gate 3"})
    assert renamed.json()["location"] == "Hall 2, north wall"
    cleared = await admin.patch(f"{TERMINALS}/{terminal_id}", json={"location": None})
    assert cleared.json()["location"] is None
    assert (await _state(device_http, token))["location"] is None


# ── Display schedule and override ─────────────────────────────────────


async def test_infoscreen_display_schedule_round_trips_and_is_validated(
    admin: httpx.AsyncClient,
) -> None:
    schedule = {"monday": [{"start": "07:00", "end": "18:00"}], "saturday": []}
    screen_id = await _screen(
        admin, "Office", display_schedule=schedule, off_on_holidays=True, language="deAT"
    )
    body = (await admin.get(f"{INFOSCREENS}/{screen_id}")).json()
    assert body["display_schedule"]["monday"] == [{"start": "07:00", "end": "18:00"}]
    assert body["display_schedule"]["sunday"] == []
    assert body["off_on_holidays"] is True
    assert body["language"] == "deAT"

    overlap = await admin.patch(
        f"{INFOSCREENS}/{screen_id}",
        json={
            "display_schedule": {
                "monday": [{"start": "07:00", "end": "12:00"}, {"start": "11:00", "end": "13:00"}]
            }
        },
    )
    assert overlap.status_code == 422
    assert overlap.json()["code"] == "InvalidInfoscreenConfigError"
    cleared = await admin.patch(
        f"{INFOSCREENS}/{screen_id}", json={"display_schedule": None, "language": None}
    )
    assert cleared.json()["display_schedule"] is None
    assert cleared.json()["language"] is None
    assert cleared.json()["off_on_holidays"] is True
    unknown = await admin.patch(f"{INFOSCREENS}/{screen_id}", json={"language": "frFR"})
    assert unknown.status_code == 422


async def test_terminal_display_power_follows_the_schedule_and_the_override(
    device_http: httpx.AsyncClient, terminal_key: str, admin: httpx.AsyncClient
) -> None:
    # An own schedule without any window keeps the display off.
    dark = await _screen(admin, "Dark", display_schedule_mode="own", display_schedule={})
    terminal_id, token = await _approved_terminal(admin, device_http, terminal_key, dark)
    state = await _state(device_http, token)
    assert (state["display_power"], state["display_power_changes_at"]) == ("off", None)

    no_end = await admin.post(f"{TERMINALS}/{terminal_id}/display-override", json={"power": "on"})
    assert no_end.status_code == 422
    assert no_end.json()["code"] == "InvalidDisplayOverrideError"

    until = datetime.now(UTC) + timedelta(hours=2)
    forced = await admin.post(
        f"{TERMINALS}/{terminal_id}/display-override",
        json={"power": "on", "until": until.isoformat()},
    )
    assert forced.status_code == 200, forced.text
    assert forced.json()["display_override"] == "on"
    assert forced.json()["display_power"] == "on"
    state = await _state(device_http, token)
    assert state["display_power"] == "on"
    assert datetime.fromisoformat(state["display_power_changes_at"]) == until

    cleared = await admin.delete(f"{TERMINALS}/{terminal_id}/display-override")
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["display_override"] is None
    assert (await _state(device_http, token))["display_power"] == "off"


async def test_screens_follow_the_default_schedule_unless_they_have_their_own(
    device_http: httpx.AsyncClient, terminal_key: str, admin: httpx.AsyncClient
) -> None:
    following = await _screen(admin, "Follows")
    assert (await admin.get(f"{INFOSCREENS}/{following}")).json()["display_schedule_mode"] == (
        "default"
    )
    _, follower = await _approved_terminal(admin, device_http, terminal_key, following)
    always = await _screen(admin, "Always", display_schedule_mode="always_on")
    _, always_token = await _approved_terminal(admin, device_http, terminal_key, always)
    _, no_screen = await _approved_terminal(admin, device_http, terminal_key, None)

    # Until a default is set, the default is always on.
    unset = (await admin.get(f"{INFOSCREENS}/display-schedule-default")).json()
    assert unset == {"display_schedule": None, "off_on_holidays": False}
    assert (await _state(device_http, follower))["display_power"] == "on"

    saved = await admin.put(
        f"{INFOSCREENS}/display-schedule-default",
        json={"display_schedule": {}, "off_on_holidays": True},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["display_schedule"]["monday"] == []
    assert saved.json()["off_on_holidays"] is True
    assert (await _state(device_http, follower))["display_power"] == "off"
    assert (await _state(device_http, always_token))["display_power"] == "on"
    assert (await _state(device_http, no_screen))["display_power"] == "on"

    own = await admin.patch(
        f"{INFOSCREENS}/{following}",
        json={"display_schedule_mode": "always_on"},
    )
    assert own.json()["display_schedule_mode"] == "always_on"
    assert (await _state(device_http, follower))["display_power"] == "on"

    invalid = await admin.put(
        f"{INFOSCREENS}/display-schedule-default",
        json={"display_schedule": {"monday": [{"start": "09:00", "end": "08:00"}]}},
    )
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "InvalidInfoscreenConfigError"


async def test_setting_the_default_schedule_needs_write_infoscreens(
    reader: httpx.AsyncClient,
) -> None:
    assert (await reader.get(f"{INFOSCREENS}/display-schedule-default")).status_code == 200
    denied = await reader.put(f"{INFOSCREENS}/display-schedule-default", json={})
    assert denied.status_code == 403


async def test_terminal_display_override_needs_an_approved_terminal_and_the_permission(
    device_http: httpx.AsyncClient,
    terminal_key: str,
    admin: httpx.AsyncClient,
    reader: httpx.AsyncClient,
) -> None:
    _, session = await _registered(device_http, terminal_key)
    terminal_id = session["state"]["terminal_id"]
    assert session["state"]["display_power"] == "on"
    body = {"power": "off", "until": _soon()}
    pending = await admin.post(f"{TERMINALS}/{terminal_id}/display-override", json=body)
    assert pending.status_code == 409
    denied = await reader.post(f"{TERMINALS}/{terminal_id}/display-override", json=body)
    assert denied.status_code == 403
    assert (await reader.delete(f"{TERMINALS}/{terminal_id}/display-override")).status_code == 403


# ── All terminals ─────────────────────────────────────────────────────


async def test_terminal_bulk_actions_hit_the_right_terminals(
    device_http: httpx.AsyncClient, terminal_key: str, admin: httpx.AsyncClient
) -> None:
    first, first_token = await _approved_terminal(admin, device_http, terminal_key, None)
    second, _ = await _approved_terminal(admin, device_http, terminal_key, None)
    _, pending = await _registered(device_http, terminal_key)

    reload = await admin.post(f"{TERMINALS}/all/reload")
    assert reload.status_code == 200, reload.text
    assert reload.json() == {"count": 2}
    identify = await admin.post(f"{TERMINALS}/all/identify")
    assert identify.json() == {"count": 2}
    terminals = (await admin.get(f"{TERMINALS}/")).json()
    assert _listed(terminals, first)["reload_requested_at"] is not None
    assert _listed(terminals, first)["identify_requested_at"] is not None
    assert _listed(terminals, pending["state"]["terminal_id"])["reload_requested_at"] is None
    assert (await _state(device_http, first_token))["reload_requested_at"] is not None

    revoke = await admin.post(f"{TERMINALS}/all/revoke")
    assert revoke.json() == {"count": 2}
    statuses = {t["id"]: t["status"] for t in (await admin.get(f"{TERMINALS}/")).json()}
    assert statuses == {
        first: "revoked",
        second: "revoked",
        pending["state"]["terminal_id"]: "pending",
    }
    assert (await admin.post(f"{TERMINALS}/all/reload")).json() == {"count": 0}

    deleted = await admin.post(f"{TERMINALS}/all/delete")
    assert deleted.json() == {"count": 3}
    assert (await admin.get(f"{TERMINALS}/")).json() == []


async def test_terminal_bulk_actions_need_manage_terminals(reader: httpx.AsyncClient) -> None:
    for action in ("reload", "identify", "revoke", "delete"):
        response = await reader.post(f"{TERMINALS}/all/{action}")
        assert response.status_code == 403, (action, response.text)


# ── Messages to terminals ─────────────────────────────────────────────


async def test_terminal_broadcast_reaches_its_audience_without_its_author(
    device_http: httpx.AsyncClient, terminal_key: str, admin: httpx.AsyncClient
) -> None:
    hall = await _screen(admin, "Hall")
    office = await _screen(admin, "Office")
    in_hall, hall_token = await _approved_terminal(admin, device_http, terminal_key, hall)
    _, office_token = await _approved_terminal(admin, device_http, terminal_key, office)
    unassigned, unassigned_token = await _approved_terminal(admin, device_http, terminal_key, None)

    to_all = await admin.post(
        BROADCASTS, json={"text": "Fire drill at **10:00**", "show_until": _soon()}
    )
    assert to_all.status_code == 201, to_all.text
    assert to_all.json()["reach_count"] == 3
    assert to_all.json()["created_by"]["username"] == "admin"
    for token in (hall_token, office_token, unassigned_token):
        message = (await _state(device_http, token))["broadcast"]
        assert message["text"] == "Fire drill at **10:00**"
        assert not any(key in message for key in _PERSON_KEYS)

    to_hall = await admin.post(
        BROADCASTS,
        json={
            "text": "Hall closes early",
            "severity": "warning",
            "style": "fullscreen",
            "show_until": _soon(),
            "all_terminals": False,
            "infoscreen_ids": [hall],
        },
    )
    assert to_hall.json()["reach_count"] == 1
    hall_message = (await _state(device_http, hall_token))["broadcast"]
    assert (hall_message["text"], hall_message["style"]) == ("Hall closes early", "fullscreen")
    assert (await _state(device_http, office_token))["broadcast"]["text"] == (
        "Fire drill at **10:00**"
    )
    preview = (await admin.get(f"{INFOSCREENS}/{hall}/feed")).json()
    assert preview["broadcast"]["text"] == "Hall closes early"
    device_feed = (await device_http.get(f"{DEVICE}/feed", headers=_bearer(hall_token))).json()
    assert device_feed["broadcast"]["text"] == "Hall closes early"

    # Moving the display to another screen moves it out of the screen pick.
    await admin.patch(f"{TERMINALS}/{in_hall}", json={"infoscreen_id": office})
    assert (await _state(device_http, hall_token))["broadcast"]["text"] == (
        "Fire drill at **10:00**"
    )

    to_unassigned = await admin.post(
        BROADCASTS,
        json={
            "text": "Unassigned",
            "show_until": _soon(),
            "all_terminals": False,
            "terminal_ids": [unassigned],
        },
    )
    assert to_unassigned.json()["reach_count"] == 1
    assert (await _state(device_http, unassigned_token))["broadcast"]["text"] == "Unassigned"

    active = (await admin.get(BROADCASTS + "/")).json()
    assert [b["text"] for b in active] == [
        "Unassigned",
        "Hall closes early",
        "Fire drill at **10:00**",
    ]

    ended = await admin.post(f"{BROADCASTS}/{to_all.json()['id']}/end")
    assert ended.status_code == 200, ended.text
    assert ended.json()["ended_at"] is not None
    again = await admin.post(f"{BROADCASTS}/{to_all.json()['id']}/end")
    assert again.json()["ended_at"] == ended.json()["ended_at"]
    assert (await _state(device_http, office_token))["broadcast"] is None
    assert len((await admin.get(BROADCASTS + "/")).json()) == 2


async def test_terminal_broadcast_reach_counts_a_draft_audience(
    device_http: httpx.AsyncClient, terminal_key: str, admin: httpx.AsyncClient
) -> None:
    hall = await _screen(admin, "Hall")
    in_hall, _ = await _approved_terminal(admin, device_http, terminal_key, hall)
    unassigned, _ = await _approved_terminal(admin, device_http, terminal_key, None)
    await _registered(device_http, terminal_key)

    async def reach(**audience: Any) -> int:
        response = await admin.post(f"{BROADCASTS}/reach", json=audience)
        assert response.status_code == 200, response.text
        count: int = response.json()["count"]
        return count

    assert await reach() == 2
    assert await reach(all_terminals=False, infoscreen_ids=[hall]) == 1
    assert await reach(all_terminals=False, terminal_ids=[unassigned]) == 1
    assert await reach(all_terminals=False, terminal_ids=[in_hall], infoscreen_ids=[hall]) == 1
    assert await reach(all_terminals=False) == 0


async def test_terminal_broadcast_validation_and_permission(
    admin: httpx.AsyncClient, reader: httpx.AsyncClient
) -> None:
    base = {"text": "Hello", "show_until": _soon()}
    for body in (
        {**base, "all_terminals": False},
        {**base, "all_terminals": False, "terminal_ids": [999]},
        {**base, "all_terminals": False, "infoscreen_ids": [999]},
        {**base, "show_until": (datetime.now(UTC) - timedelta(minutes=1)).isoformat()},
        {**base, "show_until": _soon(hours=24 * 31)},
        {**base, "text": "   "},
    ):
        response = await admin.post(BROADCASTS, json=body)
        assert response.status_code == 422, (body, response.text)
        assert response.json()["code"] == "InvalidTerminalBroadcastError"
    assert (await admin.post(BROADCASTS, json={**base, "text": "x" * 2001})).status_code == 422
    assert (await reader.post(BROADCASTS, json=base)).status_code == 403
    sent = await admin.post(BROADCASTS, json=base)
    assert (await reader.post(f"{BROADCASTS}/{sent.json()['id']}/end")).status_code == 403
    assert (await reader.get(BROADCASTS + "/")).status_code == 200
    assert (await admin.post(f"{BROADCASTS}/999/end")).status_code == 404


# ── Language ──────────────────────────────────────────────────────────


async def test_infoscreen_feed_resolves_the_language(
    admin: httpx.AsyncClient, db: AsyncSession
) -> None:
    german = await _screen(admin, "German", language="deAT")
    tenant = await _screen(admin, "Tenant")
    assert (await admin.get(f"{INFOSCREENS}/{german}/feed")).json()["language"] == "deAT"
    settings = SqlAlchemyAdminSettingsRepository(db)
    general = await settings.get_general()
    general.default_language = Language.deAT
    await settings.save_general(general)
    await db.commit()
    tenant_feed = (await admin.get(f"{INFOSCREENS}/{tenant}/feed")).json()
    assert tenant_feed["language"] == "deAT"
    refused = await admin.post(INFOSCREENS, json={"name": "French", "language": "frFR"})
    assert refused.status_code == 422
