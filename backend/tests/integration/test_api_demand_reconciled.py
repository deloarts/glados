"""
The demands of the three families over HTTP, with the lifecycle reconciler
deriving their statuses. Canceling a bought or a made demand releases its
allocations, on order lines and from stock. Only the two intents, canceled
and fulfilled, can be set through the status route; a status the
allocations decide is refused with 422. A demand holding allocations is not
deleted. A lot covers demands of its own made item only. Switching a lot's
material source cancels the old raw material demand and creates its
successor in one request, which the unique index over a lot's live demand
allows because it reads canceled_at. The drift check after every test
confirms that each stored status is its derivation.
"""

from typing import Any

import pytest

from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemAllocationSource
from src.modules.fulfillment.adapters.outbound.persistence.repositories.made_item_demand_repository.allocation import (
    SqlAlchemyMadeItemAllocationRepository,
)
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration._demand_facts import give_demand_facts
from tests.integration.repository_reads._graph import Graph
from tests.integration.test_api_lot_source_approval import _create_lot
from tests.integration.test_api_lot_source_approval import _get_lot
from tests.integration.test_api_lot_source_approval import _make_source_item
from tests.integration.test_api_lot_source_approval import _seed_settings  # noqa: F401
from tests.integration.test_api_lot_source_approval import owner  # noqa: F401
from tests.integration.test_api_lot_source_approval import project_id  # noqa: F401
from tests.integration.test_api_lot_source_approval import source_made_item_id  # noqa: F401

DEMANDS = {
    "bought": f"{API_WEB}/bought-items-demands",
    "made": f"{API_WEB}/made-items-demands",
    "source": f"{API_WEB}/source-item-demands",
}
ALLOCATIONS = {
    "bought": f"{API_WEB}/bought-items-allocations",
    "made": f"{API_WEB}/made-items-allocations",
}
LOTS = f"{API_WEB}/production-lots"

MANAGER = [
    Permission.WRITE_DEMAND_ITEMS,
    Permission.MANAGE_DEMAND_ITEMS,
    Permission.WRITE_ALLOCATIONS,
    Permission.WRITE_LOTS,
    Permission.MANAGE_LOTS,
]


@pytest.fixture
async def graph(db: Any, create_user: Any) -> Graph:
    user = await create_user(username="creator", email="creator@example.com")
    other = await create_user(username="receiver", email="receiver@example.com")
    return Graph(db, user, other)


@pytest.fixture
async def manager(auth_client: Any) -> Any:
    return await auth_client(username="manager", email="manager@example.com", permissions=MANAGER)


async def _allocations(client: Any, family: str, demand_id: int) -> list[dict[str, Any]]:
    response = await client.get(f"{ALLOCATIONS[family]}/demand/{demand_id}")
    assert response.status_code == 200, response.text
    return list(response.json())


async def _status(client: Any, family: str, demand_id: int) -> str:
    response = await client.get(f"{DEMANDS[family]}/{demand_id}")
    assert response.status_code == 200, response.text
    return str(response.json()["status"])


async def test_canceling_a_bought_demand_releases_its_line_allocation(
    graph: Graph, manager: Any
) -> None:
    allocation = await graph.bought_allocation()
    demand_id = allocation.demand_item_id
    assert await _status(manager, "bought", demand_id) == "allocated"

    response = await manager.post(f"{DEMANDS['bought']}/{demand_id}/cancel")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "canceled"
    assert await _allocations(manager, "bought", demand_id) == []
    assert await _status(manager, "bought", demand_id) == "canceled"


async def test_canceling_a_made_demand_releases_its_stock_allocation(
    db: Any, graph: Graph, manager: Any
) -> None:
    demand = await graph.made_demand()
    await SqlAlchemyMadeItemAllocationRepository(db).save(
        MadeItemDemandAllocation(
            demand_item_id=demand.id,
            lot_id=None,
            quantity=3.0,
            source=MadeItemAllocationSource.STOCK,
        )
    )
    await give_demand_facts(db, LifecycleAggregate.MADE_DEMANDS, demand.id, expected="allocated")
    await db.commit()

    response = await manager.post(f"{DEMANDS['made']}/{demand.id}/cancel")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "canceled"
    assert await _allocations(manager, "made", demand.id) == []


@pytest.mark.parametrize("family", ["bought", "made", "source"])
async def test_a_status_the_allocations_decide_cannot_be_set_by_hand(
    family: str, graph: Graph, manager: Any
) -> None:
    seed = {"bought": graph.bought_demand, "made": graph.made_demand}.get(
        family, graph.source_demand
    )
    demand = await seed()

    for target in ("open", "allocated", "ordered"):
        response = await manager.put(
            f"{DEMANDS[family]}/{demand.id}/status", params={"new_status": target}
        )
        assert response.status_code == 422, (target, response.text)
        assert response.json()["code"] == "DemandItemInvalidStatusTransitionError"
    assert await _status(manager, family, demand.id) == "open"


@pytest.mark.parametrize("family", ["bought", "made"])
async def test_an_update_records_the_changing_user(family: str, graph: Graph, manager: Any) -> None:
    seed = {"bought": graph.bought_demand, "made": graph.made_demand}[family]
    demand = await seed()

    response = await manager.put(
        f"{DEMANDS[family]}/{demand.id}", json={"quantity": 7, "unit": "pcs"}
    )

    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["creator_id"] == demand.creator_id
    assert updated["changed_by_id"] not in (None, demand.creator_id)
    assert updated["changed_by"]["id"] == updated["changed_by_id"]
    reread = (await manager.get(f"{DEMANDS[family]}/{demand.id}")).json()
    assert reread["changed_by_id"] == updated["changed_by_id"]


async def test_a_demand_holding_allocations_is_not_deleted(graph: Graph, manager: Any) -> None:
    allocation = await graph.bought_allocation()

    response = await manager.delete(f"{DEMANDS['bought']}/{allocation.demand_item_id}")

    assert response.status_code == 409, response.text
    assert response.json()["code"] == "DemandItemHasAllocationsError"
    assert len(await _allocations(manager, "bought", allocation.demand_item_id)) == 1


async def test_a_lot_refuses_a_demand_of_another_made_item(
    graph: Graph,
    manager: Any,
    source_made_item_id: int,  # noqa: F811
) -> None:
    demand = await graph.made_demand()
    assert demand.made_item_id != source_made_item_id

    response = await manager.post(
        f"{LOTS}/",
        json={
            "made_item_id": source_made_item_id,
            "project_id": demand.project_id,
            "quantity": 2.0,
            "demand_allocations": [{"demand_item_id": demand.id, "quantity": 2.0}],
        },
    )

    assert response.status_code == 409, response.text
    assert response.json()["code"] == "LotDemandMadeItemMismatchError"
    assert await _allocations(manager, "made", demand.id) == []


async def test_a_lot_refuses_a_demand_that_does_not_exist(
    manager: Any,
    project_id: int,  # noqa: F811
    source_made_item_id: int,  # noqa: F811
) -> None:
    response = await manager.post(
        f"{LOTS}/",
        json={
            "made_item_id": source_made_item_id,
            "project_id": project_id,
            "quantity": 2.0,
            "demand_allocations": [{"demand_item_id": 999_999, "quantity": 2.0}],
        },
    )

    assert response.status_code == 404, response.text
    assert response.json()["code"] == "DemandItemNotFoundError"
    listing = await manager.get(f"{LOTS}/")
    assert listing.status_code == 200, listing.text
    assert listing.json()["items"] == []


async def test_switching_the_material_source_replaces_the_raw_material_demand(
    db: Any,
    manager: Any,
    owner: Any,  # noqa: F811
    project_id: int,  # noqa: F811
    source_made_item_id: int,  # noqa: F811
) -> None:
    lot = await _create_lot(manager, source_made_item_id, project_id)
    old_demand_id = lot["input_demand_id"]
    assert old_demand_id is not None
    other_source_item_id = await _make_source_item(db, owner.id, suffix="2")

    response = await manager.put(
        f"{LOTS}/{lot['id']}/material-source",
        json={
            "source_item_id": other_source_item_id,
            "confirm_replace_demand": True,
            "expected_edit_version": lot["edit_version"],
        },
    )

    assert response.status_code == 200, response.text
    new_demand_id = (await _get_lot(manager, lot["id"]))["input_demand_id"]
    assert new_demand_id not in (None, old_demand_id)
    old = (await manager.get(f"{DEMANDS['source']}/{old_demand_id}")).json()
    assert (old["status"], old["canceled_at"] is not None) == ("canceled", True)
    new = (await manager.get(f"{DEMANDS['source']}/{new_demand_id}")).json()
    assert (new["status"], new["canceled_at"]) == ("open", None)


async def test_allocating_a_demand_again_to_the_same_line_is_refused(
    graph: Graph, manager: Any
) -> None:
    # Creating would replace the existing 5 with 2, so the quantity of the
    # existing allocation is changed through its own update instead.
    allocation = await graph.bought_allocation()

    response = await manager.post(
        ALLOCATIONS["bought"],
        json={
            "demand_item_id": allocation.demand_item_id,
            "order_item_id": allocation.order_item_id,
            "quantity": 2.0,
        },
    )

    assert response.status_code == 409, response.text
    assert response.json()["code"] == "AllocationAlreadyExistsError"
    [kept] = await _allocations(manager, "bought", allocation.demand_item_id)
    assert kept["quantity"] == 5.0
