"""
Unit tests for the source-status guards of the order item marks and for what
marking a MADE line ordered does to its lot. A line is marked requested only
from PENDING and ordered only from PENDING or REQUESTED, and marking it
ordered stamps its ordered_date. The lifecycle reconciler then derives the
lot and its positions from their facts, so a held or terminal lot keeps its
status, a canceled position stays canceled, and a position with production
orders keeps the status its running orders give it.

Repository fakes and builders come from tests/unit/order/_helpers.py,
the unit of work from tests/unit/fakes.py.
"""

from collections.abc import Sequence
from datetime import UTC
from datetime import datetime

import pytest

from src.modules.fulfillment.application.use_cases.order.mark_order_item_ordered import (
    MarkAllOrderItemsOrdered,
)
from src.modules.fulfillment.application.use_cases.order.mark_order_item_ordered import (
    MarkOrderItemOrdered,
)
from src.modules.fulfillment.application.use_cases.order.mark_order_item_ordered import (
    MarkOrderItemRequested,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.errors import OrderItemCannotBeMarkedError
from src.modules.fulfillment.domain.services.order_item_mark_rules import (
    assert_mark_ordered_allowed,
)
from src.modules.fulfillment.domain.services.order_item_mark_rules import (
    assert_mark_requested_allowed,
)
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.order._helpers import FakeOrderItemRepository
from tests.unit.order._helpers import FakeOrderRepository
from tests.unit.order._helpers import FakeProductionLotRepository
from tests.unit.order._helpers import lot_aware_reconciler
from tests.unit.order._helpers import make_order
from tests.unit.order._helpers import make_order_item
from tests.unit.order._helpers import make_production_order
from tests.unit.production_order._helpers import give_status_facts

_STATUSES = list(OrderItemStatus)
_CREATED = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
def manager() -> User:
    """manage:orders lets a mark reach an order past REQUESTED, so a refusal
    in these tests can only come from the line's own status."""
    return make_user(permissions=[Permission.WRITE_ORDERS, Permission.MANAGE_ORDERS])


def _made_line(status: OrderItemStatus = OrderItemStatus.PENDING) -> OrderItem:
    """Line #1 of order #1, the external assignment of position #1."""
    line = make_order_item(id=1, order_id=1, status=status)
    line.line_type = OrderLineType.MADE
    line.bought_item_id = None
    line.lot_position_id = 1
    line.quantity = 5.0
    return line


def _lot(status: LotStatus) -> ProductionLot:
    """Lot #1 with the facts its status stands for: a held lot its hold, a
    completed one its force-completion and completion time, a canceled one
    its cancel and a scrapped one nothing left to produce."""
    lot = ProductionLot(
        id=1,
        created=_CREATED,
        changed=None,
        changes=[],
        lot_number="LOT-1",
        quantity=0.0 if status == "scrapped" else 10.0,
        status=status,
        priority=UrgencyClass.NORMAL,
        note=None,
        creator_id=1,
        made_item_id=1,
        project_id=1,
        input_demand_id=None,
    )
    if status == "on_hold":
        lot.held_at = _CREATED
    elif status == "completed":
        lot.force_completed_at = lot.completed_at = _CREATED
    elif status == "canceled":
        lot.canceled_at = _CREATED
    return lot


def _position(
    kind: LotPositionKind,
    status: LotPositionStatus,
    *,
    quantity_completed: float = 0.0,
    production_orders: Sequence[ProductionOrder] = (),
) -> LotPosition:
    """The only position (#1) of lot #1."""
    position = LotPosition(
        id=1,
        created=_CREATED,
        changed=None,
        changes=[],
        sequence=1,
        kind=kind,
        status=status,
        quantity=10.0,
        quantity_completed=quantity_completed,
        note=None,
        creator_id=1,
        lot_id=1,
    )
    # The lot repository fills this for internal and mixed positions.
    position.production_orders = list(production_orders)
    return position


class _World:
    """Order #1 with the given lines and, optionally, lot #1 with one
    position, behind the fakes the mark use cases read and write."""

    def __init__(
        self,
        lines: list[OrderItem],
        *,
        order_status: OrderStatus = OrderStatus.DRAFT,
        lot: ProductionLot | None = None,
        position: LotPosition | None = None,
    ) -> None:
        self.orders = FakeOrderRepository([make_order(id=1, status=order_status)])
        self.lines = FakeOrderItemRepository(lines)
        self.lots = FakeProductionLotRepository(
            lots=[lot] if lot else [], positions=[position] if position else []
        )
        self.uow = FakeUnitOfWork()

    def mark_ordered(self) -> MarkOrderItemOrdered:
        return MarkOrderItemOrdered(
            order_item_repo=self.lines,
            order_repo=self.orders,
            uow=self.uow,
            reconciler=lot_aware_reconciler(self.orders, self.lines, self.lots),
        )

    def mark_all_ordered(self) -> MarkAllOrderItemsOrdered:
        return MarkAllOrderItemsOrdered(
            order_item_repo=self.lines,
            order_repo=self.orders,
            uow=self.uow,
            reconciler=lot_aware_reconciler(self.orders, self.lines, self.lots),
        )

    def mark_requested(self) -> MarkOrderItemRequested:
        return MarkOrderItemRequested(
            order_item_repo=self.lines,
            order_repo=self.orders,
            uow=self.uow,
            reconciler=lot_aware_reconciler(self.orders, self.lines, self.lots),
        )


# ── The rules ─────────────────────────────────────────────────────────


class TestMarkRules:
    @pytest.mark.parametrize("status", [s for s in _STATUSES if s != OrderItemStatus.PENDING])
    def test_mark_requested_rule_refuses_every_status_but_pending(
        self, status: OrderItemStatus
    ) -> None:
        line = make_order_item(id=7, status=status)

        with pytest.raises(
            OrderItemCannotBeMarkedError,
            match=f"#7 is {status.value} and cannot be marked as requested",
        ):
            assert_mark_requested_allowed(line)

    def test_mark_requested_rule_accepts_a_pending_line(self) -> None:
        # The rule returns None, so passing means it did not raise.
        assert_mark_requested_allowed(make_order_item(status=OrderItemStatus.PENDING))

    @pytest.mark.parametrize(
        "status",
        [s for s in _STATUSES if s not in (OrderItemStatus.PENDING, OrderItemStatus.REQUESTED)],
    )
    def test_mark_ordered_rule_refuses_every_status_but_pending_and_requested(
        self, status: OrderItemStatus
    ) -> None:
        line = make_order_item(id=7, status=status)

        with pytest.raises(
            OrderItemCannotBeMarkedError,
            match=f"#7 is {status.value} and cannot be marked as ordered",
        ):
            assert_mark_ordered_allowed(line)

    @pytest.mark.parametrize("status", [OrderItemStatus.PENDING, OrderItemStatus.REQUESTED])
    def test_mark_ordered_rule_accepts_a_pending_or_requested_line(
        self, status: OrderItemStatus
    ) -> None:
        # The rule returns None, so passing means it did not raise.
        assert_mark_ordered_allowed(make_order_item(status=status))


# ── Single-line marks ─────────────────────────────────────────────────


class TestMarkOrderedGuard:
    @pytest.mark.parametrize(
        "status",
        [
            OrderItemStatus.ORDERED,
            OrderItemStatus.PARTIALLY_DELIVERED,
            OrderItemStatus.DELIVERED,
            OrderItemStatus.CANCELED,
        ],
    )
    async def test_mark_ordered_refuses_a_line_past_requested_and_changes_nothing(
        self, status: OrderItemStatus, manager: User
    ) -> None:
        world = _World(
            [make_order_item(id=1, order_id=1, status=status)], order_status=OrderStatus.ORDERED
        )

        with pytest.raises(OrderItemCannotBeMarkedError):
            await world.mark_ordered().execute(actor=manager, order_id=1, order_item_id=1)

        line = await world.lines.get_by_id(1)
        assert line is not None
        assert (line.status, line.ordered_date, line.changes) == (status, None, [])
        assert not world.uow.committed

    async def test_mark_ordered_refuses_a_canceled_made_line_and_leaves_its_position_and_lot(
        self, manager: User
    ) -> None:
        """Canceling an order cancels its MADE line but leaves the position
        assigned. Marking that line ordered must neither revive it nor plan
        the lot."""
        world = _World(
            [_made_line(status=OrderItemStatus.CANCELED)],
            order_status=OrderStatus.CANCELED,
            lot=_lot(LotStatus.DRAFT),
            position=_position(LotPositionKind.EXTERNAL, LotPositionStatus.PENDING),
        )

        with pytest.raises(OrderItemCannotBeMarkedError):
            await world.mark_ordered().execute(actor=manager, order_id=1, order_item_id=1)

        line = await world.lines.get_by_id(1)
        assert line is not None and line.status == "canceled"
        position = await world.lots.get_position_by_id(1)
        assert (position.status, position.changes) == ("pending", [])
        lot = await world.lots.get_by_id(1)
        assert (lot.status, lot.changes) == ("draft", [])

    @pytest.mark.parametrize("status", [OrderItemStatus.PENDING, OrderItemStatus.REQUESTED])
    async def test_mark_ordered_accepts_a_pending_or_requested_line_and_stamps_its_ordered_date(
        self, status: OrderItemStatus, manager: User
    ) -> None:
        world = _World([make_order_item(id=1, order_id=1, status=status)])

        result = await world.mark_ordered().execute(actor=manager, order_id=1, order_item_id=1)

        line = await world.lines.get_by_id(1)
        assert line is not None and line.status == "ordered"
        assert line.ordered_date is not None and line.ordered_date.tzinfo is not None
        assert line.ordered_date == line.changed
        assert result.ordered_date == line.ordered_date
        assert world.uow.committed


class TestMarkRequestedGuard:
    @pytest.mark.parametrize(
        "status",
        [
            OrderItemStatus.REQUESTED,
            OrderItemStatus.ORDERED,
            OrderItemStatus.PARTIALLY_DELIVERED,
            OrderItemStatus.DELIVERED,
            OrderItemStatus.CANCELED,
        ],
    )
    async def test_mark_requested_refuses_a_line_that_is_not_pending_and_changes_nothing(
        self, status: OrderItemStatus, manager: User
    ) -> None:
        world = _World(
            [make_order_item(id=1, order_id=1, status=status)], order_status=OrderStatus.ORDERED
        )

        with pytest.raises(OrderItemCannotBeMarkedError):
            await world.mark_requested().execute(actor=manager, order_id=1, order_item_id=1)

        line = await world.lines.get_by_id(1)
        assert line is not None
        assert (line.status, line.changes) == (status, [])
        assert not world.uow.committed


# ── Bulk mark ─────────────────────────────────────────────────────────


class TestBulkMarkOrdered:
    async def test_bulk_mark_ordered_stamps_the_lines_it_marks_and_leaves_skipped_lines_alone(
        self, manager: User
    ) -> None:
        earlier = datetime(2026, 1, 2, tzinfo=UTC)
        delivered = make_order_item(id=3, order_id=1, status=OrderItemStatus.DELIVERED)
        delivered.ordered_date = earlier
        world = _World(
            [
                make_order_item(id=1, order_id=1, status=OrderItemStatus.PENDING),
                make_order_item(id=2, order_id=1, status=OrderItemStatus.REQUESTED),
                delivered,
            ],
            order_status=OrderStatus.REQUESTED,
        )

        results = await world.mark_all_ordered().execute(actor=manager, order_id=1)

        assert sorted(r.id for r in results) == [1, 2]
        for line_id in (1, 2):
            line = await world.lines.get_by_id(line_id)
            assert line is not None and line.status == "ordered"
            assert line.ordered_date is not None and line.ordered_date == line.changed
        skipped = await world.lines.get_by_id(3)
        assert skipped is not None
        assert (skipped.status, skipped.ordered_date) == ("delivered", earlier)


# ── The lot of a MADE line ────────────────────────────────────────────


class TestLotProtection:
    @pytest.mark.parametrize(
        "lot_status", [LotStatus.ON_HOLD, LotStatus.COMPLETED, LotStatus.SCRAPPED]
    )
    async def test_mark_ordered_records_the_order_on_the_position_but_keeps_the_lot_status(
        self, lot_status: LotStatus, manager: User
    ) -> None:
        """A held lot stays held until it is resumed, and a terminal lot never
        moves back to an active status."""
        world = _World(
            [_made_line()],
            lot=_lot(lot_status),
            position=_position(LotPositionKind.EXTERNAL, LotPositionStatus.PENDING),
        )

        await world.mark_ordered().execute(actor=manager, order_id=1, order_item_id=1)

        assert (await world.lots.get_position_by_id(1)).status == "ordered_or_queued"
        lot = await world.lots.get_by_id(1)
        recorded = _CREATED if lot_status == "completed" else None
        assert (lot.status, lot.changes, lot.completed_at) == (lot_status, [], recorded)

    async def test_bulk_mark_ordered_keeps_a_held_lot_on_hold(self, manager: User) -> None:
        world = _World(
            [_made_line()],
            lot=_lot(LotStatus.ON_HOLD),
            position=_position(LotPositionKind.EXTERNAL, LotPositionStatus.PENDING),
        )

        await world.mark_all_ordered().execute(actor=manager, order_id=1)

        assert (await world.lots.get_position_by_id(1)).status == "ordered_or_queued"
        lot = await world.lots.get_by_id(1)
        assert (lot.status, lot.changes) == ("on_hold", [])

    async def test_mark_ordered_leaves_a_canceled_lot_and_its_canceled_position_alone(
        self, manager: User
    ) -> None:
        """The lot cancel cascade cancels every pending line, so a pending line
        under a canceled lot exists only in drifted data. The line itself may
        still be marked; the lot and its position keep CANCELED."""
        world = _World(
            [_made_line()],
            lot=_lot(LotStatus.CANCELED),
            position=_position(LotPositionKind.EXTERNAL, LotPositionStatus.CANCELED),
        )

        await world.mark_ordered().execute(actor=manager, order_id=1, order_item_id=1)

        line = await world.lines.get_by_id(1)
        assert line is not None and line.status == "ordered"
        position = await world.lots.get_position_by_id(1)
        assert (position.status, position.changes) == ("canceled", [])
        lot = await world.lots.get_by_id(1)
        assert (lot.status, lot.changes) == ("canceled", [])

    async def test_mark_ordered_stamps_completed_at_when_the_lot_derives_completed(
        self, manager: User
    ) -> None:
        """Only a position whose stored progress already covers its quantity
        can complete the lot here. The lot then gets its completion time, as
        in every other recompute."""
        finished = make_production_order(
            id=1, lot_position_id=1, status=ProductionOrderStatus.COMPLETED
        )
        finished.quantity = finished.quantity_completed = 10.0
        give_status_facts(finished)
        world = _World(
            [_made_line()],
            lot=_lot(LotStatus.IN_PROGRESS),
            position=_position(
                LotPositionKind.MIXED,
                LotPositionStatus.COMPLETED,
                quantity_completed=10.0,
                production_orders=[finished],
            ),
        )

        await world.mark_ordered().execute(actor=manager, order_id=1, order_item_id=1)

        line = await world.lines.get_by_id(1)
        assert line is not None
        lot = await world.lots.get_by_id(1)
        assert lot.status == "completed"
        assert lot.completed_at is not None and lot.completed_at == line.ordered_date


class TestMixedPosition:
    @pytest.mark.parametrize(
        "production_order_status", [ProductionOrderStatus.IN_PROGRESS, ProductionOrderStatus.PAUSED]
    )
    async def test_mark_ordered_keeps_a_running_mixed_position_and_its_lot_in_progress(
        self, production_order_status: ProductionOrderStatus, manager: User
    ) -> None:
        """The in-house side of a mixed position is running, so marking its
        external line ordered must not drop the position to ORDERED_OR_QUEUED
        or the lot to PLANNED."""
        running = give_status_facts(
            make_production_order(id=1, lot_position_id=1, status=production_order_status)
        )
        world = _World(
            [_made_line()],
            lot=_lot(LotStatus.IN_PROGRESS),
            position=_position(
                LotPositionKind.MIXED, LotPositionStatus.IN_PROGRESS, production_orders=[running]
            ),
        )

        await world.mark_ordered().execute(actor=manager, order_id=1, order_item_id=1)

        assert (await world.lots.get_position_by_id(1)).status == "in_progress"
        lot = await world.lots.get_by_id(1)
        assert (lot.status, lot.changes) == ("in_progress", [])
