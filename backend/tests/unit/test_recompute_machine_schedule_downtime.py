"""
RecomputeMachineSchedule.execute_all() with a machine downtime wired in:
the shared calendar builder (_context.build_machine_calendars) must
subtract the downtime's overlap from the affected day before the forward
walk runs, so an in-progress order's computed end moves out and the next
queued order on the same machine shifts with it.

Anchored to the real current date (datetime.now(UTC).date()) rather than a
fixed historical one, since RecomputeMachineSchedule samples `now`
internally rather than accepting it as a parameter; the fixture's
calendar gives every day of the week the same available minutes so the
scenario is independent of which real weekday the suite happens to run
on. The downtime is open and started two days ago, so it zeros out all of
today's capacity (scheduling.apply_downtimes floors an open
downtime's window at today's start regardless of the exact time of day)
without depending on the exact wall-clock moment RecomputeMachineSchedule
happens to sample `now` at, only on today's date.

Fakes are imported from tests/unit/auto_plan/, same convention
test_recompute_machine_schedule.py/test_recompute_chain_propagation.py
already follow, plus a small FakeDowntimeRepo added here.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta

from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.domain.entities.admin_settings.production import (
    AdminProductionSettings,
)
from src.modules.fulfillment.domain.entities.machine_downtime import MachineDowntime
from src.modules.fulfillment.domain.value_objects.machine_downtime_reason import (
    MachineDowntimeReason,
)
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.schedule_conflict import ScheduleConflictReason
from tests.unit._tenant_settings import TenantSettings
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

# Every day 8h, unlike DEFAULT_WEEKLY_HOURS/WEEKDAY_HOURS elsewhere (which
# leave weekends at 0); this scenario spills a single day's work into
# "tomorrow", so it must stay independent of whichever real weekday the
# suite happens to run on.
ALL_DAYS_8H = {0: 480, 1: 480, 2: 480, 3: 480, 4: 480, 5: 480, 6: 480}


class FakeDowntimeRepo:
    def __init__(self, downtimes: list[MachineDowntime]) -> None:
        self.downtimes = downtimes

    async def get_overlapping(
        self, machine_ids: list[int], start: datetime, end: datetime
    ) -> list[MachineDowntime]:
        return [
            d
            for d in self.downtimes
            if d.machine_id in machine_ids
            and d.started_at < end
            and (d.ended_at is None or d.ended_at > start)
        ]

    async def get_open_by_machine_ids(
        self, machine_ids: list[int], *, started_by: datetime | None = None
    ) -> dict[int, MachineDowntime]:
        return {
            d.machine_id: d
            for d in self.downtimes
            if d.machine_id in machine_ids
            and d.ended_at is None
            and (started_by is None or d.started_at <= started_by)
        }


def make_downtime(
    machine_id: int, started_at: datetime, ended_at: datetime | None
) -> MachineDowntime:
    return MachineDowntime(
        id=1,
        created=started_at,
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


async def test_downtime_pushes_an_in_progress_order_and_its_successor_out_to_the_next_day():
    today = datetime.now(UTC).date()
    tomorrow = today + timedelta(days=1)

    machine = make_machine(1)
    lot_a = make_lot(1)
    lot_b = make_lot(2)
    order_a = make_order(
        1,
        lot_id=1,
        machine_id=1,
        duration_minutes=300,
        queue_sequence=1,
        status=ProductionOrderStatus.IN_PROGRESS,
        actual_start=datetime(today.year, today.month, today.day, 8, 0, tzinfo=UTC),
    )
    order_b = make_order(2, lot_id=2, machine_id=1, duration_minutes=60, queue_sequence=2)

    # Open since two days ago; apply_downtimes floors an open downtime's
    # window at today's start regardless of when it actually began, so
    # this zeros out the whole of today (0 of 480 minutes) without
    # depending on the exact wall-clock moment `now` is sampled at.
    # Tomorrow is untouched (an open downtime never projects past today),
    # so order_a's 300 minutes land there in full.
    downtime_repo = FakeDowntimeRepo(
        [
            make_downtime(
                1,
                started_at=datetime(today.year, today.month, today.day, 8, 0, tzinfo=UTC)
                - timedelta(days=2),
                ended_at=None,
            )
        ]
    )

    order_repo = FakeOrderRepo([order_a, order_b])
    repos = SchedulingRepos(
        orders=order_repo,  # type: ignore[arg-type]
        lots=FakeLotRepo([lot_a, lot_b]),  # type: ignore[arg-type]
        order_items=FakeEmptyRepo(),  # type: ignore[arg-type]
        source_item_demands=FakeEmptyRepo(),  # type: ignore[arg-type]
        source_item_allocations=FakeEmptyRepo(),  # type: ignore[arg-type]
        made_item_allocations=FakeEmptyRepo(),  # type: ignore[arg-type]
        made_item_demands=FakeEmptyRepo(),  # type: ignore[arg-type]
        settings=TenantSettings(),  # type: ignore[arg-type]
    )
    settings_repo = FakeSettingsRepo(
        AdminProductionSettings(
            id=1,
            production_order_number_format="PO-{seq:04d}",
            default_weekly_hours=ALL_DAYS_8H,
            default_external_lead_days=3,
            response_time_days=0,
            require_qa=False,
        ),
        # "Today" is the UTC date here, so the tenant is in UTC too.
        default_timezone="UTC",
    )
    recompute = RecomputeMachineSchedule(
        repos,
        FakeMachineRepo([machine]),
        FakeCalendarRepo(),
        settings_repo,
        FakePoolRepo([]),
        downtime_repo,  # type: ignore[arg-type]
        uow=FakeUnitOfWork(),  # type: ignore[arg-type]
    )

    result = await recompute.execute_all()

    # Today is fully zeroed, so order_a's 300 minutes are placed from
    # tomorrow's own day start (08:00) instead of today.
    expected_end = datetime(tomorrow.year, tomorrow.month, tomorrow.day, 13, 0, tzinfo=UTC)
    assert order_repo.orders[1].planned_end == expected_end
    assert order_repo.orders[2].planned_start == expected_end
    assert order_repo.orders[2].planned_end == expected_end + timedelta(hours=1)

    # Both orders sat on the down machine at run time, so both carry the
    # conflict badge in the walk's own result, regardless of their dates.
    scheduled_by_id = {s.order_id: s for s in result.by_machine[1]}
    assert ScheduleConflictReason.MACHINE_DOWN.value in scheduled_by_id[1].conflicts
    assert ScheduleConflictReason.MACHINE_DOWN.value in scheduled_by_id[2].conflicts
