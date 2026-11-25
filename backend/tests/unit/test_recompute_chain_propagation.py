"""
Application-level test of in-run chain propagation: a single
RecomputeMachineSchedule.execute_all() call must move an entire lot chain,
not just its first link, and GetScheduleBoard must report the exact same
dates from the same underlying data. Rebuilds a three-position reference
scenario (an INTERNAL position on a pool, an EXTERNAL position with a
typed but stale supplier date, and a manual INTERNAL QA position with its
own stale stored dates from an earlier recompute) and asserts the QA
order lands the day after the pool position's freshly recomputed end,
governed by that INTERNAL position rather than the EXTERNAL position's
earlier typed date.

Fakes are imported from tests/unit/auto_plan/, same convention
test_recompute_machine_schedule.py already follows, plus a small
FakeOrderItemRepo added here for the EXTERNAL position's typed date.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta

from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.application.use_cases.production_schedule.get_schedule_board import (
    GetScheduleBoard,
)
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from tests.unit._scheduling_clock import pin_scheduling_clock
from tests.unit._tenant_settings import TenantSettings
from tests.unit.auto_plan._helpers import DEFAULT_WEEKLY_HOURS
from tests.unit.auto_plan._helpers import make_lot
from tests.unit.auto_plan._helpers import make_machine
from tests.unit.auto_plan._helpers import make_pool
from tests.unit.auto_plan.fakes import FakeCalendarRepo
from tests.unit.auto_plan.fakes import FakeEmptyRepo
from tests.unit.auto_plan.fakes import FakeLotRepo
from tests.unit.auto_plan.fakes import FakeMachineRepo
from tests.unit.auto_plan.fakes import FakeOrderRepo
from tests.unit.auto_plan.fakes import FakePoolRepo
from tests.unit.auto_plan.fakes import FakeSettingsRepo
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.scheduling_service._helpers import MONDAY

# The walk plans no queued order before now, and the fixtures are dated in
# the week of MONDAY.
_BEFORE_THE_FIXTURES = datetime(2026, 7, 1, tzinfo=UTC)


class FakeOrderItemRepo:
    """Minimal IOrderItemRepository fake: only the two lookups the
    scheduler's chain-walk actually calls (build_contexts always prefetches
    in batch, so get_by_lot_position_ids is the one that matters, the
    singular lookup is kept too for any direct caller)."""

    def __init__(self, items: list[OrderItem]) -> None:
        self.items = items

    async def get_by_lot_position_id(self, lot_position_id: int) -> OrderItem | None:
        return next((i for i in self.items if i.lot_position_id == lot_position_id), None)

    async def get_by_lot_position_ids(self, lot_position_ids: list[int]) -> list[OrderItem]:
        return [i for i in self.items if i.lot_position_id in lot_position_ids]


class FakeLotRepoWithPositions(FakeLotRepo):
    """Extends FakeLotRepo with single and batched position reads. The
    forecast write itself goes through the base fake's
    save_position_forecasts. The reference scenario's lot objects
    are held by reference in self.lots, so mutating a position already
    mutates the lot itself, no separate storage needed."""

    async def get_position_by_id(self, position_id: int) -> LotPosition | None:
        for lot in self.lots.values():
            for position in lot.positions:
                if position.id == position_id:
                    return position
        return None

    async def get_positions_by_ids(self, position_ids: list[int]) -> list:
        positions = [await self.get_position_by_id(i) for i in position_ids]
        return [p for p in positions if p is not None]

    async def save_position(self, position: LotPosition) -> LotPosition:
        return position


def _build_reference_scenario() -> tuple[
    RecomputeMachineSchedule, GetScheduleBoard, FakeOrderRepo, FakeLotRepoWithPositions
]:
    """A 3-position lot: position 1 INTERNAL on a one-member pool (an
    old, now-stale planned_end from a previous recompute), position 2
    EXTERNAL with a typed expected delivery date far earlier than
    position 1's fresh end, position 3 INTERNAL manual QA (also with a
    stale stored planned_start/end from that same previous recompute).
    Raw material for position 1 is already available; position 1's
    not_before models "material just became available", the trigger for
    this recompute, deterministic and independent of wall-clock `now`,
    matching how every other date in this scenario is asserted relative
    to position 1's own recomputed end rather than to a fixed calendar
    date."""
    machine = make_machine(1)
    pool = make_pool(100, machine_ids=[1])
    lot = make_lot(1)  # material_arrived=True by default: input_demand_id=1

    old_stale = MONDAY - timedelta(days=14)

    position_1 = LotPosition(
        id=10,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        sequence=1,
        kind=LotPositionKind.INTERNAL,
        status=LotPositionStatus.ORDERED_OR_QUEUED,
        quantity=10.0,
        quantity_completed=0.0,
        note=None,
        creator_id=1,
        lot_id=1,
        steps=[
            LotStep(
                id=10,
                created=date(2026, 1, 1),
                note=None,
                estimated_setup_minutes=0,
                estimated_minutes_per_piece=1.0,
                sequence=1,
                creator_id=1,
                fabrication_method_id=1,
                lot_id=1,
                position_id=10,
                source_process_id=None,
            )
        ],
    )
    position_2 = LotPosition(
        id=20,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        sequence=2,
        kind=LotPositionKind.EXTERNAL,
        status=LotPositionStatus.ORDERED_OR_QUEUED,
        quantity=10.0,
        quantity_completed=0.0,
        note=None,
        creator_id=1,
        lot_id=1,
        steps=[
            LotStep(
                id=20,
                created=date(2026, 1, 1),
                note=None,
                estimated_setup_minutes=0,
                estimated_minutes_per_piece=0.0,
                sequence=3,
                creator_id=1,
                fabrication_method_id=3,
                lot_id=1,
                position_id=20,
                source_process_id=None,
                # No supplier override on the order item below, so this is
                # what resolve_position_lead_days sums for position 2's
                # own forecast.
                fabrication_method_lead_time_days=4,
            )
        ],
    )
    position_3 = LotPosition(
        id=30,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        sequence=3,
        kind=LotPositionKind.INTERNAL,
        status=LotPositionStatus.ORDERED_OR_QUEUED,
        quantity=10.0,
        quantity_completed=0.0,
        note=None,
        creator_id=1,
        lot_id=1,
        steps=[
            LotStep(
                id=30,
                created=date(2026, 1, 1),
                note=None,
                estimated_setup_minutes=0,
                estimated_minutes_per_piece=2.0,
                sequence=2,
                creator_id=1,
                fabrication_method_id=2,
                lot_id=1,
                position_id=30,
                source_process_id=None,
                fabrication_method_requires_machine=False,  # routes to the manual queue
            )
        ],
    )
    lot.positions = [position_1, position_2, position_3]

    order_1 = ProductionOrder(
        id=1,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        production_order_number="PO-0001",
        status=ProductionOrderStatus.QUEUED,
        priority=UrgencyClass.NORMAL,
        pinned=False,
        queue_sequence=1,
        quantity=10.0,
        quantity_completed=0.0,
        estimated_duration_minutes=200,
        note=None,
        # The old schedule this position had before the material that
        # unblocks it arrived; what position 3's context would read as
        # position 1's readiness if it weren't refreshed in-run.
        planned_start=datetime.combine(old_stale, time(8), tzinfo=UTC),
        planned_end=datetime.combine(old_stale, time(8), tzinfo=UTC) + timedelta(minutes=200),
        # Models "material just became available today"; deliberately a
        # planner-style override so this order's own placement never
        # depends on the real wall-clock `now`.
        not_before=MONDAY,
        actual_start=None,
        actual_end=None,
        creator_id=1,
        machine_id=None,
        machine_pool_id=pool.id,
        lot_position_id=position_1.id,
        lot_id=1,
    )
    order_3 = ProductionOrder(
        id=3,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        production_order_number="PO-0003",
        status=ProductionOrderStatus.QUEUED,
        priority=UrgencyClass.NORMAL,
        pinned=False,
        queue_sequence=1,
        quantity=10.0,
        quantity_completed=0.0,
        estimated_duration_minutes=20,
        note=None,
        planned_start=datetime.combine(old_stale, time(8), tzinfo=UTC) + timedelta(days=1),
        planned_end=datetime.combine(old_stale, time(8), tzinfo=UTC)
        + timedelta(days=1, minutes=20),
        not_before=None,
        actual_start=None,
        actual_end=None,
        creator_id=1,
        machine_id=None,
        machine_pool_id=None,
        lot_position_id=position_3.id,
        lot_id=1,
    )
    order_item = OrderItem(
        id=1,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=None,
        changes=[],
        status=OrderItemStatus.ORDERED,
        quantity=10.0,
        quantity_delivered=0.0,
        unit="pcs",
        items_per_unit=1.0,
        price=None,
        note=None,
        ordered_date=None,
        # Far earlier than position 1's fresh end; must lose the max()
        # to position 1, not govern position 3's readiness on its own.
        expected_delivery_date=MONDAY - timedelta(days=20),
        delivery_date=None,
        storage_place=None,
        expected_pickup_date=None,
        ready_for_pickup_date=None,
        position=1,
        creator_id=1,
        orderer_id=None,
        receiver_id=None,
        bought_item_id=None,
        order_id=1,
        supplier_id=1,
        project_id=1,
        line_type=OrderLineType.MADE,
        lot_position_id=position_2.id,
        source_item_id=None,
    )

    order_repo = FakeOrderRepo([order_1, order_3])
    repos = SchedulingRepos(
        orders=order_repo,  # type: ignore[arg-type]
        lots=FakeLotRepoWithPositions([lot]),  # type: ignore[arg-type]
        order_items=FakeOrderItemRepo([order_item]),  # type: ignore[arg-type]
        source_item_demands=FakeEmptyRepo(),  # type: ignore[arg-type]
        source_item_allocations=FakeEmptyRepo(),  # type: ignore[arg-type]
        made_item_allocations=FakeEmptyRepo(),  # type: ignore[arg-type]
        made_item_demands=FakeEmptyRepo(),  # type: ignore[arg-type]
        settings=TenantSettings(),  # type: ignore[arg-type]
    )
    machine_repo = FakeMachineRepo([machine])
    pool_repo = FakePoolRepo([pool])
    calendar_repo = FakeCalendarRepo()
    settings_repo = FakeSettingsRepo(
        AdminProductionSettings(
            id=1,
            production_order_number_format="PO-{seq:04d}",
            default_weekly_hours=DEFAULT_WEEKLY_HOURS,
            default_external_lead_days=3,
            response_time_days=1,
            require_qa=False,
        ),
        # The scenario's dates are UTC days, so the tenant is in UTC too.
        default_timezone="UTC",
    )
    uow = FakeUnitOfWork()
    recompute = RecomputeMachineSchedule(
        repos,
        machine_repo,
        calendar_repo,
        settings_repo,
        pool_repo,
        uow=uow,  # type: ignore[arg-type]
    )
    board = GetScheduleBoard(repos, machine_repo, calendar_repo, settings_repo, pool_repo)
    return recompute, board, order_repo, repos.lots  # type: ignore[return-value]


async def test_one_recompute_moves_the_qa_order_with_its_predecessor(monkeypatch):
    """The core case: one execute_all() call must place the QA
    order (position 3) right at position 1's own freshly recomputed end,
    governed by position 1's INTERNAL chain rather than left at its old stale
    date or governed by position 2's much earlier EXTERNAL typed
    date. Without in-run propagation this would need a second recompute
    to catch up."""
    pin_scheduling_clock(monkeypatch, _BEFORE_THE_FIXTURES)
    recompute, _board, order_repo, _lots = _build_reference_scenario()

    await recompute.execute_all()

    position_1_order = order_repo.orders[1]
    qa_order = order_repo.orders[3]
    assert position_1_order.planned_start is not None
    assert position_1_order.planned_end is not None
    # not_before=MONDAY dominates (no predecessor, no material forecast),
    # fits inside one 8h working day.
    assert position_1_order.planned_start == datetime.combine(MONDAY, time(8), tzinfo=UTC)
    assert position_1_order.planned_end == datetime.combine(
        MONDAY, time(8), tzinfo=UTC
    ) + timedelta(minutes=200)

    # An in-house predecessor adds no response time.
    expected_qa_start = position_1_order.planned_end
    assert qa_order.planned_start == expected_qa_start
    assert qa_order.planned_end == expected_qa_start + timedelta(minutes=20)


async def test_schedule_board_reports_the_same_qa_order_dates_as_the_persisted_recompute(
    monkeypatch,
):
    """GetScheduleBoard re-runs the identical propagated walk without
    persisting; its report for the QA order must match exactly what
    execute_all() just wrote, board and recompute must never disagree. Both
    walks read the same pinned clock, since the QA order starts at the
    moment its predecessor ends."""
    pin_scheduling_clock(monkeypatch, _BEFORE_THE_FIXTURES)
    recompute, board, order_repo, _lots = _build_reference_scenario()

    await recompute.execute_all()
    qa_order = order_repo.orders[3]

    board_result = await board.execute(MONDAY, MONDAY + timedelta(days=10))
    board_qa_orders = [o for o in board_result.unassigned if o.order_id == 3]
    assert len(board_qa_orders) == 1
    board_qa_order = board_qa_orders[0]

    assert board_qa_order.planned_start == qa_order.planned_start
    assert board_qa_order.planned_end == qa_order.planned_end


async def test_execute_all_persists_the_external_positions_forecast(monkeypatch):
    """One execute_all() call also writes position 2's own forecast: its
    step's fabrication_method_lead_time_days (4, no supplier override on
    the order item) summed onto the pickup date derived from position 1's
    freshly recomputed end. The typed expected_delivery_date on the order
    item still wins for the QA order's own readiness (see the other two
    tests in this module), but the forecast is persisted independent of
    that; the write is never conditioned on which date a successor ended
    up using."""
    pin_scheduling_clock(monkeypatch, _BEFORE_THE_FIXTURES)
    recompute, _board, _order_repo, lots = _build_reference_scenario()

    await recompute.execute_all()

    position_2 = await lots.get_position_by_id(20)
    assert position_2 is not None

    # Position 1 ends Monday (see the other tests); pickup buffers that by
    # response_time_days=1, delivery adds position 2's own lead days (4).
    expected_pickup = MONDAY + timedelta(days=1)
    expected_delivery = expected_pickup + timedelta(days=4)
    assert position_2.planned_pickup_date == expected_pickup
    assert position_2.planned_delivery_date == expected_delivery
