"""
Taking a lot's raw material from stock is the shortcut past ordering it: the
stock allocation counts as arrived material, so the lot's first in-house
step, which nothing could start before, is no longer waiting on raw material
and starts. A part taken from stock opens the step for that part only.
"""

import dataclasses
from typing import Any

import pytest

from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_order_repository import (
    SqlAlchemyProductionOrderRepository,
)
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration._tenant_day import tenant_today
from tests.integration.repository_reads._graph import Graph

ORDERS = f"{API_WEB}/production-orders"
STOCK = f"{API_WEB}/source-item-allocations/demand"
PERMISSIONS = [
    Permission.WRITE_PRODUCTION_ORDERS,
    Permission.MANAGE_PRODUCTION_ORDERS,
    Permission.WRITE_ALLOCATIONS,
    Permission.WRITE_DEMAND_ITEMS,
    Permission.MANAGE_DEMAND_ITEMS,
    Permission.WRITE_LOTS,
]


@pytest.fixture
async def graph(db: Any, create_user: Any) -> Graph:
    user = await create_user(username="creator", email="creator@example.com")
    other = await create_user(username="operator", email="operator@example.com")
    return Graph(db, user, other)


@pytest.fixture
async def client(auth_client: Any) -> Any:
    return await auth_client(
        username="planner", email="planner@example.com", permissions=PERMISSIONS
    )


async def _queued_order(graph: Graph) -> tuple[int, int]:
    """The lot's raw material demand of 10, nothing allocated, and a queued
    order of 10 on its first, internal position."""
    demand = await graph.source_demand()
    running = await graph.production_order()
    repo = SqlAlchemyProductionOrderRepository(graph.db)
    order = await repo.get_by_id(running.id)
    assert order is not None
    await repo.save(
        dataclasses.replace(
            order,
            status=ProductionOrderStatus.QUEUED,
            actual_start=None,
            started_operator_id=None,
        )
    )
    await graph.db.commit()
    await graph._settle_lot()
    return order.id, demand.id


async def test_raw_material_from_stock_lets_the_first_step_start(graph: Graph, client: Any) -> None:
    order_id, demand_id = await _queued_order(graph)

    before = await client.get(f"{ORDERS}/{order_id}")
    refused = await client.post(f"{ORDERS}/{order_id}/start", json={})
    taken = await client.post(f"{STOCK}/{demand_id}/fulfill-from-stock", json={"quantity": 10})
    after = await client.get(f"{ORDERS}/{order_id}")
    started = await client.post(f"{ORDERS}/{order_id}/start", json={})

    assert before.json()["waiting_on_raw_material"] is True
    assert refused.status_code == 422, refused.text
    assert refused.json()["code"] == "LotPositionOverflowError"
    assert taken.status_code == 200, taken.text
    assert after.json()["waiting_on_raw_material"] is False
    assert started.status_code == 200, started.text
    assert started.json()["status"] == "in_progress"


async def test_part_of_the_material_from_stock_opens_the_step_for_that_part(
    graph: Graph, client: Any
) -> None:
    order_id, demand_id = await _queued_order(graph)

    taken = await client.post(f"{STOCK}/{demand_id}/fulfill-from-stock", json={"quantity": 4})
    started = await client.post(f"{ORDERS}/{order_id}/start", json={})
    too_many = await client.post(
        f"{ORDERS}/{order_id}/completions",
        json={"quantity": 5, "completion_date": tenant_today().isoformat()},
    )
    enough = await client.post(
        f"{ORDERS}/{order_id}/completions",
        json={"quantity": 4, "completion_date": tenant_today().isoformat()},
    )

    assert taken.status_code == 200, taken.text
    assert started.status_code == 200, started.text
    assert too_many.status_code == 422, too_many.text
    assert enough.status_code == 200, enough.text


async def test_a_retried_take_from_stock_takes_the_quantity_once(graph: Graph, client: Any) -> None:
    _order_id, demand_id = await _queued_order(graph)
    headers = {"Idempotency-Key": "stock-1"}

    first = await client.post(
        f"{STOCK}/{demand_id}/fulfill-from-stock", json={"quantity": 4}, headers=headers
    )
    retry = await client.post(
        f"{STOCK}/{demand_id}/fulfill-from-stock", json={"quantity": 4}, headers=headers
    )

    assert first.status_code == 200, first.text
    assert retry.status_code == 200, retry.text
    assert retry.json()["total_fulfilled_from_stock"] == 4
    assert retry.json()["demand_status_changed_to"] is None
    held = (await client.get(f"{API_WEB}/source-item-allocations/demand/{demand_id}")).json()
    assert [a["quantity"] for a in held] == [4]


async def test_a_retried_allocation_create_is_answered_with_the_allocation(
    graph: Graph, client: Any
) -> None:
    line = await graph.bought_order_item()
    demand = await graph.bought_demand()
    headers = {"Idempotency-Key": "allocate-1"}
    body = {"demand_item_id": demand.id, "order_item_id": line.id, "quantity": 2}

    first = await client.post(f"{API_WEB}/bought-items-allocations/", json=body, headers=headers)
    retry = await client.post(f"{API_WEB}/bought-items-allocations/", json=body, headers=headers)

    assert first.status_code == 201, first.text
    assert retry.status_code == 201, retry.text
    assert (retry.json()["demand_item_id"], retry.json()["quantity"]) == (demand.id, 2)
