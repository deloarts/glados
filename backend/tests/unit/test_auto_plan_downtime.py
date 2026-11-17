"""
AutoPlan with a machine downtime wired in: a down machine is never
trial-placed, so a candidate that still has another eligible machine
lands there instead, and one that doesn't is reported skipped with
AutoPlanSkipReason.MACHINE_DOWN rather than the plain NO_ELIGIBLE_MACHINE
that reason gets when no machine was ever eligible in the first place.

Fakes are imported from tests/unit/auto_plan/, same convention
test_recompute_machine_schedule.py already follows, plus a small
FakeDowntimeRepo added here.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta

from src.modules.fulfillment.application.dto.production_schedule_dto import AutoPlanCommand
from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.application.use_cases.production_schedule.auto_plan import AutoPlan
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.entities.machine_downtime import MachineDowntime
from src.modules.fulfillment.domain.value_objects.auto_plan_skip_reason import AutoPlanSkipReason
from src.modules.fulfillment.domain.value_objects.machine_downtime_reason import (
    MachineDowntimeReason,
)
from src.shared_kernel.domain.services.clock import now_utc
from tests.unit._tenant_settings import TenantSettings
from tests.unit.auto_plan._helpers import DEFAULT_WEEKLY_HOURS
from tests.unit.auto_plan._helpers import SYSTEM_ACTOR
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


class FakeDowntimeRepo:
    def __init__(
        self,
        open_by_machine_id: dict[int, MachineDowntime],
        upcoming: list[MachineDowntime] | None = None,
    ) -> None:
        self._open_by_machine_id = open_by_machine_id
        self._upcoming = list(upcoming or [])

    async def get_open_by_machine_ids(
        self, machine_ids: list[int], *, started_by: datetime | None = None
    ) -> dict[int, MachineDowntime]:
        return {
            machine_id: downtime
            for machine_id, downtime in self._open_by_machine_id.items()
            if machine_id in machine_ids
            and (started_by is None or downtime.started_at <= started_by)
        }

    async def get_overlapping(
        self, machine_ids: list[int], start: datetime, end: datetime
    ) -> list[MachineDowntime]:
        return [
            downtime
            for downtime in [*self._open_by_machine_id.values(), *self._upcoming]
            if downtime.machine_id in machine_ids
            and downtime.started_at < end
            and (downtime.ended_at is None or downtime.ended_at > start)
        ]


def make_downtime(
    machine_id: int,
    started_at: datetime = datetime(2026, 1, 1, tzinfo=UTC),
    ended_at: datetime | None = None,
) -> MachineDowntime:
    return MachineDowntime(
        id=1,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=None,
        changes=[],
        machine_id=machine_id,
        started_at=started_at,
        ended_at=ended_at,
        reason=MachineDowntimeReason.BREAKDOWN,
        note=None,
        reported_by_id=1,
        ended_by_id=None,
    )


def build_auto_plan_with_downtime(
    lots,
    orders,
    machines,
    down_machine_ids: list[int],
    upcoming: list[MachineDowntime] | None = None,
):
    order_repo = FakeOrderRepo(orders)
    repos = SchedulingRepos(
        orders=order_repo,  # type: ignore[arg-type]
        lots=FakeLotRepo(lots),  # type: ignore[arg-type]
        order_items=FakeEmptyRepo(),  # type: ignore[arg-type]
        source_item_demands=FakeEmptyRepo(),  # type: ignore[arg-type]
        source_item_allocations=FakeEmptyRepo(),  # type: ignore[arg-type]
        made_item_allocations=FakeEmptyRepo(),  # type: ignore[arg-type]
        made_item_demands=FakeEmptyRepo(),  # type: ignore[arg-type]
        settings=TenantSettings(),  # type: ignore[arg-type]
    )
    machine_repo = FakeMachineRepo(machines)
    pool_repo = FakePoolRepo([])
    calendar_repo = FakeCalendarRepo()
    settings_repo = FakeSettingsRepo(
        AdminProductionSettings(
            id=1,
            production_order_number_format="PO-{seq:04d}",
            default_weekly_hours=DEFAULT_WEEKLY_HOURS,
            default_external_lead_days=3,
            response_time_days=0,
            require_qa=False,
        )
    )
    downtime_repo = FakeDowntimeRepo(
        {mid: make_downtime(mid) for mid in down_machine_ids}, upcoming
    )
    uow = FakeUnitOfWork()
    recompute = RecomputeMachineSchedule(
        repos,
        machine_repo,
        calendar_repo,
        settings_repo,
        pool_repo,
        downtime_repo,  # type: ignore[arg-type]
        uow=uow,  # type: ignore[arg-type]
    )
    auto_plan = AutoPlan(
        repos,
        machine_repo,
        calendar_repo,
        settings_repo,
        recompute,
        pool_repo,
        downtime_repo,  # type: ignore[arg-type]
        uow=uow,  # type: ignore[arg-type]
    )
    return auto_plan, order_repo


async def test_a_down_machine_is_skipped_in_favour_of_another_eligible_one():
    machine_down = make_machine(1)
    machine_up = make_machine(2)
    lot = make_lot(1)
    order = make_order(1, lot_id=1, machine_id=None, duration_minutes=60)

    auto_plan, order_repo = build_auto_plan_with_downtime(
        [lot], [order], [machine_down, machine_up], down_machine_ids=[1]
    )
    cmd = AutoPlanCommand(assign_machines=True)
    result = await auto_plan.execute(SYSTEM_ACTOR, cmd)

    assert result.skipped == []
    assert len(result.proposals) == 1
    assert order_repo.orders[1].machine_id == 2


async def test_an_upcoming_downtime_moves_the_order_to_a_machine_that_stays_up():
    """Machine 1 goes down within the hour for a month. It is not down yet,
    so the run still considers it, but its calendar has no room left before
    the downtime, and the order lands on machine 2."""
    lot = make_lot(1)
    order = make_order(1, lot_id=1, machine_id=None, duration_minutes=240)
    soon = now_utc() + timedelta(hours=1)
    maintenance = make_downtime(1, started_at=soon, ended_at=soon + timedelta(days=30))

    auto_plan, order_repo = build_auto_plan_with_downtime(
        [lot], [order], [make_machine(1), make_machine(2)], [], upcoming=[maintenance]
    )
    result = await auto_plan.execute(SYSTEM_ACTOR, AutoPlanCommand(assign_machines=True))

    assert result.skipped == []
    assert order_repo.orders[1].machine_id == 2


async def test_machine_down_is_reported_when_no_other_eligible_machine_remains():
    machine = make_machine(1)
    lot = make_lot(1)
    order = make_order(1, lot_id=1, machine_id=1, duration_minutes=60, queue_sequence=1)

    auto_plan, order_repo = build_auto_plan_with_downtime(
        [lot], [order], [machine], down_machine_ids=[1]
    )
    result = await auto_plan.execute(SYSTEM_ACTOR, AutoPlanCommand())

    assert result.proposals == []
    assert order_repo.orders[1].queue_sequence == 1
    assert len(result.skipped) == 1
    assert result.skipped[0].order_id == 1
    assert result.skipped[0].reason == AutoPlanSkipReason.MACHINE_DOWN.value


async def test_no_downtime_repo_behaves_exactly_like_before():
    """downtime_repo defaults to None (the optional-collaborator idiom):
    an AutoPlan built without one never excludes any machine."""
    machine = make_machine(1)
    lot = make_lot(1)
    order = make_order(1, lot_id=1, machine_id=None, duration_minutes=60)

    order_repo = FakeOrderRepo([order])
    repos = SchedulingRepos(
        orders=order_repo,  # type: ignore[arg-type]
        lots=FakeLotRepo([lot]),  # type: ignore[arg-type]
        order_items=FakeEmptyRepo(),  # type: ignore[arg-type]
        source_item_demands=FakeEmptyRepo(),  # type: ignore[arg-type]
        source_item_allocations=FakeEmptyRepo(),  # type: ignore[arg-type]
        made_item_allocations=FakeEmptyRepo(),  # type: ignore[arg-type]
        made_item_demands=FakeEmptyRepo(),  # type: ignore[arg-type]
        settings=TenantSettings(),  # type: ignore[arg-type]
    )
    machine_repo = FakeMachineRepo([machine])
    pool_repo = FakePoolRepo([])
    calendar_repo = FakeCalendarRepo()
    settings_repo = FakeSettingsRepo(
        AdminProductionSettings(
            id=1,
            production_order_number_format="PO-{seq:04d}",
            default_weekly_hours=DEFAULT_WEEKLY_HOURS,
            default_external_lead_days=3,
            response_time_days=0,
            require_qa=False,
        )
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
    auto_plan = AutoPlan(
        repos,
        machine_repo,
        calendar_repo,
        settings_repo,
        recompute,
        pool_repo,
        uow=uow,  # type: ignore[arg-type]
    )

    result = await auto_plan.execute(SYSTEM_ACTOR, AutoPlanCommand(assign_machines=True))

    assert len(result.proposals) == 1
    assert order_repo.orders[1].machine_id == 1
