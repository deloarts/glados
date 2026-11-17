"""
A lot's raw material demand is canceled only while the lot has not started
production. Once a position started, a cancel would leave the lot waiting on
material and drop the material it already holds from the accounting, so both
cancel routes refuse it and the demand stops offering the action; the lot's
source is switched or the lot force-completed instead.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_demand_item_model import (
    SourceItemDemandItemOrmModel,
)
from tests.integration import _lifecycle_seed as seed
from tests.integration.lifecycle_matrix._shapes import WEB
from tests.integration.lifecycle_matrix._shapes import catalogue
from tests.integration.lifecycle_matrix._writers import EVERY_WRITE_PERMISSION
from tests.integration.test_api_scrap_pieces import _seed_lot_and_order
from tests.integration.test_api_scrap_pieces import _seed_production_settings  # noqa: F401

DEMANDS = f"{WEB}/source-item-demands"


async def _lot_with_raw_material(
    db: AsyncSession, auth_client: Any, create_user: Any, lot_number: str
) -> tuple[Any, int, int]:
    owner = await create_user(username="owner", email="owner@example.com")
    await catalogue(db, owner)
    client = await auth_client(permissions=EVERY_WRITE_PERMISSION)
    lot, order = await _seed_lot_and_order(db, owner.id, lot_number=lot_number, quantity=5.0)
    demand = await seed.source_demand(
        db, "open", lot_id=lot.id, quantity=5.0, source_item_id=1, unit="pcs"
    )
    demand_id = demand.id
    stored_lot = await db.get(ProductionLotOrmModel, lot.id)
    assert stored_lot is not None
    stored_lot.input_demand_id = demand_id
    await db.commit()
    await seed.settle(db)
    return client, demand_id, order.id


async def test_the_demand_of_a_lot_not_started_is_canceled(
    db: AsyncSession, auth_client: Any, create_user: Any
) -> None:
    client, demand_id, _order_id = await _lot_with_raw_material(
        db, auth_client, create_user, "LOT-IDLE"
    )
    read = await client.get(f"{DEMANDS}/{demand_id}")
    assert read.status_code == 200, read.text
    assert "cancel" in read.json()["actions"]

    canceled = await client.post(f"{DEMANDS}/{demand_id}/cancel", params={"cancel_lot": "false"})

    assert canceled.status_code == 200, canceled.text
    assert canceled.json()["status"] == "canceled"


async def test_the_demand_of_a_started_lot_is_not_canceled(
    db: AsyncSession, auth_client: Any, create_user: Any
) -> None:
    client, demand_id, order_id = await _lot_with_raw_material(
        db, auth_client, create_user, "LOT-STARTED"
    )
    started = await client.post(f"{WEB}/production-orders/{order_id}/start", json={})
    assert started.status_code == 200, started.text

    read = await client.get(f"{DEMANDS}/{demand_id}")
    assert read.status_code == 200, read.text
    assert "cancel" not in read.json()["actions"]

    by_cancel = await client.post(f"{DEMANDS}/{demand_id}/cancel", params={"cancel_lot": "true"})
    by_status = await client.put(
        f"{DEMANDS}/{demand_id}/status", params={"new_status": "canceled", "cancel_lot": "false"}
    )

    for refused in (by_cancel, by_status):
        assert refused.status_code == 409, refused.text
        assert refused.json()["code"] == "SourceItemDemandLotStartedError"
        assert "switch" in refused.json()["detail"].lower()
    db.expire_all()
    stored = await db.get(SourceItemDemandItemOrmModel, demand_id)
    assert stored is not None
    assert stored.canceled_at is None
