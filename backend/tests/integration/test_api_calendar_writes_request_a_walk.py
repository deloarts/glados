"""
Every write that can move planned dates without touching an order requests
a walk of the schedule after its commit: machine working hours, calendar
exceptions, downtimes, tenant holidays, the production and general
settings, and a machine's archive and restore. Each request is counted by a
generation counter standing in for the Redis one.
"""

from collections.abc import Iterator
from datetime import datetime
from typing import Any

import pytest

from src.bootstrap.main import app
from src.modules.platform.adapters.inbound.api.deps.bindings import (
    get_schedule_recompute_generation_counter,
)
from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration import _lifecycle_seed as seed
from tests.integration._edit_versions import row_version
from tests.integration._suppliers import seed_supplier
from tests.integration.repository_reads._graph import Graph
from tests.integration.test_api_lifecycle_scenarios import LOTS
from tests.integration.test_api_lifecycle_scenarios import PERMISSIONS
from tests.integration.test_api_scrap_pieces import _seed_production_settings  # noqa: F401

MACHINES = f"{API_WEB}/production-machines"
SETTINGS = f"{API_WEB}/admin/settings"
HOLIDAYS = f"{API_WEB}/holidays"
FULL_TIME = {
    str(day): ([{"start": "08:00", "minutes": 480}] if day < 5 else []) for day in range(7)
}


class _Counter:
    """The generation counter in memory, counting the walk requests."""

    def __init__(self) -> None:
        self.requests = 0
        self._processed = 0

    async def increment_generation(self) -> int:
        self.requests += 1
        return self.requests

    async def current_generation(self) -> int:
        return self.requests

    async def processed_generation(self) -> int:
        return self._processed

    async def mark_processed(self, generation: int) -> None:
        self._processed = max(self._processed, generation)

    async def mark_stale(self, at: datetime) -> None:
        pass

    async def take_stale_since(self) -> datetime | None:
        return None

    async def stale_since(self) -> datetime | None:
        return None


@pytest.fixture
def counter() -> Iterator[_Counter]:
    counter = _Counter()
    app.dependency_overrides[get_schedule_recompute_generation_counter] = lambda: counter
    yield counter
    app.dependency_overrides.pop(get_schedule_recompute_generation_counter, None)


@pytest.fixture
async def planner(auth_client) -> Any:
    return await auth_client(
        permissions=[
            Permission.WRITE_MACHINES,
            Permission.READ_SETTINGS,
            Permission.WRITE_SETTINGS,
        ]
    )


@pytest.fixture
async def machine_id(planner) -> int:
    response = await planner.post(
        f"{MACHINES}/", json={"internal_name": "MILL-9", "vendor": "Contoso", "model": "VF-2"}
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


async def _requests_one_walk(counter: _Counter, response: Any) -> None:
    assert response.status_code < 300, response.text
    assert counter.requests == 1
    counter.requests = 0


async def test_machine_calendar_writes_request_a_walk(planner, machine_id, counter) -> None:
    hours = f"{MACHINES}/{machine_id}/working-hours"
    await _requests_one_walk(counter, await planner.put(hours, json={"weekly_hours": FULL_TIME}))
    await _requests_one_walk(counter, await planner.delete(hours))

    created = await planner.post(
        f"{MACHINES}/{machine_id}/calendar-exceptions",
        json={"exception_date": "2026-12-24", "available_minutes": 0, "note": "Closed"},
    )
    await _requests_one_walk(counter, created)
    exception = f"{MACHINES}/calendar-exceptions/{created.json()['id']}"
    await _requests_one_walk(
        counter,
        await planner.patch(exception, json={"available_minutes": 240, "note": "Half day"}),
    )
    await _requests_one_walk(counter, await planner.delete(exception))


async def test_downtime_writes_request_a_walk(planner, machine_id, counter) -> None:
    added = await planner.post(
        f"{MACHINES}/downtimes",
        json={
            "machine_id": machine_id,
            "started_at": "2026-01-01T08:00:00Z",
            "reason": "breakdown",
            "note": "Spindle fault",
        },
    )
    await _requests_one_walk(counter, added)
    downtime = f"{MACHINES}/downtimes/{added.json()['id']}"
    await _requests_one_walk(counter, await planner.post(f"{downtime}/end", json={}))
    await _requests_one_walk(counter, await planner.delete(downtime))


async def test_holiday_and_settings_writes_request_a_walk(planner, counter) -> None:
    created = await planner.post(
        HOLIDAYS,
        json={
            "name": "Summer shutdown",
            "category": "plant_shutdown",
            "start_date": "2026-08-03",
            "end_date": "2026-08-14",
        },
    )
    await _requests_one_walk(counter, created)
    await _requests_one_walk(counter, await planner.delete(f"{HOLIDAYS}/{created.json()['id']}"))

    production = (await planner.get(f"{SETTINGS}/production")).json()
    production["frozen_window_hours"] = 12
    await _requests_one_walk(counter, await planner.put(f"{SETTINGS}/production", json=production))


async def test_archiving_and_restoring_a_machine_request_a_walk(
    planner, machine_id, counter
) -> None:
    await _requests_one_walk(counter, await planner.post(f"{MACHINES}/{machine_id}/archive"))
    await _requests_one_walk(counter, await planner.post(f"{MACHINES}/{machine_id}/restore"))


@pytest.mark.parametrize(
    ("date_from", "date_to"), [("2026-01-01", "2030-01-01"), ("2026-03-01", "2026-02-01")]
)
async def test_the_board_refuses_an_unbounded_or_reversed_range(
    planner, date_from: str, date_to: str
) -> None:
    response = await planner.get(
        f"{API_WEB}/production-schedule/", params={"date_from": date_from, "date_to": date_to}
    )

    assert response.status_code == 422, response.text


async def test_the_kpis_refuse_a_reversed_range(planner) -> None:
    response = await planner.get(
        f"{API_WEB}/production-kpi/summary",
        params={"date_from": "2026-03-01", "date_to": "2026-02-01"},
    )

    assert response.status_code == 422, response.text


async def test_lead_time_writes_request_a_walk(auth_client, counter) -> None:
    client = await auth_client(
        permissions=[Permission.WRITE_SUPPLIERS, Permission.WRITE_FABRICATION_METHODS]
    )
    supplier = await client.post(f"{API_WEB}/suppliers/", json={"name": "Lead", "level": "B"})
    assert supplier.status_code == 201, supplier.text
    counter.requests = 0
    await _requests_one_walk(
        counter,
        await client.put(
            f"{API_WEB}/suppliers/{supplier.json()['id']}",
            json={
                "expected_edit_version": await row_version(
                    client, f"{API_WEB}/suppliers/{supplier.json()['id']}"
                ),
                "name": "Lead",
                "level": "B",
                "external_lead_time_days": 9,
            },
        ),
    )
    method = await client.post(
        f"{API_WEB}/fabrication-methods/",
        json={"name": {"enGB": "Anodising"}, "required_external": True},
    )
    assert method.status_code == 201, method.text
    counter.requests = 0
    await _requests_one_walk(
        counter,
        await client.put(
            f"{API_WEB}/fabrication-methods/{method.json()['id']}",
            json={"name": {"enGB": "Anodising"}, "required_external": True, "lead_time_days": 4},
        ),
    )


async def test_step_writes_request_a_walk(db, create_user, auth_client, counter) -> None:
    owner = await create_user(username="owner", email="owner@example.com")
    graph = Graph(db, owner, owner)
    position = await graph.internal_position()
    lot_id = position.lot_id
    client = await auth_client(permissions=PERMISSIONS)
    added = await client.post(
        f"{LOTS}/{lot_id}/steps",
        json={
            "position_id": position.id,
            "fabrication_method_id": (await graph.fabrication_method()).id,
        },
    )
    assert added.status_code == 201, added.text
    steps = (await client.get(f"{LOTS}/{lot_id}")).json()["steps"]
    counter.requests = 0

    await _requests_one_walk(
        counter,
        await client.put(
            f"{LOTS}/{lot_id}/steps/reorder",
            json={"ordered_step_ids": [step["id"] for step in reversed(steps)]},
        ),
    )
    await _requests_one_walk(
        counter, await client.delete(f"{LOTS}/{lot_id}/steps/{added.json()['id']}")
    )


async def test_a_line_moved_to_another_supplier_requests_a_walk(db, auth_client, counter) -> None:
    await seed_supplier(db, 1)
    await seed_supplier(db, 2)
    client = await auth_client(permissions=[Permission.WRITE_ORDERS, Permission.MANAGE_ORDERS])
    first = await seed.order(db, "ordered", ordered_date=seed.NOW)
    second = await seed.order(db, "draft")
    second.supplier_id = 2
    line = await seed.line(db, first, "ordered", ordered_date=seed.NOW)
    await db.commit()
    await seed.settle(db)
    counter.requests = 0

    await _requests_one_walk(
        counter,
        await client.put(
            f"/api/v1/web/orders/{first.id}/items/{line.id}/move",
            json={"target_order_id": second.id},
        ),
    )


async def test_inspection_method_writes_request_a_walk(auth_client, counter) -> None:
    client = await auth_client(permissions=[Permission.WRITE_INSPECTION_METHODS])
    method = await client.post(f"{API_WEB}/inspection-methods/", json={"name": {"enGB": "Lab"}})
    assert method.status_code == 201, method.text
    counter.requests = 0
    await _requests_one_walk(
        counter,
        await client.put(
            f"{API_WEB}/inspection-methods/{method.json()['id']}",
            json={"name": {"enGB": "Lab"}, "wait_after_minutes": 240},
        ),
    )
