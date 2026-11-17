"""
Canceling the raw material demand of a lot that has not started asks the
caller what becomes of the lot: `cancel_lot=true` cancels the lot as well,
which settles the demand with it, and `cancel_lot=false` cancels only the
demand, leaving the lot to wait on raw material until its source is
switched. Without the choice both cancel routes refuse with 422, so no
client detaches a lot from its material by accident.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_demand_item_model import (
    SourceItemDemandItemOrmModel,
)
from tests.integration.lifecycle_matrix._shapes import WEB
from tests.integration.test_api_scrap_pieces import _seed_production_settings  # noqa: F401
from tests.integration.test_api_source_demand_cancel_started_lot import DEMANDS
from tests.integration.test_api_source_demand_cancel_started_lot import _lot_with_raw_material


async def _stored(db: AsyncSession, demand_id: int) -> tuple[Any, Any]:
    db.expire_all()
    demand = await db.get(SourceItemDemandItemOrmModel, demand_id)
    assert demand is not None
    lot = await db.get(ProductionLotOrmModel, demand.lot_id)
    assert lot is not None
    return demand, lot


async def test_a_cancel_without_the_lot_choice_is_refused(
    db: AsyncSession, auth_client: Any, create_user: Any
) -> None:
    client, demand_id, _order_id = await _lot_with_raw_material(
        db, auth_client, create_user, "LOT-ASK"
    )

    by_cancel = await client.post(f"{DEMANDS}/{demand_id}/cancel")
    by_status = await client.put(f"{DEMANDS}/{demand_id}/status", params={"new_status": "canceled"})

    for refused in (by_cancel, by_status):
        assert refused.status_code == 422, refused.text
        assert refused.json()["code"] == "SourceItemDemandLotChoiceRequiredError"
    demand, lot = await _stored(db, demand_id)
    assert demand.canceled_at is None
    assert lot.input_demand_id == demand_id
    assert lot.canceled_at is None


async def test_canceling_only_the_demand_leaves_the_lot_waiting(
    db: AsyncSession, auth_client: Any, create_user: Any
) -> None:
    client, demand_id, _order_id = await _lot_with_raw_material(
        db, auth_client, create_user, "LOT-KEEP"
    )

    canceled = await client.put(
        f"{DEMANDS}/{demand_id}/status", params={"new_status": "canceled", "cancel_lot": "false"}
    )

    assert canceled.status_code == 200, canceled.text
    assert canceled.json()["status"] == "canceled"
    demand, lot = await _stored(db, demand_id)
    assert demand.canceled_at is not None
    assert lot.input_demand_id is None
    assert lot.canceled_at is None


async def test_canceling_the_lot_too_cancels_lot_and_demand(
    db: AsyncSession, auth_client: Any, create_user: Any
) -> None:
    client, demand_id, _order_id = await _lot_with_raw_material(
        db, auth_client, create_user, "LOT-DROP"
    )

    canceled = await client.post(f"{DEMANDS}/{demand_id}/cancel", params={"cancel_lot": "true"})

    assert canceled.status_code == 200, canceled.text
    assert canceled.json()["status"] == "canceled"
    demand, lot = await _stored(db, demand_id)
    assert demand.canceled_at is not None
    assert lot.canceled_at is not None
    lot_read = await client.get(f"{WEB}/production-lots/{lot.id}")
    assert lot_read.status_code == 200, lot_read.text
    assert lot_read.json()["status"] == "canceled"


async def test_the_status_route_cancels_the_lot_too(
    db: AsyncSession, auth_client: Any, create_user: Any
) -> None:
    client, demand_id, _order_id = await _lot_with_raw_material(
        db, auth_client, create_user, "LOT-DROP2"
    )

    canceled = await client.put(
        f"{DEMANDS}/{demand_id}/status", params={"new_status": "canceled", "cancel_lot": "true"}
    )

    assert canceled.status_code == 200, canceled.text
    demand, lot = await _stored(db, demand_id)
    assert demand.canceled_at is not None
    assert lot.canceled_at is not None


async def test_a_started_lot_is_not_canceled_through_its_demand(
    db: AsyncSession, auth_client: Any, create_user: Any
) -> None:
    client, demand_id, order_id = await _lot_with_raw_material(
        db, auth_client, create_user, "LOT-RUNS"
    )
    started = await client.post(f"{WEB}/production-orders/{order_id}/start", json={})
    assert started.status_code == 200, started.text

    refused = await client.post(f"{DEMANDS}/{demand_id}/cancel", params={"cancel_lot": "true"})

    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "SourceItemDemandLotStartedError"
    demand, lot = await _stored(db, demand_id)
    assert demand.canceled_at is None
    assert lot.canceled_at is None
