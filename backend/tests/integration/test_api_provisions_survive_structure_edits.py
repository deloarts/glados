"""
Pieces handed to a supplier are a physical fact: once a position holds a
provision, its supplier line can no longer be unassigned or removed, since
the position would then read unassigned and a structure edit would delete
it with the record of the pieces; so the provision always survives. An
ended lot takes no provision.
"""

from typing import Any

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_provision_model import (
    LotPositionProvisionOrmModel,
)
from tests.integration._edit_versions import line_version
from tests.integration._edit_versions import lot_version
from tests.integration._tenant_day import tenant_today
from tests.integration.test_api_lifecycle_scenarios import LOTS
from tests.integration.test_api_lifecycle_scenarios import SUPPLIER_ORDERS
from tests.integration.test_api_lifecycle_scenarios import Shop
from tests.integration.test_api_production_order_reconciled import _seed_production_settings  # noqa: F401


async def _provided_shop(db: AsyncSession, auth_client: Any) -> tuple[Shop, int, int]:
    shop = await Shop.open(db, auth_client, extra_positions=1)
    first, second = await shop.positions()
    order = await shop.production_order(first, 10.0, 1)
    _started, done = await shop.run(order, 5.0)
    assert done.status_code < 300, done.text
    assigned = await shop.assign_external(second)
    assert assigned.status_code == 200, assigned.text
    provided = await shop.client.post(
        f"{LOTS}/{shop.floor.lot_id}/positions/{second}/provisions",
        json={"quantity": 5.0, "provision_date": tenant_today().isoformat()},
    )
    assert provided.status_code == 201, provided.text
    return shop, second, await shop.made_line(second)


async def _provisions(db: AsyncSession) -> int:
    return int(await db.scalar(select(func.count()).select_from(LotPositionProvisionOrmModel)) or 0)


async def test_a_position_with_a_provision_is_not_unassigned(
    db: AsyncSession, auth_client: Any
) -> None:
    shop, position, _line = await _provided_shop(db, auth_client)

    unassigned = await shop.client.delete(f"{LOTS}/{shop.floor.lot_id}/positions/{position}/assign")

    assert unassigned.status_code == 409, unassigned.text
    assert await _provisions(db) == 1


async def test_the_supplier_line_of_a_position_with_a_provision_is_not_removed(
    db: AsyncSession, auth_client: Any
) -> None:
    shop, _position, line = await _provided_shop(db, auth_client)

    removed = await shop.client.delete(
        f"{SUPPLIER_ORDERS}/{shop.order_id}/items/{line}",
        params={"expected_edit_version": await line_version(shop.client, shop.order_id, line)},
    )

    assert removed.status_code == 409, removed.text
    assert await _provisions(db) == 1


async def test_an_ended_lot_takes_no_provision(db: AsyncSession, auth_client: Any) -> None:
    shop, position, _line = await _provided_shop(db, auth_client)
    lot_id = shop.floor.lot_id
    completed = await shop.client.post(
        f"{LOTS}/{lot_id}/complete",
        json={"expected_edit_version": await lot_version(shop.client, lot_id)},
    )
    assert completed.status_code == 200, completed.text

    provided = await shop.client.post(
        f"{LOTS}/{lot_id}/positions/{position}/provisions",
        json={"quantity": 1.0, "provision_date": tenant_today().isoformat()},
    )

    assert provided.status_code == 422, provided.text
