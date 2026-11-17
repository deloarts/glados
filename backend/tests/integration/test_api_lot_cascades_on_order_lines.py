"""
The lot actions that write supplier order lines, through the API: assigning
a position externally adds a pending line (refused on an order someone
canceled, but taken beside a canceled line of the position, and by an order
that reads canceled only because a lot cancel emptied it) and unassigning
removes it; force-completing a lot closes its external line short at the
pieces received; force-canceling a lot cancels the line. The
lifecycle reconciler derives the line's and the order's status in each, and
the drift check after every test, delivery totals included, finds nothing
left over. Rows are seeded through the repository read graph.
"""

import dataclasses
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model import (
    LotPositionOrmModel,
)
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
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.platform.const import API_WEB
from src.modules.platform.domain.value_objects.permission import Permission
from tests.integration._edit_versions import lot_version
from tests.integration._edit_versions import order_version
from tests.integration.repository_reads._graph import NOW
from tests.integration.repository_reads._graph import Graph
from tests.integration.repository_reads._graph import make

LOTS = f"{API_WEB}/production-lots"
ORDERS = f"{API_WEB}/orders"
DELIVER_URL = f"{API_WEB}/bought-items-allocations/order-item"
PLANNER = [Permission.WRITE_LOTS, Permission.MANAGE_LOTS]
BUYER = [Permission.WRITE_ORDERS, Permission.MANAGE_ORDERS]


async def _client(auth_client: Any, name: str, permissions: list[str]) -> Any:
    return await auth_client(permissions=permissions, username=name, email=f"{name}@example.com")


async def _unassigned_position(
    db: AsyncSession, graph: Graph, lot_id: int | None = None
) -> LotPosition:
    """An unassigned position of the graph's lot, or of the lot `lot_id`."""
    lot_id = lot_id if lot_id is not None else (await graph.lot()).id
    position = await SqlAlchemyProductionLotRepository(db).save_position(
        make(
            LotPosition,
            sequence=3,
            kind=LotPositionKind.UNASSIGNED,
            status=LotPositionStatus.PENDING,
            quantity=10.0,
            quantity_completed=0.0,
            creator_id=graph.uid,
            lot_id=lot_id,
        )
    )
    await db.commit()
    return position


async def _production_settings(db: AsyncSession) -> None:
    """The settings an internal assignment reads for its order numbers."""
    await SqlAlchemyAdminSettingsRepository(db).save_production(
        AdminProductionSettings(
            id=1,
            production_order_number_format="PO-{seq:04d}",
            default_weekly_hours={day: 480 for day in range(5)},
            default_external_lead_days=0,
            response_time_days=0,
            require_qa=False,
        )
    )
    await db.commit()


async def _line(db: AsyncSession, line_id: int) -> OrderItem | None:
    db.expire_all()
    return await SqlAlchemyOrderItemRepository(db).get_by_id(line_id)


async def _unordered(db: AsyncSession, line: OrderItem) -> OrderItem:
    """The line as one not yet placed with the supplier, which a lot cancel
    cancels; an ordered one stays open for purchasing."""
    line.status = OrderItemStatus.PENDING
    line.ordered_date = None
    saved = await SqlAlchemyOrderItemRepository(db).save(line)
    await db.commit()
    return saved


async def _order(db: AsyncSession, order_id: int) -> Order:
    db.expire_all()
    order = await SqlAlchemyOrderRepository(db).get_by_id(order_id)
    assert order is not None
    return order


async def test_assigning_and_unassigning_a_position_adds_and_removes_a_pending_line(
    db: AsyncSession, auth_client: Any
) -> None:
    graph = await Graph.seed(db)
    lot, order = await graph.lot(), await graph.order()
    position = await _unassigned_position(db, graph)
    buyer = await _client(auth_client, "buyer", BUYER)
    planner = await _client(auth_client, "planner", PLANNER)

    assigned = await buyer.post(
        f"{LOTS}/{lot.id}/positions/{position.id}/assign",
        json={"order_id": order.id, "unit": "pcs"},
    )

    assert assigned.status_code == 200, assigned.text
    line_id = assigned.json()["order_item_id"]
    line = await _line(db, line_id)
    assert line is not None
    assert (line.status, line.order_id, line.lot_position_id) == ("pending", order.id, position.id)
    assert (await _order(db, order.id)).status == "ordered"

    unassigned = await planner.delete(f"{LOTS}/{lot.id}/positions/{position.id}/assign")

    assert unassigned.status_code == 204, unassigned.text
    assert await _line(db, line_id) is None
    assert (await _order(db, order.id)).status == "ordered"


async def test_an_order_someone_canceled_takes_no_assigned_position(
    db: AsyncSession, auth_client: Any
) -> None:
    graph = await Graph.seed(db)
    lot = await graph.lot()
    order = await graph.order()
    order.status, order.canceled_at = OrderStatus.CANCELED, NOW
    await SqlAlchemyOrderRepository(db).save(order)
    await db.commit()
    position = await _unassigned_position(db, graph)
    buyer = await _client(auth_client, "buyer", BUYER)

    refused = await buyer.post(
        f"{LOTS}/{lot.id}/positions/{position.id}/assign",
        json={"order_id": order.id, "unit": "pcs"},
    )

    assert refused.status_code == 409, refused.text
    assert refused.json()["code"] == "OrderCanceledError"
    assert await SqlAlchemyOrderItemRepository(db).get_by_order_id(order.id) == []


async def test_an_order_emptied_by_a_lot_cancel_takes_a_position_of_another_lot(
    db: AsyncSession, auth_client: Any
) -> None:
    """Force-canceling the lot cancels the order's only line, not yet placed
    with the supplier, so the order reads canceled without anyone canceling
    it. It still takes a new line and derives from it: ordered again."""
    graph = await Graph.seed(db)
    lot = await graph.lot()
    line = await _unordered(db, await graph.made_order_item())
    planner = await _client(auth_client, "planner", PLANNER)
    buyer = await _client(auth_client, "buyer", BUYER)
    canceled = await planner.post(
        f"{LOTS}/{lot.id}/cancel",
        json={"expected_edit_version": await lot_version(planner, lot.id)},
    )
    assert canceled.status_code == 200, canceled.text
    emptied = await _order(db, line.order_id)
    assert (emptied.status, emptied.canceled_at) == ("canceled", None)
    other_lot = await SqlAlchemyProductionLotRepository(db).save(
        dataclasses.replace(
            lot,
            id=0,
            public_id=uuid4(),
            lot_number="L-9",
            status=LotStatus.PLANNED,
            input_demand_id=None,
        )
    )
    await db.commit()
    position = await _unassigned_position(db, graph, other_lot.id)

    assigned = await buyer.post(
        f"{LOTS}/{other_lot.id}/positions/{position.id}/assign",
        json={"order_id": line.order_id, "unit": "pcs"},
    )

    assert assigned.status_code == 200, assigned.text
    order = await _order(db, line.order_id)
    assert (order.status, order.canceled_at) == ("ordered", None)


async def test_a_position_whose_line_was_canceled_accepts_a_second_line_beside_it(
    db: AsyncSession, auth_client: Any
) -> None:
    """Canceling the order cancels the position's line, which no longer shows
    on the position and no longer counts against the live line index on
    order_item.lot_position_id. Planning part of the position internally and
    assigning the rest to another order adds a second line beside the
    canceled one, and the position turns MIXED."""
    await _production_settings(db)
    graph = await Graph.seed(db)
    lot, supplier = await graph.lot(), await graph.supplier()
    line = await graph.made_order_item()
    assert line.lot_position_id is not None
    other = await SqlAlchemyOrderRepository(db).save(
        make(
            Order,
            order_number="O-2",
            status=OrderStatus.DRAFT,
            creator_id=graph.uid,
            supplier_id=supplier.id,
        )
    )
    await db.commit()
    boss = await _client(
        auth_client, "boss", [*BUYER, *PLANNER, Permission.WRITE_PRODUCTION_ORDERS]
    )
    position_url = f"{LOTS}/{lot.id}/positions/{line.lot_position_id}"

    canceled = await boss.put(
        f"{ORDERS}/{line.order_id}/cancel",
        params={"expected_edit_version": await order_version(boss, line.order_id)},
    )
    planned = await boss.post(
        f"{position_url}/assign-internal", json={"orders": [{"quantity": 5.0}]}
    )
    assigned = await boss.post(
        f"{position_url}/assign",
        json={"order_id": other.id, "unit": "pcs", "quantity": 1.0},
    )

    assert canceled.status_code == 200, canceled.text
    assert planned.status_code == 200, planned.text
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["kind"] == "mixed"
    [second] = await SqlAlchemyOrderItemRepository(db).get_by_order_id(other.id)
    assert assigned.json()["order_item_id"] == second.id
    assert second.lot_position_id == line.lot_position_id
    old = await _line(db, line.id)
    assert old is not None
    assert (old.status, old.lot_position_id) == ("canceled", line.lot_position_id)


async def test_force_completing_a_lot_closes_its_external_line_short_at_the_pieces_received(
    db: AsyncSession, auth_client: Any
) -> None:
    """A force-complete ends the lot at what it produced: the line keeps the
    pieces received and books no delivery for the open rest."""
    graph = await Graph.seed(db)
    lot = await graph.lot()
    line = await graph.made_order_item()
    # The graph's external position is the lot's only one here, so it is
    # the first, whose supplier sources the material it receives.
    position = await db.get(LotPositionOrmModel, line.lot_position_id)
    assert position is not None
    position.sequence = 1
    await db.commit()
    planner = await _client(auth_client, "planner", PLANNER)
    receiver = await _client(auth_client, "receiver", [Permission.RECEIVE_DELIVERIES])
    received = await receiver.put(f"{DELIVER_URL}/{line.id}/deliver", params={"quantity": 4.0})
    assert received.status_code == 200, received.text

    completed = await planner.post(
        f"{LOTS}/{lot.id}/complete",
        json={"expected_edit_version": await lot_version(planner, lot.id)},
    )

    assert completed.status_code == 200, completed.text
    closed = await _line(db, line.id)
    assert closed is not None
    assert (closed.status, closed.quantity, closed.quantity_delivered) == ("delivered", 4.0, 4.0)
    [row] = await SqlAlchemyOrderItemDeliveryRepository(db).get_by_order_item_id(line.id)
    assert row.quantity == 4.0
    order = await _order(db, line.order_id)
    assert order.status == "delivered"
    assert order.delivery_date is not None


async def test_force_canceling_a_lot_cancels_its_unordered_line_and_the_order_it_emptied(
    db: AsyncSession, auth_client: Any
) -> None:
    graph = await Graph.seed(db)
    lot = await graph.lot()
    line = await _unordered(db, await graph.made_order_item())
    planner = await _client(auth_client, "planner", PLANNER)

    canceled = await planner.post(
        f"{LOTS}/{lot.id}/cancel",
        json={"expected_edit_version": await lot_version(planner, lot.id)},
    )

    assert canceled.status_code == 200, canceled.text
    stored = await _line(db, line.id)
    assert stored is not None
    assert stored.status == "canceled"
    assert stored.canceled_at is not None
    assert (await _order(db, line.order_id)).status == "canceled"


async def test_canceling_a_lot_keeps_its_ordered_external_line_open(
    db: AsyncSession, auth_client: Any
) -> None:
    """The supplier was ordered and sent nothing yet, so the line is not
    canceled behind its back: it stays ordered for purchasing, and the
    order with it, while the canceled lot's line takes no delivery."""
    graph = await Graph.seed(db)
    lot = await graph.lot()
    line = await graph.made_order_item()
    planner = await _client(auth_client, "planner", PLANNER)

    canceled = await planner.post(
        f"{LOTS}/{lot.id}/cancel",
        json={"expected_edit_version": await lot_version(planner, lot.id)},
    )

    assert canceled.status_code == 200, canceled.text
    stored = await _line(db, line.id)
    assert stored is not None
    assert (stored.status, stored.canceled_at) == ("ordered", None)
    assert (await _order(db, line.order_id)).status == "ordered"
