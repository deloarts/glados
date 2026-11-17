"""
Which lines the delivery endpoints accept (PUT
/bought-items-allocations/order-item/{id}/deliver and PUT
/orders/{id}/deliver-all-items): ordered or partially delivered lines of
an order that is not canceled, and for a MADE line only while its lot is
not canceled; quantities must be finite numbers, also when a JSON body
spells them NaN or Infinity. A refused line still gets 403 and 404 before
the 409, and deliver-all books every line in one transaction, so a line that
fails books nothing on the others. Prerequisites are seeded through the real
repositories like test_api_delivery_rejection.py; only the routers under
test go through HTTP.
"""

from datetime import UTC
from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.catalogue.adapters.outbound.persistence.repositories.made_item_repository.item import (
    SqlAlchemyMadeItemRepository,
)
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.delivery import (
    SqlAlchemyOrderItemDeliveryRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.order import (
    SqlAlchemyOrderRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.order_repository.order_item import (
    SqlAlchemyOrderItemRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository.lot import (
    SqlAlchemyProductionLotRepository,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.order_item_delivery import OrderItemDelivery
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.adapters.outbound.persistence.repositories.project_repository import (
    SqlAlchemyProjectRepository,
)
from src.modules.workspace.domain.entities.project import Project
from tests.integration._lot_facts import give_lot_facts

DELIVER_URL = "/api/v1/web/bought-items-allocations/order-item"
ORDERS_URL = "/api/v1/web/orders"
JSON = {"Content-Type": "application/json"}

# Line statuses that come with an ordered_date.
_PLACED = {"ordered", "partially_delivered", "delivered"}


def _order(order_number: str, status: OrderStatus, creator_id: int) -> Order:
    """A placed order, canceled when `status` says so."""
    return Order(
        id=0,
        order_number=order_number,
        created=datetime.now(UTC),
        changed=None,
        changes=[],
        status=status,
        note=None,
        ordered_date=datetime.now(UTC),
        expected_delivery_date=None,
        delivery_date=None,
        storage_place=None,
        creator_id=creator_id,
        supplier_id=1,
        canceled_at=datetime.now(UTC) if status == "canceled" else None,
    )


def _line(
    order_id: int,
    position: int,
    status: OrderItemStatus,
    *,
    quantity: float = 4.0,
    quantity_delivered: float = 0.0,
    creator_id: int = 1,
    project_id: int = 1,
    lot_position_id: int | None = None,
) -> OrderItem:
    """A VIRTUAL line, or a MADE line when `lot_position_id` is given,
    with the intents its status stands for."""
    return OrderItem(
        id=0,
        created=datetime.now(UTC),
        changed=None,
        changes=[],
        status=status,
        quantity=quantity,
        quantity_delivered=quantity_delivered,
        unit="pcs",
        items_per_unit=1.0,
        price=None,
        note=None,
        ordered_date=datetime.now(UTC) if status in _PLACED else None,
        expected_delivery_date=None,
        delivery_date=None,
        storage_place=None,
        expected_pickup_date=None,
        ready_for_pickup_date=None,
        position=position,
        creator_id=creator_id,
        orderer_id=None,
        receiver_id=None,
        bought_item_id=None,
        order_id=order_id,
        supplier_id=1,
        project_id=project_id,
        line_type=OrderLineType.MADE if lot_position_id is not None else OrderLineType.VIRTUAL,
        lot_position_id=lot_position_id,
        source_item_id=None,
        virtual_name=None if lot_position_id is not None else f"Freight {position}",
        requested_at=datetime.now(UTC) if status == "requested" else None,
        canceled_at=datetime.now(UTC) if status == "canceled" else None,
    )


async def _book(db: AsyncSession, item: OrderItem) -> None:
    """The delivery row behind the pieces a seeded line has delivered."""
    if item.quantity_delivered > 0:
        await SqlAlchemyOrderItemDeliveryRepository(db).save(
            OrderItemDelivery(
                id=0,
                order_item_id=item.id,
                quantity=item.quantity_delivered,
                delivery_date=datetime.now(UTC),
                storage_place=None,
                receiver_id=None,
                created=datetime.now(UTC),
            )
        )


async def _seed_order(
    db: AsyncSession,
    lines: list[tuple[OrderItemStatus, float]],
    order_status: OrderStatus = OrderStatus.ORDERED,
) -> tuple[int, list[int]]:
    """One order in `order_status` with one VIRTUAL line of 4 pieces per
    (status, delivered) pair; returns (order_id, line ids)."""
    order = await SqlAlchemyOrderRepository(db).save(_order("ORD-GUARD-0001", order_status, 1))
    item_repo = SqlAlchemyOrderItemRepository(db)
    ids = []
    for position, (status, delivered) in enumerate(lines, start=1):
        item = await item_repo.save(_line(order.id, position, status, quantity_delivered=delivered))
        await _book(db, item)
        ids.append(item.id)
    await db.commit()
    return order.id, ids


async def _seed_made_line_on_canceled_lot(db: AsyncSession, creator_id: int) -> tuple[int, int]:
    """A canceled lot whose canceled EXTERNAL position keeps the partially
    delivered MADE line a force-cancel leaves behind (1 of 2 delivered), on
    a partially delivered order. Returns (position id, line id)."""
    project = await SqlAlchemyProjectRepository(db).save(
        Project(id=0, created=datetime.now(UTC), creator_id=creator_id, project_number="GUARD")
    )
    made_item = await SqlAlchemyMadeItemRepository(db).save(
        MadeItem(
            id=0,
            created=datetime.now(UTC),
            changed=datetime.now(UTC),
            changes=[],
            archived=False,
            revision="0",
            revision_date=None,
            revision_note=None,
            article_name="Delivery guard test part",
            status=MadeItemCatalogueStatus.ACTIVE,
            data_source=DataSource.WEB,
            part_number=None,
            material=None,
            mass=None,
            base_size=None,
            note=None,
            weblink=None,
            files=[],
            creator_id=creator_id,
            approver_id=None,
            bought_item_id=None,
            source_item_id=None,
            article_group_ids=[],
            successor_item_id=None,
            changed_by_id=None,
        )
    )
    await db.commit()
    lot_repo = SqlAlchemyProductionLotRepository(db)
    lot = await lot_repo.save(
        ProductionLot(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            lot_number="LOT-GUARD",
            quantity=2.0,
            status=LotStatus.CANCELED,
            priority=UrgencyClass.NORMAL,
            note=None,
            creator_id=creator_id,
            made_item_id=made_item.id,
            project_id=project.id,
            input_demand_id=None,
        )
    )
    position = await lot_repo.save_position(
        LotPosition(
            id=0,
            created=datetime.now(UTC),
            changed=None,
            changes=[],
            sequence=1,
            kind=LotPositionKind.EXTERNAL,
            status=LotPositionStatus.CANCELED,
            quantity=2.0,
            quantity_completed=1.0,
            note=None,
            creator_id=creator_id,
            lot_id=lot.id,
        )
    )
    order = await SqlAlchemyOrderRepository(db).save(
        _order("ORD-GUARD-MADE", OrderStatus.PARTIALLY_DELIVERED, creator_id)
    )
    item = await SqlAlchemyOrderItemRepository(db).save(
        _line(
            order.id,
            1,
            OrderItemStatus.PARTIALLY_DELIVERED,
            quantity=2.0,
            quantity_delivered=1.0,
            creator_id=creator_id,
            project_id=project.id,
            lot_position_id=position.id,
        )
    )
    await _book(db, item)
    await give_lot_facts(db, lot.id)
    await db.commit()
    return position.id, item.id


async def _read_line(db: AsyncSession, item_id: int) -> OrderItem:
    db.expire_all()
    item = await SqlAlchemyOrderItemRepository(db).get_by_id(item_id)
    assert item is not None
    return item


@pytest.fixture
async def receiver(auth_client):
    return await auth_client(permissions=[Permission.RECEIVE_DELIVERIES])


class TestDeliverRefusesLinesThatCannotTakeADelivery:
    @pytest.mark.parametrize(
        "line_status",
        [OrderItemStatus.PENDING, OrderItemStatus.REQUESTED, OrderItemStatus.CANCELED],
    )
    async def test_deliver_on_a_line_that_is_not_placed_or_is_canceled_returns_409(
        self, db: AsyncSession, receiver, line_status: OrderItemStatus
    ) -> None:
        # Next to an ordered line, so the order stays placed.
        _order_id, (item_id, _ordered_id) = await _seed_order(
            db, [(line_status, 0.0), (OrderItemStatus.ORDERED, 0.0)]
        )

        response = await receiver.put(f"{DELIVER_URL}/{item_id}/deliver", params={"quantity": 1.0})

        assert response.status_code == 409, response.text
        assert response.json()["code"] == "OrderItemNotDeliverableError"
        item = await _read_line(db, item_id)
        assert (item.status, item.quantity_delivered) == (line_status, 0.0)

    async def test_deliver_on_a_partially_delivered_line_of_a_canceled_order_returns_409(
        self, db: AsyncSession, receiver
    ) -> None:
        _order_id, (item_id,) = await _seed_order(
            db, [(OrderItemStatus.PARTIALLY_DELIVERED, 1.0)], order_status=OrderStatus.CANCELED
        )

        response = await receiver.put(f"{DELIVER_URL}/{item_id}/deliver", params={"quantity": 1.0})

        assert response.status_code == 409, response.text
        assert response.json()["code"] == "OrderItemNotDeliverableError"
        assert (await _read_line(db, item_id)).quantity_delivered == 1.0

    async def test_deliver_on_a_made_line_of_a_canceled_lot_returns_409(
        self, db: AsyncSession, receiver, create_user
    ) -> None:
        owner = await create_user(username="guard-owner", email="guard-owner@example.com")
        position_id, item_id = await _seed_made_line_on_canceled_lot(db, owner.id)

        response = await receiver.put(f"{DELIVER_URL}/{item_id}/deliver", params={"quantity": 1.0})

        assert response.status_code == 409, response.text
        assert response.json()["code"] == "OrderItemNotDeliverableError"
        assert (await _read_line(db, item_id)).quantity_delivered == 1.0
        position = await SqlAlchemyProductionLotRepository(db).get_position_by_id(position_id)
        assert position is not None
        assert position.status == LotPositionStatus.CANCELED.value
        assert position.quantity_completed == 1.0


class TestARefusedDeliveryChecksPermissionAndLineFirst:
    async def test_a_canceled_line_still_gets_403_and_404_before_the_409(
        self, db: AsyncSession, receiver, auth_client
    ) -> None:
        _order_id, (item_id, _ordered_id) = await _seed_order(
            db, [(OrderItemStatus.CANCELED, 0.0), (OrderItemStatus.ORDERED, 0.0)]
        )
        stranger = await auth_client(
            permissions=[], username="stranger", email="stranger@example.com"
        )
        url = f"{DELIVER_URL}/{item_id}/deliver"

        forbidden = await stranger.put(url, params={"quantity": 1.0})
        missing = await receiver.put(
            f"{DELIVER_URL}/{item_id + 100}/deliver", params={"quantity": 1.0}
        )
        refused = await receiver.put(url, params={"quantity": 1.0})

        assert (forbidden.status_code, missing.status_code, refused.status_code) == (
            403,
            404,
            409,
        )
        item = await _read_line(db, item_id)
        assert (item.status, item.quantity_delivered) == (OrderItemStatus.CANCELED, 0.0)


class TestDeliverAllIsOneTransaction:
    async def test_a_line_that_fails_books_nothing_on_the_lines_before_it(
        self, db: AsyncSession, receiver
    ) -> None:
        order_id, line_ids = await _seed_order(
            db, [(OrderItemStatus.ORDERED, 0.0), (OrderItemStatus.ORDERED, 0.0)]
        )
        # More rejected pieces than the second line has open.
        too_many = {
            "order_item_id": line_ids[1],
            "quantity_rejected": 5.0,
            "rejection_reason": "supplier_damage",
            "rejection_outcome": "redeliver",
        }

        response = await receiver.put(
            f"{ORDERS_URL}/{order_id}/deliver-all-items", json={"rejections": [too_many]}
        )

        assert response.status_code == 422, response.text
        assert response.json()["code"] == "InvalidDeliveryQuantityError"
        for item_id in line_ids:
            item = await _read_line(db, item_id)
            assert (item.status, item.quantity_delivered) == (OrderItemStatus.ORDERED, 0.0)
        deliveries = SqlAlchemyOrderItemDeliveryRepository(db)
        assert await deliveries.get_by_order_item_ids(line_ids) == []


class TestDeliverAllSkipsLinesThatCannotTakeADelivery:
    async def test_deliver_all_reports_why_each_line_was_skipped(
        self, db: AsyncSession, receiver
    ) -> None:
        order_id, (_ordered_id, pending_id, canceled_id) = await _seed_order(
            db,
            [
                (OrderItemStatus.ORDERED, 0.0),
                (OrderItemStatus.PENDING, 0.0),
                (OrderItemStatus.CANCELED, 0.0),
            ],
        )

        response = await receiver.put(f"{ORDERS_URL}/{order_id}/deliver-all-items")

        assert response.status_code == 200, response.text
        skipped = {s["order_item_id"]: s["reason"] for s in response.json()["skipped"]}
        assert skipped == {pending_id: "not_ordered", canceled_id: "canceled"}

    async def test_a_rejection_for_a_line_not_on_the_order_is_refused(
        self, db: AsyncSession, receiver
    ) -> None:
        order_id, (ordered_id,) = await _seed_order(db, [(OrderItemStatus.ORDERED, 0.0)])

        response = await receiver.put(
            f"{ORDERS_URL}/{order_id}/deliver-all-items",
            json={"rejections": [_rejection(ordered_id + 100)]},
        )

        assert response.status_code == 404, response.text
        assert response.json()["code"] == "OrderItemNotFoundError"
        assert (await _read_line(db, ordered_id)).quantity_delivered == 0.0

    async def test_a_rejection_for_a_line_that_takes_no_delivery_is_refused(
        self, db: AsyncSession, receiver
    ) -> None:
        order_id, (ordered_id, pending_id) = await _seed_order(
            db, [(OrderItemStatus.ORDERED, 0.0), (OrderItemStatus.PENDING, 0.0)]
        )

        response = await receiver.put(
            f"{ORDERS_URL}/{order_id}/deliver-all-items",
            json={"rejections": [_rejection(pending_id)]},
        )

        assert response.status_code == 409, response.text
        assert response.json()["code"] == "OrderItemNotDeliverableError"
        assert (await _read_line(db, ordered_id)).quantity_delivered == 0.0

    async def test_deliver_all_delivers_only_the_ordered_line(
        self, db: AsyncSession, receiver
    ) -> None:
        order_id, (ordered_id, pending_id, canceled_id) = await _seed_order(
            db,
            [
                (OrderItemStatus.ORDERED, 0.0),
                (OrderItemStatus.PENDING, 0.0),
                (OrderItemStatus.CANCELED, 0.0),
            ],
        )

        response = await receiver.put(f"{ORDERS_URL}/{order_id}/deliver-all-items")

        assert response.status_code == 200, response.text
        assert [item["id"] for item in response.json()["delivered"]] == [ordered_id]
        assert ordered_id not in {s["order_item_id"] for s in response.json()["skipped"]}
        assert (await _read_line(db, ordered_id)).status == "delivered"
        for item_id, status in ((pending_id, "pending"), (canceled_id, "canceled")):
            item = await _read_line(db, item_id)
            assert (item.status, item.quantity_delivered) == (status, 0.0)


class TestOrderRollupIgnoresCanceledLines:
    async def test_an_order_with_a_canceled_line_is_delivered_once_its_other_line_is(
        self, db: AsyncSession, receiver
    ) -> None:
        order_id, (ordered_id, _canceled_id) = await _seed_order(
            db, [(OrderItemStatus.ORDERED, 0.0), (OrderItemStatus.CANCELED, 0.0)]
        )

        response = await receiver.put(f"{DELIVER_URL}/{ordered_id}/deliver")

        assert response.status_code == 200, response.text
        db.expire_all()
        order = await SqlAlchemyOrderRepository(db).get_by_id(order_id)
        assert order is not None
        assert order.status == "delivered"


class TestNonFiniteQuantitiesAreRejected:
    @pytest.mark.parametrize("quantity", ["nan", "inf", "-Infinity"])
    async def test_deliver_with_a_non_finite_quantity_returns_422(
        self, db: AsyncSession, receiver, quantity: str
    ) -> None:
        _order_id, (item_id,) = await _seed_order(db, [(OrderItemStatus.ORDERED, 0.0)])

        response = await receiver.put(
            f"{DELIVER_URL}/{item_id}/deliver", params={"quantity": quantity}
        )

        assert response.status_code == 422, response.text
        error = response.json()["detail"][0]
        assert (error["type"], error["loc"], error["input"]) == (
            "finite_number",
            ["query", "quantity"],
            quantity,
        )
        item = await _read_line(db, item_id)
        assert (item.status, item.quantity_delivered) == (OrderItemStatus.ORDERED, 0.0)

    @pytest.mark.parametrize("token", ["NaN", "Infinity"])
    async def test_deliver_with_a_non_finite_rejected_quantity_in_the_body_returns_422(
        self, db: AsyncSession, receiver, token: str
    ) -> None:
        _order_id, (item_id,) = await _seed_order(db, [(OrderItemStatus.ORDERED, 0.0)])

        response = await receiver.put(
            f"{DELIVER_URL}/{item_id}/deliver",
            content=f'{{"quantity_rejected": {token}}}',
            headers=JSON,
        )

        assert response.status_code == 422, response.text
        error = response.json()["detail"][0]
        assert (error["type"], error["loc"], error["input"]) == (
            "finite_number",
            ["body", "quantity_rejected"],
            token,
        )
        assert (await _read_line(db, item_id)).quantity_delivered == 0.0

    async def test_deliver_all_with_a_nan_rejection_returns_422(
        self, db: AsyncSession, receiver
    ) -> None:
        order_id, (item_id,) = await _seed_order(db, [(OrderItemStatus.ORDERED, 0.0)])
        body = (
            f'{{"rejections": [{{"order_item_id": {item_id}, "quantity_rejected": NaN, '
            '"rejection_reason": "supplier_damage", "rejection_outcome": "redeliver"}]}'
        )

        response = await receiver.put(
            f"{ORDERS_URL}/{order_id}/deliver-all-items", content=body, headers=JSON
        )

        assert response.status_code == 422, response.text
        error = response.json()["detail"][0]
        assert error["type"] == "finite_number"
        assert error["loc"] == ["body", "rejections", 0, "quantity_rejected"]
        assert (await _read_line(db, item_id)).quantity_delivered == 0.0

    async def test_an_ordinary_validation_error_keeps_its_usual_shape(
        self, db: AsyncSession, receiver
    ) -> None:
        _order_id, (item_id,) = await _seed_order(db, [(OrderItemStatus.ORDERED, 0.0)])

        response = await receiver.put(
            f"{DELIVER_URL}/{item_id}/deliver", params={"quantity": "abc"}
        )

        assert response.status_code == 422, response.text
        assert response.json() == {
            "detail": [
                {
                    "type": "float_parsing",
                    "loc": ["query", "quantity"],
                    "msg": "Input should be a valid number, unable to parse string as a number",
                    "input": "abc",
                }
            ]
        }


def _rejection(order_item_id: int) -> dict[str, object]:
    return {
        "order_item_id": order_item_id,
        "quantity_rejected": 1.0,
        "rejection_reason": "supplier_damage",
        "rejection_outcome": "redeliver",
    }
