"""
Records the nightly baseline: the dates the active scheduler persisted for
the orders inside the committed horizon, and when every open lot was planned
to finish. It runs once per tenant day, after the walk that follows midnight
has moved "today", and it never dates anything itself, so the baseline is
the plan as the floor saw it that morning in either scheduler mode.

The caller holds the baseline's advisory lock, so only one worker records
the day; the one-baseline-per-day index still refuses a second row should
two ever race.
"""

from datetime import datetime
from datetime import time

from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.application.services.scheduling_context import (
    describe_lot_target_dates,
)
from src.modules.fulfillment.application.services.scheduling_context import holiday_dates
from src.modules.fulfillment.domain.entities.production_plan import FORWARD_WALK_ENGINE
from src.modules.fulfillment.domain.entities.production_plan import FORWARD_WALK_ENGINE_VERSION
from src.modules.fulfillment.domain.entities.production_plan import ProductionPlan
from src.modules.fulfillment.domain.entities.production_plan import ProductionPlanLot
from src.modules.fulfillment.domain.policies.wait_after import position_wait_after_minutes
from src.modules.fulfillment.domain.policies.wait_after import step_waits
from src.modules.fulfillment.domain.services.plan_baseline import baseline_entries
from src.modules.fulfillment.domain.services.plan_baseline import commit_horizon_end
from src.modules.fulfillment.domain.services.plan_baseline import lot_planned_finishes
from src.modules.fulfillment.domain.services.scheduling.machine_calendar import (
    build_machine_calendar,
)
from src.modules.fulfillment.domain.value_objects.plan_kind import PlanKind
from src.modules.fulfillment.domain.value_objects.plan_kind import PlanStatus
from src.modules.fulfillment.domain.value_objects.plan_kind import SchedulerMode
from src.modules.fulfillment.ports.outbound.repositories.machine_calendar_repository import (
    IMachineCalendarRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_plan_repository import (
    IProductionPlanRepository,
)
from src.modules.platform.application.services.tenant_timezone import tenant_zone
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.services.clock import as_utc
from src.shared_kernel.domain.services.clock import now_utc

# The earliest local time of day the baseline is recorded. The periodic walk
# runs right after midnight, and this leaves it time to date the new day.
BASELINE_EARLIEST = time(0, 30)


class RecordPlanBaseline:
    def __init__(
        self,
        plan_repo: IProductionPlanRepository,
        repos: SchedulingRepos,
        calendar_repo: IMachineCalendarRepository,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._plans = plan_repo
        self._repos = repos
        self._calendars = calendar_repo
        self._uow = uow

    async def execute(self, now: datetime | None = None) -> ProductionPlan | None:
        """Records today's baseline and returns it, or None when today has
        one already or it is too early in the day."""
        zone = await tenant_zone(self._repos.settings)
        local_now = as_utc(now or now_utc()).astimezone(zone)
        today = local_now.date()
        if local_now.time() < BASELINE_EARLIEST:
            return None
        if await self._plans.exists_for(PlanKind.BASELINE, today):
            return None

        planning = await self._repos.settings.get_planning()
        production = await self._repos.settings.get_production()
        calendar = build_machine_calendar(
            production.default_weekly_hours,
            None,
            {},
            zone=zone,
            holidays=await holiday_dates(self._calendars),
        )
        horizon_end = commit_horizon_end(today, planning.commit_horizon_working_days, calendar)

        orders = await self._repos.orders.get_all_non_terminal()
        lot_ids = sorted({order.lot_id for order in orders if order.lot_id})
        lots = await self._repos.lots.get_by_ids(lot_ids) if lot_ids else []
        positions = [position for lot in lots for position in lot.positions]
        lot_orders = (
            await self._repos.orders.get_by_lot_position_ids([p.id for p in positions])
            if positions
            else []
        )
        finishes = lot_planned_finishes(
            lot_orders,
            {p.id: p.lot_id for p in positions},
            {p.id: position_wait_after_minutes(p.kind, step_waits(p.steps)) for p in positions},
        )
        targets = await describe_lot_target_dates(lots, self._repos)

        plan = await self._plans.add(
            ProductionPlan(
                id=0,
                kind=PlanKind.BASELINE,
                scheduler_mode=SchedulerMode.CURRENT,
                engine=FORWARD_WALK_ENGINE,
                engine_version=FORWARD_WALK_ENGINE_VERSION,
                plan_day=today,
                created=as_utc(local_now),
                status=PlanStatus.RECORDED,
                entries=baseline_entries(orders, horizon_end),
                lots=[
                    ProductionPlanLot(
                        id=0,
                        lot_id=lot.id,
                        lot_number=lot.lot_number,
                        target_date=targets.get(lot.id, (None, None, None))[0],
                        planned_finish=finishes.get(lot.id),
                    )
                    for lot in lots
                ],
            )
        )
        await self._uow.commit()
        log.info(
            f"Recorded the baseline of {today.isoformat()}: {len(plan.entries)} order(s) "
            f"before {horizon_end.isoformat()}, {len(plan.lots)} lot(s)."
        )
        return plan
