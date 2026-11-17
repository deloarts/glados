"""
How an order line that will not be delivered in full is settled. A line that
received nothing is canceled: it stays on the order as canceled and every
allocation on it is released, a fulfilled demand keeping its status. A line
that received pieces is closed short: its quantity becomes the pieces
delivered or lost, its allocations shrink to that quantity with the rounding
settled in favour of the oldest demand, and every demand on it is recomputed.
Canceling an order settles its lines the same way, a delivered line staying
as it is. Each action needs the order's update permission before the line's
state is checked, and locks the lot of a MADE line first. Fakes and builders
come from tests/unit/order/_helpers.py.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.fulfillment.application.use_cases.order.cancel_order_item import CancelOrderItem
from src.modules.fulfillment.application.use_cases.order.close_order_item_short import (
    CloseOrderItemShort,
)
from src.modules.fulfillment.application.use_cases.order.update_order import CancelOrder
from src.modules.fulfillment.domain.entities.bought_item_allocation import (
    BoughtItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.source_item_allocation import (
    SourceItemDemandAllocation,
)
from src.modules.fulfillment.domain.errors import OrderItemCannotBeCanceledError
from src.modules.fulfillment.domain.errors import OrderItemCannotBeClosedShortError
from src.modules.fulfillment.domain.errors import OrderItemNotFoundError
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler_harness
from tests.unit.lifecycle.fake_reconciler import give_order_facts
from tests.unit.lifecycle.fake_reconciler import give_order_item_facts
from tests.unit.order._helpers import FakeAllocationRepository
from tests.unit.order._helpers import FakeDemandRepository
from tests.unit.order._helpers import FakeEventBus
from tests.unit.order._helpers import FakeOrderItemRepository
from tests.unit.order._helpers import FakeOrderRepository
from tests.unit.order._helpers import FakeSourceItemAllocationRepository
from tests.unit.order._helpers import FakeSourceItemDemandRepository
from tests.unit.order._helpers import FakeUnitOfWork
from tests.unit.order._helpers import make_allocation
from tests.unit.order._helpers import make_demand
from tests.unit.order._helpers import make_order
from tests.unit.order._helpers import make_order_item
from tests.unit.order._helpers import make_source_item_allocation
from tests.unit.order._helpers import make_source_item_demand

MANAGER = make_user(permissions=[Permission.WRITE_ORDERS, Permission.MANAGE_ORDERS])
STRANGER = make_user(id=2, username="stranger", permissions=[])

_A = LifecycleAggregate


def _line(
    id: int,
    status: OrderItemStatus,
    *,
    quantity: float = 10.0,
    delivered: float = 0.0,
    lost: float = 0.0,
    order_id: int = 1,
) -> OrderItem:
    """A line with the facts its status derives from."""
    line = make_order_item(id=id, order_id=order_id, status=status)
    line.quantity = quantity
    line.quantity_delivered = delivered
    line.quantity_rejected = lost
    line.quantity_rejected_lost = lost
    return give_order_item_facts(line)


def _made(line: OrderItem, *, lot_id: int) -> OrderItem:
    """Turns the line into a MADE line supplying a position of `lot_id`."""
    line.line_type, line.bought_item_id = OrderLineType.MADE, None
    line.lot_position_id, line.lot_id = 40 + line.id, lot_id
    return line


class _Allocations(FakeAllocationRepository):
    """Bought allocations whose save writes the row in place, as the
    repository's does."""

    async def save(self, allocation: BoughtItemDemandAllocation) -> BoughtItemDemandAllocation:
        await self.delete(allocation)
        return await super().save(allocation)


class _SourceAllocations(FakeSourceItemAllocationRepository):
    """Source allocations whose save writes the row in place."""

    async def save(self, allocation: SourceItemDemandAllocation) -> SourceItemDemandAllocation:
        await self.delete(allocation)
        self._allocations.append(allocation)
        return allocation


class _World:
    """Order #1 with the given lines and allocations, and the settling use
    cases over it, sharing one reconciler as in a request."""

    def __init__(
        self,
        lines: list[OrderItem],
        *,
        order: Order | None = None,
        allocations: list[BoughtItemDemandAllocation] | None = None,
        demands: list | None = None,
        source_allocations: list[SourceItemDemandAllocation] | None = None,
        source_demands: list | None = None,
    ) -> None:
        self.order = order or give_order_facts(make_order(id=1, status=OrderStatus.ORDERED))
        self.orders = FakeOrderRepository([self.order])
        self.lines = FakeOrderItemRepository(lines)
        self.allocations = _Allocations(allocations)
        self.demands = FakeDemandRepository(demands)
        self.source_allocations = _SourceAllocations(source_allocations)
        self.source_demands = FakeSourceItemDemandRepository(source_demands)
        self.uow = FakeUnitOfWork()
        self.harness = demand_reconciler_harness(
            orders=self.orders,
            order_items=self.lines,
            bought_demands=self.demands,
            bought_allocations=self.allocations,
            source_demands=self.source_demands,
            source_allocations=self.source_allocations,
        )

    def cancel_line(self) -> CancelOrderItem:
        return CancelOrderItem(
            self.orders,
            self.lines,
            self.allocations,
            uow=self.uow,
            reconciler=self.harness.reconciler,
            source_item_allocation_repo=self.source_allocations,
        )

    def close_short(self) -> CloseOrderItemShort:
        return CloseOrderItemShort(
            self.orders,
            self.lines,
            self.allocations,
            uow=self.uow,
            reconciler=self.harness.reconciler,
            source_item_allocation_repo=self.source_allocations,
        )

    def cancel_order(self) -> CancelOrder:
        return CancelOrder(
            self.orders,
            self.lines,
            self.allocations,
            event_bus=FakeEventBus(),
            uow=self.uow,
            reconciler=self.harness.reconciler,
            source_item_allocation_repo=self.source_allocations,
        )

    async def line(self, id: int) -> OrderItem:
        found = await self.lines.get_by_id(id)
        assert found is not None
        return found

    async def bought_on(self, line_id: int) -> dict[int, float]:
        """The bought allocations on the line, by demand id."""
        return {
            a.demand_item_id: a.quantity
            for a in await self.allocations.get_by_order_item_id(line_id)
        }

    async def source_on(self, line_id: int) -> dict[int, float]:
        """The source allocations on the line, by demand id."""
        return {
            a.demand_item_id: a.quantity
            for a in await self.source_allocations.get_by_order_item_id(line_id)
        }


class TestCancelLine:
    async def test_an_ordered_line_is_canceled_and_every_allocation_on_it_released(
        self,
    ) -> None:
        bought = make_demand(id=1, status=BoughtItemDemandStatus.ORDERED)
        source = make_source_item_demand(id=5, status=SourceItemDemandStatus.ALLOCATED)
        world = _World(
            [_line(1, OrderItemStatus.ORDERED), _line(2, OrderItemStatus.ORDERED)],
            allocations=[make_allocation(demand_item_id=1, order_item_id=1, quantity=6.0)],
            demands=[bought],
            source_allocations=[make_source_item_allocation(demand_item_id=5, quantity=4.0)],
            source_demands=[source],
        )

        result = await world.cancel_line().execute(MANAGER, 1, 1)

        line = await world.line(1)
        assert (result.status, line.status) == ("canceled", "canceled")
        assert line.canceled_at is not None
        assert line.quantity == 10.0
        assert line.changes[-2].endswith("Canceled.")
        assert line.changes[-1].endswith("Status: ordered → canceled (order item #1 canceled).")
        assert await world.bought_on(1) == {}
        assert await world.source_on(1) == {}
        assert bought.status == "open"
        # The released demand's changelog names the line whose cancel freed it.
        assert bought.changes[-1].endswith("Status: ordered → open (order item #1 canceled).")
        assert source.status == "open"
        # The order's other line keeps it ordered.
        assert world.order.status == "ordered"
        assert world.uow.committed is True

    async def test_the_last_live_line_canceled_cancels_the_order(self) -> None:
        world = _World([_line(1, OrderItemStatus.ORDERED), _line(2, OrderItemStatus.CANCELED)])

        await world.cancel_line().execute(MANAGER, 1, 1)

        assert world.order.status == "canceled"
        assert world.order.canceled_at is None

    async def test_a_fulfilled_demand_loses_its_allocation_but_keeps_its_status(self) -> None:
        fulfilled = make_demand(id=1, status=BoughtItemDemandStatus.FULFILLED)
        fulfilled.fulfilled_manually_at = datetime(2026, 1, 1, tzinfo=UTC)
        world = _World(
            [_line(1, OrderItemStatus.ORDERED)],
            allocations=[make_allocation(demand_item_id=1, order_item_id=1)],
            demands=[fulfilled],
        )

        await world.cancel_line().execute(MANAGER, 1, 1)

        assert await world.bought_on(1) == {}
        assert (fulfilled.status, fulfilled.changes) == ("fulfilled", [])

    async def test_a_line_with_lost_pieces_is_closed_short_instead(self) -> None:
        world = _World([_line(1, OrderItemStatus.PARTIALLY_DELIVERED, lost=2.0)])

        with pytest.raises(OrderItemCannotBeCanceledError, match="close it short instead"):
            await world.cancel_line().execute(MANAGER, 1, 1)

        line = await world.line(1)
        assert (line.status, line.canceled_at, line.changes) == ("partially_delivered", None, [])
        assert world.uow.committed is False

    @pytest.mark.parametrize(
        ("status", "delivered", "message"),
        [
            (OrderItemStatus.DELIVERED, 10.0, "is delivered and cannot be canceled"),
            (OrderItemStatus.CANCELED, 0.0, "is already canceled"),
        ],
    )
    async def test_a_delivered_or_canceled_line_is_refused(
        self, status: OrderItemStatus, delivered: float, message: str
    ) -> None:
        world = _World([_line(1, status, delivered=delivered)])

        with pytest.raises(OrderItemCannotBeCanceledError, match=message):
            await world.cancel_line().execute(MANAGER, 1, 1)

        assert world.uow.committed is False

    async def test_the_permission_is_checked_before_the_state(self) -> None:
        world = _World([_line(1, OrderItemStatus.DELIVERED, delivered=10.0)])

        with pytest.raises(InsufficientPermissionsError):
            await world.cancel_line().execute(STRANGER, 1, 1)

    async def test_a_line_named_under_another_order_is_not_found(self) -> None:
        world = _World([_line(1, OrderItemStatus.ORDERED, order_id=2)])

        with pytest.raises(OrderItemNotFoundError):
            await world.cancel_line().execute(MANAGER, 1, 1)

    async def test_a_made_line_is_canceled_after_its_lot_is_locked(self) -> None:
        world = _World([_made(_line(1, OrderItemStatus.ORDERED), lot_id=9)])

        await world.cancel_line().execute(MANAGER, 1, 1)

        assert (await world.line(1)).status == "canceled"
        assert world.harness.lock_log == [
            (_A.LOTS, (9,)),
            (_A.ORDERS, (1,)),
            (_A.ORDER_ITEMS, (1,)),
        ]


class TestCloseShort:
    async def test_a_partially_delivered_line_closes_at_its_deliveries_and_delivers_the_order(
        self,
    ) -> None:
        # The supplier ships only 6 of 10. The order's other live line is
        # delivered and its canceled line does not count.
        world = _World(
            [
                _line(1, OrderItemStatus.PARTIALLY_DELIVERED, delivered=6.0),
                _line(2, OrderItemStatus.DELIVERED, quantity=5.0, delivered=5.0),
                _line(3, OrderItemStatus.CANCELED, quantity=4.0),
            ],
            order=give_order_facts(make_order(id=1, status=OrderStatus.PARTIALLY_DELIVERED)),
        )

        result = await world.close_short().execute(MANAGER, 1, 1)

        line = await world.line(1)
        assert (result.status, result.quantity) == ("delivered", 6.0)
        assert (line.status, line.quantity, line.quantity_delivered) == ("delivered", 6.0, 6.0)
        assert line.changes[-2].endswith("Closed short at 6.000 of 10.000 pcs.")
        assert line.changes[-1].endswith("Status: partially_delivered → delivered (closed short).")
        assert world.order.status == "delivered"
        assert world.order.delivery_date is not None
        assert world.order.changes[-2].endswith(
            "Status: partially_delivered → delivered (closed short)."
        )
        assert world.order.changes[-1].endswith("Delivery date: set (closed short).")
        assert world.uow.committed is True

    async def test_lost_pieces_count_toward_the_closed_quantity(self) -> None:
        world = _World([_line(1, OrderItemStatus.PARTIALLY_DELIVERED, delivered=4.0, lost=2.0)])

        await world.close_short().execute(MANAGER, 1, 1)

        line = await world.line(1)
        assert (line.status, line.quantity) == ("delivered", 6.0)

    @staticmethod
    def _three_allocations(quantity: float, delivered: float) -> _World:
        """A line with an equal allocation for bought demands #2 and #1 and
        source demand #1. Bought demands come before source demands, each
        family by id, so bought demand #1 is the oldest and the source
        demand the newest."""
        share = quantity / 3
        return _World(
            [_line(1, OrderItemStatus.PARTIALLY_DELIVERED, quantity=quantity, delivered=delivered)],
            allocations=[
                make_allocation(demand_item_id=2, order_item_id=1, quantity=share),
                make_allocation(demand_item_id=1, order_item_id=1, quantity=share),
            ],
            demands=[
                make_demand(id=1, status=BoughtItemDemandStatus.ORDERED),
                make_demand(id=2, status=BoughtItemDemandStatus.ORDERED),
            ],
            source_allocations=[make_source_item_allocation(demand_item_id=1, quantity=share)],
            source_demands=[make_source_item_demand(id=1, status=SourceItemDemandStatus.ORDERED)],
        )

    async def test_allocations_are_cut_from_the_end_of_the_fill(self) -> None:
        # 1 of 3 delivered reached the oldest bought demand; the newer ones,
        # the source demand last, give up what never came.
        world = self._three_allocations(3.0, delivered=1.0)

        await world.close_short().execute(MANAGER, 1, 1)

        assert await world.bought_on(1) == {1: pytest.approx(1.0)}
        assert await world.source_on(1) == {}

    async def test_a_partly_reached_demand_keeps_the_pieces_that_reached_it(self) -> None:
        # 2 of 9 delivered: the oldest demand's allocation of 3 keeps the 2.
        world = self._three_allocations(9.0, delivered=2.0)

        await world.close_short().execute(MANAGER, 1, 1)

        assert await world.bought_on(1) == {1: pytest.approx(2.0)}
        assert await world.source_on(1) == {}

    async def test_an_allocation_that_shrinks_to_nothing_is_released(self) -> None:
        world = _World(
            [_line(1, OrderItemStatus.PARTIALLY_DELIVERED, delivered=0.001)],
            allocations=[
                make_allocation(demand_item_id=1, order_item_id=1, quantity=5.0),
                make_allocation(demand_item_id=2, order_item_id=1, quantity=5.0),
            ],
            demands=[
                make_demand(id=1, status=BoughtItemDemandStatus.ORDERED),
                make_demand(id=2, status=BoughtItemDemandStatus.ORDERED),
            ],
        )

        await world.close_short().execute(MANAGER, 1, 1)

        assert await world.bought_on(1) == {1: pytest.approx(0.001)}

    async def test_every_demand_on_the_line_is_recomputed(self) -> None:
        # 6 of 10 delivered reach both allocations in their fill order; once
        # the line is closed at 6, every demand on it is derived again.
        bought = make_demand(id=1, status=BoughtItemDemandStatus.ORDERED)
        bought.quantity = 4.0
        source = make_source_item_demand(id=2, status=SourceItemDemandStatus.ORDERED)
        source.quantity = 2.0
        world = _World(
            [_line(1, OrderItemStatus.PARTIALLY_DELIVERED, delivered=6.0)],
            allocations=[make_allocation(demand_item_id=1, order_item_id=1, quantity=4.0)],
            demands=[bought],
            source_allocations=[make_source_item_allocation(demand_item_id=2, quantity=2.0)],
            source_demands=[source],
        )

        await world.close_short().execute(MANAGER, 1, 1)

        assert await world.bought_on(1) == {1: 4.0}
        assert bought.status == "fulfilled"
        assert bought.changes[-1].endswith("Status: ordered → fulfilled (closed short).")
        assert source.status == "fulfilled"

    async def test_closing_a_line_of_a_canceled_order_does_not_revive_the_order(self) -> None:
        # An order canceled before its partially delivered lines were
        # closed short along with it.
        order = give_order_facts(make_order(id=1, status=OrderStatus.CANCELED))
        world = _World([_line(1, OrderItemStatus.PARTIALLY_DELIVERED, delivered=6.0)], order=order)

        result = await world.close_short().execute(MANAGER, 1, 1)

        assert result.status == "delivered"
        assert (order.status, order.changes) == ("canceled", [])

    async def test_a_line_that_received_nothing_is_canceled_instead(self) -> None:
        world = _World([_line(1, OrderItemStatus.ORDERED)])

        with pytest.raises(OrderItemCannotBeClosedShortError, match="cancel it instead"):
            await world.close_short().execute(MANAGER, 1, 1)

        assert world.uow.committed is False

    @pytest.mark.parametrize(
        ("status", "delivered"),
        [
            (OrderItemStatus.PENDING, 0.0),
            (OrderItemStatus.DELIVERED, 10.0),
            (OrderItemStatus.CANCELED, 0.0),
        ],
    )
    async def test_a_line_neither_ordered_nor_partially_delivered_is_refused(
        self, status: OrderItemStatus, delivered: float
    ) -> None:
        world = _World([_line(1, status, delivered=delivered)])

        with pytest.raises(
            OrderItemCannotBeClosedShortError, match=f"has status '{status.value}' and cannot be"
        ):
            await world.close_short().execute(MANAGER, 1, 1)

        assert (await world.line(1)).quantity == 10.0

    async def test_the_permission_is_checked_before_the_state(self) -> None:
        world = _World([_line(1, OrderItemStatus.ORDERED)])

        with pytest.raises(InsufficientPermissionsError):
            await world.close_short().execute(STRANGER, 1, 1)

    async def test_a_made_line_is_closed_after_its_lot_is_locked(self) -> None:
        world = _World(
            [_made(_line(1, OrderItemStatus.PARTIALLY_DELIVERED, delivered=3.0), lot_id=9)]
        )

        await world.close_short().execute(MANAGER, 1, 1)

        assert ((await world.line(1)).status, (await world.line(1)).quantity) == (
            "delivered",
            3.0,
        )
        assert world.harness.lock_log == [
            (_A.LOTS, (9,)),
            (_A.ORDERS, (1,)),
            (_A.ORDER_ITEMS, (1,)),
        ]


class TestCancelOrder:
    async def test_lines_that_received_pieces_are_closed_short_and_the_others_canceled(
        self,
    ) -> None:
        demands = [make_demand(id=i, status=BoughtItemDemandStatus.ORDERED) for i in (1, 2, 3)]
        world = _World(
            [
                _line(1, OrderItemStatus.ORDERED),
                _line(2, OrderItemStatus.PARTIALLY_DELIVERED, delivered=4.0),
                _line(3, OrderItemStatus.DELIVERED, delivered=10.0),
                _line(4, OrderItemStatus.PENDING),
            ],
            order=give_order_facts(make_order(id=1, status=OrderStatus.PARTIALLY_DELIVERED)),
            allocations=[
                make_allocation(demand_item_id=1, order_item_id=1),
                make_allocation(demand_item_id=2, order_item_id=2),
                make_allocation(demand_item_id=3, order_item_id=3),
            ],
            demands=demands,
        )

        result = await world.cancel_order().execute(MANAGER, 1)

        assert result.status == "canceled"
        lines = {line.id: line for line in await world.lines.get_by_order_id(1)}
        assert {i: (lines[i].status, lines[i].quantity) for i in lines} == {
            1: ("canceled", 10.0),
            2: ("delivered", 4.0),
            3: ("delivered", 10.0),
            4: ("canceled", 10.0),
        }
        assert lines[2].canceled_at is None
        assert (
            lines[2]
            .changes[-2]
            .endswith("Closed short at 4.000 of 10.000 pcs: order #1 was canceled.")
        )
        assert lines[3].changes == []
        assert await world.bought_on(1) == {}
        assert await world.bought_on(2) == {2: 4.0}
        assert await world.bought_on(3) == {3: 10.0}
        # The closed line covers 4 of its demand's 10 now, which leaves that
        # demand allocated; the delivered line's demand is not touched.
        assert [d.status for d in demands] == ["open", "allocated", "ordered"]
        assert world.uow.committed is True

    async def test_the_lots_of_made_lines_are_locked_before_the_order_and_its_lines(
        self,
    ) -> None:
        world = _World(
            [
                _made(_line(1, OrderItemStatus.PARTIALLY_DELIVERED, delivered=2.0), lot_id=9),
                _line(2, OrderItemStatus.ORDERED),
                _line(3, OrderItemStatus.DELIVERED, delivered=10.0),
            ],
            order=give_order_facts(make_order(id=1, status=OrderStatus.PARTIALLY_DELIVERED)),
        )

        await world.cancel_order().execute(MANAGER, 1)

        assert world.harness.lock_log == [
            (_A.LOTS, (9,)),
            (_A.ORDERS, (1,)),
            (_A.ORDER_ITEMS, (1, 2)),
        ]
