"""
Marking a bought or source item demand fulfilled by hand keeps only the
pieces that already reached it on each order line and releases the rest of
its allocations, so the line is not held by a demand that waits for nothing.
The pieces a line delivered stay with the demands they reached in the fill
order, and a line freed this way can be shrunk.
"""

from dataclasses import replace
from typing import Any

import pytest

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_repository.demand_item import (
    SqlAlchemyBoughtItemDemandItemRepository,
)
from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration._edit_versions import line_version
from tests.integration.repository_reads._graph import Graph

ORDERS = f"{API_WEB}/orders"
ALL = [
    Permission.WRITE_ORDERS,
    Permission.MANAGE_ORDERS,
    Permission.WRITE_ALLOCATIONS,
    Permission.RECEIVE_DELIVERIES,
    Permission.WRITE_DEMAND_ITEMS,
    Permission.MANAGE_DEMAND_ITEMS,
]


@pytest.fixture
async def graph(db: Any, create_user: Any) -> Graph:
    user = await create_user(username="creator", email="creator@example.com")
    other = await create_user(username="receiver", email="receiver@example.com")
    return Graph(db, user, other)


@pytest.fixture
async def buyer(auth_client: Any) -> Any:
    return await auth_client(username="buyer", email="buyer@example.com", permissions=ALL)


async def _open_demand(graph: Graph, quantity: float) -> int:
    template = await graph.bought_demand()
    saved = await SqlAlchemyBoughtItemDemandItemRepository(graph.db).save(
        replace(template, id=0, quantity=quantity, status=BoughtItemDemandStatus.OPEN, changes=[])
    )
    await graph.db.commit()
    return saved.id


async def _ordered_line(
    graph: Graph, buyer: Any, quantity: float, item: dict[str, Any], delivered: float
) -> tuple[int, int]:
    """An ordered line of `quantity` carrying the allocations in `item`, with
    `delivered` pieces booked, as (order id, line id)."""
    order = await graph.order()
    project = await graph.project()
    created = await buyer.post(
        f"{ORDERS}/{order.id}/items",
        json={
            "order_id": order.id,
            "supplier_id": order.supplier_id,
            "project_id": project.id,
            "quantity": quantity,
            "unit": "pcs",
            **item,
        },
    )
    assert created.status_code == 201, created.text
    line = int(created.json()["id"])
    ordered = await buyer.put(f"{ORDERS}/{order.id}/items/{line}/mark-ordered")
    assert ordered.status_code == 200, ordered.text
    if delivered:
        booked = await buyer.put(
            f"{API_WEB}/bought-items-allocations/order-item/{line}/deliver",
            params={"quantity": delivered},
        )
        assert booked.status_code == 200, booked.text
    return order.id, line


async def _bought_line(
    graph: Graph, buyer: Any, quantity: float, shares: dict[int, float], delivered: float
) -> tuple[int, int]:
    return await _ordered_line(
        graph,
        buyer,
        quantity,
        {
            "bought_item_id": (await graph.bought_item()).id,
            "bought_demand_allocations": [
                {"demand_item_id": demand_id, "quantity": share}
                for demand_id, share in shares.items()
            ],
        },
        delivered,
    )


async def _fulfil(client: Any, family: str, demand_id: int) -> dict[str, Any]:
    response = await client.put(
        f"{API_WEB}/{family}/{demand_id}/status", params={"new_status": "fulfilled"}
    )
    assert response.status_code == 200, response.text
    return dict(response.json())


async def _allocated(client: Any, route: str, demand_id: int) -> dict[int | None, float]:
    response = await client.get(f"{API_WEB}/{route}/demand/{demand_id}")
    assert response.status_code == 200, response.text
    return {row["order_item_id"]: row["quantity"] for row in response.json()}


async def test_a_fulfilled_demand_keeps_only_its_arrived_pieces(graph: Graph, buyer: Any) -> None:
    demand = await _open_demand(graph, 5.0)
    _, line = await _bought_line(graph, buyer, 10, {demand: 5}, delivered=2)

    fulfilled = await _fulfil(buyer, "bought-items-demands", demand)

    assert fulfilled["status"] == "fulfilled"
    assert await _allocated(buyer, "bought-items-allocations", demand) == {line: 2}


async def test_a_line_freed_by_the_fulfil_can_be_shrunk(graph: Graph, buyer: Any) -> None:
    demand = await _open_demand(graph, 5.0)
    order_id, line = await _bought_line(graph, buyer, 5, {demand: 5}, delivered=0)

    await _fulfil(buyer, "bought-items-demands", demand)
    shrunk = await buyer.put(
        f"{ORDERS}/{order_id}/items/{line}",
        json={
            "quantity": 3,
            "unit": "pcs",
            "expected_edit_version": await line_version(buyer, order_id, line),
        },
    )

    assert await _allocated(buyer, "bought-items-allocations", demand) == {}
    assert shrunk.status_code == 200, shrunk.text
    assert shrunk.json()["quantity"] == 3


async def test_the_other_demands_on_the_line_keep_what_reached_them(
    graph: Graph, buyer: Any
) -> None:
    older = await _open_demand(graph, 5.0)
    younger = await _open_demand(graph, 5.0)
    await _bought_line(graph, buyer, 10, {older: 5, younger: 5}, delivered=7)

    await _fulfil(buyer, "bought-items-demands", younger)

    older_allocated = await _allocated(buyer, "bought-items-allocations", older)
    younger_allocated = await _allocated(buyer, "bought-items-allocations", younger)
    assert list(older_allocated.values()) == [5]
    assert list(younger_allocated.values()) == [2]


async def test_an_older_demand_fulfilled_early_leaves_the_rest_to_the_younger(
    graph: Graph, buyer: Any
) -> None:
    older = await _open_demand(graph, 5.0)
    younger = await _open_demand(graph, 5.0)
    _, line = await _bought_line(graph, buyer, 10, {older: 5, younger: 5}, delivered=3)

    await _fulfil(buyer, "bought-items-demands", older)
    booked = await buyer.put(
        f"{API_WEB}/bought-items-allocations/order-item/{line}/deliver", params={"quantity": 5}
    )
    assert booked.status_code == 200, booked.text

    assert await _allocated(buyer, "bought-items-allocations", older) == {line: 3}
    younger_demand = await buyer.get(f"{API_WEB}/bought-items-demands/{younger}")
    assert younger_demand.json()["status"] == "fulfilled"


async def test_a_source_demand_keeps_only_its_arrived_pieces(graph: Graph, buyer: Any) -> None:
    demand = await graph.source_demand()
    _, line = await _ordered_line(
        graph,
        buyer,
        10,
        {
            "source_item_id": (await graph.source_item()).id,
            "source_demand_allocations": [{"demand_item_id": demand.id, "quantity": 10}],
        },
        delivered=4,
    )

    fulfilled = await _fulfil(buyer, "source-item-demands", demand.id)

    assert fulfilled["status"] == "fulfilled"
    assert await _allocated(buyer, "source-item-allocations", demand.id) == {line: 4}
