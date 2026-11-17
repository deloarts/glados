"""
A line moved onto an order of another supplier, as when it was booked on
the wrong order, stays as it was ordered; both orders record the move with
the old and the new supplier, so purchasing can follow up with the one that
may still expect the order.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.models.order_model import OrderOrmModel
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration import _lifecycle_seed as seed
from tests.integration._edit_versions import line_version
from tests.integration._suppliers import seed_supplier

ORDERS = "/api/v1/web/orders"


async def test_a_line_moved_to_another_supplier_is_recorded_on_both_orders(
    db: AsyncSession, auth_client: Any
) -> None:
    await seed_supplier(db, 1)
    await seed_supplier(db, 2)
    client = await auth_client(permissions=[Permission.WRITE_ORDERS, Permission.MANAGE_ORDERS])
    first = await seed.order(db, "ordered", ordered_date=seed.NOW)
    second = await seed.order(db, "draft")
    second.supplier_id = 2
    line = await seed.line(db, first, "ordered", ordered_date=seed.NOW)
    await db.commit()
    await seed.settle(db)
    order_ids = (first.id, second.id)

    moved = await client.put(
        f"{ORDERS}/{first.id}/items/{line.id}/move", json={"target_order_id": second.id}
    )

    assert moved.status_code == 200, moved.text
    assert moved.json()["status"] == "ordered"
    db.expire_all()
    for order_id in order_ids:
        order = await db.get(OrderOrmModel, order_id)
        assert order is not None
        changelog = " ".join(str(entry) for entry in order.changes)
        assert "Supplier 1" in changelog and "Supplier 2" in changelog, changelog


async def test_a_moved_line_has_a_new_edit_version(db: AsyncSession, auth_client: Any) -> None:
    await seed_supplier(db, 1)
    client = await auth_client(permissions=[Permission.WRITE_ORDERS, Permission.MANAGE_ORDERS])
    first = await seed.order(db, "draft")
    second = await seed.order(db, "draft")
    line = await seed.line(db, first, "pending")
    await db.commit()
    await seed.settle(db)
    before = await line_version(client, first.id, line.id)

    moved = await client.put(
        f"{ORDERS}/{first.id}/items/{line.id}/move", json={"target_order_id": second.id}
    )

    assert moved.status_code == 200, moved.text
    assert moved.json()["edit_version"] == before + 1
