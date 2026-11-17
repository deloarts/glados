"""
The order use cases record facts and intents and leave every line and order
status to the lifecycle reconciler. Each locks what it writes in the one lock
order before it checks (a mark, a delivery and deliver-all lock the lot of a
MADE line before the order and the line), and afterwards the rows show what
the reconciler derived: a submit or a request stamps the order and its open
lines, a cancel stamps the order, cancels the lines that received nothing and
closes the partially delivered ones short, removing or moving a line derives
its orders anew, deliver-all books every line in one transaction, and an
order whose lines were all marked ordered one by one gets its ordered date.
Fakes and builders come from tests/unit/order/_helpers.py, the
reconciler from tests/unit/lifecycle/fake_reconciler.py.
"""

import pytest

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.fulfillment.application.dto.order_dto import DeliveryRejectionInput
from src.modules.fulfillment.application.use_cases.order.delete_order_item import RemoveOrderItem
from src.modules.fulfillment.application.use_cases.order.mark_order_item_ordered import (
    MarkOrderItemOrdered,
)
from src.modules.fulfillment.application.use_cases.order.move_order_item import MoveOrderItem
from src.modules.fulfillment.application.use_cases.order.process_order_item_delivery import (
    DeliverAllOrderItems,
)
from src.modules.fulfillment.application.use_cases.order.process_order_item_delivery import (
    ProcessOrderItemDelivery,
)
from src.modules.fulfillment.application.use_cases.order.update_order import CancelOrder
from src.modules.fulfillment.application.use_cases.order.update_order import RequestOrder
from src.modules.fulfillment.application.use_cases.order.update_order import SubmitOrder
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.errors import InvalidDeliveryQuantityError
from src.modules.fulfillment.domain.events.order_events import OrderSubmitted
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.platform.domain.exceptions import ConcurrentModificationError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler
from tests.unit.lifecycle.fake_reconciler import give_order_facts
from tests.unit.lifecycle.fake_reconciler import give_order_item_facts
from tests.unit.lifecycle.fake_reconciler import order_reconciler
from tests.unit.lifecycle.fake_reconciler import order_reconciler_harness
from tests.unit.order._helpers import FakeAllocationRepository
from tests.unit.order._helpers import FakeDemandRepository
from tests.unit.order._helpers import FakeEventBus
from tests.unit.order._helpers import FakeOrderItemRepository
from tests.unit.order._helpers import FakeOrderRepository
from tests.unit.order._helpers import FakeUnitOfWork
from tests.unit.order._helpers import make_allocation
from tests.unit.order._helpers import make_demand
from tests.unit.order._helpers import make_order
from tests.unit.order._helpers import make_order_item
from tests.unit.production_lot._helpers import NoLotCreation
from tests.unit.production_lot.fakes import FakeMadeItemAllocationRepository
from tests.unit.production_lot.fakes import FakeMadeItemDemandRepository
from tests.unit.production_lot.fakes import delivery_collaborators
from tests.unit.test_bought_item_delivery import FakeDeliveryRepository

MANAGER = make_user(permissions=[Permission.WRITE_ORDERS, Permission.MANAGE_ORDERS])
RECEIVER = make_user(id=3, username="receiver", permissions=[Permission.RECEIVE_DELIVERIES])

_A = LifecycleAggregate


def _line(
    id: int, status: OrderItemStatus, *, order_id: int = 1, delivered: float = 0.0
) -> OrderItem:
    """A line of ten pieces with the facts its status derives from."""
    line = make_order_item(id=id, order_id=order_id, status=status)
    line.quantity_delivered = delivered
    return give_order_item_facts(line)


class TestSubmitAndRequest:
    async def test_submit_marks_the_open_lines_ordered_and_leaves_the_others(self) -> None:
        order = make_order(id=1, status=OrderStatus.DRAFT)
        orders = FakeOrderRepository([order])
        lines = FakeOrderItemRepository(
            [
                _line(1, OrderItemStatus.PENDING),
                _line(2, OrderItemStatus.REQUESTED),
                _line(3, OrderItemStatus.CANCELED),
            ]
        )
        bus, uow = FakeEventBus(), FakeUnitOfWork()
        use_case = SubmitOrder(
            orders,
            event_bus=bus,
            uow=uow,
            reconciler=order_reconciler(orders, lines),
            order_item_repo=lines,
        )

        result = await use_case.execute(MANAGER, 1)

        assert result.status == "ordered"
        assert order.ordered_date is not None
        for line_id, old in ((1, "pending"), (2, "requested")):
            line = await lines.get_by_id(line_id)
            assert line is not None
            assert (line.status, line.ordered_date) == ("ordered", order.ordered_date)
            assert line.changes[-2].endswith("Marked as ordered: order #1 was submitted.")
            assert line.changes[-1].endswith(f"Status: {old} → ordered (order #1 submitted).")
        canceled = await lines.get_by_id(3)
        assert canceled is not None
        assert (canceled.status, canceled.ordered_date, canceled.changes) == ("canceled", None, [])
        assert [type(e) for e in bus.published] == [OrderSubmitted]
        assert uow.committed is True

    async def test_request_stamps_the_order_and_its_pending_lines(self) -> None:
        order = make_order(id=1, status=OrderStatus.DRAFT)
        orders = FakeOrderRepository([order])
        lines = FakeOrderItemRepository(
            [_line(1, OrderItemStatus.PENDING), _line(2, OrderItemStatus.PENDING)]
        )
        use_case = RequestOrder(
            orders,
            event_bus=FakeEventBus(),
            uow=FakeUnitOfWork(),
            reconciler=order_reconciler(orders, lines),
            order_item_repo=lines,
        )

        result = await use_case.execute(MANAGER, 1)

        assert result.status == "requested"
        assert order.requested_at is not None
        for line in await lines.get_by_order_id(1):
            assert (line.status, line.requested_at) == ("requested", order.requested_at)


class TestCancel:
    async def test_cancel_stamps_the_order_and_settles_its_open_lines(self) -> None:
        order = give_order_facts(make_order(id=1, status=OrderStatus.PARTIALLY_DELIVERED))
        orders = FakeOrderRepository([order])
        lines = FakeOrderItemRepository(
            [
                _line(1, OrderItemStatus.ORDERED),
                _line(2, OrderItemStatus.PARTIALLY_DELIVERED, delivered=4.0),
                _line(3, OrderItemStatus.PENDING),
            ]
        )
        allocations = FakeAllocationRepository([make_allocation(demand_item_id=1, order_item_id=1)])
        demand = make_demand(id=1, status=BoughtItemDemandStatus.ORDERED)
        use_case = CancelOrder(
            orders,
            lines,
            allocations,
            event_bus=FakeEventBus(),
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                bought_demands=FakeDemandRepository([demand]),
                bought_allocations=allocations,
                orders=orders,
                order_items=lines,
            ),
        )

        result = await use_case.execute(MANAGER, 1)

        assert result.status == "canceled"
        assert order.canceled_at is not None
        for line_id in (1, 3):
            line = await lines.get_by_id(line_id)
            assert line is not None
            assert (line.status, line.canceled_at) == ("canceled", order.canceled_at)
        # The partially delivered line is closed short at its deliveries.
        closed = await lines.get_by_id(2)
        assert closed is not None
        assert (closed.status, closed.quantity, closed.canceled_at) == ("delivered", 4.0, None)
        assert await allocations.get_by_order_item_id(1) == []
        assert demand.status == "open"


class TestRemoveAndMove:
    async def test_removing_the_last_open_line_delivers_the_order(self) -> None:
        order = give_order_facts(make_order(id=1, status=OrderStatus.PARTIALLY_DELIVERED))
        orders = FakeOrderRepository([order])
        lines = FakeOrderItemRepository(
            [_line(1, OrderItemStatus.DELIVERED, delivered=10.0), _line(2, OrderItemStatus.PENDING)]
        )
        use_case = RemoveOrderItem(
            orders,
            lines,
            FakeAllocationRepository(),
            uow=FakeUnitOfWork(),
            reconciler=order_reconciler(orders, lines),
        )

        await use_case.execute(MANAGER, 1, 2)

        assert await lines.get_by_id(2) is None
        assert order.status == "delivered"
        assert order.delivery_date is not None

    async def test_moving_a_line_derives_both_orders_anew(self) -> None:
        source = give_order_facts(make_order(id=1, status=OrderStatus.PARTIALLY_DELIVERED))
        target = make_order(id=2, status=OrderStatus.DRAFT)
        orders = FakeOrderRepository([source, target])
        lines = FakeOrderItemRepository(
            [_line(1, OrderItemStatus.ORDERED), _line(2, OrderItemStatus.DELIVERED, delivered=10.0)]
        )
        use_case = MoveOrderItem(
            orders, lines, uow=FakeUnitOfWork(), reconciler=order_reconciler(orders, lines)
        )

        await use_case.execute(MANAGER, 1, 1, 2)

        assert source.status == "delivered"
        assert target.status == "ordered"


class TestLockOrder:
    async def test_a_mark_locks_the_lot_before_the_order_and_the_line(self) -> None:
        orders = FakeOrderRepository([make_order(id=1, status=OrderStatus.DRAFT)])
        made = _line(1, OrderItemStatus.PENDING)
        made.line_type, made.bought_item_id = OrderLineType.MADE, None
        made.lot_position_id, made.lot_id = 4, 9
        lines = FakeOrderItemRepository([made])
        harness = order_reconciler_harness(orders, lines)
        use_case = MarkOrderItemOrdered(
            lines,
            orders,
            uow=FakeUnitOfWork(),
            reconciler=harness.reconciler,
        )

        await use_case.execute(MANAGER, 1, 1)

        assert harness.lock_log == [(_A.LOTS, (9,)), (_A.ORDERS, (1,)), (_A.ORDER_ITEMS, (1,))]

    async def test_a_delivery_locks_the_lot_before_the_order_and_the_line(self) -> None:
        world = _Deliveries([_made_line(1, lot_id=9)])

        await world.deliver.execute(RECEIVER, 1, quantity=2.0)

        assert world.harness.lock_log == [
            (_A.LOTS, (9,)),
            (_A.ORDERS, (1,)),
            (_A.ORDER_ITEMS, (1,)),
        ]

    async def test_deliver_all_locks_the_lots_the_order_and_every_line_at_once(self) -> None:
        world = _Deliveries([_made_line(1, lot_id=9), _line(2, OrderItemStatus.ORDERED)])

        await world.deliver_all.execute(RECEIVER, 1)

        assert world.harness.lock_log == [
            (_A.LOTS, (9,)),
            (_A.ORDERS, (1,)),
            (_A.ORDER_ITEMS, (1, 2)),
        ]


def _made_line(id: int, *, lot_id: int) -> OrderItem:
    """An ordered MADE line that supplies a position of lot `lot_id`."""
    made = _line(id, OrderItemStatus.ORDERED)
    made.line_type, made.bought_item_id = OrderLineType.MADE, None
    made.lot_position_id, made.lot_id = 40 + id, lot_id
    return made


class _Deliveries:
    """Order #1, placed, with the given lines, and the delivery and
    deliver-all use cases over it, sharing one reconciler as in a request."""

    def __init__(self, lines: list[OrderItem]) -> None:
        self.order = give_order_facts(make_order(id=1, status=OrderStatus.ORDERED))
        self.orders = FakeOrderRepository([self.order])
        self.lines = FakeOrderItemRepository(lines)
        self.bus, self.uow = FakeEventBus(), FakeUnitOfWork()
        self.harness = order_reconciler_harness(self.orders, self.lines)
        self.deliver = ProcessOrderItemDelivery(
            self.lines,
            self.orders,
            FakeDeliveryRepository(),
            event_bus=self.bus,
            uow=self.uow,
            reconciler=self.harness.reconciler,
            made_item_demand_repo=FakeMadeItemDemandRepository(),
            made_item_allocation_repo=FakeMadeItemAllocationRepository(),
            create_lot=NoLotCreation(),
            **delivery_collaborators(),
        )
        self.deliver_all = DeliverAllOrderItems(
            self.orders,
            self.lines,
            self.deliver,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=self.harness.reconciler,
        )


class _MovedWhileLocking(FakeOrderItemRepository):
    """Moves line #1 to order #2 the first time it is read through its lock,
    as a move that commits while the delivery waits for the line's lock."""

    async def get_by_id_for_update(self, id: int) -> OrderItem | None:
        item = await super().get_by_id_for_update(id)
        if item is not None and item.id == 1:
            item.order_id = 2
        return item


class TestMovedWhileWaiting:
    async def test_a_delivery_on_a_line_moved_to_another_order_meanwhile_is_refused(self) -> None:
        world = _Deliveries([])
        world.orders = FakeOrderRepository(
            [world.order, give_order_facts(make_order(id=2, status=OrderStatus.ORDERED))]
        )
        world.lines = _MovedWhileLocking([_line(1, OrderItemStatus.ORDERED)])
        world.harness = order_reconciler_harness(world.orders, world.lines)
        deliver = ProcessOrderItemDelivery(
            world.lines,
            world.orders,
            FakeDeliveryRepository(),
            event_bus=world.bus,
            uow=world.uow,
            reconciler=world.harness.reconciler,
            made_item_demand_repo=FakeMadeItemDemandRepository(),
            made_item_allocation_repo=FakeMadeItemAllocationRepository(),
            create_lot=NoLotCreation(),
            **delivery_collaborators(),
        )

        with pytest.raises(ConcurrentModificationError):
            await deliver.execute(RECEIVER, 1, quantity=2.0)

        assert world.uow.committed is False
        assert (await world.lines.get_by_id(1)).quantity_delivered == 0.0


class TestDeliverAll:
    async def test_a_line_that_fails_leaves_the_whole_order_uncommitted(self) -> None:
        world = _Deliveries([_line(1, OrderItemStatus.ORDERED), _line(2, OrderItemStatus.ORDERED)])
        # More rejected pieces than the second line has open.
        too_many = DeliveryRejectionInput(
            order_item_id=2,
            quantity_rejected=11.0,
            rejection_reason="supplier_damage",
            rejection_outcome="redeliver",
        )

        with pytest.raises(InvalidDeliveryQuantityError):
            await world.deliver_all.execute(RECEIVER, 1, rejections=[too_many])

        assert world.uow.committed is False
        assert world.bus.published == []
        assert world.harness.bus.published == []

    async def test_every_deliverable_line_is_booked_and_the_others_are_skipped(self) -> None:
        world = _Deliveries(
            [
                _line(1, OrderItemStatus.ORDERED),
                _line(2, OrderItemStatus.PARTIALLY_DELIVERED, delivered=4.0),
                _line(3, OrderItemStatus.PENDING),
            ]
        )

        result = await world.deliver_all.execute(RECEIVER, 1)

        assert sorted(r.id for r in result.delivered) == [1, 2]
        assert [(s.order_item_id, s.reason) for s in result.skipped] == [(3, "not_ordered")]
        assert [
            (line.status, line.quantity_delivered) for line in await world.lines.get_by_order_id(1)
        ] == [
            ("delivered", 10.0),
            ("delivered", 10.0),
            ("pending", 0.0),
        ]
        # The pending line keeps the order partially delivered.
        assert world.order.status == "partially_delivered"
        assert world.uow.committed is True


class _MovedBeforeTheLockedRead(FakeOrderItemRepository):
    """Moves line #1 to order #2 when deliver-all reads its locked lines
    again, as a move that commits while deliver-all waits for the locks."""

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list:
        found = await super().get_by_ids(ids, refresh=refresh)
        for item in found:
            if refresh and item.id == 1:
                item.order_id = 2
        return found


class TestDeliverAllMovedWhileWaiting:
    def _world(self) -> _Deliveries:
        world = _Deliveries([])
        world.orders = FakeOrderRepository(
            [world.order, give_order_facts(make_order(id=2, status=OrderStatus.ORDERED))]
        )
        world.lines = _MovedBeforeTheLockedRead(
            [_line(1, OrderItemStatus.ORDERED), _line(2, OrderItemStatus.ORDERED)]
        )
        world.harness = order_reconciler_harness(world.orders, world.lines)
        world.deliver = ProcessOrderItemDelivery(
            world.lines,
            world.orders,
            FakeDeliveryRepository(),
            event_bus=world.bus,
            uow=world.uow,
            reconciler=world.harness.reconciler,
            made_item_demand_repo=FakeMadeItemDemandRepository(),
            made_item_allocation_repo=FakeMadeItemAllocationRepository(),
            create_lot=NoLotCreation(),
            **delivery_collaborators(),
        )
        world.deliver_all = DeliverAllOrderItems(
            world.orders,
            world.lines,
            world.deliver,
            event_bus=world.bus,
            uow=world.uow,
            reconciler=world.harness.reconciler,
        )
        return world

    async def test_deliver_all_skips_a_line_moved_to_another_order_meanwhile(self) -> None:
        world = self._world()

        result = await world.deliver_all.execute(RECEIVER, 1)

        assert [r.id for r in result.delivered] == [2]
        assert [(s.order_item_id, s.reason) for s in result.skipped] == [(1, "moved")]
        moved = await world.lines.get_by_id(1)
        assert moved is not None
        assert (moved.order_id, moved.quantity_delivered) == (2, 0.0)

    async def test_deliver_all_refuses_a_rejection_on_a_line_moved_meanwhile(self) -> None:
        world = self._world()
        rejection = DeliveryRejectionInput(
            order_item_id=1,
            quantity_rejected=1.0,
            rejection_reason="supplier_damage",
            rejection_outcome="redeliver",
        )

        with pytest.raises(ConcurrentModificationError):
            await world.deliver_all.execute(RECEIVER, 1, rejections=[rejection])

        assert world.uow.committed is False


class TestOrderedDate:
    async def test_marking_every_line_ordered_one_by_one_records_the_orders_ordered_date(
        self,
    ) -> None:
        order = make_order(id=1, status=OrderStatus.DRAFT)
        orders = FakeOrderRepository([order])
        lines = FakeOrderItemRepository(
            [_line(1, OrderItemStatus.PENDING), _line(2, OrderItemStatus.PENDING)]
        )

        def mark() -> MarkOrderItemOrdered:
            return MarkOrderItemOrdered(
                lines,
                orders,
                uow=FakeUnitOfWork(),
                reconciler=order_reconciler(orders, lines),
            )

        await mark().execute(MANAGER, 1, 1)
        assert (order.status, order.ordered_date) == ("partially_ordered", None)

        await mark().execute(MANAGER, 1, 2)

        second = await lines.get_by_id(2)
        assert second is not None
        assert order.status == "ordered"
        assert order.ordered_date is not None
        assert order.ordered_date == second.ordered_date
        assert order.changes[-1].endswith("Ordered date: set (derived from recorded facts).")
