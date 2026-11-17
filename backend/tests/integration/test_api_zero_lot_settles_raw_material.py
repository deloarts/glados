"""
A scrap that takes a lot to zero settles its raw material demand the way a
lot cancel does: a demand whose material was already ordered is not
canceled behind the supplier's back but fulfilled at what arrived, and its
still open supplier line is named to purchasing.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_demand_item_model import (
    SourceItemDemandItemOrmModel,
)
from src.modules.fulfillment.domain.events.lot_events import LotSupplierLinesToSettle
from tests.integration import _lifecycle_seed as seed
from tests.integration._edit_versions import lot_version
from tests.integration._edit_versions import production_order_version
from tests.integration.lifecycle_matrix._shapes import WEB
from tests.integration.lifecycle_matrix._shapes import catalogue
from tests.integration.lifecycle_matrix._writers import EVERY_WRITE_PERMISSION
from tests.integration.test_api_scrap_pieces import _seed_lot_and_order
from tests.integration.test_api_scrap_pieces import _seed_production_settings  # noqa: F401


async def test_a_lot_scrapped_to_zero_settles_its_ordered_raw_material(
    db: AsyncSession, auth_client: Any, create_user: Any, published_events: list[object]
) -> None:
    owner = await create_user(username="owner", email="owner@example.com")
    await catalogue(db, owner)
    client = await auth_client(permissions=EVERY_WRITE_PERMISSION)
    lot, order = await _seed_lot_and_order(db, owner.id, lot_number="LOT-RAW", quantity=5.0)
    demand = await seed.source_demand(
        db, "ordered", lot_id=lot.id, quantity=5.0, source_item_id=1, unit="pcs"
    )
    supplier_order = await seed.order(db, "ordered", ordered_date=seed.NOW)
    line = await seed.line(db, supplier_order, "ordered", ordered_date=seed.NOW, quantity=5.0)
    line.line_type, line.bought_item_id, line.source_item_id = "SOURCE", None, 1
    await seed.source_allocation(db, demand, line, 5.0)
    demand_id = demand.id
    stored_lot = await db.get(ProductionLotOrmModel, lot.id)
    assert stored_lot is not None
    stored_lot.input_demand_id = demand_id
    await db.commit()
    await seed.settle(db)
    started = await client.post(f"{WEB}/production-orders/{order.id}/start", json={})
    assert started.status_code == 200, started.text
    published_events.clear()

    scrapped = await client.post(
        f"{WEB}/production-orders/{order.id}/scrap",
        json={
            "quantity": 5.0,
            "reason": "tool_breakage",
            "create_replacement": False,
            "expected_edit_version": await production_order_version(client, order.id),
            "expected_lot_edit_version": await lot_version(client, lot.id),
        },
    )

    assert scrapped.status_code == 200, scrapped.text
    db.expire_all()
    stored = await db.get(SourceItemDemandItemOrmModel, demand_id)
    assert stored is not None
    assert stored.canceled_at is None
    notices = [e for e in published_events if isinstance(e, LotSupplierLinesToSettle)]
    assert len(notices) == 1 and notices[0].open_lines, notices
