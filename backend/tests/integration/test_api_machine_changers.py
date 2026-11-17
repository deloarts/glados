"""
The machine catalogue and calendar routes record who changed a row last.
Each case creates a record as one user and edits it as another, then checks
that the response and a separate read name the second user as the changer
while the creator stays the first.
"""

from typing import Any

import pytest

from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission

MACHINES = f"{API_WEB}/production-machines"
POOLS = f"{API_WEB}/production-machine-pools"
HOLIDAYS = f"{API_WEB}/holidays"
MACHINE = {"internal_name": "MILL-1", "vendor": "Contoso", "model": "VF-2"}
FULL_TIME = {
    str(day): ([{"start": "08:00", "minutes": 480}] if day < 5 else []) for day in range(7)
}
PART_TIME = {
    str(day): ([{"start": "13:30", "minutes": 240}] if day < 5 else []) for day in range(7)
}
SHUTDOWN = {
    "name": "Summer shutdown",
    "category": "plant_shutdown",
    "start_date": "2026-08-03",
    "end_date": "2026-08-14",
}


@pytest.fixture
async def writer(auth_client) -> Any:
    return await auth_client(permissions=[Permission.WRITE_MACHINES])


@pytest.fixture
async def editor(auth_client) -> Any:
    return await auth_client(
        permissions=[Permission.WRITE_MACHINES], username="editor", email="editor@example.com"
    )


async def _ok(response: Any, status: int = 200) -> dict[str, Any]:
    assert response.status_code == status, response.text
    return dict(response.json())


async def _create_machine(client: Any) -> dict[str, Any]:
    return await _ok(await client.post(f"{MACHINES}/", json=MACHINE), 201)


def _assert_changed_by_other_user(created: dict[str, Any], updated: dict[str, Any]) -> None:
    assert updated["creator_id"] == created["creator_id"]
    assert updated["changed_by_id"] not in (None, created["creator_id"])


async def test_machine_records_the_changing_user(writer, editor) -> None:
    created = await _create_machine(writer)

    updated = await _ok(
        await editor.patch(f"{MACHINES}/{created['id']}", json={"internal_name": "MILL-1B"})
    )

    _assert_changed_by_other_user(created, updated)
    assert updated["changed_by_full_name"]
    reread = await _ok(await writer.get(f"{MACHINES}/{created['id']}"))
    assert reread["changed_by_id"] == updated["changed_by_id"]

    listed = await _ok(await writer.get(f"{MACHINES}/?changed_by_id={updated['changed_by_id']}"))
    assert [m["id"] for m in listed["items"]] == [created["id"]]
    listed = await _ok(await writer.get(f"{MACHINES}/?changed_by_id={created['creator_id']}"))
    assert listed["items"] == []


async def test_pool_records_the_changing_user(writer, editor) -> None:
    machine = await _create_machine(writer)
    created = await _ok(
        await writer.post(f"{POOLS}/", json={"name": "Mills", "machine_ids": [machine["id"]]}),
        201,
    )

    updated = await _ok(await editor.patch(f"{POOLS}/{created['id']}", json={"name": "Lathes"}))

    _assert_changed_by_other_user(created, updated)
    assert updated["changed_by_full_name"]
    reread = await _ok(await writer.get(f"{POOLS}/{created['id']}"))
    assert reread["changed_by_id"] == updated["changed_by_id"]
    listed = await _ok(await writer.get(f"{POOLS}/?changed_by_id={updated['changed_by_id']}"))
    assert [p["id"] for p in listed["items"]] == [created["id"]]


async def test_working_hours_record_the_changing_user(writer, editor) -> None:
    machine = await _create_machine(writer)
    url = f"{MACHINES}/{machine['id']}/working-hours"
    created = await _ok(await writer.put(url, json={"weekly_hours": FULL_TIME}))

    updated = await _ok(await editor.put(url, json={"weekly_hours": PART_TIME}))

    _assert_changed_by_other_user(created, updated)
    assert updated["changed_by"]["id"] == updated["changed_by_id"]
    reread = await _ok(await writer.get(url))
    assert reread["changed_by_id"] == updated["changed_by_id"]


async def test_calendar_exception_records_the_changing_user(writer, editor) -> None:
    machine = await _create_machine(writer)
    created = await _ok(
        await writer.post(
            f"{MACHINES}/{machine['id']}/calendar-exceptions",
            json={"exception_date": "2026-12-24", "available_minutes": 0},
        ),
        201,
    )

    updated = await _ok(
        await editor.patch(
            f"{MACHINES}/calendar-exceptions/{created['id']}",
            json={"available_minutes": 240, "start": "06:00"},
        )
    )

    _assert_changed_by_other_user(created, updated)
    assert updated["changed_by"]["id"] == updated["changed_by_id"]
    listed = (await writer.get(f"{MACHINES}/{machine['id']}/calendar-exceptions")).json()
    assert [e["changed_by_id"] for e in listed] == [updated["changed_by_id"]]


async def test_downtime_records_the_changing_user(writer, editor) -> None:
    machine = await _create_machine(writer)
    body = {
        "machine_id": machine["id"],
        "started_at": "2026-01-01T08:00:00Z",
        "ended_at": "2026-01-01T09:00:00Z",
        "reason": "breakdown",
    }
    created = await _ok(await writer.post(f"{MACHINES}/downtimes", json=body), 201)

    updated = await _ok(
        await editor.put(
            f"{MACHINES}/downtimes/{created['id']}",
            json={key: value for key, value in body.items() if key != "machine_id"}
            | {"note": "Spindle fault"},
        )
    )

    assert updated["reported_by_id"] == created["reported_by_id"]
    assert updated["changed_by_id"] not in (None, created["reported_by_id"])
    assert updated["changed_by_full_name"]


async def test_holiday_records_the_changing_user(auth_client) -> None:
    permissions = [Permission.WRITE_MACHINES]
    admin = await auth_client(permissions=permissions)
    other_admin = await auth_client(
        permissions=permissions, username="other-admin", email="other-admin@example.com"
    )
    created = await _ok(await admin.post(HOLIDAYS, json=SHUTDOWN), 201)

    updated = await _ok(
        await other_admin.put(f"{HOLIDAYS}/{created['id']}", json={**SHUTDOWN, "name": "Shutdown"})
    )

    _assert_changed_by_other_user(created, updated)
    assert updated["changed_by"]["id"] == updated["changed_by_id"]
    listed = (await admin.get(HOLIDAYS)).json()
    assert [h["changed_by_id"] for h in listed] == [updated["changed_by_id"]]
