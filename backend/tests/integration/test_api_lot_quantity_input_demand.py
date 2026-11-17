"""
A DRAFT lot's quantity edit takes its raw material demand along in
proportion, by the rules of a direct edit of the demand: an open demand is
resized, while an allocated demand, or a size that is no whole number of a
counted unit, refuses the lot edit with the demand's own error and changes
neither.
"""

from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_demand_item_model import (
    SourceItemDemandItemOrmModel,
)
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration import _lifecycle_seed as seed
from tests.integration._edit_versions import lot_version

LOTS = "/api/v1/web/production-lots"


@pytest.fixture
async def writer(auth_client: Any) -> Any:
    return await auth_client(permissions=[Permission.WRITE_LOTS])


async def _lot_with_demand(
    db: AsyncSession, lot_quantity: float, demand_quantity: float, unit: str, status: str = "open"
) -> tuple[int, int]:
    lot = await seed.lot(db, "draft", quantity=lot_quantity)
    demand = await seed.source_demand(
        db, status, lot_id=lot.id, quantity=demand_quantity, unit=unit
    )
    lot.input_demand_id = demand.id
    await db.commit()
    return lot.id, demand.id


async def _stored(db: AsyncSession, lot_id: int, demand_id: int) -> tuple[float, float]:
    lot = await db.get(ProductionLotOrmModel, lot_id, populate_existing=True)
    demand = await db.get(SourceItemDemandItemOrmModel, demand_id, populate_existing=True)
    assert lot is not None and demand is not None
    return lot.quantity, demand.quantity


async def _edit(client: Any, lot_id: int, quantity: float) -> Any:
    return await client.patch(
        f"{LOTS}/{lot_id}",
        json={"quantity": quantity, "expected_edit_version": await lot_version(client, lot_id)},
    )


async def test_lot_quantity_edit_resizes_the_open_raw_material_demand(
    db: AsyncSession, writer: Any
) -> None:
    lot_id, demand_id = await _lot_with_demand(db, 4.0, 6.0, "kg")

    edited = await _edit(writer, lot_id, 6)

    assert edited.status_code == 200, edited.text
    assert await _stored(db, lot_id, demand_id) == (6.0, 9.0)


async def test_lot_quantity_edit_refuses_a_fraction_of_counted_pieces(
    db: AsyncSession, writer: Any
) -> None:
    lot_id, demand_id = await _lot_with_demand(db, 2.0, 3.0, "pcs")

    refused = await _edit(writer, lot_id, 3)

    assert refused.status_code == 422, refused.text
    assert refused.json()["code"] == "FractionalPiecesError"
    assert await _stored(db, lot_id, demand_id) == (2.0, 3.0)


async def test_lot_quantity_edit_refuses_an_allocated_raw_material_demand(
    db: AsyncSession, writer: Any
) -> None:
    lot_id, demand_id = await _lot_with_demand(db, 4.0, 4.0, "kg", status="allocated")
    order = await seed.order(db, "draft")
    line = await seed.line(db, order, "pending")
    line.line_type, line.bought_item_id, line.source_item_id = "SOURCE", None, 1
    demand = await db.get(SourceItemDemandItemOrmModel, demand_id)
    assert demand is not None
    await seed.source_allocation(db, demand, line, 4.0)
    await db.commit()

    refused = await _edit(writer, lot_id, 6)

    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "SourceItemDemandAlreadyOrderedError"
    assert await _stored(db, lot_id, demand_id) == (4.0, 4.0)
