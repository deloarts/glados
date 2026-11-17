"""
OrderSchedulingContext.upstream_input_available: the flag behind both the
WAITING_ON_PREDECESSOR badge and ProductionOrder.can_start for an upstream that has produced nothing
yet, as opposed to one with a merely future planned date
(predecessor_ready_at). Mirrors lot_rules.assert_position_has_available_
input, which hard-blocks Start/Resume in exactly this state; without the
flag an unassigned (hence unplanned) predecessor leaves the successor
looking startable right up until the 422.

Covers the population side in build_order_context; the conflict-emission
side lives in
tests/unit/scheduling_service/test_calendar_and_earliest_start.py::TestAwaitingPredecessorOutput
(badge emission). No database, no HTTP.
"""

from dataclasses import replace
from datetime import UTC
from datetime import date
from datetime import datetime

from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.application.services.scheduling_context import _resolve_can_start
from src.modules.fulfillment.application.services.scheduling_context import build_order_context
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.production_order_interruption import (
    ProductionOrderInterruption,
)
from src.modules.fulfillment.domain.services.scheduling import schedule_unassigned_orders
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.domain.value_objects.schedule_conflict import ScheduleConflictReason
from tests.unit._tenant_settings import TenantSettings

# ── Fixtures ──────────────────────────────────────────────────────────


def make_step(position_id: int) -> LotStep:
    return LotStep(
        id=position_id,
        created=date(2026, 1, 1),
        note=None,
        estimated_setup_minutes=10,
        estimated_minutes_per_piece=2.0,
        sequence=position_id,
        creator_id=1,
        fabrication_method_id=1,
        lot_id=1,
        position_id=position_id,
        source_process_id=None,
    )


def make_position(
    id: int,
    sequence: int,
    quantity_completed: float = 0.0,
    kind: LotPositionKind = LotPositionKind.INTERNAL,
) -> LotPosition:
    return LotPosition(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        sequence=sequence,
        kind=kind,
        status=LotPositionStatus.ORDERED_OR_QUEUED,
        quantity=10.0,
        quantity_completed=quantity_completed,
        note=None,
        creator_id=1,
        lot_id=1,
        steps=[make_step(id)],
    )


def make_lot() -> ProductionLot:
    return ProductionLot(
        id=1,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        lot_number="LOT-0001",
        quantity=10.0,
        status=LotStatus.PLANNED,
        priority=UrgencyClass.NORMAL,
        note=None,
        creator_id=1,
        made_item_id=1,
        project_id=1,
        input_demand_id=None,
    )


def make_order(id: int, lot_position_id: int) -> ProductionOrder:
    return ProductionOrder(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        production_order_number=f"PO-{id:04d}",
        status=ProductionOrderStatus.QUEUED,
        priority=UrgencyClass.NORMAL,
        pinned=False,
        queue_sequence=1,
        quantity=10.0,
        quantity_completed=0.0,
        estimated_duration_minutes=30,
        note=None,
        planned_start=None,
        planned_end=None,
        not_before=None,
        actual_start=None,
        actual_end=None,
        creator_id=1,
        machine_id=1,
        lot_position_id=lot_position_id,
    )


class FakeEmptyRepo:
    def __init__(self, raw_material_arrived: float = 0.0) -> None:
        self._raw_material_arrived = raw_material_arrived

    async def get_by_id(self, id: int):
        return None

    async def get_raw_material_arrived_quantity(self, demand_id: int) -> float:
        return self._raw_material_arrived

    async def get_raw_material_arrived_quantities(self, demand_ids: list[int]) -> dict[int, float]:
        return {d: await self.get_raw_material_arrived_quantity(d) for d in demand_ids}

    async def get_by_ids(self, ids: list[int]) -> list:
        return []

    async def get_by_lot_id(self, lot_id: int) -> list:
        return []

    async def get_by_lot_ids(self, lot_ids: list[int]) -> list:
        return [a for lot_id in lot_ids for a in await self.get_by_lot_id(lot_id)]

    async def get_by_lot_position_id(self, lot_position_id: int):
        return None

    async def get_by_demand_item_id(self, demand_item_id: int) -> list:
        return []

    async def get_by_demand_item_ids(self, demand_item_ids: list[int]) -> list:
        return [a for d in demand_item_ids for a in await self.get_by_demand_item_id(d)]


class FakeOrderRepo:
    def __init__(self, orders: list[ProductionOrder]) -> None:
        self._orders = orders

    async def get_by_lot_position_id(self, lot_position_id: int) -> list[ProductionOrder]:
        return [o for o in self._orders if o.lot_position_id == lot_position_id]


def build_repos(
    orders: list[ProductionOrder], raw_material_arrived: float = 0.0
) -> SchedulingRepos:
    empty = FakeEmptyRepo(raw_material_arrived)
    return SchedulingRepos(
        orders=FakeOrderRepo(orders),  # type: ignore[arg-type]
        lots=empty,  # type: ignore[arg-type]
        order_items=empty,  # type: ignore[arg-type]
        source_item_demands=empty,  # type: ignore[arg-type]
        source_item_allocations=empty,  # type: ignore[arg-type]
        made_item_allocations=empty,  # type: ignore[arg-type]
        made_item_demands=empty,  # type: ignore[arg-type]
        settings=TenantSettings(),  # type: ignore[arg-type]
    )


async def context_for(predecessor_completed: float, own_completed: float = 0.0):
    """A two-position lot, context built for the sequence-2 position."""
    lot = make_lot()
    lot.positions = [
        make_position(id=1, sequence=1, quantity_completed=predecessor_completed),
        make_position(id=2, sequence=2, quantity_completed=own_completed),
    ]
    order = make_order(id=20, lot_position_id=2)
    return await build_order_context(
        order, lot, machine=None, repos=build_repos([order]), target_date=None, zone=UTC
    )


# ── Tests ─────────────────────────────────────────────────────────────


class TestUpstreamInputAvailable:
    async def test_predecessor_has_produced_nothing(self):
        assert (await context_for(predecessor_completed=0.0)).upstream_input_available is False

    async def test_predecessor_has_produced_something(self):
        assert (await context_for(predecessor_completed=5.0)).upstream_input_available is True

    async def test_successor_has_already_consumed_everything_upstream_made(self):
        """Predecessor made 3, this position already completed all 3: there
        is nothing left to work on until the predecessor makes more."""
        ctx = await context_for(predecessor_completed=3.0, own_completed=3.0)
        assert ctx.upstream_input_available is False

    async def test_partially_consumed_upstream_is_still_available(self):
        ctx = await context_for(predecessor_completed=6.0, own_completed=4.0)
        assert ctx.upstream_input_available is True

    async def _sequence_one_ctx(
        self,
        *,
        input_demand_id=None,
        arrived=0.0,
        is_alteration=False,
        kind=LotPositionKind.INTERNAL,
    ):
        lot = make_lot()
        lot.input_demand_id = input_demand_id
        # is_alteration is derived from source_made_item_id.
        lot.source_made_item_id = 99 if is_alteration else None
        lot.positions = [make_position(id=1, sequence=1, kind=kind)]
        order = make_order(id=10, lot_position_id=1)
        return await build_order_context(
            order,
            lot,
            machine=None,
            repos=build_repos([order], raw_material_arrived=arrived),
            target_date=None,
            zone=UTC,
        )

    async def test_sequence_one_with_no_demand_linked_has_no_input(self):
        """Mirrors _assert_upstream_available: an INTERNAL position 1 on a
        non-alteration lot with no raw-material demand resolves a
        determinate 0.0 arrived, not "unconstrained": Start is blocked
        and can_start must say so."""
        assert (await self._sequence_one_ctx()).upstream_input_available is False

    async def test_sequence_one_with_nothing_arrived_has_no_input(self):
        ctx = await self._sequence_one_ctx(input_demand_id=99, arrived=0.0)
        assert ctx.upstream_input_available is False

    async def test_sequence_one_with_material_arrived_has_input(self):
        ctx = await self._sequence_one_ctx(input_demand_id=99, arrived=4.0)
        assert ctx.upstream_input_available is True

    async def test_an_alteration_lot_position_one_is_unconstrained(self):
        """A rework/alteration lot has no source-item demand at all: it
        legitimately passes None, i.e. unconstrained."""
        ctx = await self._sequence_one_ctx(is_alteration=True)
        assert ctx.upstream_input_available is True

    async def test_position_sequence_is_carried_for_the_badge_gate(self):
        """The badge stays off sequence 1 via position_sequence, not by
        leaving upstream_input_available True (see _static_conflicts)."""
        assert (await self._sequence_one_ctx()).position_sequence == 1
        assert (await context_for(predecessor_completed=0.0)).position_sequence == 2


class TestWaitingOnMaterialFlag:
    """The read-model side of the sequence-1 badge: WAITING_ON_MATERIAL is
    what scheduling.forward_walk._static_conflicts derives from
    upstream_input_available=False at position_sequence<=1 (see
    TestUpstreamInputAvailable above for how build_order_context populates
    that flag). _static_conflicts is private and no test in this module
    imports a scheduling private name, so this goes through
    schedule_unassigned_orders, same as
    TestAwaitingPredecessorOutput.test_machine_less_unassigned_orders_are_
    flagged_too does for WAITING_ON_PREDECESSOR in
    tests/unit/scheduling_service/test_calendar_and_earliest_start.py."""

    def _conflicts_for(self, ctx: object) -> list[str]:
        return schedule_unassigned_orders([ctx])[0].conflicts

    async def test_demand_linked_but_nothing_arrived_is_flagged(self):
        helper = TestUpstreamInputAvailable()
        ctx = await helper._sequence_one_ctx(input_demand_id=99, arrived=0.0)
        assert ScheduleConflictReason.WAITING_ON_MATERIAL.value in self._conflicts_for(ctx)

    async def test_material_arrived_is_not_flagged(self):
        helper = TestUpstreamInputAvailable()
        ctx = await helper._sequence_one_ctx(input_demand_id=99, arrived=4.0)
        assert ScheduleConflictReason.WAITING_ON_MATERIAL.value not in self._conflicts_for(ctx)

    async def test_alteration_lot_is_not_flagged(self):
        helper = TestUpstreamInputAvailable()
        ctx = await helper._sequence_one_ctx(is_alteration=True)
        assert ScheduleConflictReason.WAITING_ON_MATERIAL.value not in self._conflicts_for(ctx)

    async def test_external_sequence_one_is_not_flagged(self):
        helper = TestUpstreamInputAvailable()
        ctx = await helper._sequence_one_ctx(kind=LotPositionKind.EXTERNAL)
        assert ScheduleConflictReason.WAITING_ON_MATERIAL.value not in self._conflicts_for(ctx)


# ── can_start ─────────────────────────────────────────────────────────


class TestResolveCanStart:
    """_resolve_can_start mirrors StartProductionOrder's STATE guards (not
    its permission checks), so the board can disable Start instead of
    offering a click that is already known to 422."""

    async def _ctx_and_lot(self, *, predecessor_completed=5.0, is_manual=False):
        lot = make_lot()
        lot.positions = [
            make_position(id=1, sequence=1, quantity_completed=predecessor_completed),
            make_position(id=2, sequence=2),
        ]
        order = make_order(id=20, lot_position_id=2)
        ctx = await build_order_context(
            order, lot, machine=None, repos=build_repos([order]), target_date=None, zone=UTC
        )
        if is_manual:
            ctx = replace(ctx, is_manual_step=True)
        return order, lot, ctx

    async def test_a_queued_order_with_upstream_and_a_machine_can_start(self):
        order, lot, ctx = await self._ctx_and_lot()
        assert _resolve_can_start(order, lot, ctx) is True

    async def test_a_paused_order_can_still_start_resume(self):
        order, lot, ctx = await self._ctx_and_lot()
        order.status = ProductionOrderStatus.PAUSED
        # A paused order carries the operator's open interruption, which
        # resume closes.
        order.interruptions = [
            ProductionOrderInterruption(
                id=1,
                production_order_id=order.id,
                paused_at=datetime(2026, 1, 1, 9, tzinfo=UTC),
                resumed_at=None,
                paused_by_id=1,
                resumed_by_id=None,
                created=datetime(2026, 1, 1, 9, tzinfo=UTC),
            )
        ]
        assert _resolve_can_start(order, lot, ctx) is True

    async def test_an_in_progress_order_cannot_start_again(self):
        order, lot, ctx = await self._ctx_and_lot()
        order.status = ProductionOrderStatus.IN_PROGRESS
        assert _resolve_can_start(order, lot, ctx) is False

    async def test_a_completed_order_cannot_start(self):
        order, lot, ctx = await self._ctx_and_lot()
        order.status = ProductionOrderStatus.COMPLETED
        assert _resolve_can_start(order, lot, ctx) is False

    async def test_exhausted_upstream_blocks_start(self):
        order, lot, ctx = await self._ctx_and_lot(predecessor_completed=0.0)
        assert _resolve_can_start(order, lot, ctx) is False

    async def test_a_lot_on_hold_blocks_start(self):
        order, lot, ctx = await self._ctx_and_lot()
        lot.status = LotStatus.ON_HOLD
        assert _resolve_can_start(order, lot, ctx) is False

    async def test_no_machine_and_no_pool_blocks_start(self):
        order, lot, ctx = await self._ctx_and_lot()
        order.machine_id = None
        order.machine_pool_id = None
        assert _resolve_can_start(order, lot, ctx) is False

    async def test_a_machine_less_manual_position_can_start_without_one(self):
        """A pure-manual (or inspection) position never gets a machine."""
        order, lot, ctx = await self._ctx_and_lot(is_manual=True)
        order.machine_id = None
        order.machine_pool_id = None
        assert _resolve_can_start(order, lot, ctx) is True

    async def test_a_pool_assigned_order_can_start(self):
        order, lot, ctx = await self._ctx_and_lot()
        order.machine_id = None
        order.machine_pool_id = 7
        assert _resolve_can_start(order, lot, ctx) is True
