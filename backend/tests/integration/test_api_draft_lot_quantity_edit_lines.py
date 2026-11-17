"""
A quantity edit of a DRAFT lot reaches the supplier lines of its external
positions that are not ordered yet: a line larger than its position's new
quantity shrinks with it, so the lot never completes while pieces it no
longer needs stay on a supplier order.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from tests.integration._edit_versions import lot_version
from tests.integration.test_api_lifecycle_scenarios import LOTS
from tests.integration.test_api_lifecycle_scenarios import Shop
from tests.integration.test_api_production_order_reconciled import _seed_production_settings  # noqa: F401


async def test_lowering_a_draft_lot_shrinks_its_pending_supplier_line(
    db: AsyncSession, auth_client: Any
) -> None:
    shop = await Shop.open(db, auth_client, extra_positions=1)
    _first, second = await shop.positions()
    lot_id = shop.floor.lot_id
    assigned = await shop.assign_external(second)
    assert assigned.status_code == 200, assigned.text
    line = await shop.made_line(second)

    patched = await shop.client.patch(
        f"{LOTS}/{lot_id}",
        json={"quantity": 4.0, "expected_edit_version": await lot_version(shop.client, lot_id)},
    )

    assert patched.status_code == 200, patched.text
    db.expire_all()
    stored = await db.get(OrderItemOrmModel, line)
    assert stored is not None
    assert stored.quantity == 4.0
