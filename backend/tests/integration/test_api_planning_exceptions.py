"""
The planner's exception list over HTTP: a bought demand whose order line
lost pieces and has a rest no allocation covers, a made demand left short by
a force-completed lot, a live lot whose raw material is not allocated and a
live lot past its target date each appear once with their kind; a fulfilled
demand does not.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any

import pytest

from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_repository.demand_item import (
    SqlAlchemyBoughtItemDemandItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.order_item import (
    SqlAlchemyOrderItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.platform.const import API_WEB
from tests.integration.repository_reads._graph import Graph

EXCEPTIONS = f"{API_WEB}/production-exceptions/"


# The scenarios write facts straight to the rows, as the builders do.
pytestmark = pytest.mark.usefixtures("allow_lifecycle_drift")


@pytest.fixture
async def graph(db: Any, create_user: Any) -> Graph:
    user = await create_user(username="creator", email="creator@example.com")
    other = await create_user(username="operator", email="operator@example.com")
    return Graph(db, user, other)


@pytest.fixture
async def client(auth_client: Any) -> Any:
    return await auth_client(username="planner", email="planner@example.com", permissions=[])


async def _rows(client: Any, kind: str) -> list[dict[str, Any]]:
    response = await client.get(EXCEPTIONS)
    assert response.status_code == 200, response.text
    return [row for row in response.json() if row["kind"] == kind]


async def test_a_bought_demand_short_after_lost_pieces(graph: Graph, client: Any) -> None:
    allocation = await graph.bought_allocation()
    lines = SqlAlchemyOrderItemRepository(graph.db)
    line = await lines.get_by_id(allocation.order_item_id)
    assert line is not None
    line.quantity_rejected_lost = 1.0
    await lines.save(line)
    await graph.db.commit()

    [row] = await _rows(client, "lost_at_receipt")

    assert (row["family"], row["demand_id"]) == ("bought", allocation.demand_item_id)
    assert (row["order_id"], row["line_position"]) == (line.order_id, line.position)
    assert row["quantity_short"] == 5.0
    assert row["order_number"]


async def test_a_fulfilled_demand_is_not_listed(graph: Graph, client: Any) -> None:
    allocation = await graph.bought_allocation()
    lines = SqlAlchemyOrderItemRepository(graph.db)
    line = await lines.get_by_id(allocation.order_item_id)
    assert line is not None
    line.quantity_rejected_lost = 1.0
    await lines.save(line)
    demands = SqlAlchemyBoughtItemDemandItemRepository(graph.db)
    demand = await demands.get_by_id(allocation.demand_item_id)
    assert demand is not None
    demand.fulfilled_manually_at = datetime.now(UTC)
    await demands.save(demand)
    await graph.db.commit()

    assert await _rows(client, "lost_at_receipt") == []


async def test_a_made_demand_left_short_by_a_force_complete(graph: Graph, client: Any) -> None:
    allocation = await graph.made_allocation()
    lots = SqlAlchemyProductionLotRepository(graph.db)
    lot = await lots.get_by_id(allocation.lot_id or 0)
    assert lot is not None
    lot.force_completed_at = datetime.now(UTC) - timedelta(days=1)
    await lots.save(lot)
    await graph.db.commit()

    [row] = await _rows(client, "lot_ended_short")

    assert (row["family"], row["demand_id"], row["lot_id"]) == (
        "made",
        allocation.demand_item_id,
        lot.id,
    )
    assert row["quantity_short"] == 5.0


async def test_a_live_lot_with_unallocated_raw_material(graph: Graph, client: Any) -> None:
    demand = await graph.source_demand()
    await graph.production_order()

    [row] = await _rows(client, "material_short")

    assert (row["demand_id"], row["unallocated"], row["quantity_short"]) == (demand.id, 10.0, 10.0)
    assert row["lot_id"] == demand.lot_id


async def test_a_live_lot_past_its_target_date(graph: Graph, client: Any) -> None:
    await graph.production_order()
    lot = await graph.lot()
    lots = SqlAlchemyProductionLotRepository(graph.db)
    stored = await lots.get_by_id(lot.id)
    assert stored is not None
    stored.required_delivery_date = (datetime.now(UTC) - timedelta(days=3)).date()
    await lots.save(stored)
    await graph.db.commit()

    [row] = await _rows(client, "late")

    assert (row["lot_id"], row["target_date"]) == (
        lot.id,
        stored.required_delivery_date.isoformat(),
    )
