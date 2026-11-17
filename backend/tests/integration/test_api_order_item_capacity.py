"""
A bought line's capacity is shared by bought item demands and by source
item demands sourced from the same bought item. On the throwaway SQLite
file, both allocation repositories sum the two allocation tables for a
line, and through HTTP a source allocation is refused once bought demands
hold the whole line, while what they leave stays allocatable.
"""

from typing import Any

import pytest

from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_repository.allocation import (
    SqlAlchemyBoughtItemAllocationRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.source_item_allocation_repository import (
    SqlAlchemySourceItemAllocationRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.source_item_demand_repository import (
    SqlAlchemySourceItemDemandRepository,
)
from src.modules.fulfillment.domain.entities.bought_item_allocation import (
    BoughtItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.source_item_allocation import (
    SourceItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration._demand_facts import give_demand_facts
from tests.integration.repository_reads._graph import TODAY
from tests.integration.repository_reads._graph import Graph
from tests.integration.repository_reads._graph import make

SOURCE_ALLOCATIONS = f"{API_WEB}/source-item-allocations"


@pytest.fixture
async def graph(db, create_user) -> Graph:
    user = await create_user(username="owner", email="owner@example.com")
    other = await create_user(username="receiver", email="receiver@example.com")
    return Graph(db, user, other)


@pytest.fixture
async def allocator(auth_client) -> Any:
    return await auth_client(
        username="allocator",
        email="allocator@example.com",
        permissions=[Permission.WRITE_ALLOCATIONS],
    )


async def _bought_sourced_source_demand(graph: Graph) -> int:
    """An open source item demand of 10 whose material is the graph's bought
    item, so it can draw on the same bought lines as a bought demand."""
    item = await graph.bought_item()
    lot = await graph.lot()
    project = await graph.project()
    demand = await SqlAlchemySourceItemDemandRepository(graph.db).save(
        make(
            SourceItemDemandItem,
            status=SourceItemDemandStatus.OPEN,
            quantity=10.0,
            unit="pcs",
            items_per_unit=1.0,
            high_priority=False,
            notify_on_delivery=False,
            desired_delivery_date=TODAY,
            creator_id=graph.uid,
            bought_item_id=item.id,
            source_item_id=None,
            lot_id=lot.id,
            project_id=project.id,
        )
    )
    await graph.db.commit()
    return demand.id


async def _bought_demand_holding(graph: Graph, quantity: float) -> int:
    """The graph's bought line of 10, with a bought demand holding
    `quantity` of it. Returns the line's id."""
    line = await graph.bought_order_item()
    demand = await graph.bought_demand()
    await SqlAlchemyBoughtItemAllocationRepository(graph.db).save(
        BoughtItemDemandAllocation(
            demand_item_id=demand.id, order_item_id=line.id, quantity=quantity
        )
    )
    # The ordered line of 10 derives ORDERED once the demand of 10 holds all
    # of it, ALLOCATED below that.
    covered = "ordered" if quantity >= 10.0 else "allocated"
    await give_demand_facts(
        graph.db, LifecycleAggregate.BOUGHT_DEMANDS, demand.id, expected=covered
    )
    await graph.db.commit()
    return line.id


async def test_both_repositories_sum_both_allocation_tables(db, graph: Graph) -> None:
    line_id = await _bought_demand_holding(graph, 5.0)
    source_demand_id = await _bought_sourced_source_demand(graph)
    await SqlAlchemySourceItemAllocationRepository(db).save(
        SourceItemDemandAllocation(
            demand_item_id=source_demand_id, order_item_id=line_id, quantity=3.0
        )
    )
    await give_demand_facts(
        db, LifecycleAggregate.SOURCE_DEMANDS, source_demand_id, expected="allocated"
    )
    untouched_line = await graph.source_order_item()
    await db.commit()

    for repo in (
        SqlAlchemyBoughtItemAllocationRepository(db),
        SqlAlchemySourceItemAllocationRepository(db),
    ):
        assert await repo.get_allocated_quantity_for_order_item(line_id) == 8.0
        assert await repo.get_allocated_quantity_for_order_item(untouched_line.id) == 0.0


async def test_a_source_allocation_is_refused_on_a_line_bought_demands_hold(
    graph: Graph, allocator: Any
) -> None:
    line_id = await _bought_demand_holding(graph, 10.0)
    source_demand_id = await _bought_sourced_source_demand(graph)

    response = await allocator.post(
        f"{SOURCE_ALLOCATIONS}/",
        json={"demand_item_id": source_demand_id, "order_item_id": line_id, "quantity": 1},
    )

    assert response.status_code == 422, response.text
    assert response.json()["code"] == "AllocationOverflowError"
    stored = await allocator.get(f"{SOURCE_ALLOCATIONS}/demand/{source_demand_id}")
    assert stored.status_code == 200, stored.text
    assert stored.json() == []


async def test_what_bought_demands_leave_on_a_line_stays_allocatable(
    graph: Graph, allocator: Any
) -> None:
    line_id = await _bought_demand_holding(graph, 6.0)
    source_demand_id = await _bought_sourced_source_demand(graph)

    too_much = await allocator.post(
        f"{SOURCE_ALLOCATIONS}/",
        json={"demand_item_id": source_demand_id, "order_item_id": line_id, "quantity": 5},
    )
    assert too_much.status_code == 422, too_much.text

    response = await allocator.post(
        f"{SOURCE_ALLOCATIONS}/",
        json={"demand_item_id": source_demand_id, "order_item_id": line_id, "quantity": 4},
    )

    assert response.status_code == 201, response.text
    stored = await allocator.get(f"{SOURCE_ALLOCATIONS}/demand/{source_demand_id}")
    assert stored.status_code == 200, stored.text
    assert [(a["order_item_id"], a["quantity"]) for a in stored.json()] == [(line_id, 4)]
