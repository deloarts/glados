"""
Proves that the bought item write routes persist what they report.
Creating, archiving and restoring a catalogue item, creating, editing, bucketing,
changing the status of and deleting a demand, and creating, updating and
deleting an order or stock allocation are each read back through a
separate request, so a use case that forgets to commit its unit of work
fails here instead of silently losing the write.
"""

from typing import Any

import pytest

from src.modules.catalogue.domain.events.bought_item_events import BoughtItemCreated
from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration.repository_reads._graph import Graph

ITEMS = f"{API_WEB}/bought-items"
DEMANDS = f"{API_WEB}/bought-items-demands"
ALLOCATIONS = f"{API_WEB}/bought-items-allocations"
BUCKETS = f"{API_WEB}/bought-items-demand-buckets"


@pytest.fixture
async def buyer(auth_client) -> Any:
    return await auth_client(
        username="buyer",
        email="buyer@example.com",
        permissions=[
            Permission.WRITE_BOUGHT_ITEMS,
            Permission.DELETE_BOUGHT_ITEMS,
            Permission.WRITE_DEMAND_ITEMS,
            Permission.MANAGE_DEMAND_ITEMS,
            Permission.WRITE_ALLOCATIONS,
        ],
    )


@pytest.fixture
async def seeded(db, create_user) -> dict[str, int]:
    """A bought item, a project to demand it for, and an order line for
    that same item to allocate from."""
    user = await create_user(username="owner", email="owner@example.com")
    other = await create_user(username="receiver", email="receiver@example.com")
    graph = Graph(db, user, other)
    item = await graph.bought_item()
    order_item = await graph.bought_order_item()
    project = await graph.project()
    await db.commit()
    return {
        "item_id": item.id,
        "order_item_id": order_item.id,
        "project_id": project.id,
        "supplier_id": item.manufacturer_id,
    }


async def _create_demand(client: Any, seeded: dict[str, int]) -> int:
    response = await client.post(
        f"{DEMANDS}/",
        json={
            "item_id": seeded["item_id"],
            "project_id": seeded["project_id"],
            "quantity": 5,
            "unit": "pcs",
        },
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


async def _reread(client: Any, demand_id: int) -> dict[str, Any]:
    response = await client.get(f"{DEMANDS}/{demand_id}")
    assert response.status_code == 200, response.text
    return dict(response.json())


async def test_create_is_persisted(
    buyer, seeded: dict[str, int], published_events: list[object]
) -> None:
    response = await buyer.post(
        f"{ITEMS}/",
        json={
            "order_code_1": "OC-NEW-1",
            "article_name": "Spring",
            "manufacturer_id": seeded["supplier_id"],
        },
    )
    assert response.status_code == 201, response.text
    reread = await buyer.get(f"{ITEMS}/{response.json()['id']}")
    assert reread.status_code == 200, reread.text
    assert reread.json()["article_name"] == "Spring"
    assert any(isinstance(e, BoughtItemCreated) for e in published_events)


async def test_archive_and_restore_are_persisted(buyer, seeded: dict[str, int]) -> None:
    item_id = seeded["item_id"]

    async def archived() -> bool:
        response = await buyer.get(f"{ITEMS}/{item_id}")
        assert response.status_code == 200, response.text
        return bool(response.json()["archived"])

    response = await buyer.post(f"{ITEMS}/{item_id}/archive")
    assert response.status_code == 200, response.text
    assert await archived() is True

    response = await buyer.post(f"{ITEMS}/{item_id}/restore")
    assert response.status_code == 200, response.text
    assert await archived() is False


async def test_demand_writes_are_persisted(buyer, seeded: dict[str, int]) -> None:
    demand_id = await _create_demand(buyer, seeded)
    assert (await _reread(buyer, demand_id))["quantity"] == 5

    updated = await buyer.put(f"{DEMANDS}/{demand_id}", json={"quantity": 7, "unit": "pcs"})
    assert updated.status_code == 200, updated.text
    assert (await _reread(buyer, demand_id))["quantity"] == 7

    bucket = await buyer.post(f"{BUCKETS}/", json={"name": "Urgent", "color": "#ff0000"})
    assert bucket.status_code == 201, bucket.text
    bucketed = await buyer.put(
        f"{DEMANDS}/{demand_id}/bucket", json={"bucket_id": bucket.json()["id"]}
    )
    assert bucketed.status_code == 200, bucketed.text
    assert (await _reread(buyer, demand_id))["bucket_id"] == bucket.json()["id"]

    # Only the two intents are set by hand; the other statuses follow from
    # the allocations. A fulfilled demand is not deleted, so a second demand
    # takes the status write.
    fulfilled_id = await _create_demand(buyer, seeded)
    moved = await buyer.put(f"{DEMANDS}/{fulfilled_id}/status", params={"new_status": "fulfilled"})
    assert moved.status_code == 200, moved.text
    assert (await _reread(buyer, fulfilled_id))["status"] == "fulfilled"

    deleted = await buyer.delete(f"{DEMANDS}/{demand_id}")
    assert deleted.status_code == 200, deleted.text
    assert (await buyer.get(f"{DEMANDS}/{demand_id}")).status_code == 404


async def test_allocation_writes_are_persisted(buyer, seeded: dict[str, int]) -> None:
    demand_id = await _create_demand(buyer, seeded)
    order_item_id = seeded["order_item_id"]

    async def allocations() -> list[tuple[str, float]]:
        response = await buyer.get(f"{ALLOCATIONS}/demand/{demand_id}")
        assert response.status_code == 200, response.text
        return sorted((a["source"], a["quantity"]) for a in response.json())

    created = await buyer.post(
        f"{ALLOCATIONS}/",
        json={"demand_item_id": demand_id, "order_item_id": order_item_id, "quantity": 2},
    )
    assert created.status_code == 201, created.text
    assert await allocations() == [("order", 2)]
    assert (await _reread(buyer, demand_id))["status"] != "open"

    updated = await buyer.put(
        f"{ALLOCATIONS}/demand/{demand_id}/order-item/{order_item_id}", json={"quantity": 3}
    )
    assert updated.status_code == 200, updated.text
    assert await allocations() == [("order", 3)]

    stocked = await buyer.put(f"{ALLOCATIONS}/demand/{demand_id}/stock", json={"quantity": 1})
    assert stocked.status_code == 200, stocked.text
    assert await allocations() == [("order", 3), ("stock", 1)]

    unstocked = await buyer.delete(f"{ALLOCATIONS}/demand/{demand_id}/stock")
    assert unstocked.status_code == 204, unstocked.text
    assert await allocations() == [("order", 3)]

    deleted = await buyer.delete(f"{ALLOCATIONS}/demand/{demand_id}/order-item/{order_item_id}")
    assert deleted.status_code == 204, deleted.text
    assert await allocations() == []
    assert (await _reread(buyer, demand_id))["status"] == "open"
