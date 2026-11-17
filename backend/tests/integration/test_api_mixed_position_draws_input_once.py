"""
A MIXED position's supplier share and its own orders draw on one input: the
pieces handed to the supplier are not there for the machine, and what the
machine processed is not there to hand over, so the position never uses more
than its predecessor made.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model import (
    ProductionOrderOrmModel,
)
from tests.integration._tenant_day import tenant_today
from tests.integration.test_api_lifecycle_scenarios import LOTS
from tests.integration.test_api_lifecycle_scenarios import ORDERS
from tests.integration.test_api_lifecycle_scenarios import Shop
from tests.integration.test_api_production_order_reconciled import _seed_production_settings  # noqa: F401


async def _mixed_shop(db: AsyncSession, auth_client: Any) -> tuple[Shop, int, int]:
    """Position 1 completes 10; position 2 is MIXED, 5 by a supplier line
    and 5 by an internal order."""
    shop = await Shop.open(db, auth_client, extra_positions=1)
    first, second = await shop.positions()
    _started, done = await shop.run(await shop.production_order(first, 10.0, 1), 10.0)
    assert done.status_code == 200, done.text
    external = await shop.client.post(
        f"{LOTS}/{shop.floor.lot_id}/positions/{second}/assign",
        json={
            "order_id": shop.order_id,
            "unit": "pcs",
            "quantity": 5,
        },
    )
    assert external.status_code < 300, external.text
    internal = await shop.client.post(
        f"{LOTS}/{shop.floor.lot_id}/positions/{second}/assign-internal",
        json={"orders": [{"machine_id": shop.floor.machine_id, "quantity": 5}]},
    )
    assert internal.status_code < 300, internal.text
    order_id = (
        await db.execute(
            select(ProductionOrderOrmModel.id).where(
                ProductionOrderOrmModel.lot_position_id == second
            )
        )
    ).scalar_one()
    return shop, second, order_id


async def _provide(shop: Shop, position_id: int, quantity: float) -> Any:
    return await shop.client.post(
        f"{LOTS}/{shop.floor.lot_id}/positions/{position_id}/provisions",
        json={"quantity": quantity, "provision_date": tenant_today().isoformat()},
    )


async def test_pieces_handed_to_the_supplier_are_not_there_for_the_machine(
    db: AsyncSession, auth_client: Any
) -> None:
    shop, second, order_id = await _mixed_shop(db, auth_client)
    provided = await _provide(shop, second, 10)
    assert provided.status_code == 201, provided.text

    started = await shop.client.post(f"{ORDERS}/{order_id}/start", json={})

    assert started.status_code == 422, started.text
    assert started.json()["code"] == "LotPositionOverflowError"


async def test_pieces_the_machine_processed_are_not_there_to_hand_over(
    db: AsyncSession, auth_client: Any
) -> None:
    shop, second, order_id = await _mixed_shop(db, auth_client)
    _started, done = await shop.run(order_id, 5.0)
    assert done.status_code == 200, done.text

    too_many = await _provide(shop, second, 10)
    the_rest = await _provide(shop, second, 5)

    assert too_many.status_code == 422, too_many.text
    assert too_many.json()["code"] == "LotPositionProvisionOverflowError"
    assert the_rest.status_code == 201, the_rest.text
