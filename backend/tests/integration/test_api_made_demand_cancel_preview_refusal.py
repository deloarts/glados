"""
Canceling a made item demand whose lot already made good pieces: the lot's
own cancel refuses such a lot and points to force-complete, so the demand
cancel is refused as well. The cancel preview marks that lot as refusing,
so it never promises a cancel that is then refused.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.models.made_item_demand_item_model import (
    MadeItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration import _lifecycle_seed as seed

DEMANDS = "/api/v1/web/made-items-demands"


async def test_made_demand_cancel_preview_marks_a_lot_with_good_pieces_as_refusing(
    db: AsyncSession, auth_client: Any
) -> None:
    lot = await seed.lot(db, "in_progress")
    position = await seed.position(db, lot, "external", "in_progress")
    order = await seed.order(db, "partially_delivered", ordered_date=seed.NOW)
    await seed.line(
        db, order, "partially_delivered", at=position, ordered_date=seed.NOW, quantity_delivered=4.0
    )
    demand = await seed.made_demand(db, "ordered", lot, 10.0)
    await db.commit()
    await seed.settle(db)
    manager = await auth_client(
        permissions=[
            Permission.WRITE_DEMAND_ITEMS,
            Permission.MANAGE_DEMAND_ITEMS,
            Permission.WRITE_LOTS,
            Permission.MANAGE_LOTS,
        ]
    )

    impact = (await manager.get(f"{DEMANDS}/{demand.id}/cancel-impact")).json()
    canceled = await manager.post(f"{DEMANDS}/{demand.id}/cancel")

    [lot_impact] = impact["lots"]
    assert (lot_impact["will_cancel"], lot_impact["cancel_refused"]) == (True, True)
    assert canceled.status_code == 422, canceled.text
    assert "force-complete" in canceled.json()["detail"]
    stored_lot = await db.get(ProductionLotOrmModel, lot.id, populate_existing=True)
    stored_demand = await db.get(MadeItemDemandItemOrmModel, demand.id, populate_existing=True)
    assert stored_lot is not None and stored_lot.status == "in_progress"
    assert stored_demand is not None and stored_demand.canceled_at is None
