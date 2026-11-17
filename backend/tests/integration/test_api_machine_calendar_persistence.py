"""
Proves that the machine calendar write routes persist what they report.
Every write, a working hours override and a calendar exception alike, is
read back through a separate request, so a use case that forgets to commit
its unit of work fails here instead of silently losing the write.
"""

from typing import Any

import pytest

from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission

MACHINES = f"{API_WEB}/production-machines"
FULL_TIME = {
    str(day): ([{"start": "08:00", "minutes": 480}] if day < 5 else []) for day in range(7)
}
PART_TIME = {
    str(day): ([{"start": "13:30", "minutes": 240}] if day < 5 else []) for day in range(7)
}


@pytest.fixture
async def writer(auth_client) -> Any:
    return await auth_client(permissions=[Permission.WRITE_MACHINES])


@pytest.fixture
async def machine_id(writer) -> int:
    response = await writer.post(
        f"{MACHINES}/", json={"internal_name": "MILL-1", "vendor": "Contoso", "model": "VF-2"}
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


async def test_working_hours_writes_are_persisted(writer, machine_id: int) -> None:
    url = f"{MACHINES}/{machine_id}/working-hours"

    async def reread() -> Any:
        response = await writer.get(url)
        assert response.status_code == 200, response.text
        return response.json()

    created = await writer.put(url, json={"weekly_hours": FULL_TIME})
    assert created.status_code == 200, created.text
    assert (await reread())["weekly_hours"] == FULL_TIME

    updated = await writer.put(url, json={"weekly_hours": PART_TIME})
    assert updated.status_code == 200, updated.text
    assert (await reread())["weekly_hours"] == PART_TIME

    deleted = await writer.delete(url)
    assert deleted.status_code == 204, deleted.text
    assert await reread() is None


async def test_calendar_exception_writes_are_persisted(writer, machine_id: int) -> None:
    async def reread() -> list[dict[str, Any]]:
        response = await writer.get(f"{MACHINES}/{machine_id}/calendar-exceptions")
        assert response.status_code == 200, response.text
        return list(response.json())

    created = await writer.post(
        f"{MACHINES}/{machine_id}/calendar-exceptions",
        json={"exception_date": "2026-12-24", "available_minutes": 0, "note": "Closed"},
    )
    assert created.status_code == 201, created.text
    exception_id = created.json()["id"]
    assert [(e["id"], e["available_minutes"], e["start"]) for e in await reread()] == [
        (exception_id, 0, "08:00")
    ]

    updated = await writer.patch(
        f"{MACHINES}/calendar-exceptions/{exception_id}",
        json={"available_minutes": 240, "start": "06:00", "note": "Half day"},
    )
    assert updated.status_code == 200, updated.text
    assert [(e["available_minutes"], e["start"], e["note"]) for e in await reread()] == [
        (240, "06:00", "Half day")
    ]

    deleted = await writer.delete(f"{MACHINES}/calendar-exceptions/{exception_id}")
    assert deleted.status_code == 204, deleted.text
    assert await reread() == []
