"""
Arrived pieces fill a line oldest demand first, so an allocation of an older
demand that sorts ahead of a younger one would take the pieces that already
reached the younger one and move it back from fulfilled. Such an allocation
is refused, and auto-allocate passes over the line.
"""

from dataclasses import replace
from typing import Any

import pytest

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_demand_item_model import (
    BoughtItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_repository.demand_item import (
    SqlAlchemyBoughtItemDemandItemRepository,
)
from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration.repository_reads._graph import Graph

ALL = [
    Permission.WRITE_ORDERS,
    Permission.MANAGE_ORDERS,
    Permission.WRITE_ALLOCATIONS,
    Permission.RECEIVE_DELIVERIES,
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


async def _status(db: Any, demand_id: int) -> str:
    row = await db.get(BoughtItemDemandItemOrmModel, demand_id, populate_existing=True)
    return row.status


async def _line_delivered_for(graph: Graph, buyer: Any, newer: int) -> int:
    """A line of 10 carrying `newer`'s share of 5, with 5 pieces delivered."""
    order = await graph.order()
    project = await graph.project()
    created = await buyer.post(
        f"{API_WEB}/orders/{order.id}/items",
        json={
            "order_id": order.id,
            "supplier_id": order.supplier_id,
            "project_id": project.id,
            "quantity": 10,
            "unit": "pcs",
            "bought_item_id": (await graph.bought_item()).id,
            "bought_demand_allocations": [{"demand_item_id": newer, "quantity": 5}],
        },
    )
    assert created.status_code == 201, created.text
    line = int(created.json()["id"])
    ordered = await buyer.put(f"{API_WEB}/orders/{order.id}/items/{line}/mark-ordered")
    assert ordered.status_code == 200, ordered.text
    delivered = await buyer.put(
        f"{API_WEB}/bought-items-allocations/order-item/{line}/deliver", params={"quantity": 5}
    )
    assert delivered.status_code == 200, delivered.text
    return line


async def test_an_older_demand_cannot_take_the_pieces_a_younger_one_received(
    graph: Graph, buyer: Any, db: Any
) -> None:
    older = await _open_demand(graph, 5.0)
    newer = await _open_demand(graph, 5.0)
    line = await _line_delivered_for(graph, buyer, newer)
    assert await _status(db, newer) == "fulfilled"

    refused = await buyer.post(
        f"{API_WEB}/bought-items-allocations/",
        json={"demand_item_id": older, "order_item_id": line, "quantity": 5},
    )

    assert refused.status_code == 409, refused.text
    assert await _status(db, newer) == "fulfilled"


async def test_auto_allocate_passes_over_a_line_whose_pieces_reached_another_demand(
    graph: Graph, buyer: Any, db: Any
) -> None:
    older = await _open_demand(graph, 5.0)
    newer = await _open_demand(graph, 5.0)
    await _line_delivered_for(graph, buyer, newer)

    allocated = await buyer.post(f"{API_WEB}/bought-items-allocations/demand/{older}/auto-allocate")

    assert allocated.status_code == 200, allocated.text
    assert allocated.json()["allocations_created"] == 0
    assert await _status(db, newer) == "fulfilled"
