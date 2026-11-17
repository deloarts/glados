"""
A position whose production order was started, paused and canceled carries
a record of work: its start, its interruptions and their times. A structure
edit no longer treats it as untouched, so deleting the position's last step
is refused and the order with its history stays.
"""

from typing import Any

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model import (
    LotPositionOrmModel,
)
from tests.integration._edit_versions import production_order_version
from tests.integration.test_api_lifecycle_scenarios import LOTS
from tests.integration.test_api_lifecycle_scenarios import Shop
from tests.integration.test_api_production_order_reconciled import ORDERS
from tests.integration.test_api_production_order_reconciled import _seed_production_settings  # noqa: F401


async def test_a_position_whose_canceled_order_had_started_is_kept(
    db: AsyncSession, auth_client: Any
) -> None:
    shop = await Shop.open(db, auth_client, extra_positions=1)
    first, second = await shop.positions()
    upstream = await shop.production_order(first, 10.0, 1)
    _started, done = await shop.run(upstream, 10.0)
    assert done.status_code == 200, done.text
    method = await shop.graph.fabrication_method()
    step = await shop.client.post(
        f"{LOTS}/{shop.floor.lot_id}/steps",
        json={"position_id": second, "role": "fabrication", "fabrication_method_id": method.id},
    )
    assert step.status_code == 201, step.text
    order = await shop.production_order(second, 10.0, 2)
    for action in ("start", "pause"):
        response = await shop.client.post(f"{ORDERS}/{order}/{action}", json={})
        assert response.status_code == 200, response.text
    canceled = await shop.client.post(
        f"{ORDERS}/{order}/cancel",
        json={
            "expected_edit_version": await production_order_version(shop.client, order),
            "reason": "wrong machine",
        },
    )
    assert canceled.status_code == 200, canceled.text

    deleted = await shop.client.delete(f"{LOTS}/{shop.floor.lot_id}/steps/{step.json()['id']}")

    assert deleted.status_code in (409, 422), deleted.text
    db.expire_all()
    kept = await db.scalar(
        select(func.count())
        .select_from(LotPositionOrmModel)
        .where(LotPositionOrmModel.id == second)
    )
    assert kept == 1
