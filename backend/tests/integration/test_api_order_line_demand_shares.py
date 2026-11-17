"""
A new order line takes the share of each demand the request names: a short
line meant for the second of two demands covers that one, source item
demands are allocated in the same request as their line, and shares that do
not fit the line, name a demand twice or put bought demands on a source line
answer 422 before anything is written.
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
from tests.integration.repository_reads._graph import Graph

BUYER = [Permission.WRITE_ORDERS, Permission.MANAGE_ORDERS]


@pytest.fixture
async def graph(db: Any, create_user: Any) -> Graph:
    user = await create_user(username="creator", email="creator@example.com")
    other = await create_user(username="receiver", email="receiver@example.com")
    return Graph(db, user, other)


@pytest.fixture
async def buyer(auth_client: Any) -> Any:
    return await auth_client(username="buyer", email="buyer@example.com", permissions=BUYER)


async def _open_demand(graph: Graph, quantity: float) -> int:
    template = await graph.bought_demand()
    saved = await SqlAlchemyBoughtItemDemandItemRepository(graph.db).save(
        replace(template, id=0, quantity=quantity, status=BoughtItemDemandStatus.OPEN, changes=[])
    )
    await graph.db.commit()
    return saved.id


async def _line(buyer: Any, graph: Graph, quantity: float, **shares: Any) -> Any:
    order = await graph.order()
    project = await graph.project()
    body: dict[str, Any] = {
        "order_id": order.id,
        "supplier_id": order.supplier_id,
        "project_id": project.id,
        "quantity": quantity,
        "unit": "pcs",
        **shares,
    }
    if "source_item_id" not in body:
        body["bought_item_id"] = (await graph.bought_item()).id
    return await buyer.post(f"{API_WEB}/orders/{order.id}/items", json=body)


async def _allocated(buyer: Any, family: str, demand_id: int) -> float:
    path = {"bought": "bought-items-allocations", "source": "source-item-allocations"}[family]
    response = await buyer.get(f"{API_WEB}/{path}/demand/{demand_id}")
    assert response.status_code == 200, response.text
    return sum(a["quantity"] for a in response.json())


async def test_a_short_line_covers_the_demand_it_is_named_for(graph: Graph, buyer: Any) -> None:
    first = await _open_demand(graph, 5.0)
    second = await _open_demand(graph, 3.0)

    response = await _line(
        buyer,
        graph,
        3.0,
        bought_demand_allocations=[{"demand_item_id": second, "quantity": 3.0}],
    )

    assert response.status_code == 201, response.text
    assert await _allocated(buyer, "bought", first) == 0.0
    assert await _allocated(buyer, "bought", second) == 3.0


async def test_a_source_line_allocates_its_source_demand_in_the_same_request(
    graph: Graph, buyer: Any
) -> None:
    demand = await graph.source_demand()
    item = await graph.source_item()
    before = await _allocated(buyer, "source", demand.id)

    response = await _line(
        buyer,
        graph,
        4.0,
        source_item_id=item.id,
        source_demand_allocations=[{"demand_item_id": demand.id, "quantity": 4.0}],
    )

    assert response.status_code == 201, response.text
    assert await _allocated(buyer, "source", demand.id) == before + 4.0


@pytest.mark.parametrize(
    ("shares", "reason"),
    [
        (
            {"bought_demand_allocations": [{"demand_item_id": 1, "quantity": 6.0}]},
            "exceed the line's quantity",
        ),
        (
            {
                "bought_demand_allocations": [
                    {"demand_item_id": 1, "quantity": 1.0},
                    {"demand_item_id": 1, "quantity": 1.0},
                ]
            },
            "only once",
        ),
    ],
    ids=["above_the_line", "a_demand_twice"],
)
async def test_shares_that_do_not_fit_answer_422(
    graph: Graph, buyer: Any, shares: dict[str, Any], reason: str
) -> None:
    await _open_demand(graph, 5.0)

    response = await _line(buyer, graph, 5.0, **shares)

    assert response.status_code == 422, response.text
    assert reason in response.text


async def test_bought_demands_on_a_source_line_answer_422(graph: Graph, buyer: Any) -> None:
    demand = await _open_demand(graph, 5.0)
    item = await graph.source_item()

    response = await _line(
        buyer,
        graph,
        5.0,
        source_item_id=item.id,
        bought_demand_allocations=[{"demand_item_id": demand, "quantity": 5.0}],
    )

    assert response.status_code == 422, response.text
    assert "bought item line only" in response.text
