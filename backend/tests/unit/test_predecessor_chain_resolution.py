"""
A QA order (position 3, machine-less) must not get a planned date before
its own predecessor's end. If position 2 (an EXTERNAL position on a draft
order with no dates) resolved to "no constraint" and contributed nothing,
the forward walk would floor position 3 at the shared no-machine queue's
cursor, which can be an unrelated lot's planned_end.

Covers both halves of the rule:
  - _context.resolve_predecessor_ready_at (application layer): chain
    resolution over every earlier position of the lot, not just the one
    immediately before this order's own position.
  - scheduling.advance_machine_queue (domain layer): an unknowable
    chain with nothing physically available yet gets no planned date at
    all, rather than a fictional one.

No database, no HTTP, pure functions/fakes only.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.application.services.scheduling_context import build_contexts
from src.modules.fulfillment.application.services.scheduling_context import build_order_context
from src.modules.fulfillment.application.services.scheduling_context import (
    compute_conflicts_for_orders,
)
from src.modules.fulfillment.application.services.scheduling_context import (
    resolve_predecessor_ready_at,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.services.scheduling import advance_machine_queue
from src.modules.fulfillment.domain.services.scheduling import build_machine_calendar
from src.modules.fulfillment.domain.services.scheduling import compute_order_conflicts
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.domain.value_objects.schedule_conflict import ScheduleConflictReason
from tests.unit._tenant_settings import TenantSettings

WEEKDAY_HOURS = {0: 480, 1: 480, 2: 480, 3: 480, 4: 480, 5: 0, 6: 0}
MONDAY = date(2026, 8, 3)


# ── Fixtures ─────────────────────────────────────────────────────────────


def make_step(position_id: int) -> LotStep:
    return LotStep(
        id=position_id,
        created=date(2026, 1, 1),
        note=None,
        estimated_setup_minutes=10,
        estimated_minutes_per_piece=2.0,
        sequence=1,
        creator_id=1,
        fabrication_method_id=1,
        lot_id=82,
        position_id=position_id,
        source_process_id=None,
    )


def make_position(
    id: int,
    sequence: int,
    kind: LotPositionKind,
    status: LotPositionStatus = LotPositionStatus.ORDERED_OR_QUEUED,
    quantity_completed: float = 0.0,
) -> LotPosition:
    return LotPosition(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        sequence=sequence,
        kind=kind,
        status=status,
        quantity=10.0,
        quantity_completed=quantity_completed,
        note=None,
        creator_id=1,
        lot_id=82,
        steps=[make_step(id)],
    )


def make_lot() -> ProductionLot:
    return ProductionLot(
        id=82,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        lot_number="LN-26-00027",
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
        machine_id=None,
        lot_position_id=lot_position_id,
    )


def make_order_item(
    id: int,
    lot_position_id: int,
    delivery_date: date | None = None,
    expected_delivery_date: date | None = None,
    ready_for_pickup_date: date | None = None,
) -> OrderItem:
    return OrderItem(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        status=OrderItemStatus.DELIVERED if delivery_date else OrderItemStatus.PENDING,
        quantity=10.0,
        quantity_delivered=10.0 if delivery_date else 0.0,
        unit="pcs",
        items_per_unit=1.0,
        price=None,
        note=None,
        ordered_date=date(2026, 1, 1),
        expected_delivery_date=expected_delivery_date,
        delivery_date=delivery_date,
        storage_place=None,
        expected_pickup_date=None,
        ready_for_pickup_date=ready_for_pickup_date,
        position=1,
        creator_id=1,
        orderer_id=None,
        receiver_id=None,
        bought_item_id=None,
        order_id=1,
        supplier_id=1,
        project_id=1,
        line_type=OrderLineType.SOURCE,
        lot_position_id=lot_position_id,
        source_item_id=1,
    )


class FakeOrderRepo:
    def __init__(self, orders: list[ProductionOrder]) -> None:
        self._orders = orders
        self.batch_calls = 0

    async def get_by_lot_position_id(self, lot_position_id: int) -> list[ProductionOrder]:
        return [o for o in self._orders if o.lot_position_id == lot_position_id]

    async def get_by_lot_position_ids(self, lot_position_ids: list[int]) -> list[ProductionOrder]:
        self.batch_calls += 1
        return [o for o in self._orders if o.lot_position_id in lot_position_ids]


class FakeOrderItemRepo:
    def __init__(self, items: list[OrderItem]) -> None:
        self._by_position = {i.lot_position_id: i for i in items if i.lot_position_id is not None}
        self.single_calls = 0
        self.batch_calls = 0

    async def get_by_lot_position_id(self, lot_position_id: int) -> OrderItem | None:
        self.single_calls += 1
        return self._by_position.get(lot_position_id)

    async def get_by_lot_position_ids(self, lot_position_ids: list[int]) -> list[OrderItem]:
        self.batch_calls += 1
        return [self._by_position[pid] for pid in lot_position_ids if pid in self._by_position]

    async def get_by_ids(self, ids: list[int]) -> list[OrderItem]:
        return []


class FakeLotRepoForContexts:
    """Unlike FakeEmptyRepo (always None), returns a real lot by id; needed
    by build_contexts, which looks lots up via repos.lots.get_by_id(order.
    lot_id) rather than having them passed in directly."""

    def __init__(self, lot: ProductionLot) -> None:
        self._lot = lot

    async def get_by_id(self, lot_id: int) -> ProductionLot | None:
        return self._lot if lot_id == self._lot.id else None

    async def get_by_ids(self, ids: list[int]) -> list:
        found = [await self.get_by_id(i) for i in ids]
        return [item for item in found if item is not None]

    async def get_raw_material_arrived_quantity(self, demand_id: int) -> float:
        return 0.0

    async def get_raw_material_arrived_quantities(self, demand_ids: list[int]) -> dict[int, float]:
        return {d: await self.get_raw_material_arrived_quantity(d) for d in demand_ids}


class FakeEmptyRepo:
    async def get_by_id(self, id: int):
        return None

    async def get_raw_material_arrived_quantity(self, demand_id: int) -> float:
        return 0.0

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


def build_repos(
    orders: list[ProductionOrder] | None = None,
    order_items: list[OrderItem] | None = None,
) -> SchedulingRepos:
    empty = FakeEmptyRepo()
    return SchedulingRepos(
        orders=FakeOrderRepo(orders) if orders is not None else empty,  # type: ignore[arg-type]
        lots=empty,  # type: ignore[arg-type]
        order_items=FakeOrderItemRepo(order_items) if order_items is not None else empty,  # type: ignore[arg-type]
        source_item_demands=empty,  # type: ignore[arg-type]
        source_item_allocations=empty,  # type: ignore[arg-type]
        made_item_allocations=empty,  # type: ignore[arg-type]
        made_item_demands=empty,  # type: ignore[arg-type]
        settings=TenantSettings(),  # type: ignore[arg-type]
    )


# ── resolve_predecessor_ready_at: chain resolution ──────────────────────


async def test_transitive_floor_is_max_of_all_open_earlier_positions():
    """Position 1 (internal, dated 2026-01-10) and position 2 (internal,
    dated later, 2026-01-13) are both open; position 3's predecessor_
    ready_at must be the LATER of the two, not just the immediate
    predecessor's (position 2's) own date, proving the max() floor spans
    the whole chain."""
    pos1 = make_position(id=1, sequence=1, kind=LotPositionKind.INTERNAL)
    pos2 = make_position(id=2, sequence=2, kind=LotPositionKind.INTERNAL)
    pos3 = make_position(id=3, sequence=3, kind=LotPositionKind.INTERNAL)
    lot = make_lot()
    lot.positions = [pos1, pos2, pos3]

    order1 = make_order(id=10, lot_position_id=1)
    order1.planned_end = datetime(2026, 1, 10, 14, 0)
    order2 = make_order(id=20, lot_position_id=2)
    order2.planned_end = datetime(2026, 1, 13, 9, 0)
    repos = build_repos(orders=[order1, order2])

    ready_at, chain_unknown = await resolve_predecessor_ready_at(pos3, lot, repos, zone=UTC)

    assert ready_at == date(2026, 1, 13)
    assert chain_unknown is False


async def test_earlier_signal_reaches_through_a_terminal_middle_position():
    """Position 1 is dated (2026-01-10) and open; position 2 sits between
    it and position 3 but is COMPLETED (terminal); it must be skipped
    entirely, not block position 1's date from reaching position 3."""
    pos1 = make_position(id=1, sequence=1, kind=LotPositionKind.INTERNAL)
    pos2 = make_position(
        id=2,
        sequence=2,
        kind=LotPositionKind.INTERNAL,
        status=LotPositionStatus.COMPLETED,
    )
    pos3 = make_position(id=3, sequence=3, kind=LotPositionKind.INTERNAL)
    lot = make_lot()
    lot.positions = [pos1, pos2, pos3]

    order1 = make_order(id=10, lot_position_id=1)
    order1.planned_end = datetime(2026, 1, 10, 14, 0)
    # Position 2 has no sibling orders at all (fully wrapped up, nothing to
    # report), which would otherwise read as "no date signal" if it weren't
    # skipped for being terminal.
    repos = build_repos(orders=[order1])

    ready_at, chain_unknown = await resolve_predecessor_ready_at(pos3, lot, repos, zone=UTC)

    assert ready_at == date(2026, 1, 10)
    assert chain_unknown is False


async def test_terminal_only_earlier_position_is_skipped_without_marking_unknown():
    """A single terminal earlier position with nothing else in the chain:
    contributes no date, but must NOT flag the chain unknown either;
    it's done, there's nothing left to wait on."""
    pos1 = make_position(
        id=1,
        sequence=1,
        kind=LotPositionKind.EXTERNAL,
        status=LotPositionStatus.CANCELED,
    )
    pos2 = make_position(id=2, sequence=2, kind=LotPositionKind.INTERNAL)
    lot = make_lot()
    lot.positions = [pos1, pos2]
    repos = build_repos()

    ready_at, chain_unknown = await resolve_predecessor_ready_at(pos2, lot, repos, zone=UTC)

    assert ready_at is None
    assert chain_unknown is False


async def test_unassigned_earlier_position_marks_chain_unknown():
    """Nothing committed on position 1 yet (still UNASSIGNED); position 2
    cannot know when its input will be ready, the chain is unknowable."""
    pos1 = make_position(id=1, sequence=1, kind=LotPositionKind.UNASSIGNED)
    pos2 = make_position(id=2, sequence=2, kind=LotPositionKind.INTERNAL)
    lot = make_lot()
    lot.positions = [pos1, pos2]
    repos = build_repos()

    ready_at, chain_unknown = await resolve_predecessor_ready_at(pos2, lot, repos, zone=UTC)

    assert ready_at is None
    assert chain_unknown is True


async def test_regression_ln_26_00027_undated_draft_position_marks_chain_unknown():
    """Position 1 (internal) is dated,
    position 2 (external, a draft order with no delivery/pickup/expected
    dates at all) is open but has no date signal of its own. Position 3
    (the QA position) must see position 1's date (it's still known) AND
    have the chain marked unknown (position 2's own finish time isn't)."""
    pos1 = make_position(id=1, sequence=1, kind=LotPositionKind.INTERNAL)
    pos2 = make_position(id=2, sequence=2, kind=LotPositionKind.EXTERNAL)
    pos3 = make_position(id=3, sequence=3, kind=LotPositionKind.INTERNAL)
    lot = make_lot()
    lot.positions = [pos1, pos2, pos3]

    order1 = make_order(id=10, lot_position_id=1)
    order1.planned_end = datetime(2026, 8, 25, 16, 0)
    draft_item = make_order_item(id=50, lot_position_id=2)  # no dates at all
    repos = build_repos(orders=[order1], order_items=[draft_item])

    ready_at, chain_unknown = await resolve_predecessor_ready_at(pos3, lot, repos, zone=UTC)

    assert ready_at == date(2026, 8, 25)  # position 1's own signal still reaches through
    assert chain_unknown is True  # but the overall chain is unknowable


# ── End-to-end: build_order_context + advance_machine_queue ─────────────


async def test_end_to_end_unknowable_chain_without_upstream_input_yields_no_planned_dates():
    """The whole scenario via the real pipeline: build_order_context
    resolves predecessor_chain_unknown=True for the QA order (position 3),
    upstream_input_available is False (position 2 has delivered nothing,
    quantity_completed=0), so advance_machine_queue must refuse to invent
    a planned date."""
    pos1 = make_position(id=1, sequence=1, kind=LotPositionKind.INTERNAL)
    pos2 = make_position(id=2, sequence=2, kind=LotPositionKind.EXTERNAL, quantity_completed=0.0)
    pos3 = make_position(id=3, sequence=3, kind=LotPositionKind.INTERNAL)
    lot = make_lot()
    lot.positions = [pos1, pos2, pos3]

    order1 = make_order(id=10, lot_position_id=1)
    order1.planned_end = datetime(2026, 8, 25, 16, 0)
    draft_item = make_order_item(id=50, lot_position_id=2)  # no dates, nothing delivered
    qa_order = make_order(id=30, lot_position_id=3)
    repos = build_repos(orders=[order1, qa_order], order_items=[draft_item])

    ctx = await build_order_context(
        qa_order, lot, machine=None, repos=repos, target_date=None, zone=UTC
    )

    assert ctx.predecessor_chain_unknown is True
    assert ctx.upstream_input_available is False

    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time(), tzinfo=UTC)
    # A stale cursor from an unrelated lot/order sharing the no-machine
    # queue, exactly the "cursor-fiction" a date must not come from.
    stale_cursor = datetime(2026, 8, 20, 10, 0, tzinfo=UTC)

    planned_start, planned_end, next_cursor = advance_machine_queue(
        ctx, stale_cursor, calendar, now
    )

    assert planned_start is None
    assert planned_end is None
    assert next_cursor == stale_cursor  # cursor not consumed, like PAUSED


async def test_end_to_end_unknowable_chain_with_upstream_input_available_still_gets_dates():
    """Same chain, but position 2 already delivered part of its quantity
    (quantity_completed > 0); parts are physically waiting at position 3,
    so a now/cursor-floored forecast is honest and must still be produced."""
    pos1 = make_position(id=1, sequence=1, kind=LotPositionKind.INTERNAL)
    pos2 = make_position(id=2, sequence=2, kind=LotPositionKind.EXTERNAL, quantity_completed=4.0)
    pos3 = make_position(id=3, sequence=3, kind=LotPositionKind.INTERNAL)
    lot = make_lot()
    lot.positions = [pos1, pos2, pos3]

    order1 = make_order(id=10, lot_position_id=1)
    order1.planned_end = datetime(2026, 8, 25, 16, 0)
    draft_item = make_order_item(id=50, lot_position_id=2)
    qa_order = make_order(id=30, lot_position_id=3)
    repos = build_repos(orders=[order1, qa_order], order_items=[draft_item])

    ctx = await build_order_context(
        qa_order, lot, machine=None, repos=repos, target_date=None, zone=UTC
    )

    assert ctx.predecessor_chain_unknown is True
    assert ctx.upstream_input_available is True

    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time(), tzinfo=UTC)

    planned_start, planned_end, next_cursor = advance_machine_queue(ctx, None, calendar, now)

    assert planned_start is not None
    assert planned_end is not None
    assert next_cursor == planned_end


# ── build_contexts: batch order-item prefetch (Fix 2) ───────────────────


async def test_build_contexts_batches_order_item_lookups_across_the_whole_pass():
    """A lot with an EXTERNAL position 1 feeding TWO later, open positions
    (2 and 3); each one's own chain walk needs position 1's order item.
    Before the batch prefetch, that was one live get_by_lot_position_id
    call per order whose chain passes through position 1 (2 calls here,
    one per order); the batch path must issue exactly one
    get_by_lot_position_ids call for the whole await build_contexts() pass
    instead, and never fall back to the live single-position query at
    all."""
    pos1 = make_position(id=1, sequence=1, kind=LotPositionKind.EXTERNAL)
    pos2 = make_position(id=2, sequence=2, kind=LotPositionKind.INTERNAL)
    pos3 = make_position(id=3, sequence=3, kind=LotPositionKind.INTERNAL)
    lot = make_lot()
    lot.positions = [pos1, pos2, pos3]

    order_item = make_order_item(id=50, lot_position_id=1, delivery_date=date(2026, 1, 10))
    order_a = make_order(id=20, lot_position_id=2)
    order_a.lot_id = lot.id
    order_b = make_order(id=30, lot_position_id=3)
    order_b.lot_id = lot.id

    order_item_repo = FakeOrderItemRepo([order_item])
    order_repo = FakeOrderRepo([order_a, order_b])
    repos = SchedulingRepos(
        orders=order_repo,  # type: ignore[arg-type]
        lots=FakeLotRepoForContexts(lot),  # type: ignore[arg-type]
        order_items=order_item_repo,  # type: ignore[arg-type]
        source_item_demands=FakeEmptyRepo(),  # type: ignore[arg-type]
        source_item_allocations=FakeEmptyRepo(),  # type: ignore[arg-type]
        made_item_allocations=FakeEmptyRepo(),  # type: ignore[arg-type]
        made_item_demands=FakeEmptyRepo(),  # type: ignore[arg-type]
        settings=TenantSettings(),  # type: ignore[arg-type]
    )

    contexts = await build_contexts([order_a, order_b], repos, zone=UTC)

    assert order_item_repo.batch_calls == 1
    assert order_item_repo.single_calls == 0

    ctx_b_batch = next(c for c in contexts if c.order_id == order_b.id)
    assert ctx_b_batch.predecessor_ready_at == date(2026, 1, 10)

    # The single-order path (build_order_context called directly, with no
    # prefetched dict) falls back to the live per-position query. Same
    # inputs, so it must land on exactly the same context values as the
    # batch path above.
    ctx_b_direct = await build_order_context(
        order_b, lot, machine=None, repos=repos, target_date=None, zone=UTC
    )
    assert ctx_b_batch == ctx_b_direct


async def test_compute_conflicts_for_orders_batches_order_item_lookups_across_the_whole_pass():
    """Same N+1 shape as build_contexts (see the test above), but for the
    read-side batch path: compute_conflicts_for_orders is what
    GetLot/GetLots/GetProductionOrder(s)/get_qa_tasks all funnel through,
    so without the prefetch a list view would pay one live order-item
    query per EXTERNAL/MIXED earlier position, per order, on every page
    read. _prefetch_sibling_orders_by_position's own docstring names
    compute_conflicts_for_orders as an intended prefetch caller; this
    mirrors that wiring for order items too."""
    pos1 = make_position(id=1, sequence=1, kind=LotPositionKind.EXTERNAL)
    pos2 = make_position(id=2, sequence=2, kind=LotPositionKind.INTERNAL)
    pos3 = make_position(id=3, sequence=3, kind=LotPositionKind.INTERNAL)
    lot = make_lot()
    lot.positions = [pos1, pos2, pos3]

    order_item = make_order_item(id=50, lot_position_id=1, delivery_date=date(2026, 1, 10))
    order_a = make_order(id=20, lot_position_id=2)
    order_a.lot_id = lot.id
    order_b = make_order(id=30, lot_position_id=3)
    order_b.lot_id = lot.id

    order_item_repo = FakeOrderItemRepo([order_item])
    order_repo = FakeOrderRepo([order_a, order_b])
    repos = SchedulingRepos(
        orders=order_repo,  # type: ignore[arg-type]
        lots=FakeLotRepoForContexts(lot),  # type: ignore[arg-type]
        order_items=order_item_repo,  # type: ignore[arg-type]
        source_item_demands=FakeEmptyRepo(),  # type: ignore[arg-type]
        source_item_allocations=FakeEmptyRepo(),  # type: ignore[arg-type]
        made_item_allocations=FakeEmptyRepo(),  # type: ignore[arg-type]
        made_item_demands=FakeEmptyRepo(),  # type: ignore[arg-type]
        settings=TenantSettings(),  # type: ignore[arg-type]
    )
    machine_repo = FakeEmptyRepo()  # neither order has a machine_id, never consulted

    conflicts = await compute_conflicts_for_orders([order_a, order_b], repos, machine_repo)  # type: ignore[arg-type]

    assert order_item_repo.batch_calls == 1
    assert order_item_repo.single_calls == 0

    # The unprefetched path (build_order_context called directly, live
    # per-position fallback) plus the same NO_MACHINE_ASSIGNED addition
    # compute_conflicts_for_orders itself applies, must produce identical
    # conflicts to the batch path above.
    ctx_b_direct = await build_order_context(
        order_b, lot, machine=None, repos=repos, target_date=None, zone=UTC
    )
    expected_conflicts_b = compute_order_conflicts(
        ctx_b_direct, order_b.planned_end, datetime.now(UTC)
    )
    if order_b.machine_id is None and not ctx_b_direct.is_manual_step:
        expected_conflicts_b = [
            *expected_conflicts_b,
            ScheduleConflictReason.NO_MACHINE_ASSIGNED.value,
        ]
    assert conflicts[order_b.id] == expected_conflicts_b
