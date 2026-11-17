"""
What the order use cases refuse, and in which order they check. A line in a
status its action does not accept still gets the permission error (403) and
the not-found error (404) before the status refusal (409), so a caller learns
nothing about a line it may not change or that is not on the order it named.
Only a pending or requested line is removed, an ordered one is canceled
instead; a line moves only while nothing was delivered or rejected on it; and
its quantity changes only while it is open, a MADE line never growing past
what its position's production orders leave it. An order someone canceled
takes no new or moved line, while one that reads canceled only because every
line is canceled takes either and derives from it, and a delivered order
takes a new line. A substitution changes nothing while an allocation on the
line belongs to a fulfilled or canceled demand. Fakes and builders come from
tests/unit/order/_helpers.py.
"""

from collections.abc import Awaitable
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime

import pytest

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.fulfillment.application.dto.order_dto import CreateOrderItemCommand
from src.modules.fulfillment.application.dto.order_dto import UpdateOrderItemCommand
from src.modules.fulfillment.application.use_cases.order.cancel_order_item import CancelOrderItem
from src.modules.fulfillment.application.use_cases.order.close_order_item_short import (
    CloseOrderItemShort,
)
from src.modules.fulfillment.application.use_cases.order.create_order_item import CreateOrderItem
from src.modules.fulfillment.application.use_cases.order.delete_order_item import RemoveOrderItem
from src.modules.fulfillment.application.use_cases.order.mark_order_item_ordered import (
    MarkOrderItemOrdered,
)
from src.modules.fulfillment.application.use_cases.order.mark_order_item_ordered import (
    MarkOrderItemRequested,
)
from src.modules.fulfillment.application.use_cases.order.move_order_item import MoveOrderItem
from src.modules.fulfillment.application.use_cases.order.process_order_item_delivery import (
    ProcessOrderItemDelivery,
)
from src.modules.fulfillment.application.use_cases.order.update_order_item import UpdateOrderItem
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.errors import DemandItemAlreadyCanceledError
from src.modules.fulfillment.domain.errors import DemandItemAlreadyFulfilledError
from src.modules.fulfillment.domain.errors import LotPositionQuantityExceedsRemainingError
from src.modules.fulfillment.domain.errors import OrderCanceledError
from src.modules.fulfillment.domain.errors import OrderItemCanceledError
from src.modules.fulfillment.domain.errors import OrderItemCannotBeCanceledError
from src.modules.fulfillment.domain.errors import OrderItemCannotBeClosedShortError
from src.modules.fulfillment.domain.errors import OrderItemCannotBeMarkedError
from src.modules.fulfillment.domain.errors import OrderItemCannotBeMovedError
from src.modules.fulfillment.domain.errors import OrderItemCannotBeRemovedError
from src.modules.fulfillment.domain.errors import OrderItemNotDeliverableError
from src.modules.fulfillment.domain.errors import OrderItemNotFoundError
from src.modules.fulfillment.domain.errors import OrderItemQuantityNotEditableError
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import DomainError
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.lifecycle.fake_reconciler import give_order_facts
from tests.unit.lifecycle.fake_reconciler import give_order_item_facts
from tests.unit.lifecycle.fake_reconciler import order_reconciler
from tests.unit.lifecycle.fake_reconciler import order_reconciler_harness
from tests.unit.order._helpers import ExistingSuppliers
from tests.unit.order._helpers import FakeAllocationRepository
from tests.unit.order._helpers import FakeCatalogueRepository
from tests.unit.order._helpers import FakeDemandRepository
from tests.unit.order._helpers import FakeEventBus
from tests.unit.order._helpers import FakeOrderItemRepository
from tests.unit.order._helpers import FakeOrderRepository
from tests.unit.order._helpers import FakeProductionLotRepository
from tests.unit.order._helpers import FakeSourceItemRepository
from tests.unit.order._helpers import FakeUnitOfWork
from tests.unit.order._helpers import make_allocation
from tests.unit.order._helpers import make_bought_item
from tests.unit.order._helpers import make_demand
from tests.unit.order._helpers import make_order
from tests.unit.order._helpers import make_order_item
from tests.unit.order._helpers import make_production_order
from tests.unit.production_lot._helpers import NoLotCreation
from tests.unit.production_lot.fakes import FakeMadeItemAllocationRepository
from tests.unit.production_lot.fakes import FakeMadeItemDemandRepository
from tests.unit.production_lot.fakes import FakeProjectRepository
from tests.unit.production_lot.fakes import delivery_collaborators
from tests.unit.test_bought_item_delivery import FakeDeliveryRepository

STRANGER = make_user(id=2, username="stranger", permissions=[])
MANAGER = make_user(permissions=[Permission.WRITE_ORDERS, Permission.MANAGE_ORDERS])
RECEIVER = make_user(id=3, username="receiver", permissions=[Permission.RECEIVE_DELIVERIES])

DELIVERED_LINE, ORDERED_LINE, CANCELED_LINE = 1, 2, 3
OTHER_ORDER = 2


def _line(id: int, status: OrderItemStatus, delivered: float = 0.0) -> OrderItem:
    line = make_order_item(id=id, order_id=1, status=status)
    line.quantity_delivered = delivered
    return give_order_item_facts(line)


class _World:
    """Order #1, partially delivered, with a delivered, an ordered and a
    canceled line, and order #2, a draft without lines."""

    def __init__(self) -> None:
        self.orders = FakeOrderRepository(
            [
                give_order_facts(make_order(id=1, status=OrderStatus.PARTIALLY_DELIVERED)),
                make_order(id=OTHER_ORDER),
            ]
        )
        self.lines = FakeOrderItemRepository(
            [
                _line(DELIVERED_LINE, OrderItemStatus.DELIVERED, delivered=10.0),
                _line(ORDERED_LINE, OrderItemStatus.ORDERED),
                _line(CANCELED_LINE, OrderItemStatus.CANCELED),
            ]
        )
        self.uow = FakeUnitOfWork()
        self.reconciler = order_reconciler(self.orders, self.lines)

    async def snapshot(self) -> list[tuple[str, float, int]]:
        """Status, delivered pieces and changelog length of every line."""
        return [
            (line.status, line.quantity_delivered, len(line.changes))
            for line in await self.lines.get_by_order_id(1)
        ]

    def mark_ordered(self) -> MarkOrderItemOrdered:
        return MarkOrderItemOrdered(
            self.lines,
            self.orders,
            uow=self.uow,
            reconciler=self.reconciler,
        )

    def mark_requested(self) -> MarkOrderItemRequested:
        return MarkOrderItemRequested(
            self.lines, self.orders, uow=self.uow, reconciler=self.reconciler
        )

    def remove(self) -> RemoveOrderItem:
        return RemoveOrderItem(
            self.orders,
            self.lines,
            FakeAllocationRepository(),
            uow=self.uow,
            reconciler=self.reconciler,
        )

    def deliver(self) -> ProcessOrderItemDelivery:
        return ProcessOrderItemDelivery(
            self.lines,
            self.orders,
            FakeDeliveryRepository(),
            event_bus=FakeEventBus(),
            uow=self.uow,
            reconciler=self.reconciler,
            made_item_demand_repo=FakeMadeItemDemandRepository(),
            made_item_allocation_repo=FakeMadeItemAllocationRepository(),
            create_lot=NoLotCreation(),
            **delivery_collaborators(),
        )

    def cancel_line(self) -> CancelOrderItem:
        return CancelOrderItem(
            self.orders,
            self.lines,
            FakeAllocationRepository(),
            uow=self.uow,
            reconciler=self.reconciler,
        )

    def close_short(self) -> CloseOrderItemShort:
        return CloseOrderItemShort(
            self.orders,
            self.lines,
            FakeAllocationRepository(),
            uow=self.uow,
            reconciler=self.reconciler,
        )

    def update(self) -> UpdateOrderItem:
        return UpdateOrderItem(
            order_item_repo=self.lines,
            order_repo=self.orders,
            catalogue_repo=FakeCatalogueRepository(),
            allocation_repo=FakeAllocationRepository(),
            demand_repo=FakeDemandRepository(),
            uow=self.uow,
            reconciler=self.reconciler,
            project_repo=FakeProjectRepository(),
        )


# An action on a line of the path's order: (world, actor, order id, line id).
Action = Callable[[_World, User, int, int], Awaitable[object]]


async def _mark_ordered(world: _World, actor: User, order_id: int, line_id: int) -> object:
    return await world.mark_ordered().execute(actor, order_id, line_id)


async def _mark_requested(world: _World, actor: User, order_id: int, line_id: int) -> object:
    return await world.mark_requested().execute(actor, order_id, line_id)


async def _remove(world: _World, actor: User, order_id: int, line_id: int) -> object:
    return await world.remove().execute(actor, order_id, line_id)


async def _cancel_line(world: _World, actor: User, order_id: int, line_id: int) -> object:
    return await world.cancel_line().execute(actor, order_id, line_id)


async def _close_short(world: _World, actor: User, order_id: int, line_id: int) -> object:
    return await world.close_short().execute(actor, order_id, line_id)


async def _set_quantity_12(world: _World, actor: User, order_id: int, line_id: int) -> object:
    return await world.update().execute(
        actor, order_id, line_id, UpdateOrderItemCommand(quantity=12.0, unit="pcs")
    )


@dataclass(frozen=True)
class _Case:
    action: Action
    line_id: int
    refusal: type[DomainError]


_CASES = {
    "mark ordered on a delivered line": _Case(
        _mark_ordered, DELIVERED_LINE, OrderItemCannotBeMarkedError
    ),
    "mark requested on an ordered line": _Case(
        _mark_requested, ORDERED_LINE, OrderItemCannotBeMarkedError
    ),
    "remove a delivered line": _Case(_remove, DELIVERED_LINE, OrderItemCannotBeRemovedError),
    "remove an ordered line": _Case(_remove, ORDERED_LINE, OrderItemCannotBeRemovedError),
    "cancel a delivered line": _Case(_cancel_line, DELIVERED_LINE, OrderItemCannotBeCanceledError),
    "close short a line that received nothing": _Case(
        _close_short, ORDERED_LINE, OrderItemCannotBeClosedShortError
    ),
    "change the quantity of a delivered line": _Case(
        _set_quantity_12, DELIVERED_LINE, OrderItemQuantityNotEditableError
    ),
}


class TestARefusedLineChecksPermissionAndPathFirst:
    @pytest.mark.parametrize("case", list(_CASES.values()), ids=list(_CASES))
    async def test_an_actor_without_the_permission_gets_the_permission_error(
        self, case: _Case
    ) -> None:
        world = _World()
        before = await world.snapshot()

        with pytest.raises(InsufficientPermissionsError):
            await case.action(world, STRANGER, 1, case.line_id)

        assert await world.snapshot() == before
        assert world.uow.committed is False

    @pytest.mark.parametrize("case", list(_CASES.values()), ids=list(_CASES))
    async def test_a_line_named_under_another_order_is_not_found(self, case: _Case) -> None:
        world = _World()
        before = await world.snapshot()

        with pytest.raises(OrderItemNotFoundError):
            await case.action(world, MANAGER, OTHER_ORDER, case.line_id)

        assert await world.snapshot() == before
        assert world.uow.committed is False

    @pytest.mark.parametrize("case", list(_CASES.values()), ids=list(_CASES))
    async def test_only_then_the_status_refuses_the_action(self, case: _Case) -> None:
        world = _World()
        before = await world.snapshot()

        with pytest.raises(case.refusal):
            await case.action(world, MANAGER, 1, case.line_id)

        assert await world.snapshot() == before
        assert world.uow.committed is False


class TestARefusedDeliveryChecksPermissionAndLineFirst:
    async def test_an_actor_without_receive_deliveries_gets_the_permission_error(self) -> None:
        world = _World()

        with pytest.raises(InsufficientPermissionsError):
            await world.deliver().execute(STRANGER, CANCELED_LINE, quantity=1.0)

        assert world.uow.committed is False

    async def test_an_unknown_line_is_not_found(self) -> None:
        world = _World()

        with pytest.raises(OrderItemNotFoundError):
            await world.deliver().execute(RECEIVER, 99, quantity=1.0)

        assert world.uow.committed is False

    async def test_only_then_a_canceled_line_refuses_the_delivery(self) -> None:
        world = _World()
        before = await world.snapshot()

        with pytest.raises(OrderItemNotDeliverableError):
            await world.deliver().execute(RECEIVER, CANCELED_LINE, quantity=1.0)

        assert await world.snapshot() == before
        assert world.uow.committed is False


# ── Remove, move and quantity edits ──────────────────────────────────


def _settled_lines() -> FakeOrderItemRepository:
    """Lines of order #1 for the restrictions below: ordered, partially
    delivered, canceled, and ordered with two pieces rejected for
    redelivery."""
    rejected = _line(4, OrderItemStatus.ORDERED)
    rejected.quantity_rejected = 2.0
    return FakeOrderItemRepository(
        [
            _line(1, OrderItemStatus.ORDERED),
            _line(2, OrderItemStatus.PARTIALLY_DELIVERED, delivered=4.0),
            _line(3, OrderItemStatus.CANCELED),
            rejected,
        ]
    )


class TestLineRestrictions:
    def setup_method(self) -> None:
        self.orders = FakeOrderRepository(
            [
                give_order_facts(make_order(id=1, status=OrderStatus.PARTIALLY_DELIVERED)),
                make_order(id=OTHER_ORDER),
            ]
        )
        self.lines = _settled_lines()
        self.uow = FakeUnitOfWork()
        self.reconciler = order_reconciler(self.orders, self.lines)

    def _remove(self) -> RemoveOrderItem:
        return RemoveOrderItem(
            self.orders,
            self.lines,
            FakeAllocationRepository(),
            uow=self.uow,
            reconciler=self.reconciler,
        )

    def _update(self, lots: FakeProductionLotRepository | None = None) -> UpdateOrderItem:
        return UpdateOrderItem(
            order_item_repo=self.lines,
            order_repo=self.orders,
            catalogue_repo=FakeCatalogueRepository(),
            allocation_repo=FakeAllocationRepository(),
            demand_repo=FakeDemandRepository(),
            lot_repo=lots,
            uow=self.uow,
            reconciler=self.reconciler,
            project_repo=FakeProjectRepository(),
        )

    async def test_an_ordered_line_is_canceled_instead_of_removed(self) -> None:
        with pytest.raises(OrderItemCannotBeRemovedError, match="cancel it instead"):
            await self._remove().execute(MANAGER, 1, 1)

        assert await self.lines.get_by_id(1) is not None

    async def test_a_canceled_line_stays_on_the_order(self) -> None:
        with pytest.raises(OrderItemCannotBeRemovedError, match="has status 'canceled'"):
            await self._remove().execute(MANAGER, 1, 3)

    @pytest.mark.parametrize(
        ("line_id", "message"),
        [
            (2, "has delivered or rejected pieces"),
            (4, "has delivered or rejected pieces"),
            (3, "has status 'canceled' and cannot be moved"),
        ],
        ids=["partially delivered", "rejected for redelivery", "canceled"],
    )
    async def test_a_line_that_received_pieces_or_is_canceled_stays_on_its_order(
        self, line_id: int, message: str
    ) -> None:
        move = MoveOrderItem(self.orders, self.lines, uow=self.uow, reconciler=self.reconciler)

        with pytest.raises(OrderItemCannotBeMovedError, match=message):
            await move.execute(MANAGER, 1, line_id, OTHER_ORDER)

        line = await self.lines.get_by_id(line_id)
        assert line is not None and line.order_id == 1
        assert self.uow.committed is False

    async def test_a_partially_delivered_line_is_closed_short_instead_of_cut(self) -> None:
        with pytest.raises(OrderItemQuantityNotEditableError, match="close it short instead"):
            await self._update().execute(
                MANAGER, 1, 2, UpdateOrderItemCommand(quantity=4.0, unit="pcs")
            )

        line = await self.lines.get_by_id(2)
        assert line is not None and line.quantity == 10.0
        assert self.uow.committed is False

    async def test_a_canceled_line_keeps_its_quantity(self) -> None:
        with pytest.raises(OrderItemQuantityNotEditableError, match=r"can no longer be changed\.$"):
            await self._update().execute(
                MANAGER, 1, 3, UpdateOrderItemCommand(quantity=4.0, unit="pcs")
            )

    async def test_a_note_on_a_canceled_line_is_refused(self) -> None:
        line = await self.lines.get_by_id(3)
        assert line is not None
        with pytest.raises(OrderItemCanceledError):
            await self._update().execute(
                MANAGER,
                1,
                3,
                UpdateOrderItemCommand(quantity=line.quantity, unit=line.unit, note="Late"),
            )
        assert self.uow.committed is False

    async def test_a_note_on_a_partially_delivered_line_is_still_accepted(self) -> None:
        result = await self._update().execute(
            MANAGER, 1, 2, UpdateOrderItemCommand(quantity=10.0, unit="pcs", note="Rest in May")
        )

        assert (result.note, result.quantity) == ("Rest in May", 10.0)

    async def test_a_made_line_grows_only_into_what_its_position_leaves_it(self) -> None:
        # A position of 10 with 4 on a live production order leaves the
        # line 6; the canceled order, which made nothing, takes no share.
        lots = await self._made_line_on_a_position()

        with pytest.raises(LotPositionQuantityExceedsRemainingError, match=r"leaves 6\.000 pcs"):
            await self._update(lots).execute(
                MANAGER, 1, 5, UpdateOrderItemCommand(quantity=7.0, unit="pcs")
            )
        result = await self._update(lots).execute(
            MANAGER, 1, 5, UpdateOrderItemCommand(quantity=5.0, unit="pcs")
        )

        assert result.quantity == 5.0

    async def test_a_made_line_is_edited_after_its_lot_is_locked(self) -> None:
        lots = await self._made_line_on_a_position()
        harness = order_reconciler_harness(self.orders, self.lines)
        update = UpdateOrderItem(
            order_item_repo=self.lines,
            order_repo=self.orders,
            catalogue_repo=FakeCatalogueRepository(),
            allocation_repo=FakeAllocationRepository(),
            demand_repo=FakeDemandRepository(),
            lot_repo=lots,
            uow=self.uow,
            reconciler=harness.reconciler,
            project_repo=FakeProjectRepository(),
        )

        await update.execute(MANAGER, 1, 5, UpdateOrderItemCommand(quantity=5.0, unit="pcs"))

        assert harness.lock_log == [
            (LifecycleAggregate.LOTS, (9,)),
            (LifecycleAggregate.ORDERS, (1,)),
            (LifecycleAggregate.ORDER_ITEMS, (5,)),
        ]

    async def _made_line_on_a_position(self) -> FakeProductionLotRepository:
        """Saves MADE line #5 of 6 pieces on position #41 of lot #9, a
        position of 10 with a live production order of 4 and a canceled one
        of 3, and returns the lot repository holding the position."""
        made = _line(5, OrderItemStatus.ORDERED)
        made.quantity = 6.0
        made.line_type, made.bought_item_id = OrderLineType.MADE, None
        made.lot_position_id, made.lot_id = 41, 9
        await self.lines.save(made)
        in_house = make_production_order(id=1, lot_position_id=41)
        in_house.quantity = 4.0
        canceled = make_production_order(
            id=2, lot_position_id=41, status=ProductionOrderStatus.CANCELED
        )
        canceled.quantity = 3.0
        position = LotPosition(
            id=41,
            created=datetime(2026, 1, 1, tzinfo=UTC),
            changed=None,
            changes=[],
            sequence=1,
            kind=LotPositionKind.MIXED,
            status=LotPositionStatus.IN_PROGRESS,
            quantity=10.0,
            quantity_completed=0.0,
            note=None,
            creator_id=1,
            lot_id=9,
            production_orders=[in_house, canceled],
        )
        return FakeProductionLotRepository(positions=[position])


# ── New lines on finished orders ─────────────────────────────────────


def _create_line(
    orders: FakeOrderRepository, lines: FakeOrderItemRepository, uow: FakeUnitOfWork
) -> CreateOrderItem:
    return CreateOrderItem(
        project_repo=FakeProjectRepository(),
        supplier_repo=ExistingSuppliers(),
        order_item_repo=lines,
        item_repo=FakeCatalogueRepository(),
        order_repo=orders,
        demand_repo=FakeDemandRepository(),
        allocation_repo=FakeAllocationRepository(),
        source_item_repo=FakeSourceItemRepository(),
        uow=uow,
        reconciler=order_reconciler(orders, lines),
    )


def _freight() -> CreateOrderItemCommand:
    return CreateOrderItemCommand(
        order_id=1, supplier_id=1, project_id=1, virtual_name="Freight", quantity=1.0, unit="pcs"
    )


class TestNewLinesOnFinishedOrders:
    async def test_an_order_someone_canceled_takes_no_new_line(self) -> None:
        # The cancel intent, canceled_at, is what refuses the line.
        orders = FakeOrderRepository(
            [give_order_facts(make_order(id=1, status=OrderStatus.CANCELED))]
        )
        lines = FakeOrderItemRepository([_line(1, OrderItemStatus.CANCELED)])
        uow = FakeUnitOfWork()

        with pytest.raises(OrderCanceledError, match="Order #1 is canceled"):
            await _create_line(orders, lines, uow).execute(MANAGER, _freight())

        assert [line.id for line in await lines.get_by_order_id(1)] == [1]
        assert uow.committed is False

    async def test_an_order_canceled_only_by_its_lines_takes_a_line_and_derives_from_it(
        self,
    ) -> None:
        """A placed order whose every line is canceled reads canceled
        without its cancel intent; a new line makes it ordered again."""
        order = make_order(id=1, status=OrderStatus.CANCELED)
        order.ordered_date = datetime(2026, 1, 2, tzinfo=UTC)
        orders = FakeOrderRepository([order])
        lines = FakeOrderItemRepository([_line(1, OrderItemStatus.CANCELED)])

        result = await _create_line(orders, lines, FakeUnitOfWork()).execute(MANAGER, _freight())

        assert result.status == "pending"
        assert (order.status, order.canceled_at) == ("ordered", None)

    async def test_a_delivered_order_takes_a_new_line_and_is_partially_delivered_again(
        self,
    ) -> None:
        order = give_order_facts(make_order(id=1, status=OrderStatus.DELIVERED))
        orders = FakeOrderRepository([order])
        lines = FakeOrderItemRepository([_line(1, OrderItemStatus.DELIVERED, delivered=10.0)])

        result = await _create_line(orders, lines, FakeUnitOfWork()).execute(MANAGER, _freight())

        assert result.status == "pending"
        assert order.status == "partially_delivered"


class TestMovesIntoFinishedOrders:
    """A moved line meets the rule a new line meets: only an order someone
    canceled refuses it."""

    @staticmethod
    def _world(target: Order) -> tuple[MoveOrderItem, FakeOrderItemRepository, FakeUnitOfWork]:
        source = give_order_facts(make_order(id=1, status=OrderStatus.ORDERED))
        orders = FakeOrderRepository([source, target])
        canceled = _line(9, OrderItemStatus.CANCELED)
        canceled.order_id = target.id
        lines = FakeOrderItemRepository([_line(1, OrderItemStatus.ORDERED), canceled])
        uow = FakeUnitOfWork()
        move = MoveOrderItem(orders, lines, uow=uow, reconciler=order_reconciler(orders, lines))
        return move, lines, uow

    async def test_an_order_someone_canceled_takes_no_moved_line(self) -> None:
        target = give_order_facts(make_order(id=OTHER_ORDER, status=OrderStatus.CANCELED))
        move, lines, uow = self._world(target)

        with pytest.raises(OrderItemCannotBeMovedError, match="Order #2 is canceled"):
            await move.execute(MANAGER, 1, 1, OTHER_ORDER)

        line = await lines.get_by_id(1)
        assert line is not None and line.order_id == 1
        assert uow.committed is False

    async def test_an_order_canceled_only_by_its_lines_takes_a_moved_line_and_derives_from_it(
        self,
    ) -> None:
        """A placed order whose every line is canceled reads canceled
        without its cancel intent; a moved-in line makes it ordered again."""
        target = make_order(id=OTHER_ORDER, status=OrderStatus.CANCELED)
        target.ordered_date = datetime(2026, 1, 2, tzinfo=UTC)
        move, _lines, uow = self._world(target)

        result = await move.execute(MANAGER, 1, 1, OTHER_ORDER)

        assert (result.order_id, result.status) == (OTHER_ORDER, "ordered")
        assert (target.status, target.canceled_at) == ("ordered", None)
        assert uow.committed is True


# ── Substitutions ────────────────────────────────────────────────────


class TestSubstitutionOnALineWithFinishedDemands:
    def _use_case(
        self, demand_status: BoughtItemDemandStatus
    ) -> tuple[UpdateOrderItem, FakeOrderItemRepository, FakeAllocationRepository]:
        orders = FakeOrderRepository(
            [give_order_facts(make_order(id=1, status=OrderStatus.ORDERED))]
        )
        lines = FakeOrderItemRepository([_line(1, OrderItemStatus.ORDERED)])
        allocations = FakeAllocationRepository([make_allocation(demand_item_id=1)])
        use_case = UpdateOrderItem(
            order_item_repo=lines,
            order_repo=orders,
            catalogue_repo=FakeCatalogueRepository([make_bought_item(id=7)]),
            allocation_repo=allocations,
            demand_repo=FakeDemandRepository([make_demand(id=1, status=demand_status)]),
            uow=FakeUnitOfWork(),
            reconciler=order_reconciler(orders, lines),
            project_repo=FakeProjectRepository(),
        )
        return use_case, lines, allocations

    @pytest.mark.parametrize(
        ("demand_status", "refusal"),
        [
            (BoughtItemDemandStatus.FULFILLED, DemandItemAlreadyFulfilledError),
            (BoughtItemDemandStatus.CANCELED, DemandItemAlreadyCanceledError),
        ],
    )
    async def test_a_substitution_is_refused_while_a_demand_on_the_line_is_finished(
        self, demand_status: BoughtItemDemandStatus, refusal: type[DomainError]
    ) -> None:
        use_case, lines, allocations = self._use_case(demand_status)

        with pytest.raises(refusal):
            await use_case.execute(
                MANAGER,
                1,
                1,
                UpdateOrderItemCommand(quantity=10.0, unit="pcs", bought_item_id=7),
            )

        line = await lines.get_by_id(1)
        assert line is not None and line.bought_item_id == 1
        (allocation,) = await allocations.get_by_order_item_id(1)
        assert allocation.substitute_item_id is None

    async def test_a_substitution_on_a_line_whose_demands_are_live_goes_through(self) -> None:
        use_case, lines, allocations = self._use_case(BoughtItemDemandStatus.ORDERED)

        await use_case.execute(
            MANAGER,
            1,
            1,
            UpdateOrderItemCommand(quantity=10.0, unit="pcs", bought_item_id=7),
        )

        line = await lines.get_by_id(1)
        assert line is not None and line.bought_item_id == 7
        # The fake appends on save, so the one allocation may be listed twice.
        assert {a.substitute_item_id for a in await allocations.get_by_order_item_id(1)} == {7}
