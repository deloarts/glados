"""
Which order lines take a delivery. OrderRules.can_deliver and
assert_can_deliver accept only ordered or partially delivered lines of an
order that is not canceled, and for a MADE line only while its lot is not
canceled; assert_valid_delivery refuses quantities that are not finite.
ProcessOrderItemDelivery enforces the rule, DeliverAllOrderItems filters
with it, and the order's derived status ignores canceled lines. Fakes and
builders come from test_bought_item_delivery.py and the production lot
fakes rather than being redefined.
"""

import copy
import math
from datetime import date

import pytest

from src.modules.fulfillment.application.use_cases.order.process_order_item_delivery import (
    DeliverAllOrderItems,
)
from src.modules.fulfillment.application.use_cases.order.process_order_item_delivery import (
    ProcessOrderItemDelivery,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.errors import InvalidDeliveryQuantityError
from src.modules.fulfillment.domain.errors import OrderItemNotDeliverableError
from src.modules.fulfillment.domain.services.order_rules import OrderRules
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from tests.unit.lifecycle.fake_reconciler import give_order_facts
from tests.unit.lifecycle.fake_reconciler import give_order_item_facts
from tests.unit.lifecycle.fake_reconciler import order_reconciler
from tests.unit.production_lot._helpers import NoLotCreation
from tests.unit.production_lot.fakes import FakeMadeItemAllocationRepository
from tests.unit.production_lot.fakes import FakeMadeItemDemandRepository
from tests.unit.production_lot.fakes import FakeProductionLotRepository
from tests.unit.production_lot.fakes import delivery_collaborators
from tests.unit.production_order.fakes import FakeProductionOrderRepository
from tests.unit.production_order.fakes import production_order_reconciler
from tests.unit.test_bought_item_delivery import FakeDeliveryRepository
from tests.unit.test_bought_item_delivery import FakeEventBus
from tests.unit.test_bought_item_delivery import FakeOrderItemRepository
from tests.unit.test_bought_item_delivery import FakeOrderRepository
from tests.unit.test_bought_item_delivery import FakeUnitOfWork
from tests.unit.test_bought_item_delivery import make_order
from tests.unit.test_bought_item_delivery import make_order_item
from tests.unit.test_bought_item_delivery import make_user

ORDERED = OrderItemStatus.ORDERED
PARTIALLY_DELIVERED = OrderItemStatus.PARTIALLY_DELIVERED
_NOT_ORDERED_YET = {OrderItemStatus.PENDING, OrderItemStatus.REQUESTED}
ALL_LINE_STATUSES = list(OrderItemStatus)
DELIVERABLE_LINE_STATUSES = {ORDERED, PARTIALLY_DELIVERED}
NOT_DELIVERABLE_LINE_STATUSES = [
    status for status in ALL_LINE_STATUSES if status not in DELIVERABLE_LINE_STATUSES
]
NON_FINITE = [math.nan, math.inf, -math.inf]

# Quantity already delivered per line status, so every line is consistent
# with its status (lines have quantity 10).
_DELIVERED_FOR_STATUS = {
    OrderItemStatus.PARTIALLY_DELIVERED: 4.0,
    OrderItemStatus.DELIVERED: 10.0,
}


def make_line(id: int, status: OrderItemStatus) -> OrderItem:
    """A line of order #1 with the facts its status derives from."""
    line = make_order_item(
        id=id,
        order_id=1,
        quantity=10.0,
        quantity_delivered=_DELIVERED_FOR_STATUS.get(status, 0.0),
        status=status,
    )
    if status in _NOT_ORDERED_YET:
        # The shared builder stamps an ordered_date on every line.
        line.ordered_date = None
    return give_order_item_facts(line)


class Harness:
    """One order with the given lines, the delivery use case over it and
    deliver-all composed on top, all on in-memory fakes."""

    def __init__(
        self,
        lines: list[OrderItem],
        order_status: OrderStatus = OrderStatus.ORDERED,
        lot_repo: FakeProductionLotRepository | None = None,
    ) -> None:
        self.order = give_order_facts(make_order(id=1, status=order_status))
        self.order_items = FakeOrderItemRepository(lines)
        self.orders = FakeOrderRepository([self.order])
        self.deliveries = FakeDeliveryRepository()
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        # With a lot, the reconciler also derives the lot and its positions
        # from the line, as the app's does.
        reconciler = (
            order_reconciler(self.orders, self.order_items)
            if lot_repo is None
            else production_order_reconciler(
                FakeProductionOrderRepository(),
                lot_repo,
                self.bus,
                orders=self.orders,
                order_items=self.order_items,
            )
        )
        self.deliver = ProcessOrderItemDelivery(
            order_item_repo=self.order_items,
            order_repo=self.orders,
            delivery_repo=self.deliveries,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=reconciler,
            made_item_demand_repo=FakeMadeItemDemandRepository(),
            made_item_allocation_repo=FakeMadeItemAllocationRepository(),
            create_lot=NoLotCreation(),
            **delivery_collaborators(lot_repo=lot_repo),
        )
        self.deliver_all = DeliverAllOrderItems(
            order_repo=self.orders,
            order_item_repo=self.order_items,
            delivery_use_case=self.deliver,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=reconciler,
        )

    async def assert_nothing_booked(self, line: OrderItem, status: str, delivered: float) -> None:
        assert line.status == status
        assert line.quantity_delivered == delivered
        assert await self.deliveries.get_by_order_item_id(line.id) == []
        assert self.bus.published == []
        assert self.uow.committed is False


async def lot_with_external_position(
    lot_status: LotStatus, position_status: LotPositionStatus, quantity_completed: float
) -> FakeProductionLotRepository:
    """A lot of 5 pieces whose single EXTERNAL position is supplied by a
    MADE line (see made_line)."""
    lot_repo = FakeProductionLotRepository()
    lot = await lot_repo.save(
        ProductionLot(
            id=0,
            created=date(2026, 1, 1),
            changed=None,
            changes=[],
            lot_number="LOT-1",
            quantity=5.0,
            status=lot_status,
            priority=UrgencyClass.NORMAL,
            note=None,
            creator_id=1,
            made_item_id=1,
            project_id=1,
            input_demand_id=None,
        )
    )
    await lot_repo.save_position(
        LotPosition(
            id=0,
            created=date(2026, 1, 1),
            changed=None,
            changes=[],
            sequence=1,
            kind=LotPositionKind.EXTERNAL,
            status=position_status,
            quantity=5.0,
            quantity_completed=quantity_completed,
            note=None,
            creator_id=1,
            lot_id=lot.id,
        )
    )
    return lot_repo


def made_line(id: int = 1, quantity_delivered: float = 2.0) -> OrderItem:
    """A partially delivered MADE line of 5 pieces on lot position 1."""
    line = make_order_item(
        id=id,
        order_id=1,
        quantity=5.0,
        quantity_delivered=quantity_delivered,
        status=PARTIALLY_DELIVERED,
    )
    line.line_type = OrderLineType.MADE
    line.bought_item_id = None
    line.lot_position_id = 1
    return line


# ── OrderRules.can_deliver / assert_can_deliver ─────────────────────────


class TestCanDeliverRule:
    @pytest.mark.parametrize("line_status", ALL_LINE_STATUSES)
    def test_can_deliver_accepts_only_ordered_or_partially_delivered_lines(
        self, line_status: OrderItemStatus
    ) -> None:
        order = make_order(status=OrderStatus.ORDERED)
        line = make_line(1, line_status)

        assert OrderRules.can_deliver(order, line) is (line_status in DELIVERABLE_LINE_STATUSES)

    @pytest.mark.parametrize("line_status", NOT_DELIVERABLE_LINE_STATUSES)
    def test_assert_can_deliver_names_the_line_status(self, line_status: OrderItemStatus) -> None:
        with pytest.raises(OrderItemNotDeliverableError, match=f"status '{line_status.value}'"):
            OrderRules.assert_can_deliver(make_order(), make_line(1, line_status))

    @pytest.mark.parametrize("line_status", ALL_LINE_STATUSES)
    def test_can_deliver_refuses_every_line_of_a_canceled_order(
        self, line_status: OrderItemStatus
    ) -> None:
        order = make_order(status=OrderStatus.CANCELED)
        line = make_line(1, line_status)

        assert OrderRules.can_deliver(order, line) is False
        with pytest.raises(OrderItemNotDeliverableError, match="is canceled"):
            OrderRules.assert_can_deliver(order, line)

    def test_can_deliver_refuses_a_line_whose_lot_is_canceled(self) -> None:
        order = make_order()
        line = made_line()

        assert OrderRules.can_deliver(order, line, LotStatus.CANCELED.value) is False
        with pytest.raises(OrderItemNotDeliverableError, match="canceled production lot"):
            OrderRules.assert_can_deliver(order, line, LotStatus.CANCELED.value)

    def test_can_deliver_accepts_a_line_whose_lot_is_live(self) -> None:
        order = make_order()
        line = made_line()

        assert OrderRules.can_deliver(order, line, LotStatus.IN_PROGRESS.value) is True
        OrderRules.assert_can_deliver(order, line, LotStatus.IN_PROGRESS.value)


# ── OrderRules.assert_valid_delivery, finite quantities ─────────────────


class TestFiniteDeliveryQuantities:
    @pytest.mark.parametrize("value", NON_FINITE)
    def test_assert_valid_delivery_refuses_a_non_finite_delivered_quantity(
        self, value: float
    ) -> None:
        with pytest.raises(
            InvalidDeliveryQuantityError,
            match="delivered quantity of order item #1 must be a finite number",
        ):
            OrderRules.assert_valid_delivery(make_line(1, ORDERED), value, 0.0, 10.0, None, None)

    @pytest.mark.parametrize("value", NON_FINITE)
    def test_assert_valid_delivery_refuses_a_non_finite_rejected_quantity(
        self, value: float
    ) -> None:
        with pytest.raises(
            InvalidDeliveryQuantityError,
            match="rejected quantity of order item #1 must be a finite number",
        ):
            OrderRules.assert_valid_delivery(
                make_line(1, ORDERED), 1.0, value, 10.0, "supplier_damage", "redeliver"
            )

    @pytest.mark.parametrize("value", NON_FINITE)
    def test_assert_valid_delivery_refuses_a_line_without_a_finite_open_quantity(
        self, value: float
    ) -> None:
        with pytest.raises(
            InvalidDeliveryQuantityError,
            match="open quantity of order item #1 must be a finite number",
        ):
            OrderRules.assert_valid_delivery(make_line(1, ORDERED), 1.0, 0.0, value, None, None)


# ── ProcessOrderItemDelivery ─────────────────────────────────────────────


class TestDeliveryRefusesLinesThatCannotTakeOne:
    @pytest.mark.parametrize("line_status", NOT_DELIVERABLE_LINE_STATUSES)
    async def test_delivery_refuses_a_line_that_is_not_ordered_or_partially_delivered(
        self, line_status: OrderItemStatus
    ) -> None:
        line = make_line(1, line_status)
        delivered_before = line.quantity_delivered
        harness = Harness([line])

        with pytest.raises(OrderItemNotDeliverableError, match=f"status '{line_status.value}'"):
            await harness.deliver.execute(actor=make_user(), order_item_id=1, quantity=1.0)

        await harness.assert_nothing_booked(line, line_status, delivered_before)

    @pytest.mark.parametrize("line_status", sorted(DELIVERABLE_LINE_STATUSES))
    async def test_delivery_refuses_a_line_of_a_canceled_order(
        self, line_status: OrderItemStatus
    ) -> None:
        line = make_line(1, line_status)
        delivered_before = line.quantity_delivered
        harness = Harness([line], order_status=OrderStatus.CANCELED)

        with pytest.raises(OrderItemNotDeliverableError, match="is canceled"):
            await harness.deliver.execute(actor=make_user(), order_item_id=1, quantity=1.0)

        await harness.assert_nothing_booked(line, line_status, delivered_before)
        assert harness.order.status == OrderStatus.CANCELED.value

    async def test_delivery_checks_the_permission_before_the_line_status(self) -> None:
        harness = Harness([make_line(1, OrderItemStatus.CANCELED)])

        with pytest.raises(InsufficientPermissionsError):
            await harness.deliver.execute(
                actor=make_user(permissions=[]), order_item_id=1, quantity=1.0
            )

    @pytest.mark.parametrize("value", NON_FINITE)
    async def test_delivery_refuses_a_non_finite_quantity_and_books_nothing(
        self, value: float
    ) -> None:
        line = make_line(1, ORDERED)
        harness = Harness([line])

        with pytest.raises(InvalidDeliveryQuantityError):
            await harness.deliver.execute(actor=make_user(), order_item_id=1, quantity=value)

        await harness.assert_nothing_booked(line, ORDERED, 0.0)

    async def test_delivery_refuses_a_made_line_whose_lot_is_canceled(self) -> None:
        lot_repo = await lot_with_external_position(
            LotStatus.CANCELED, LotPositionStatus.CANCELED, quantity_completed=2.0
        )
        line = made_line(quantity_delivered=2.0)
        harness = Harness([line], lot_repo=lot_repo)

        with pytest.raises(OrderItemNotDeliverableError, match="canceled production lot"):
            await harness.deliver.execute(actor=make_user(), order_item_id=1, quantity=1.0)

        await harness.assert_nothing_booked(line, PARTIALLY_DELIVERED, 2.0)
        position = await lot_repo.get_position_by_id(1)
        assert position is not None
        assert position.status == LotPositionStatus.CANCELED.value
        assert position.quantity_completed == 2.0

    async def test_delivery_on_a_made_line_of_a_live_lot_goes_through(self) -> None:
        lot_repo = await lot_with_external_position(
            LotStatus.IN_PROGRESS,
            LotPositionStatus.PARTIALLY_COMPLETED,
            quantity_completed=2.0,
        )
        harness = Harness([made_line(quantity_delivered=2.0)], lot_repo=lot_repo)

        result = await harness.deliver.execute(actor=make_user(), order_item_id=1, quantity=1.0)

        assert result.quantity_delivered == 3.0
        position = await lot_repo.get_position_by_id(1)
        assert position is not None
        assert position.quantity_completed == 3.0
        assert harness.uow.committed is True


# ── DeliverAllOrderItems ─────────────────────────────────────────────────


class TestDeliverAllSkipsLinesThatCannotTakeADelivery:
    async def test_deliver_all_delivers_only_ordered_and_partially_delivered_lines(self) -> None:
        lines = [make_line(id, status) for id, status in enumerate(ALL_LINE_STATUSES, start=1)]
        before = {line.id: (line.status, line.quantity_delivered) for line in lines}
        harness = Harness(lines)

        result = await harness.deliver_all.execute(actor=make_user(), order_id=1)

        delivered_ids = sorted(line.id for line in result.delivered)
        assert delivered_ids == sorted(
            line.id for line in lines if before[line.id][0] in DELIVERABLE_LINE_STATUSES
        )
        assert sorted(s.order_item_id for s in result.skipped) == sorted(
            line.id for line in lines if line.id not in delivered_ids
        )
        for line in lines:
            if line.id in delivered_ids:
                assert line.status == OrderItemStatus.DELIVERED.value
                assert line.quantity_delivered == 10.0
            else:
                assert (line.status, line.quantity_delivered) == before[line.id]

    async def test_deliver_all_on_a_canceled_order_books_nothing(self) -> None:
        # Every line is skipped by the single delivery rule, which refuses a
        # canceled order, and nothing is committed.
        lines = [make_line(1, ORDERED), make_line(2, PARTIALLY_DELIVERED)]
        harness = Harness(lines, order_status=OrderStatus.CANCELED)

        result = await harness.deliver_all.execute(actor=make_user(), order_id=1)

        assert result.delivered == []
        assert [(s.order_item_id, s.reason) for s in result.skipped] == [
            (1, "order_canceled"),
            (2, "order_canceled"),
        ]
        assert [line.quantity_delivered for line in lines] == [0.0, 4.0]
        assert await harness.deliveries.get_by_order_item_id(1) == []
        assert harness.uow.committed is False
        assert harness.order.status == OrderStatus.CANCELED.value

    async def test_deliver_all_skips_a_made_line_whose_lot_is_canceled(self) -> None:
        lot_repo = await lot_with_external_position(
            LotStatus.CANCELED, LotPositionStatus.CANCELED, quantity_completed=2.0
        )
        made = made_line(id=1, quantity_delivered=2.0)
        bought = make_line(2, ORDERED)
        harness = Harness([made, bought], lot_repo=lot_repo)

        result = await harness.deliver_all.execute(actor=make_user(), order_id=1)

        assert [line.id for line in result.delivered] == [2]
        assert [(s.order_item_id, s.reason) for s in result.skipped] == [(1, "lot_canceled")]
        assert made.quantity_delivered == 2.0
        assert bought.status == OrderItemStatus.DELIVERED.value

    async def test_deliver_all_books_made_lines_on_consecutive_positions_of_one_lot(
        self,
    ) -> None:
        """Position 2 takes its input from what position 1 receives in the
        same deliver-all, before the reconciler stores either count."""
        lot_repo = await lot_with_external_position(
            LotStatus.PLANNED, LotPositionStatus.ORDERED_OR_QUEUED, 0.0
        )
        [first] = await lot_repo.get_positions(1)
        second = copy.copy(first)
        second.id, second.sequence = 0, 2
        second = await lot_repo.save_position(second)
        lines = [made_line(id=1, quantity_delivered=0.0), made_line(id=2, quantity_delivered=0.0)]
        lines[1].lot_position_id = second.id
        for line in lines:
            line.status = ORDERED
            # As the repository fills it from the position.
            line.lot_id = 1
        harness = Harness(lines, lot_repo=lot_repo)

        result = await harness.deliver_all.execute(actor=make_user(), order_id=1)

        assert sorted(line.id for line in result.delivered) == [1, 2]
        positions = await lot_repo.get_positions(1)
        assert [(p.quantity_completed, p.status) for p in positions] == [
            (5.0, LotPositionStatus.COMPLETED.value),
            (5.0, LotPositionStatus.COMPLETED.value),
        ]


# ── Order roll-up ────────────────────────────────────────────────────────


class TestOrderRollupIgnoresCanceledLines:
    async def test_delivering_the_last_live_line_completes_an_order_with_a_canceled_line(
        self,
    ) -> None:
        harness = Harness([make_line(1, ORDERED), make_line(2, OrderItemStatus.CANCELED)])

        await harness.deliver.execute(actor=make_user(), order_item_id=1)

        order = await harness.orders.get_by_id(1)
        assert order is not None
        assert order.status == OrderStatus.DELIVERED.value
        assert order.delivery_date is not None
