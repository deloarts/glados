"""
A supplier line of a lot position closed short leaves the rest of the
position open. The position offers its rest again: a second supplier line
takes it, or production orders do, but never more than the rest, and the
lot reaches its quantity once the second line arrives.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from tests.integration._edit_versions import line_version
from tests.integration.test_api_lifecycle_scenarios import LOTS
from tests.integration.test_api_lifecycle_scenarios import SUPPLIER_ORDERS
from tests.integration.test_api_lifecycle_scenarios import Shop
from tests.integration.test_api_production_order_reconciled import _seed_production_settings  # noqa: F401


async def _closed_short_at_six(db: AsyncSession, auth_client: Any) -> tuple[Shop, int, int]:
    """Position 1 completes 10; position 2's supplier line of 10 delivers 6
    and is closed short. Returns the shop, position 2 and the line."""
    shop = await Shop.open(db, auth_client, extra_positions=1)
    first, second = await shop.positions()
    _started, done = await shop.run(await shop.production_order(first, 10.0, 1), 10.0)
    assert done.status_code == 200, done.text
    assigned = await shop.assign_external(second)
    assert assigned.status_code == 200, assigned.text
    line = await shop.made_line(second)
    submitted = await shop.client.put(f"{SUPPLIER_ORDERS}/{shop.order_id}/submit", json={})
    assert submitted.status_code == 200, submitted.text
    delivered = await shop.deliver(line, 6.0)
    assert delivered.status_code == 200, delivered.text
    closed = await shop.client.post(
        f"{SUPPLIER_ORDERS}/{shop.order_id}/items/{line}/close-short",
        params={"expected_edit_version": await line_version(shop.client, shop.order_id, line)},
    )
    assert closed.status_code == 200, closed.text
    return shop, second, line


async def _position(shop: Shop, position_id: int) -> dict[str, Any]:
    lot = await shop.client.get(f"{LOTS}/{shop.floor.lot_id}")
    assert lot.status_code == 200, lot.text
    return next(p for p in lot.json()["positions"] if p["id"] == position_id)


async def _new_order(shop: Shop) -> int:
    supplier_id = (await shop.client.get(f"{SUPPLIER_ORDERS}/{shop.order_id}")).json()[
        "supplier_id"
    ]
    created = await shop.client.post(f"{SUPPLIER_ORDERS}/", json={"supplier_id": supplier_id})
    assert created.status_code == 201, created.text
    return int(created.json()["id"])


async def test_a_position_closed_short_offers_its_rest_to_a_second_supplier_line(
    db: AsyncSession, auth_client: Any
) -> None:
    shop, second, first_line = await _closed_short_at_six(db, auth_client)

    position = await _position(shop, second)
    assert position["quantity_remaining"] == 4
    assert position["order_item_closed_short"] is True
    assert "assign_external" in position["actions"]

    rest_order = await _new_order(shop)
    assigned = await shop.client.post(
        f"{LOTS}/{shop.floor.lot_id}/positions/{second}/assign",
        json={"order_id": rest_order, "unit": "pcs"},
    )
    assert assigned.status_code == 200, assigned.text
    db.expire_all()
    lines = (
        await db.execute(
            select(OrderItemOrmModel.id, OrderItemOrmModel.quantity)
            .where(OrderItemOrmModel.lot_position_id == second)
            .order_by(OrderItemOrmModel.id)
        )
    ).all()
    (closed_line, closed_quantity), (rest_line, rest_quantity) = lines
    assert (closed_line, closed_quantity, rest_quantity) == (first_line, 6, 4)

    position = await _position(shop, second)
    assert position["order_item_id"] == rest_line
    assert position["order_item_closed_short"] is False
    assert position["quantity_remaining"] == 0
    assert position["quantity_completed"] == 6
    assert "assign_external" not in position["actions"]

    again = await shop.client.post(
        f"{LOTS}/{shop.floor.lot_id}/positions/{second}/assign",
        json={"order_id": rest_order, "unit": "pcs"},
    )
    assert again.status_code == 409, again.text

    submitted = await shop.client.put(f"{SUPPLIER_ORDERS}/{rest_order}/submit", json={})
    assert submitted.status_code == 200, submitted.text
    delivered = await shop.deliver(rest_line, 4.0)
    assert delivered.status_code == 200, delivered.text

    position = await _position(shop, second)
    assert (position["status"], position["kind"], position["quantity_completed"]) == (
        "completed",
        "external",
        10,
    )
    lot = (await shop.client.get(f"{LOTS}/{shop.floor.lot_id}")).json()
    assert (lot["status"], lot["quantity_completed"]) == ("completed", 10)


async def test_production_orders_take_at_most_the_rest_of_a_position_closed_short(
    db: AsyncSession, auth_client: Any
) -> None:
    shop, second, _line = await _closed_short_at_six(db, auth_client)
    url = f"{LOTS}/{shop.floor.lot_id}/positions/{second}/assign-internal"

    too_many = await shop.client.post(
        url, json={"orders": [{"machine_id": shop.floor.machine_id, "quantity": 5}]}
    )
    assert too_many.status_code == 422, too_many.text

    rest = await shop.client.post(
        url, json={"orders": [{"machine_id": shop.floor.machine_id, "quantity": 4}]}
    )
    assert rest.status_code < 300, rest.text
    position = await _position(shop, second)
    assert (position["kind"], position["quantity_remaining"]) == ("mixed", 0)


async def test_a_position_lists_its_line_closed_short_below_the_new_line(
    db: AsyncSession, auth_client: Any
) -> None:
    shop, second, first_line = await _closed_short_at_six(db, auth_client)
    first_order_number = (await _position(shop, second))["order_number"]
    assert (await _position(shop, second))["earlier_order_lines"] == []

    rest_order = await _new_order(shop)
    assigned = await shop.client.post(
        f"{LOTS}/{shop.floor.lot_id}/positions/{second}/assign",
        json={"order_id": rest_order, "unit": "pcs"},
    )
    assert assigned.status_code == 200, assigned.text
    expected = {
        "order_item_id": first_line,
        "order_id": shop.order_id,
        "order_number": first_order_number,
        "quantity": 6,
        "quantity_delivered": 6,
        "closed_short": True,
    }

    def _view(position: dict[str, Any]) -> list[dict[str, Any]]:
        return [{key: line[key] for key in expected} for line in position["earlier_order_lines"]]

    assert _view(assigned.json()) == [expected]
    position = await _position(shop, second)
    assert position["order_id"] == rest_order
    assert _view(position) == [expected]
