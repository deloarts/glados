"""
The lot intents and the facts they leave: a hold is an overlay on what the
facts derive, so marking a line ordered or booking a delivery on a held lot
keeps it ON_HOLD, while a held lot whose last position completes is
COMPLETED and has nothing left to resume. A cancel ends the live work, a
partially delivered MADE line closed short at its pieces received. The lot
intent table answers who may act and from which status, with the error
classes the actions have always raised.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

import pytest

from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.application.dto.production_lot_dto import CancelLotCommand
from src.modules.fulfillment.application.dto.production_lot_dto import CompleteLotCommand
from src.modules.fulfillment.application.dto.production_order_dto import (
    CancelProductionOrderCommand,
)
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import CancelLot
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import CompleteLot
from src.modules.fulfillment.application.use_cases.production_order.production_order_lifecycle import (
    CancelProductionOrder,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.source_item_allocation import (
    SourceItemDemandAllocation,
)
from src.modules.fulfillment.domain.errors import LotInvalidStatusTransitionError
from src.modules.fulfillment.domain.errors import LotNotScrappableError
from src.modules.fulfillment.domain.errors import LotStructureLockedError
from src.modules.fulfillment.domain.events.lot_events import LotEndedShort
from src.modules.fulfillment.domain.events.lot_events import LotSupplierLinesToSettle
from src.modules.fulfillment.domain.services import lot_rules
from src.modules.fulfillment.domain.services.lifecycle.intents import LOT_INTENTS
from src.modules.fulfillment.domain.services.lot_rules import LotRules
from src.modules.fulfillment.domain.services.lot_rules import assert_delivery_disposition_allowed
from src.modules.fulfillment.domain.services.lot_rules import assert_lot_action
from src.modules.fulfillment.domain.services.lot_rules import assert_scrap_allowed
from src.modules.fulfillment.domain.services.lot_rules import compute_position_remaining
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction
from tests.factories import make_user
from tests.unit.fakes import FakeEventBus
from tests.unit.lifecycle.fake_world import NOW
from tests.unit.lifecycle.fake_world import FakeWorld
from tests.unit.lifecycle.fake_world import actor
from tests.unit.lifecycle.fake_world import make
from tests.unit.production_lot._floor import Floor
from tests.unit.production_lot._helpers import make_demand
from tests.unit.production_lot._helpers import make_order
from tests.unit.production_lot._helpers import make_order_item
from tests.unit.production_lot._helpers import make_source_item_demand
from tests.unit.production_lot.fakes import FakeBoughtItemAllocationRepository
from tests.unit.production_lot.fakes import FakeMadeItemAllocationRepository
from tests.unit.production_lot.fakes import FakeMadeItemDemandRepository
from tests.unit.production_lot.fakes import FakeOrderItemRepository
from tests.unit.production_lot.fakes import FakeOrderRepository
from tests.unit.production_lot.fakes import FakeSourceItemAllocationRepository
from tests.unit.production_lot.fakes import FakeSourceItemDemandRepository
from tests.unit.production_lot.fakes import FakeUnitOfWork
from tests.unit.production_order.fakes import lifecycle_collaborators

HELD = datetime(2026, 1, 1, tzinfo=UTC)
ACTOR = actor()


async def _reconcile(world: FakeWorld, line_id: int) -> None:
    reconciler = LifecycleReconciler(
        world.repositories, FakeEventBus(), aggregates=frozenset(LifecycleAggregate)
    )
    reconciler.touch_order_items([line_id])
    await reconciler.run(ACTOR, NOW)


def _held_lot_with_a_line(world: FakeWorld, **line: object) -> tuple[ProductionLot, int]:
    lot = world.lot(status=LotStatus.ON_HOLD, held_at=HELD)
    position = world.position(lot, kind=LotPositionKind.EXTERNAL, status=LotPositionStatus.PENDING)
    order = world.order(status=OrderStatus.ORDERED, ordered_date=NOW)
    made = world.line(order, position=position, **line)  # type: ignore[arg-type]
    return lot, made.id


# ── The hold overlay ────────────────────────────────────────────────────


async def test_marking_the_line_of_a_held_lot_ordered_keeps_the_lot_on_hold() -> None:
    world = FakeWorld()
    lot, line_id = _held_lot_with_a_line(world, status=OrderItemStatus.PENDING, ordered_date=NOW)

    await _reconcile(world, line_id)

    assert world.order_items[line_id].status == "ordered"
    assert [p.status for p in world.positions.values()] == ["ordered_or_queued"]
    assert world.lots[lot.id].status == "on_hold"


async def test_a_delivery_on_a_held_lot_keeps_the_lot_on_hold() -> None:
    world = FakeWorld()
    lot, line_id = _held_lot_with_a_line(
        world, status=OrderItemStatus.ORDERED, ordered_date=NOW, delivered=4.0
    )

    await _reconcile(world, line_id)

    assert [p.status for p in world.positions.values()] == ["partially_completed"]
    assert world.lots[lot.id].status == "on_hold"


async def test_a_held_lot_whose_last_position_completes_is_completed() -> None:
    world = FakeWorld()
    lot, line_id = _held_lot_with_a_line(
        world, status=OrderItemStatus.ORDERED, ordered_date=NOW, delivered=10.0
    )

    await _reconcile(world, line_id)

    completed = world.lots[lot.id]
    assert completed.status == "completed"
    with pytest.raises(LotInvalidStatusTransitionError):
        assert_lot_action(LifecycleAction.RESUME, completed, make_user(permissions=["write:lots"]))


# ── Who may act, from which status ──────────────────────────────────────


def _lot(status: LotStatus, **values: object) -> ProductionLot:
    return make(ProductionLot, id=1, status=status, quantity=10.0, creator_id=1, **values)


def test_cancel_needs_manage_lots_even_for_the_creator() -> None:
    lot = _lot(LotStatus.IN_PROGRESS)

    with pytest.raises(InsufficientPermissionsError):
        assert_lot_action(LifecycleAction.CANCEL, lot, make_user(id=1, permissions=["write:lots"]))
    assert_lot_action(
        LifecycleAction.CANCEL,
        lot,
        make_user(id=2, permissions=[Permission.WRITE_LOTS, Permission.MANAGE_LOTS]),
    )


@pytest.mark.parametrize("status", [LotStatus.COMPLETED, LotStatus.CANCELED, LotStatus.SCRAPPED])
def test_a_terminal_lot_takes_no_hold_cancel_or_force_complete(status: LotStatus) -> None:
    planner = make_user(permissions=[Permission.WRITE_LOTS, Permission.MANAGE_LOTS])
    lot = _lot(status)

    for action in (LifecycleAction.HOLD, LifecycleAction.CANCEL, LifecycleAction.FORCE_COMPLETE):
        with pytest.raises(LotInvalidStatusTransitionError):
            assert_lot_action(action, lot, planner)


def test_resume_needs_a_held_lot() -> None:
    planner = make_user(permissions=[Permission.WRITE_LOTS])

    with pytest.raises(LotInvalidStatusTransitionError):
        assert_lot_action(LifecycleAction.RESUME, _lot(LotStatus.IN_PROGRESS), planner)
    assert_lot_action(LifecycleAction.RESUME, _lot(LotStatus.ON_HOLD, held_at=HELD), planner)


# ── Cancel and force-complete over the use cases ────────────────────────


class TestCancelAndForceComplete:
    @pytest.fixture(autouse=True)
    async def _setup(self) -> None:
        """A lot of 4 with one external position whose MADE line has two of
        its four pieces delivered, and a made demand of 4 on the lot."""
        self.floor = Floor(positions=1)
        self.lot = await self.floor.lot(4.0)
        [self.position] = await self.floor.positions(self.lot.id)
        self.line = make_order_item(id=1, lot_position_id=self.position.id)
        self.line.status = OrderItemStatus.PARTIALLY_DELIVERED
        self.line.quantity = 4.0
        self.line.quantity_delivered = 2.0
        self.line.ordered_date = date(2026, 1, 1)
        self.order_items = FakeOrderItemRepository([self.line])
        self.parent_orders = FakeOrderRepository([make_order(id=1)])
        self.parent_orders._orders[1].status = OrderStatus.PARTIALLY_DELIVERED
        self.made_demands = FakeMadeItemDemandRepository([make_demand(id=9, quantity=4.0)])
        self.made_allocations = FakeMadeItemAllocationRepository(
            [MadeItemDemandAllocation(demand_item_id=9, lot_id=self.lot.id, quantity=4.0)]
        )
        self.planner = make_user(permissions=[Permission.WRITE_LOTS, Permission.MANAGE_LOTS])
        self.uow = FakeUnitOfWork()

    def _collaborators(self) -> dict[str, object]:
        return lifecycle_collaborators(
            self.floor.orders,
            self.floor.lots,
            self.floor.bus,
            orders=self.parent_orders,
            order_items=self.order_items,
            made_demands=self.made_demands,
            made_allocations=self.made_allocations,
        )

    def _cancel_lot(self) -> CancelLot:
        return CancelLot(
            self.floor.lots,
            self.floor.orders,
            self.order_items,
            FakeBoughtItemAllocationRepository(),
            self.made_allocations,
            FakeSourceItemDemandRepository(),
            FakeSourceItemAllocationRepository(),
            event_bus=self.floor.bus,
            uow=self.uow,
            parent_order_repo=self.parent_orders,
            **self._collaborators(),
        )

    async def _settle(self) -> None:
        settle = self._collaborators()["reconciler"]
        assert isinstance(settle, LifecycleReconciler)
        settle.touch_lots([self.lot.id])
        await settle.run(self.planner, NOW)

    async def test_cancel_is_refused_once_a_position_has_good_pieces(self) -> None:
        # The two delivered pieces completed the position; force-complete
        # keeps them, a cancel would throw them away.
        await self._settle()

        with pytest.raises(LotInvalidStatusTransitionError, match="force-complete"):
            await self._cancel_lot().execute(
                self.planner, self.lot.id, CancelLotCommand(reason="customer dropped it")
            )

        line = await self.order_items.get_by_id(1)
        assert line is not None
        assert (line.quantity, line.status) == (4.0, "partially_delivered")
        assert (await self.floor.reload(self.lot.id)).canceled_at is None

    async def test_cancel_keeps_an_ordered_line_open_for_purchasing(self) -> None:
        self.line.status = OrderItemStatus.ORDERED
        self.line.quantity_delivered = 0.0

        await self._cancel_lot().execute(
            self.planner, self.lot.id, CancelLotCommand(reason="customer dropped it")
        )

        line = await self.order_items.get_by_id(1)
        assert line is not None
        assert (line.status, line.canceled_at) == ("ordered", None)
        lot = await self.floor.reload(self.lot.id)
        assert (lot.status, lot.positions[0].status) == ("canceled", "canceled")
        [settle] = [e for e in self.floor.bus.published if isinstance(e, LotSupplierLinesToSettle)]
        order = await self.parent_orders.get_by_id(1)
        assert order is not None
        assert (settle.ended, settle.open_lines, settle.canceled_lines, settle.order_id) == (
            "canceled",
            [f"{order.order_number} pos. {line.position}"],
            [],
            1,
        )

    async def test_cancel_of_a_held_lot_clears_its_hold(self) -> None:
        self.line.status = OrderItemStatus.ORDERED
        self.line.quantity_delivered = 0.0
        lot = await self.floor.reload(self.lot.id)
        lot.held_at = datetime(2026, 1, 3, tzinfo=UTC)
        await self.floor.lots.save(lot)
        settle = self._collaborators()["reconciler"]
        assert isinstance(settle, LifecycleReconciler)
        settle.touch_lots([self.lot.id])
        await settle.run(self.planner, NOW)
        assert (await self.floor.reload(self.lot.id)).status == "on_hold"

        await CancelLot(
            self.floor.lots,
            self.floor.orders,
            self.order_items,
            FakeBoughtItemAllocationRepository(),
            self.made_allocations,
            FakeSourceItemDemandRepository(),
            FakeSourceItemAllocationRepository(),
            event_bus=self.floor.bus,
            uow=self.uow,
            parent_order_repo=self.parent_orders,
            **self._collaborators(),
        ).execute(self.planner, self.lot.id, CancelLotCommand(reason="customer dropped it"))

        lot = await self.floor.reload(self.lot.id)
        assert (lot.status, lot.held_at) == ("canceled", None)

    async def test_force_complete_recomputes_the_made_demands_of_the_lot(self) -> None:
        settle = self._collaborators()["reconciler"]
        assert isinstance(settle, LifecycleReconciler)
        settle.touch_lots([self.lot.id])
        await settle.run(self.planner, NOW)

        result = await CompleteLot(
            self.floor.lots,
            self.floor.orders,
            self.order_items,
            event_bus=self.floor.bus,
            uow=self.uow,
            parent_order_repo=self.parent_orders,
            made_item_demand_repo=self.made_demands,
            made_item_allocation_repo=self.made_allocations,
            **self._collaborators(),
            source_item_demand_repo=FakeSourceItemDemandRepository(),
            source_item_allocation_repo=FakeSourceItemAllocationRepository(),
            bought_allocation_repo=FakeBoughtItemAllocationRepository(),
        ).execute(self.planner, self.lot.id, CompleteLotCommand())

        assert (result.status, result.quantity) == ("completed", 2.0)
        lot = await self.floor.reload(self.lot.id)
        assert lot.force_completed_at is not None
        demand = await self.made_demands.get_by_id(9)
        assert demand is not None
        # The allocation shrinks with the lot to the two pieces it produced,
        # so the reconciler derives the demand of four, stored open, as
        # allocated: two pieces cover it, which is less than it needs.
        allocations = await self.made_allocations.get_by_lot_id(self.lot.id)
        assert [a.quantity for a in allocations] == [2.0]
        assert demand.status == "allocated"
        [short] = [e for e in self.floor.bus.published if isinstance(e, LotEndedShort)]
        assert (short.quantity, short.original_quantity, short.demand_ids) == (2.0, 4.0, [9])


async def test_force_complete_keeps_an_allocation_that_fits_what_the_lot_produced() -> None:
    """A lot of 10 with one allocation of 4 that produced 6 keeps the 4:
    the allocations shrink only by what they exceed the new quantity."""
    floor = Floor(positions=1)
    lot = await floor.lot(10.0, demands=[(9, 4.0, MadeItemDemandStatus.OPEN)])
    [only] = await floor.positions(lot.id)
    running = await floor.order(only, processed=6.0)
    await floor.settle(lot.id)
    planner = make_user(permissions=[Permission.WRITE_LOTS, Permission.MANAGE_LOTS])
    lines, parents = FakeOrderItemRepository(), FakeOrderRepository([])

    result = await CompleteLot(
        floor.lots,
        floor.orders,
        lines,
        event_bus=floor.bus,
        uow=FakeUnitOfWork(),
        parent_order_repo=parents,
        made_item_demand_repo=floor.made_demands,
        made_item_allocation_repo=floor.made_allocations,
        **lifecycle_collaborators(
            floor.orders,
            floor.lots,
            floor.bus,
            orders=parents,
            order_items=lines,
            made_demands=floor.made_demands,
            made_allocations=floor.made_allocations,
        ),
        source_item_demand_repo=FakeSourceItemDemandRepository(),
        source_item_allocation_repo=FakeSourceItemAllocationRepository(),
        bought_allocation_repo=FakeBoughtItemAllocationRepository(),
    ).execute(planner, lot.id, CompleteLotCommand())

    assert result.quantity == 6.0
    assert [a.quantity for a in await floor.made_allocations.get_by_lot_id(lot.id)] == [4.0]
    # Nothing was cut, so nobody is told a demand ended short.
    assert not any(isinstance(e, LotEndedShort) for e in floor.bus.published)
    # The order closed at its 6 pieces is sized to them: 10 minutes of setup
    # and 2 minutes a piece for the position's one step.
    assert (running.quantity, running.estimated_duration_minutes) == (6.0, 22)


async def _force_complete(floor: Floor, lot_id: int, **repos: object):
    planner = make_user(permissions=[Permission.WRITE_LOTS, Permission.MANAGE_LOTS])
    lines, parents = FakeOrderItemRepository(), FakeOrderRepository([])
    return await CompleteLot(
        floor.lots,
        floor.orders,
        lines,
        event_bus=floor.bus,
        uow=FakeUnitOfWork(),
        parent_order_repo=parents,
        made_item_demand_repo=floor.made_demands,
        made_item_allocation_repo=floor.made_allocations,
        **{
            "source_item_demand_repo": floor.source_demands,
            "source_item_allocation_repo": floor.source_allocations,
            "bought_allocation_repo": FakeBoughtItemAllocationRepository(),
            **repos,
        },  # type: ignore[arg-type]
        **lifecycle_collaborators(
            floor.orders,
            floor.lots,
            floor.bus,
            orders=parents,
            order_items=lines,
            made_demands=floor.made_demands,
            made_allocations=floor.made_allocations,
        ),
    ).execute(planner, lot_id, CompleteLotCommand())


async def test_force_complete_records_the_pieces_it_drops_between_positions() -> None:
    """Position 1 finished 6 pieces and position 2 only 2 of them, so the
    lot closes at 2 and the 4 between the positions are dropped on file."""
    floor = Floor(positions=2)
    lot = await floor.lot(10.0)
    first, second = await floor.positions(lot.id)
    await floor.order(first, processed=6.0)
    await floor.order(second, processed=2.0)
    await floor.settle(lot.id)

    result = await _force_complete(floor, lot.id)

    assert result.quantity == 2.0
    dropped = [e for e in await floor.lots.get_events(lot.id) if e.event_type == "wip_dropped"]
    assert [(e.entity_id, e.payload) for e in dropped] == [
        (first.id, {"position_sequence": 1, "pieces": 4.0})
    ]


async def test_force_complete_records_raw_material_that_arrived_and_was_not_used() -> None:
    """Ten blanks arrived in stock for a lot whose first position used 6;
    the lot is force-completed and the 4 left over are on file."""
    floor = Floor(positions=1)
    lot = await floor.lot(10.0)
    [only] = await floor.positions(lot.id)
    await floor.order(only, processed=6.0)
    demand = make_source_item_demand(id=lot.input_demand_id or 77, lot_id=lot.id)
    demand.quantity, demand.unit, demand.status = 10.0, "PCS", SourceItemDemandStatus.ALLOCATED
    lot.input_demand_id = demand.id
    await floor.lots.save(lot)
    demands = FakeSourceItemDemandRepository([demand])
    stock = SourceItemDemandAllocation(demand_item_id=demand.id, order_item_id=None, quantity=10.0)
    await floor.settle(lot.id)

    await _force_complete(
        floor,
        lot.id,
        source_item_demand_repo=demands,
        source_item_allocation_repo=FakeSourceItemAllocationRepository([stock]),
        bought_allocation_repo=FakeBoughtItemAllocationRepository(),
    )

    left = [
        e for e in await floor.lots.get_events(lot.id) if e.event_type == "raw_material_left_over"
    ]
    assert [e.payload for e in left] == [{"quantity": 4.0, "unit": "PCS"}]
    settled = await demands.get_by_id(demand.id)
    assert settled is not None and settled.fulfilled_manually_at is not None


async def test_canceling_an_order_keeps_the_pieces_it_completed_on_the_position() -> None:
    """The pieces a canceled order completed exist and still count for its
    position, which stays INTERNAL for them, and are not planned again."""
    floor = Floor(positions=1)
    lot = await floor.lot(10.0)
    [only] = await floor.positions(lot.id)
    order = await floor.order(only, processed=3.0)
    await floor.settle(lot.id)

    await CancelProductionOrder(
        floor.orders,
        floor.lots,
        event_bus=floor.bus,
        uow=FakeUnitOfWork(),
        **lifecycle_collaborators(floor.orders, floor.lots, floor.bus),
    ).execute(floor.planner, order.id, CancelProductionOrderCommand())

    assert order.status == ProductionOrderStatus.CANCELED.value
    [position] = await floor.positions(lot.id)
    assert (position.kind, position.status, position.quantity_completed) == (
        "internal",
        "partially_completed",
        3.0,
    )
    assert compute_position_remaining(position.quantity, None, position.production_orders) == 7.0


# ── Structure, reorder and scrap decide through the table ───────────────


class _RecordingIntents:
    """Stands in for the lot intent table and records which actions a guard
    asked it about, answering with the real table."""

    def __init__(self) -> None:
        self.asked: list[LifecycleAction] = []

    def check(self, action, lot, context, user):  # type: ignore[no-untyped-def]
        self.asked.append(action)
        return LOT_INTENTS.check(action, lot, context, user)


@pytest.fixture
def recorded(monkeypatch: pytest.MonkeyPatch) -> _RecordingIntents:
    recording = _RecordingIntents()
    monkeypatch.setattr(lot_rules, "LOT_INTENTS", recording)
    return recording


def test_structure_edits_and_appends_ask_the_lot_intent_table(
    recorded: _RecordingIntents,
) -> None:
    planner = make_user(permissions=[Permission.WRITE_LOTS])

    LotRules.assert_can_edit_structure(planner, _lot(LotStatus.PLANNED))
    LotRules.assert_can_append_position(planner, _lot(LotStatus.PLANNED))
    LotRules.assert_can_edit_structure(
        planner, _lot(LotStatus.PLANNED), LifecycleAction.REORDER_POSITIONS
    )

    assert recorded.asked == [
        LifecycleAction.EDIT_STRUCTURE,
        LifecycleAction.EDIT_STRUCTURE,
        LifecycleAction.REORDER_POSITIONS,
    ]


def test_a_scrap_asks_the_lot_intent_table(recorded: _RecordingIntents) -> None:
    lot = _lot(LotStatus.IN_PROGRESS)
    position = make(
        LotPosition, id=1, lot_id=1, sequence=1, kind=LotPositionKind.INTERNAL, quantity=10.0
    )

    assert_scrap_allowed(lot, position, 1.0, ACTOR, raw_material_arrived=None)

    assert recorded.asked == [LifecycleAction.SCRAP]


@pytest.mark.parametrize("status", [LotStatus.COMPLETED, LotStatus.CANCELED, LotStatus.SCRAPPED])
def test_a_terminal_lot_takes_no_structure_edit_or_reorder(status: LotStatus) -> None:
    planner = make_user(permissions=[Permission.WRITE_LOTS])

    for action in (LifecycleAction.EDIT_STRUCTURE, LifecycleAction.REORDER_POSITIONS):
        with pytest.raises(LotStructureLockedError):
            LotRules.assert_can_edit_structure(planner, _lot(status), action)
    with pytest.raises(LotStructureLockedError):
        LotRules.assert_can_append_position(planner, _lot(status))


def test_a_held_lot_takes_no_scrap_until_it_is_resumed() -> None:
    position = make(
        LotPosition, id=1, lot_id=1, sequence=1, kind=LotPositionKind.INTERNAL, quantity=10.0
    )

    with pytest.raises(LotNotScrappableError):
        assert_scrap_allowed(
            _lot(LotStatus.ON_HOLD, held_at=HELD), position, 1.0, ACTOR, raw_material_arrived=None
        )


def test_a_lost_disposition_at_receipt_stays_allowed_on_a_held_lot() -> None:
    """A goods-receipt LOST disposition records what arrived; it is not the
    scrap intent, so a hold does not refuse it."""
    position = make(
        LotPosition, id=1, lot_id=1, sequence=1, kind=LotPositionKind.EXTERNAL, quantity=10.0
    )

    assert_delivery_disposition_allowed(_lot(LotStatus.ON_HOLD, held_at=HELD), position)
