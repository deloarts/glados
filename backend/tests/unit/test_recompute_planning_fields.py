"""
RecomputeMachineSchedule reads every order long before it writes, so it hands
the repository only the planned window and author of the orders whose values
the walk changed, together with the pin flag it read, and never the schedule
write that also carries machine, pool, sequence and pin. The store below hands
out copies on the walk's read, as a database does, and lets a test commit a
change between the read and the write. No database.
"""

import copy
from collections.abc import Callable
from datetime import UTC
from datetime import datetime

from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    ProductionOrderPlanningFields,
)
from tests.unit._tenant_settings import TenantSettings
from tests.unit.auto_plan._helpers import DEFAULT_WEEKLY_HOURS
from tests.unit.auto_plan._helpers import make_lot
from tests.unit.auto_plan._helpers import make_machine
from tests.unit.auto_plan._helpers import make_order
from tests.unit.auto_plan.fakes import FakeCalendarRepo
from tests.unit.auto_plan.fakes import FakeEmptyRepo
from tests.unit.auto_plan.fakes import FakeLotRepo
from tests.unit.auto_plan.fakes import FakeMachineRepo
from tests.unit.auto_plan.fakes import FakeOrderRepo
from tests.unit.auto_plan.fakes import FakePoolRepo
from tests.unit.auto_plan.fakes import FakeSettingsRepo
from tests.unit.fakes import FakeUnitOfWork

_PINNED_START = datetime(2026, 1, 5, 8, 0, tzinfo=UTC)
_PINNED_END = datetime(2026, 1, 5, 9, 0, tzinfo=UTC)
_MOVED_START = datetime(2026, 1, 7, 13, 0, tzinfo=UTC)
_MOVED_END = datetime(2026, 1, 7, 14, 0, tzinfo=UTC)


class _Store(FakeOrderRepo):
    def __init__(self, orders: list[ProductionOrder]) -> None:
        super().__init__(orders)
        self.plans: list[ProductionOrderPlanningFields] = []
        self.between_read_and_write: Callable[[], None] = lambda: None

    async def get_all_non_terminal(self) -> list[ProductionOrder]:
        read = [copy.deepcopy(o) for o in await super().get_all_non_terminal()]
        self.between_read_and_write()
        return read

    async def save_planning_fields(self, plans: list[ProductionOrderPlanningFields]) -> None:
        self.plans.extend(plans)
        await super().save_planning_fields(plans)

    async def save_schedule(self, orders: list[ProductionOrder]) -> None:
        raise AssertionError("the recompute must write the planning fields only")


def _recompute(
    store: _Store, lots: list[ProductionLot], machines: list[ProductionMachine]
) -> RecomputeMachineSchedule:
    repos = SchedulingRepos(
        orders=store,  # type: ignore[arg-type]
        lots=FakeLotRepo(lots),  # type: ignore[arg-type]
        order_items=FakeEmptyRepo(),  # type: ignore[arg-type]
        source_item_demands=FakeEmptyRepo(),  # type: ignore[arg-type]
        source_item_allocations=FakeEmptyRepo(),  # type: ignore[arg-type]
        made_item_allocations=FakeEmptyRepo(),  # type: ignore[arg-type]
        made_item_demands=FakeEmptyRepo(),  # type: ignore[arg-type]
        settings=TenantSettings(),  # type: ignore[arg-type]
    )
    settings = AdminProductionSettings(
        id=1,
        production_order_number_format="PO-{seq:04d}",
        default_weekly_hours=DEFAULT_WEEKLY_HOURS,
        default_external_lead_days=3,
        response_time_days=0,
        require_qa=False,
    )
    return RecomputeMachineSchedule(
        repos,
        FakeMachineRepo(machines),
        FakeCalendarRepo(),
        FakeSettingsRepo(settings),
        FakePoolRepo([]),
        uow=FakeUnitOfWork(),  # type: ignore[arg-type]
    )


def _queued(order_id: int, machine_id: int) -> ProductionOrder:
    return make_order(
        order_id, lot_id=order_id, machine_id=machine_id, duration_minutes=60, queue_sequence=1
    )


def _pinned(order_id: int, machine_id: int) -> ProductionOrder:
    order = make_order(
        order_id,
        lot_id=order_id,
        machine_id=machine_id,
        duration_minutes=60,
        queue_sequence=1,
        pinned=True,
        planned_start=_PINNED_START,
        planned_end=_PINNED_END,
    )
    order.planned_by_id = 77
    return order


async def test_hands_over_the_changed_planning_fields_with_the_pin_it_read():
    unpinned = _queued(1, machine_id=1)
    unpinned.planned_by_id = 55  # a stale attribution the walk clears
    store = _Store([unpinned, _pinned(2, machine_id=2)])

    result = await _recompute(
        store, [make_lot(1), make_lot(2)], [make_machine(1), make_machine(2)]
    ).execute_all()

    scheduled = result.by_machine[1][0]
    assert scheduled.planned_start is not None
    # The pinned order keeps its window and author, so nothing is written for it.
    assert store.plans == [
        ProductionOrderPlanningFields(
            order_id=1,
            planned_start=scheduled.planned_start,
            planned_end=scheduled.planned_end,
            planned_by_id=None,
            pinned_when_read=False,
            place_when_read=(1, None, 1),
        )
    ]
    assert store.orders[2].planned_by_id == 77


async def test_a_machine_change_committed_during_the_walk_survives():
    store = _Store([_queued(1, machine_id=1)])

    def reassign() -> None:
        store.orders[1].machine_id = 2
        store.orders[1].machine_pool_id = 3
        store.orders[1].queue_sequence = 5

    store.between_read_and_write = reassign

    recompute = _recompute(store, [make_lot(1)], [make_machine(1), make_machine(2)])
    result = await recompute.execute_all()

    stored = store.orders[1]
    assert (stored.machine_id, stored.machine_pool_id, stored.queue_sequence) == (2, 3, 5)
    assert stored.planned_start == result.by_machine[1][0].planned_start
    assert stored.planned_start is not None


async def test_a_window_pinned_during_the_walk_is_kept():
    store = _Store([_queued(1, machine_id=1)])

    def pin() -> None:
        store.orders[1].pinned = True
        store.orders[1].planned_start = _MOVED_START
        store.orders[1].planned_end = _MOVED_END
        store.orders[1].planned_by_id = 9

    store.between_read_and_write = pin

    await _recompute(store, [make_lot(1)], [make_machine(1)]).execute_all()

    # The plan was computed from the unpinned read; the repository skips it.
    assert [p.pinned_when_read for p in store.plans] == [False]
    stored = store.orders[1]
    assert stored.pinned is True
    assert (stored.planned_start, stored.planned_end, stored.planned_by_id) == (
        _MOVED_START,
        _MOVED_END,
        9,
    )


async def test_a_pinned_window_moved_during_the_walk_is_not_written_back():
    store = _Store([_pinned(1, machine_id=1)])

    def move() -> None:
        store.orders[1].planned_start = _MOVED_START
        store.orders[1].planned_end = _MOVED_END
        store.orders[1].planned_by_id = 9

    store.between_read_and_write = move

    await _recompute(store, [make_lot(1)], [make_machine(1)]).execute_all()

    assert store.plans == []
    stored = store.orders[1]
    assert (stored.planned_start, stored.planned_end, stored.planned_by_id) == (
        _MOVED_START,
        _MOVED_END,
        9,
    )
