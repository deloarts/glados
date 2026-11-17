"""
Round trips of the order reads and of deliver-all, measured for an order of
two lines and one of six. The order reads cost the same however many lines
the order has; deliver-all costs a fixed amount per line it books on top of
a fixed overhead, so a per-line lookup creeping in shows as a larger
difference between the two orders.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.order import (
    SqlAlchemyOrderRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.order_item import (
    SqlAlchemyOrderItemRepository,
)
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.platform.domain.value_objects.permission import Permission

ORDERS_URL = "/api/v1/web/orders"
# Statements deliver-all spends per booked VIRTUAL line: the delivery row,
# the line's write and its read back with its changer, and the reconciler's
# status write.
DELIVER_ALL_PER_LINE = 26


def _order(number: str) -> Order:
    now = datetime.now(UTC)
    return Order(
        id=0,
        order_number=number,
        created=now,
        changed=None,
        changes=[],
        status=OrderStatus.ORDERED,
        note=None,
        ordered_date=now,
        expected_delivery_date=None,
        delivery_date=None,
        storage_place=None,
        creator_id=1,
        supplier_id=1,
    )


def _line(order_id: int, position: int) -> OrderItem:
    now = datetime.now(UTC)
    return OrderItem(
        id=0,
        created=now,
        changed=None,
        changes=[],
        status=OrderItemStatus.ORDERED,
        quantity=4.0,
        quantity_delivered=0.0,
        unit="pcs",
        items_per_unit=1.0,
        price=None,
        note=None,
        ordered_date=now,
        expected_delivery_date=None,
        delivery_date=None,
        storage_place=None,
        expected_pickup_date=None,
        ready_for_pickup_date=None,
        position=position,
        creator_id=1,
        orderer_id=None,
        receiver_id=None,
        bought_item_id=None,
        order_id=order_id,
        supplier_id=1,
        project_id=1,
        line_type=OrderLineType.VIRTUAL,
        lot_position_id=None,
        source_item_id=None,
        virtual_name=f"Freight {position}",
    )


async def _seed(db, number: str, lines: int) -> int:
    order = await SqlAlchemyOrderRepository(db).save(_order(number))
    for position in range(1, lines + 1):
        await SqlAlchemyOrderItemRepository(db).save(_line(order.id, position))
    await db.commit()
    return order.id


async def _counted(query_counter, call) -> int:
    with query_counter() as statements:
        response = await call()
    assert response.status_code == 200, response.text
    return len(statements)


@pytest.fixture
async def receiver(auth_client):
    return await auth_client(permissions=[Permission.RECEIVE_DELIVERIES])


async def test_the_order_read_costs_the_same_for_two_and_six_lines(
    db, receiver, query_counter
) -> None:
    small = await _seed(db, "ORD-QC-0001", 2)
    large = await _seed(db, "ORD-QC-0002", 6)
    # The first request of a client also loads its session and settings.
    await receiver.get(f"{ORDERS_URL}/{small}")

    small_count = await _counted(query_counter, lambda: receiver.get(f"{ORDERS_URL}/{small}"))
    large_count = await _counted(query_counter, lambda: receiver.get(f"{ORDERS_URL}/{large}"))

    assert large_count == small_count, (small_count, large_count)


async def test_deliver_all_costs_a_fixed_amount_per_booked_line(
    db, receiver, query_counter
) -> None:
    small = await _seed(db, "ORD-QC-0003", 2)
    large = await _seed(db, "ORD-QC-0004", 6)

    small_count = await _counted(
        query_counter, lambda: receiver.put(f"{ORDERS_URL}/{small}/deliver-all-items")
    )
    large_count = await _counted(
        query_counter, lambda: receiver.put(f"{ORDERS_URL}/{large}/deliver-all-items")
    )

    # The booking's own reads and writes; the line itself is read once for
    # all lines, not once per line.
    assert (large_count - small_count) / 4 <= DELIVER_ALL_PER_LINE, (small_count, large_count)
