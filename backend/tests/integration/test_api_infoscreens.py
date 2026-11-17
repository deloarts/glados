"""HTTP coverage of infoscreens: create, edit, archive and restore with
their permission and validation refusals, the preview feed, and the device
feed answering exactly what the preview shows."""

from collections.abc import AsyncIterator
from collections.abc import Awaitable
from collections.abc import Callable
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.main import app
from src.modules.operations.adapters.inbound.api.deps.services import get_terminal_auth_rate_limiter
from src.modules.operations.application.services.terminal_auth_rate_limiter import (
    TerminalAuthRateLimiter,
)
from src.modules.platform.const import VERSION
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration._terminal_helpers import DEVICE
from tests.integration._terminal_helpers import INFOSCREENS
from tests.integration._terminal_helpers import TERMINAL_KEYS
from tests.integration._terminal_helpers import TERMINALS
from tests.integration._terminal_helpers import Device
from tests.integration._terminal_helpers import device_client
from tests.integration._terminal_helpers import seed_production
from tests.integration._terminal_helpers import seed_security

_EVERY_WIDGET_PAGES: list[dict[str, Any]] = [
    {
        "layout": "grid_2x2",
        "slots": [
            {"type": "machine_board", "title": "Mills", "next_count": 2},
            {"type": "lots_due", "horizon_days": 14, "show_customer": True},
            {"type": "late_lots"},
            {"type": "qa_queue"},
        ],
    },
    {
        "layout": "main_side",
        "slots": [
            {"type": "deliveries_expected", "horizon_days": 5},
            {"type": "message", "text": "Wear ear protection", "severity": "warning"},
        ],
    },
    {"layout": "two_columns", "slots": [{"type": "clock", "show_next_holiday": True}, None]},
]


@pytest.fixture(autouse=True)
async def _settings(db: AsyncSession) -> AsyncIterator[None]:
    await seed_security(db)
    await seed_production(db)
    limiter = TerminalAuthRateLimiter()
    app.dependency_overrides[get_terminal_auth_rate_limiter] = lambda: limiter
    yield
    app.dependency_overrides.pop(get_terminal_auth_rate_limiter, None)


@pytest.fixture
async def writer(auth_client: Callable[..., Awaitable[httpx.AsyncClient]]) -> httpx.AsyncClient:
    return await auth_client(
        permissions=[
            Permission.WRITE_INFOSCREENS,
            Permission.MANAGE_TERMINALS,
            Permission.MANAGE_API_KEYS,
            Permission.WRITE_MACHINES,
        ],
        username="writer",
        email="writer@example.com",
    )


@pytest.fixture
async def reader(auth_client: Callable[..., Awaitable[httpx.AsyncClient]]) -> httpx.AsyncClient:
    return await auth_client(permissions=[], username="reader", email="reader@example.com")


async def _create(client: httpx.AsyncClient, **overrides: Any) -> httpx.Response:
    body: dict[str, Any] = {"name": "Hall 1", "pages": _EVERY_WIDGET_PAGES}
    body.update(overrides)
    return await client.post(INFOSCREENS, json=body)


async def test_infoscreen_create_read_and_list(
    writer: httpx.AsyncClient, reader: httpx.AsyncClient
) -> None:
    response = await _create(writer, theme_preset="Nora", primary_color="emerald")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["color_mode"] == "dark"
    assert body["rotation_seconds"] == 30
    assert body["show_banner"] is True
    assert body["theme_preset"] == "Nora"
    assert body["creator"]["username"] == "writer"
    assert body["shown_on"] == []
    assert body["pages"][0]["slots"][0]["next_count"] == 2
    assert body["pages"][2]["slots"][1] is None
    clock = body["pages"][2]["slots"][0]
    assert (clock["style"], clock["show_seconds"]) == ("digital", False)
    assert body["show_header"] is True
    assert body["header"] == {
        "left": ["logo", "title"],
        "center": [],
        "right": ["clock"],
        "text": None,
    }
    assert body["show_footer"] is False
    assert body["footer"] == {"left": [], "center": [], "right": ["last_updated"], "text": None}

    assert (await reader.get(f"{INFOSCREENS}/{body['id']}")).json()["name"] == "Hall 1"
    assert [s["id"] for s in (await reader.get(f"{INFOSCREENS}/")).json()] == [body["id"]]


async def test_infoscreen_writes_need_write_infoscreens(
    writer: httpx.AsyncClient, reader: httpx.AsyncClient
) -> None:
    screen_id = (await _create(writer)).json()["id"]
    assert (await _create(reader, name="Other")).status_code == 403
    assert (await reader.patch(f"{INFOSCREENS}/{screen_id}", json={"name": "x"})).status_code == 403
    assert (await reader.post(f"{INFOSCREENS}/{screen_id}/archive")).status_code == 403
    assert (await reader.post(f"{INFOSCREENS}/{screen_id}/restore")).status_code == 403


@pytest.mark.parametrize(
    "pages",
    [
        [{"layout": "full", "slots": [None, None]}],
        [{"layout": "grid_2x2", "slots": [None]}],
        [{"layout": "full", "slots": [{"type": "weather"}]}],
        [{"layout": "full", "slots": [{"type": "machine_board", "next_count": 0}]}],
        [{"layout": "full", "slots": [{"type": "message", "text": ""}]}],
        [{"layout": "full", "slots": [{"type": "clock", "style": "sundial"}]}],
    ],
)
async def test_infoscreen_invalid_pages_answer_422(
    writer: httpx.AsyncClient, pages: list[dict[str, Any]]
) -> None:
    assert (await _create(writer, pages=pages)).status_code == 422


async def test_infoscreen_invalid_settings_answer_422(writer: httpx.AsyncClient) -> None:
    assert (await _create(writer, rotation_seconds=5)).status_code == 422
    assert (await _create(writer, color_mode="sepia")).status_code == 422
    assert (await _create(writer, theme_preset="Bootstrap")).status_code == 422


async def test_infoscreen_update_keeps_unsent_fields_and_clears_explicit_nulls(
    writer: httpx.AsyncClient,
) -> None:
    created = (await _create(writer, description="Wall", theme_preset="Lara")).json()
    response = await writer.patch(
        f"{INFOSCREENS}/{created['id']}",
        json={
            "rotation_seconds": 45,
            "theme_preset": None,
            "pages": [{"layout": "full", "slots": [None]}],
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["rotation_seconds"] == 45
    assert body["theme_preset"] is None
    assert body["description"] == "Wall"
    assert body["pages"] == [{"layout": "full", "slots": [None]}]
    assert body["changed_by"]["username"] == "writer"


async def test_infoscreen_names_are_unique_among_live_screens(writer: httpx.AsyncClient) -> None:
    first = (await _create(writer)).json()
    duplicate = await _create(writer, name="hall 1")
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "InfoscreenNameTakenError"

    archived = await writer.post(f"{INFOSCREENS}/{first['id']}/archive")
    assert archived.json()["archived"] is True
    assert (await writer.post(f"{INFOSCREENS}/{first['id']}/archive")).status_code == 200
    assert (await writer.get(f"{INFOSCREENS}/")).json() == []
    assert len((await writer.get(f"{INFOSCREENS}/", params={"include_archived": True})).json()) == 1

    assert (await _create(writer)).status_code == 201
    restore = await writer.post(f"{INFOSCREENS}/{first['id']}/restore")
    assert restore.status_code == 409


async def test_infoscreen_preview_feed_has_data_for_every_slot(
    writer: httpx.AsyncClient, reader: httpx.AsyncClient
) -> None:
    machine = await writer.post(
        "/api/v1/web/production-machines/",
        json={"internal_name": "Mill 1", "vendor": "DMG", "model": "DMU 50"},
    )
    assert machine.status_code == 201, machine.text
    screen_id = (await _create(writer)).json()["id"]

    response = await reader.get(f"{INFOSCREENS}/{screen_id}/feed")
    assert response.status_code == 200, response.text
    feed = response.json()
    assert feed["backend_version"] == VERSION
    assert feed["infoscreen"]["id"] == screen_id
    types = [[slot["type"] if slot else None for slot in page] for page in feed["widgets"]]
    assert types == [
        ["machine_board", "lots_due", "late_lots", "qa_queue"],
        ["deliveries_expected", "message"],
        ["clock", None],
    ]
    board = feed["widgets"][0][0]["machines"]
    assert [m["machine_name"] for m in board] == ["Mill 1"]
    assert board[0]["state"] in ("idle", "closed")
    assert board[0]["current"] is None
    assert feed["widgets"][1][1] == {
        "type": "message",
        "text": "Wear ear protection",
        "severity": "warning",
        "text_align": "left",
        "vertical_align": "middle",
    }
    assert (await reader.get(f"{INFOSCREENS}/999/feed")).status_code == 404

    downtime = await writer.post(
        "/api/v1/web/production-machines/downtimes",
        json={
            "machine_id": machine.json()["id"],
            "started_at": (datetime.now(UTC) - timedelta(minutes=5)).isoformat(),
            "reason": "breakdown",
        },
    )
    assert downtime.status_code == 201, downtime.text
    board = (await reader.get(f"{INFOSCREENS}/{screen_id}/feed")).json()["widgets"][0][0]
    assert board["machines"][0]["state"] == "down"
    assert board["machines"][0]["downtime_reason"] == "breakdown"


def _terminal_key_body() -> dict[str, str]:
    # Seeded security settings cap token lifetimes, so a key needs an expiry.
    return {"name": "Hall", "expires_at": (datetime.now(UTC) + timedelta(days=30)).isoformat()}


async def test_infoscreen_device_feed_equals_the_preview(writer: httpx.AsyncClient) -> None:
    screen_id = (await _create(writer)).json()["id"]
    key = (await writer.post(TERMINAL_KEYS, json=_terminal_key_body())).json()["key"]
    async with device_client() as client:
        session = (await Device().start_session(client, key)).json()
        state = session["state"]
        approved = await writer.post(
            f"{TERMINALS}/{state['terminal_id']}/approve",
            json={
                "pairing_code": state["pairing_code"],
                "name": "Hall",
                "infoscreen_id": screen_id,
            },
        )
        assert approved.status_code == 200, approved.text
        device = await client.get(
            f"{DEVICE}/feed", headers={"Authorization": f"Bearer {session['access_token']}"}
        )
    preview = await writer.get(f"{INFOSCREENS}/{screen_id}/feed")
    assert device.status_code == 200, device.text
    device_feed, preview_feed = device.json(), preview.json()
    device_feed.pop("generated_at")
    preview_feed.pop("generated_at")
    assert device_feed == preview_feed


async def test_infoscreen_feed_carries_the_tenant_timezone(
    writer: httpx.AsyncClient,
    reader: httpx.AsyncClient,
    auth_client: Callable[..., Awaitable[httpx.AsyncClient]],
) -> None:
    screen_id = (await _create(writer)).json()["id"]
    feed = (await reader.get(f"{INFOSCREENS}/{screen_id}/feed")).json()
    assert feed["timezone"] == "Europe/Vienna"

    admin = await auth_client(
        permissions=[Permission.WRITE_SETTINGS], username="admin", email="admin@example.com"
    )
    changed = await admin.put(
        "/api/v1/web/admin/settings/general", json={"default_timezone": "America/New_York"}
    )
    assert changed.status_code == 200, changed.text

    feed = (await reader.get(f"{INFOSCREENS}/{screen_id}/feed")).json()
    assert feed["timezone"] == "America/New_York"


async def test_infoscreen_archived_screen_cannot_be_assigned(writer: httpx.AsyncClient) -> None:
    screen_id = (await _create(writer)).json()["id"]
    await writer.post(f"{INFOSCREENS}/{screen_id}/archive")
    key = (await writer.post(TERMINAL_KEYS, json=_terminal_key_body())).json()["key"]
    async with device_client() as client:
        state = (await Device().start_session(client, key)).json()["state"]
    response = await writer.post(
        f"{TERMINALS}/{state['terminal_id']}/approve",
        json={"pairing_code": state["pairing_code"], "name": "Hall", "infoscreen_id": screen_id},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "InfoscreenArchivedError"


async def test_infoscreen_header_and_footer_edit_and_validation(writer: httpx.AsyncClient) -> None:
    created = (await _create(writer)).json()
    response = await writer.patch(
        f"{INFOSCREENS}/{created['id']}",
        json={
            "show_footer": True,
            "footer": {
                "left": ["app_name"],
                "center": ["text"],
                "right": ["last_updated"],
                "text": "Hall 3",
            },
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["show_footer"] is True
    assert body["footer"] == {
        "left": ["app_name"],
        "center": ["text"],
        "right": ["last_updated"],
        "text": "Hall 3",
    }
    assert body["header"] == {
        "left": ["logo", "title"],
        "center": [],
        "right": ["clock"],
        "text": None,
    }

    duplicate = await writer.patch(
        f"{INFOSCREENS}/{created['id']}", json={"header": {"left": ["clock"], "right": ["clock"]}}
    )
    assert duplicate.status_code == 422
    assert duplicate.json()["code"] == "InvalidInfoscreenConfigError"
    unknown = await _create(writer, name="Other", header={"left": ["weather"]})
    assert unknown.status_code == 422


async def test_infoscreen_feed_carries_the_next_holiday_for_a_bar(
    writer: httpx.AsyncClient, auth_client: Callable[..., Awaitable[httpx.AsyncClient]]
) -> None:
    planner = await auth_client(
        permissions=[Permission.WRITE_MACHINES], username="planner", email="planner@example.com"
    )
    start = (datetime.now(UTC) + timedelta(days=10)).date().isoformat()
    holiday = await planner.post(
        "/api/v1/web/holidays/",
        json={
            "name": "Plant closed",
            "category": "plant_shutdown",
            "start_date": start,
            "end_date": start,
        },
    )
    assert holiday.status_code == 201, holiday.text

    plain = (await _create(writer, name="Plain")).json()
    assert (await writer.get(f"{INFOSCREENS}/{plain['id']}/feed")).json()["next_holiday"] is None

    with_bar = await _create(
        writer, name="Holiday", show_footer=True, footer={"center": ["next_holiday"]}
    )
    feed = (await writer.get(f"{INFOSCREENS}/{with_bar.json()['id']}/feed")).json()
    assert feed["next_holiday"] == {"date": start, "name": "Plant closed"}
    assert feed["infoscreen"]["footer"] == {
        "left": [],
        "center": ["next_holiday"],
        "right": [],
        "text": None,
    }
    assert feed["infoscreen"]["show_header"] is True

    hidden = await _create(
        writer, name="Hidden", show_footer=False, footer={"right": ["next_holiday"]}
    )
    feed = (await writer.get(f"{INFOSCREENS}/{hidden.json()['id']}/feed")).json()
    assert feed["next_holiday"] is None
