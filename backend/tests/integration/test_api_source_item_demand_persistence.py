"""
Proves that the source item demand and allocation write routes persist
what they report. Editing a demand, bucketing it and changing its status,
and creating, updating and deleting an order or stock allocation are each
read back through a separate request, so a use case that forgets to commit
its unit of work fails here instead of silently losing the write.
"""

from datetime import date
from typing import Any

import pytest

from src.modules.fulfillment.adapters.outbound.persistence.repositories.source_item_demand_repository import (
    SqlAlchemySourceItemDemandRepository,
)
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration.repository_reads._graph import Graph

DEMANDS = f"{API_WEB}/source-item-demands"
ALLOCATIONS = f"{API_WEB}/source-item-allocations"
BUCKETS = f"{API_WEB}/source-item-demand-buckets"


@pytest.fixture
async def planner(auth_client) -> Any:
    return await auth_client(
        username="planner",
        email="planner@example.com",
        permissions=[
            Permission.WRITE_LOTS,
            Permission.WRITE_DEMAND_ITEMS,
            Permission.MANAGE_DEMAND_ITEMS,
            Permission.WRITE_ALLOCATIONS,
        ],
    )


@pytest.fixture
async def seeded(db, create_user) -> dict[str, int]:
    """An open demand for a source item without a lot behind it, plus an
    order line for that same source item to allocate from."""
    user = await create_user(username="owner", email="owner@example.com")
    other = await create_user(username="receiver", email="receiver@example.com")
    graph = Graph(db, user, other)
    source_item = await graph.source_item()
    order_item = await graph.source_order_item()
    project = await graph.project()
    demand = await SqlAlchemySourceItemDemandRepository(db).save(
        SourceItemDemandItem(
            id=0,
            created=date.today(),
            changed=None,
            changes=[],
            status=SourceItemDemandStatus.OPEN,
            quantity=5.0,
            unit="pcs",
            items_per_unit=1.0,
            high_priority=False,
            notify_on_delivery=False,
            note=None,
            desired_delivery_date=None,
            creator_id=user.id,
            bought_item_id=None,
            source_item_id=source_item.id,
            lot_id=987654,
            project_id=project.id,
        )
    )
    await db.commit()
    return {"demand_id": demand.id, "order_item_id": order_item.id}


async def _reread(client: Any, demand_id: int) -> dict[str, Any]:
    response = await client.get(f"{DEMANDS}/{demand_id}")
    assert response.status_code == 200, response.text
    return dict(response.json())


async def test_demand_writes_are_persisted(planner, seeded: dict[str, int]) -> None:
    demand_id = seeded["demand_id"]

    updated = await planner.put(f"{DEMANDS}/{demand_id}", json={"quantity": 7, "unit": "pcs"})
    assert updated.status_code == 200, updated.text
    assert (await _reread(planner, demand_id))["quantity"] == 7

    bucket = await planner.post(f"{BUCKETS}/", json={"name": "Urgent", "color": "#ff0000"})
    assert bucket.status_code == 201, bucket.text
    bucketed = await planner.put(
        f"{DEMANDS}/{demand_id}/bucket", json={"bucket_id": bucket.json()["id"]}
    )
    assert bucketed.status_code == 200, bucketed.text
    assert (await _reread(planner, demand_id))["bucket_id"] == bucket.json()["id"]

    # Only the two intents are set by hand; the other statuses follow from
    # the allocations.
    moved = await planner.put(f"{DEMANDS}/{demand_id}/status", params={"new_status": "fulfilled"})
    assert moved.status_code == 200, moved.text
    assert (await _reread(planner, demand_id))["status"] == "fulfilled"


async def test_an_update_records_the_changing_user(planner, seeded: dict[str, int]) -> None:
    demand_id = seeded["demand_id"]
    before = await _reread(planner, demand_id)

    updated = await planner.put(f"{DEMANDS}/{demand_id}", json={"quantity": 7, "unit": "pcs"})

    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["creator_id"] == before["creator_id"]
    assert body["changed_by_id"] not in (None, before["creator_id"])
    assert body["changed_by"]["id"] == body["changed_by_id"]
    assert (await _reread(planner, demand_id))["changed_by_id"] == body["changed_by_id"]


async def test_allocation_writes_are_persisted(planner, seeded: dict[str, int]) -> None:
    demand_id = seeded["demand_id"]
    order_item_id = seeded["order_item_id"]

    async def allocations() -> list[tuple[str, float]]:
        response = await planner.get(f"{ALLOCATIONS}/demand/{demand_id}")
        assert response.status_code == 200, response.text
        return sorted((a["source"], a["quantity"]) for a in response.json())

    created = await planner.post(
        f"{ALLOCATIONS}/",
        json={"demand_item_id": demand_id, "order_item_id": order_item_id, "quantity": 2},
    )
    assert created.status_code == 201, created.text
    assert await allocations() == [("order", 2)]
    assert (await _reread(planner, demand_id))["status"] != "open"

    updated = await planner.put(
        f"{ALLOCATIONS}/demand/{demand_id}/order-item/{order_item_id}", json={"quantity": 3}
    )
    assert updated.status_code == 200, updated.text
    assert await allocations() == [("order", 3)]

    stocked = await planner.put(f"{ALLOCATIONS}/demand/{demand_id}/stock", json={"quantity": 1})
    assert stocked.status_code == 200, stocked.text
    assert await allocations() == [("order", 3), ("stock", 1)]

    unstocked = await planner.delete(f"{ALLOCATIONS}/demand/{demand_id}/stock")
    assert unstocked.status_code == 204, unstocked.text
    assert await allocations() == [("order", 3)]

    deleted = await planner.delete(f"{ALLOCATIONS}/demand/{demand_id}/order-item/{order_item_id}")
    assert deleted.status_code == 204, deleted.text
    assert await allocations() == []
    assert (await _reread(planner, demand_id))["status"] == "open"
