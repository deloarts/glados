"""
receive:deliveries permission gate on the delivery endpoints
(PUT /bought-items-allocations/order-item/{id}/deliver and
PUT /orders/{id}/deliver-all-items). Before this permission existed, any
authenticated user could record deliveries, see
OrderRules.assert_can_receive_delivery.
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

RECEIVE_DELIVERIES = [Permission.RECEIVE_DELIVERIES]
WRITE_ORDERS_ONLY = [Permission.WRITE_ORDERS, Permission.MANAGE_ORDERS]


@pytest.fixture
async def receiver(auth_client):
    return await auth_client(permissions=RECEIVE_DELIVERIES)


@pytest.fixture
async def order_writer(auth_client):
    """write:orders + manage:orders, but deliberately NOT receive:deliveries
    the case the new permission exists to separate out."""
    return await auth_client(permissions=WRITE_ORDERS_ONLY)


async def _seed_order_item(db, *, quantity: float = 10.0) -> tuple[int, int]:
    """Seeds one order with one VIRTUAL line item directly through the
    repositories (no catalogue/supplier setup needed for a VIRTUAL line,
    see OrderItem.line_type's docstring), and returns (order_id, item_id)."""
    order = await SqlAlchemyOrderRepository(db).save(
        Order(
            id=0,
            order_number="ORD-2026-0001",
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            status=OrderStatus.ORDERED,
            note=None,
            ordered_date=datetime.now(UTC),
            expected_delivery_date=None,
            delivery_date=None,
            storage_place=None,
            creator_id=1,
            supplier_id=1,
        )
    )
    item = await SqlAlchemyOrderItemRepository(db).save(
        OrderItem(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            status=OrderItemStatus.ORDERED,
            quantity=quantity,
            quantity_delivered=0.0,
            unit="pcs",
            items_per_unit=1.0,
            price=None,
            note=None,
            ordered_date=datetime.now(UTC),
            expected_delivery_date=None,
            delivery_date=None,
            storage_place=None,
            expected_pickup_date=None,
            ready_for_pickup_date=None,
            position=1,
            creator_id=1,
            orderer_id=None,
            receiver_id=None,
            bought_item_id=None,
            order_id=order.id,
            supplier_id=1,
            project_id=1,
            line_type=OrderLineType.VIRTUAL,
            lot_position_id=None,
            source_item_id=None,
            virtual_name="Freight",
        )
    )
    await db.commit()
    return order.id, item.id


class TestDeliverOrderItemPermission:
    async def test_actor_without_permission_gets_403(self, db, order_writer):
        _order_id, item_id = await _seed_order_item(db)

        response = await order_writer.put(
            f"/api/v1/web/bought-items-allocations/order-item/{item_id}/deliver",
            params={"quantity": 2.0},
        )

        assert response.status_code == 403
        assert response.json()["code"] == "InsufficientPermissionsError"

    async def test_actor_without_any_permission_gets_403(self, db, auth_client):
        _order_id, item_id = await _seed_order_item(db)
        no_permissions = await auth_client(permissions=[])

        response = await no_permissions.put(
            f"/api/v1/web/bought-items-allocations/order-item/{item_id}/deliver",
            params={"quantity": 2.0},
        )

        assert response.status_code == 403

    async def test_actor_with_permission_succeeds(self, db, receiver):
        _order_id, item_id = await _seed_order_item(db)

        response = await receiver.put(
            f"/api/v1/web/bought-items-allocations/order-item/{item_id}/deliver",
            params={"quantity": 2.0},
        )

        assert response.status_code == 200
        assert response.json()["quantity_delivered"] == 2.0


class TestDeliverAllOrderItemsPermission:
    async def test_actor_without_permission_gets_403(self, db, order_writer):
        order_id, _item_id = await _seed_order_item(db)

        response = await order_writer.put(f"/api/v1/web/orders/{order_id}/deliver-all-items")

        assert response.status_code == 403
        assert response.json()["code"] == "InsufficientPermissionsError"

    async def test_actor_with_permission_succeeds(self, db, receiver):
        order_id, _item_id = await _seed_order_item(db)

        response = await receiver.put(f"/api/v1/web/orders/{order_id}/deliver-all-items")

        assert response.status_code == 200
        assert len(response.json()["delivered"]) == 1
        assert response.json()["delivered"][0]["quantity_delivered"] == 10.0
