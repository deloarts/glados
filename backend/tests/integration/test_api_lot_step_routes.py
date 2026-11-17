"""
The step routes name the lot and the step; a step of another lot is not
found there, so a request cannot reach a step through the wrong lot.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from tests.integration.test_api_lifecycle_scenarios import LOTS
from tests.integration.test_api_lifecycle_scenarios import Shop
from tests.integration.test_api_production_order_reconciled import _seed_production_settings  # noqa: F401


async def test_a_step_is_not_found_through_another_lot(db: AsyncSession, auth_client: Any) -> None:
    shop = await Shop.open(db, auth_client, extra_positions=1)
    _first, second = await shop.positions()
    method = await shop.graph.fabrication_method()
    added = await shop.client.post(
        f"{LOTS}/{shop.floor.lot_id}/steps",
        json={"position_id": second, "fabrication_method_id": method.id},
    )
    assert added.status_code == 201, added.text
    step = f"{LOTS}/{shop.floor.lot_id + 1000}/steps/{added.json()['id']}"

    patched = await shop.client.patch(step, json={"fabrication_method_id": method.id})
    deleted = await shop.client.delete(step)

    assert patched.status_code == 404, patched.text
    assert deleted.status_code == 404, deleted.text
