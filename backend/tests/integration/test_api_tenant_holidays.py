"""
The holiday calendar routes persist what they report: every write is read
back through a separate request. Every signed-in user reads the calendar, a
user without write:machines is refused the write and the delete, and a holiday that ends before it starts answers
422.
"""

from typing import Any

import pytest

from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission

HOLIDAYS = f"{API_WEB}/holidays"
SHUTDOWN = {
    "name": "Summer shutdown",
    "category": "plant_shutdown",
    "start_date": "2026-08-03",
    "end_date": "2026-08-14",
}


@pytest.fixture
async def admin(auth_client) -> Any:
    return await auth_client(permissions=[Permission.WRITE_MACHINES])


async def _listed(client: Any) -> list[dict[str, Any]]:
    response = await client.get(HOLIDAYS)
    assert response.status_code == 200, response.text
    return list(response.json())


async def test_holiday_writes_are_persisted(admin) -> None:
    created = await admin.post(HOLIDAYS, json=SHUTDOWN)
    assert created.status_code == 201, created.text
    holiday_id = created.json()["id"]
    assert [(h["id"], h["end_date"]) for h in await _listed(admin)] == [(holiday_id, "2026-08-14")]

    updated = await admin.put(
        f"{HOLIDAYS}/{holiday_id}",
        json={
            **SHUTDOWN,
            "name": "National Day",
            "category": "public_holiday",
            "end_date": "2026-08-03",
        },
    )
    assert updated.status_code == 200, updated.text
    assert [(h["name"], h["category"], h["end_date"]) for h in await _listed(admin)] == [
        ("National Day", "public_holiday", "2026-08-03")
    ]

    deleted = await admin.delete(f"{HOLIDAYS}/{holiday_id}")
    assert deleted.status_code == 204, deleted.text
    assert await _listed(admin) == []


async def test_a_reader_cannot_add_a_holiday(auth_client) -> None:
    reader = await auth_client(permissions=[])

    response = await reader.post(HOLIDAYS, json=SHUTDOWN)

    assert response.status_code == 403, response.text
    assert await _listed(reader) == []


async def test_deleting_a_holiday_needs_write_machines(auth_client) -> None:
    writer = await auth_client(permissions=[Permission.WRITE_MACHINES])
    created = await writer.post(HOLIDAYS, json=SHUTDOWN)
    assert created.status_code == 201, created.text
    reader = await auth_client(username="reader", email="reader@example.com", permissions=[])

    response = await reader.delete(f"{HOLIDAYS}/{created.json()['id']}")

    assert response.status_code == 403, response.text
    assert [h["id"] for h in await _listed(writer)] == [created.json()["id"]]


async def test_a_holiday_ending_before_it_starts_is_refused(admin) -> None:
    response = await admin.post(HOLIDAYS, json={**SHUTDOWN, "end_date": "2026-08-01"})

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "InvalidScheduleCalendarError"
