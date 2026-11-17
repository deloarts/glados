"""
A delivery correction takes back accepted pieces of one delivery row. It
books a new row with the negative quantity, naming the corrected row and the
reason, lowers the line's delivered total by the same amount, so the total
stays the sum of the rows, and lets the lifecycle reconciler derive the line
and its order again. It takes back at most what the row accepted less
earlier corrections of it, never corrects a correction, and is refused on a
MADE line, on a line that is neither partially delivered nor delivered, and
while a demand allocated to the line is fulfilled. It needs
receive:deliveries, checked before anything is read. Fakes and builders come
from tests/unit/order/_helpers.py.
"""

from datetime import UTC
from datetime import datetime
from types import SimpleNamespace

import pytest

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.fulfillment.application.use_cases.order.correct_order_item_delivery import (
    CorrectOrderItemDelivery,
)
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.order_item_delivery import OrderItemDelivery
from src.modules.fulfillment.domain.errors import DeliveryCannotBeCorrectedError
from src.modules.fulfillment.domain.errors import InvalidDeliveryQuantityError
from src.modules.fulfillment.domain.errors import OrderItemDeliveryNotFoundError
from src.modules.fulfillment.domain.errors import OrderItemNotFoundError
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.rejection_outcome import RejectionOutcome
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler_harness
from tests.unit.lifecycle.fake_reconciler import give_order_facts
from tests.unit.lifecycle.fake_reconciler import give_order_item_facts
from tests.unit.lifecycle.fake_reconciler import order_reconciler
from tests.unit.order._helpers import FakeAllocationRepository
from tests.unit.order._helpers import FakeDemandRepository
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
from tests.unit.test_bought_item_delivery import FakeDeliveryRepository

RECEIVER = make_user(id=3, username="receiver", permissions=[Permission.RECEIVE_DELIVERIES])
MANAGER = make_user(permissions=[Permission.WRITE_ORDERS, Permission.MANAGE_ORDERS])

_BOOKED = datetime(2026, 3, 2, tzinfo=UTC)


def _row(quantity: float, *, rejected: float = 0.0, line_id: int = 1) -> OrderItemDelivery:
    return OrderItemDelivery(
        id=0,
        order_item_id=line_id,
        quantity=quantity,
        delivery_date=_BOOKED,
        storage_place="Shelf A",
        receiver_id=RECEIVER.id,
        created=_BOOKED,
        quantity_rejected=rejected,
        rejection_reason="supplier_damage" if rejected else None,
        rejection_outcome=RejectionOutcome.REDELIVER if rejected else None,
    )


class _Lots:
    """Lots by id, as far as the correction reads them."""

    def __init__(self, lots: dict) -> None:
        self._lots = lots

    async def get_by_id(self, lot_id: int):
        return self._lots.get(lot_id)


def _lot(processed_at_first: float) -> SimpleNamespace:
    """A lot whose first position processed `processed_at_first` pieces."""
    first = SimpleNamespace(
        sequence=1,
        production_orders=[SimpleNamespace(pieces_processed=processed_at_first)],
        order_item_quantity_delivered=None,
        closed_lines_delivered=0.0,
        provisioned_quantity=0.0,
        quantity_completed=0.0,
    )
    return SimpleNamespace(positions=[first])


def _fulfilled_by_hand(demand, fulfilled):
    demand.status = fulfilled
    demand.fulfilled_manually_at = _BOOKED
    return demand


class _World:
    """Order #1 with one line of ten pieces and its delivery rows, the line
    status following from the rows; and the correction use case."""

    def __init__(
        self,
        rows: list[OrderItemDelivery],
        *,
        status: OrderItemStatus,
        made: bool = False,
        allocations: list | None = None,
        demands: list | None = None,
        source_allocations: list | None = None,
        source_demands: list | None = None,
        lots: dict | None = None,
    ) -> None:
        # The order stands where its one line does, delivered or ordered.
        self.order = give_order_facts(make_order(id=1, status=OrderStatus(status.value)))
        if status == OrderItemStatus.DELIVERED:
            self.order.delivery_date = _BOOKED
        self.orders = FakeOrderRepository([self.order])
        line = make_order_item(id=1, order_id=1, status=status)
        line.quantity_delivered = sum(r.quantity for r in rows)
        line.quantity_rejected = sum(r.quantity_rejected for r in rows)
        if made:
            line.line_type, line.bought_item_id = OrderLineType.MADE, None
            line.lot_position_id, line.lot_id = 41, 9
        self.line: OrderItem = give_order_item_facts(line)
        self.lines = FakeOrderItemRepository([self.line])
        self.deliveries = FakeDeliveryRepository()
        self.deliveries._deliveries = rows
        for number, row in enumerate(rows, start=1):
            row.id = number
        self.deliveries._next_id = len(rows) + 1
        self.uow = FakeUnitOfWork()
        self.use_case = CorrectOrderItemDelivery(
            self.orders,
            self.lines,
            self.deliveries,
            FakeAllocationRepository(allocations),
            FakeDemandRepository(demands),
            uow=self.uow,
            reconciler=order_reconciler(self.orders, self.lines),
            source_item_allocation_repo=FakeSourceItemAllocationRepository(source_allocations),
            source_item_demand_repo=FakeSourceItemDemandRepository(source_demands),
            lot_repo=_Lots(lots or {}),
        )

    async def correct(
        self, delivery_id: int, quantity: float, *, actor=RECEIVER, order_item_id: int = 1
    ):
        return await self.use_case.execute(
            actor, 1, order_item_id, delivery_id, quantity, "Counted twice"
        )

    async def rows(self) -> list[OrderItemDelivery]:
        return await self.deliveries.get_by_order_item_id(1)


def _delivered() -> _World:
    """Ten pieces delivered in two rows, six and four."""
    return _World([_row(6.0), _row(4.0)], status=OrderItemStatus.DELIVERED)


class TestCorrection:
    async def test_a_correction_books_a_negative_row_and_lowers_the_delivered_total(
        self,
    ) -> None:
        world = _delivered()

        result = await world.correct(1, 2.0)

        correction = (await world.rows())[-1]
        assert (correction.id, correction.quantity) == (3, -2.0)
        assert (correction.corrects_delivery_id, correction.correction_reason) == (
            1,
            "Counted twice",
        )
        assert (correction.receiver_id, correction.storage_place) == (RECEIVER.id, "Shelf A")
        assert world.line.quantity_delivered == 8.0
        assert sum(r.quantity for r in await world.rows()) == world.line.quantity_delivered
        assert (result.status, world.line.status) == (
            "partially_delivered",
            "partially_delivered",
        )
        assert world.line.changes[-2].endswith(
            "Delivery #1 corrected: took back 2.000 pcs (Counted twice); 8.000/10.000 delivered."
        )
        assert world.line.changes[-1].endswith(
            "Status: delivered → partially_delivered (delivery corrected)."
        )
        assert world.order.status == "partially_delivered"
        assert world.order.delivery_date is None
        assert world.order.changes[-1].endswith("Delivery date: cleared (delivery corrected).")
        assert [(r.id, r.corrects_delivery_id) for r in result.delivery_records] == [
            (1, None),
            (2, None),
            (3, 1),
        ]
        assert world.uow.committed is True

    async def test_a_row_takes_corrections_up_to_what_it_accepted(self) -> None:
        world = _delivered()
        await world.correct(1, 4.0)

        with pytest.raises(DeliveryCannotBeCorrectedError, match=r"has 2\.000 pcs accepted"):
            await world.correct(1, 3.0)
        await world.correct(1, 2.0)

        assert world.line.quantity_delivered == 4.0
        assert [r.quantity for r in await world.rows()] == [6.0, 4.0, -4.0, -2.0]

    async def test_the_delivered_total_never_drops_below_zero(self) -> None:
        # A total already below its rows, which only a booking outside the
        # delivery rows could leave.
        world = _delivered()
        world.line.quantity_delivered = 3.0

        with pytest.raises(DeliveryCannotBeCorrectedError, match=r"has 3\.000 pcs delivered"):
            await world.correct(1, 4.0)

    async def test_a_correction_row_is_not_corrected_itself(self) -> None:
        world = _delivered()
        await world.correct(1, 2.0)

        with pytest.raises(DeliveryCannotBeCorrectedError, match="is itself a correction"):
            await world.correct(3, 1.0)

    async def test_a_made_line_is_refused(self) -> None:
        world = _World([_row(10.0)], status=OrderItemStatus.DELIVERED, made=True)

        with pytest.raises(DeliveryCannotBeCorrectedError, match="is a MADE line"):
            await world.correct(1, 1.0)

        assert world.line.quantity_delivered == 10.0
        assert world.uow.committed is False

    async def test_a_line_that_accepted_nothing_is_refused(self) -> None:
        # The supplier's pieces were all rejected for redelivery, so the
        # line is still ordered.
        world = _World([_row(0.0, rejected=2.0)], status=OrderItemStatus.ORDERED)

        with pytest.raises(DeliveryCannotBeCorrectedError, match="has status 'ordered'"):
            await world.correct(1, 1.0)

    @pytest.mark.parametrize("quantity", [0.0, -1.0, float("nan"), float("inf")])
    async def test_the_quantity_is_a_finite_positive_number(self, quantity: float) -> None:
        world = _delivered()

        with pytest.raises(InvalidDeliveryQuantityError):
            await world.correct(1, quantity)

        assert world.line.quantity_delivered == 10.0

    async def test_a_demand_the_deliveries_fulfil_derives_back(self) -> None:
        demand = make_demand(id=1, status=BoughtItemDemandStatus.FULFILLED)
        world = _World(
            [_row(6.0), _row(4.0)],
            status=OrderItemStatus.DELIVERED,
            allocations=[make_allocation(demand_item_id=1, order_item_id=1)],
            demands=[demand],
        )
        harness = demand_reconciler_harness(
            bought_demands=world.use_case._demands,
            bought_allocations=world.use_case._allocations,
            order_items=world.lines,
            orders=world.orders,
        )
        world.use_case._reconciler = harness.reconciler

        await world.correct(1, 2.0)

        assert world.line.quantity_delivered == 8.0
        stored = await world.use_case._demands.get_by_id(1)
        assert stored is not None and stored.status == "ordered"

    async def test_refused_while_a_bought_demand_on_the_line_is_fulfilled_by_hand(self) -> None:
        world = _World(
            [_row(6.0), _row(4.0)],
            status=OrderItemStatus.DELIVERED,
            allocations=[make_allocation(demand_item_id=1, order_item_id=1)],
            demands=[_fulfilled_by_hand(make_demand(id=1), BoughtItemDemandStatus.FULFILLED)],
        )

        consumed = r"consumed its pieces \(demand #1, fulfilled by hand\)"
        with pytest.raises(DeliveryCannotBeCorrectedError, match=consumed):
            await world.correct(1, 2.0)

        assert len(await world.rows()) == 2

    async def test_refused_while_a_source_demand_on_the_line_is_fulfilled_by_hand(self) -> None:
        world = _World(
            [_row(6.0), _row(4.0)],
            status=OrderItemStatus.DELIVERED,
            source_allocations=[make_source_item_allocation(demand_item_id=2)],
            source_demands=[
                _fulfilled_by_hand(make_source_item_demand(id=2), SourceItemDemandStatus.FULFILLED)
            ],
        )

        with pytest.raises(DeliveryCannotBeCorrectedError, match="source item demand #2"):
            await world.correct(1, 2.0)

    async def test_refused_once_the_lot_of_a_source_demand_used_its_material(self) -> None:
        world = _World(
            [_row(6.0), _row(4.0)],
            status=OrderItemStatus.DELIVERED,
            source_allocations=[make_source_item_allocation(demand_item_id=2)],
            source_demands=[make_source_item_demand(id=2, status=SourceItemDemandStatus.FULFILLED)],
            lots={1: _lot(processed_at_first=1.0)},
        )

        with pytest.raises(DeliveryCannotBeCorrectedError, match="its lot started"):
            await world.correct(1, 2.0)

    async def test_a_source_demand_whose_lot_has_not_started_lets_it_through(self) -> None:
        world = _World(
            [_row(6.0), _row(4.0)],
            status=OrderItemStatus.DELIVERED,
            source_allocations=[make_source_item_allocation(demand_item_id=2)],
            source_demands=[make_source_item_demand(id=2, status=SourceItemDemandStatus.FULFILLED)],
            lots={1: _lot(processed_at_first=0.0)},
        )

        await world.correct(1, 2.0)

        assert world.line.quantity_delivered == 8.0

    async def test_a_live_demand_on_the_line_lets_the_correction_through(self) -> None:
        demand = make_demand(id=1, status=BoughtItemDemandStatus.ORDERED)
        world = _World(
            [_row(6.0), _row(4.0)],
            status=OrderItemStatus.DELIVERED,
            allocations=[make_allocation(demand_item_id=1, order_item_id=1, quantity=5.0)],
            demands=[demand],
        )

        await world.correct(2, 4.0)

        assert world.line.quantity_delivered == 6.0
        assert demand.status == "ordered"

    async def test_the_demands_on_the_line_are_locked_before_the_consumed_check(self) -> None:
        """Locking the line widens to the demands allocated to it, so no one
        can mark one of them fulfilled between the check and the commit. The
        refused correction has already acquired the demand."""
        world = _World(
            [_row(6.0), _row(4.0)],
            status=OrderItemStatus.DELIVERED,
            allocations=[make_allocation(demand_item_id=1, order_item_id=1)],
            demands=[_fulfilled_by_hand(make_demand(id=1), BoughtItemDemandStatus.FULFILLED)],
        )
        harness = demand_reconciler_harness(
            bought_demands=world.use_case._demands,
            bought_allocations=world.use_case._allocations,
            order_items=world.lines,
            orders=world.orders,
        )
        world.use_case._reconciler = harness.reconciler

        with pytest.raises(DeliveryCannotBeCorrectedError):
            await world.correct(1, 2.0)

        assert (LifecycleAggregate.BOUGHT_DEMANDS, (1,)) in harness.lock_log


class TestCorrectionChecksPermissionAndPathFirst:
    async def test_an_actor_without_receive_deliveries_gets_the_permission_error(self) -> None:
        world = _delivered()

        with pytest.raises(InsufficientPermissionsError):
            await world.correct(1, 2.0, actor=MANAGER, order_item_id=99)

    async def test_an_unknown_line_is_not_found(self) -> None:
        world = _delivered()

        with pytest.raises(OrderItemNotFoundError):
            await world.correct(1, 2.0, order_item_id=99)

    async def test_a_row_of_another_line_is_not_found(self) -> None:
        world = _delivered()
        world.deliveries._deliveries.append(_row(1.0, line_id=2))
        world.deliveries._deliveries[-1].id = 7

        with pytest.raises(OrderItemDeliveryNotFoundError, match="Delivery #7 not found"):
            await world.correct(7, 1.0)


_EARLIER = datetime(2026, 3, 1, tzinfo=UTC)


def _dated(row: OrderItemDelivery, when: datetime) -> OrderItemDelivery:
    row.delivery_date = when
    return row


class TestDeliveryDate:
    """The line's delivery date is when its standing goods last arrived:
    the latest delivery row a correction has not taken back in full."""

    def _world(self, *rows: OrderItemDelivery) -> _World:
        world = _World(list(rows), status=OrderItemStatus.DELIVERED)
        world.line.delivery_date = max(r.delivery_date for r in rows)
        return world

    async def test_taking_every_piece_back_clears_the_delivery_date(self) -> None:
        world = self._world(_row(10.0))

        await world.correct(1, 10.0)

        assert world.line.quantity_delivered == 0.0
        assert world.line.delivery_date is None

    async def test_taking_the_latest_row_back_falls_back_to_the_earlier_one(self) -> None:
        world = self._world(_dated(_row(6.0), _EARLIER), _row(4.0))

        await world.correct(2, 4.0)

        assert world.line.delivery_date == _EARLIER

    async def test_a_partly_corrected_row_keeps_its_date(self) -> None:
        world = self._world(_dated(_row(6.0), _EARLIER), _row(4.0))

        await world.correct(2, 1.0)

        assert world.line.delivery_date == _BOOKED

    async def test_a_row_with_rejected_pieces_still_counts_as_an_arrival(self) -> None:
        world = self._world(_dated(_row(0.0, rejected=2.0), _EARLIER), _row(4.0))

        await world.correct(2, 4.0)

        assert world.line.delivery_date == _EARLIER
