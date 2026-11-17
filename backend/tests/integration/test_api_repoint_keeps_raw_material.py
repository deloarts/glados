"""
A bought line that a lot's raw material demand draws on keeps its bought
item: that demand takes no substitute, so pointing the line at another item
is refused while the allocation is there, and the line stays as it was.
"""

from dataclasses import replace
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

import tests.integration.test_api_order_item_capacity as capacity
from src.modules.catalogue.adapters.outbound.persistence.repositories.bought_item_repository.item import (
    SqlAlchemyBoughtItemRepository,
)
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.source_item_allocation_repository import (
    SqlAlchemySourceItemAllocationRepository,
)
from src.modules.fulfillment.domain.entities.source_item_allocation import (
    SourceItemDemandAllocation,
)
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration._demand_facts import give_demand_facts
from tests.integration.repository_reads._graph import Graph


@pytest.fixture
async def graph(db: AsyncSession, create_user: Any) -> Graph:
    user = await create_user(username="owner", email="owner@example.com")
    other = await create_user(username="receiver", email="receiver@example.com")
    return Graph(db, user, other)


async def test_a_line_with_raw_material_is_not_pointed_at_another_item(
    db: AsyncSession, graph: Graph, auth_client: Any
) -> None:
    client = await auth_client(
        username="buyer",
        email="buyer@example.com",
        permissions=[
            Permission.WRITE_ORDERS,
            Permission.MANAGE_ORDERS,
            Permission.WRITE_ALLOCATIONS,
        ],
    )
    line = await graph.bought_order_item()
    demand_id = await capacity._bought_sourced_source_demand(graph)
    await SqlAlchemySourceItemAllocationRepository(db).save(
        SourceItemDemandAllocation(demand_item_id=demand_id, order_item_id=line.id, quantity=3.0)
    )
    await give_demand_facts(
        db, LifecycleAggregate.SOURCE_DEMANDS, demand_id, expected="ordered", exact=False
    )
    item = await graph.bought_item()
    other = await SqlAlchemyBoughtItemRepository(db).save(
        replace(
            item,
            id=0,
            part_number="B-2",
            order_code_1="OC-2",
            gtin=None,
            ean=None,
            edp_part_id=None,
            pdm_file_id=None,
            data_source=DataSource.WEB,
        )
    )
    await db.commit()
    row = await db.get(OrderItemOrmModel, line.id, populate_existing=True)
    assert row is not None
    order_id, quantity, unit, version = row.order_id, row.quantity, row.unit, row.edit_version

    response = await client.put(
        f"{API_WEB}/orders/{order_id}/items/{line.id}",
        json={
            "quantity": quantity,
            "unit": unit,
            "bought_item_id": other.id,
            "expected_edit_version": version,
        },
    )

    assert response.status_code == 409, response.text
    assert response.json()["code"] == "OrderItemHoldsRawMaterialError"
    row = await db.get(OrderItemOrmModel, line.id, populate_existing=True)
    assert row is not None and row.bought_item_id == item.id
