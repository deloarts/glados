"""
Deliver-all with a rejection that loses pieces of a lot, over HTTP: the
rejected MADE line books its accepted pieces and keeps the lost ones lost,
every other open line of the order is delivered in full, and the demands
on those lines, which sort before the lot's own demands in the lock order,
are locked with them up front. A rejection named twice for one line is
refused instead of booking only the last one.
"""

from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration import _lifecycle_seed as seed
from tests.integration.test_api_scrap_pieces import _seed_production_settings  # noqa: F401

ORDERS = "/api/v1/web/orders"


@pytest.fixture
async def receiver(auth_client: Any) -> httpx.AsyncClient:
    client: httpx.AsyncClient = await auth_client(
        permissions=[
            Permission.WRITE_ORDERS,
            Permission.MANAGE_ORDERS,
            Permission.RECEIVE_DELIVERIES,
            Permission.MANAGE_LOTS,
        ]
    )
    return client


def _lost(line_id: int, quantity: float) -> dict[str, Any]:
    return {
        "order_item_id": line_id,
        "quantity_rejected": quantity,
        "rejection_reason": "wrong_spec",
        "rejection_outcome": "lost",
        "create_replacement": False,
    }


async def _items(client: httpx.AsyncClient, order_id: int) -> dict[int, dict[str, Any]]:
    order = (await client.get(f"{ORDERS}/{order_id}")).json()
    return {int(item["id"]): item for item in order["items"]}


@pytest.mark.parametrize("lot_demand", ["made", "source"])
async def test_lost_pieces_on_a_made_line_beside_a_bought_line_book_the_whole_order(
    db: AsyncSession, receiver: httpx.AsyncClient, lot_demand: str
) -> None:
    lot = await seed.lot(db, "in_progress")
    position = await seed.position(db, lot, "external", "ordered_or_queued")
    order = await seed.order(db, "ordered", ordered_date=seed.NOW)
    made_line = await seed.line(db, order, "ordered", at=position, ordered_date=seed.NOW)
    bought_line = await seed.line(db, order, "ordered", ordered_date=seed.NOW)
    await seed.bought_demand(db, "open", bought_line, 5.0)
    if lot_demand == "made":
        await seed.made_demand(db, "open", lot, 10.0)
    else:
        source = await seed.source_demand(db, "open", lot_id=lot.id, quantity=10.0, unit="pcs")
        lot.input_demand_id = source.id
    await db.commit()
    await seed.settle(db)

    response = await receiver.put(
        f"{ORDERS}/{order.id}/deliver-all-items", json={"rejections": [_lost(made_line.id, 2.0)]}
    )

    assert response.status_code == 200, response.text
    items = await _items(receiver, order.id)
    assert items[bought_line.id]["status"] == "delivered"
    assert items[bought_line.id]["quantity_delivered"] == 10.0
    assert items[made_line.id]["quantity_delivered"] == 8.0


async def test_a_rejection_named_twice_for_one_line_is_refused(
    db: AsyncSession, receiver: httpx.AsyncClient
) -> None:
    order = await seed.order(db, "ordered", ordered_date=seed.NOW)
    line = await seed.line(db, order, "ordered", ordered_date=seed.NOW)
    await db.commit()
    await seed.settle(db)

    response = await receiver.put(
        f"{ORDERS}/{order.id}/deliver-all-items",
        json={
            "rejections": [
                _lost(line.id, 2.0),
                {**_lost(line.id, 3.0), "rejection_outcome": "redeliver"},
            ]
        },
    )

    assert response.status_code == 422, response.text
    assert (await _items(receiver, order.id))[line.id]["quantity_delivered"] == 0.0
