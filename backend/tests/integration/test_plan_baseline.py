"""
The nightly baseline and the purge of expired plans against the real
repositories on SQLite: one baseline per tenant day with the open orders
inside the committed horizon and every open lot, nothing before half past
midnight, and plans older than the retention purged.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.inbound.api.deps.production import build_purge_expired_plans
from src.modules.fulfillment.adapters.inbound.api.deps.production import build_record_plan_baseline
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_plan_repository import (
    SqlAlchemyProductionPlanRepository,
)
from src.modules.fulfillment.domain.entities.production_plan import ProductionPlan
from src.modules.fulfillment.domain.value_objects.plan_kind import PlanKind
from src.modules.fulfillment.domain.value_objects.plan_kind import PlanStatus
from src.modules.fulfillment.domain.value_objects.plan_kind import SchedulerMode
from src.modules.platform.const import SERVER_DEFAULT_TIMEZONE
from src.shared_kernel.domain.services.clock import as_utc
from tests.integration import _lifecycle_seed as seed

ZONE = ZoneInfo(SERVER_DEFAULT_TIMEZONE)
# A Thursday morning in the tenant's zone; the default week works Monday
# to Friday, so five working days reach the next Wednesday.
THURSDAY = date(2026, 3, 5)
MORNING = datetime(2026, 3, 5, 6, 0, tzinfo=ZONE)
# Stored datetimes are UTC; SQLite would keep only the wall clock of a
# value in another zone and hand it back naive.
HORIZON_END = datetime(2026, 3, 12, 0, 0, tzinfo=ZONE).astimezone(UTC)


async def _seed_two_orders(db: AsyncSession) -> tuple[int, int, int]:
    """A lot with one order inside the horizon and one beyond it. Returns the
    lot id and the two order ids."""
    lot = await seed.lot(db, "in_progress")
    position = await seed.position(db, lot, "internal", "pending")
    inside = await seed.production_order(
        db,
        position,
        "queued",
        machine_id=1,
        queue_sequence=1,
        planned_start=HORIZON_END - timedelta(days=2),
        planned_end=HORIZON_END - timedelta(days=2) + timedelta(hours=3),
    )
    beyond = await seed.production_order(
        db,
        position,
        "queued",
        machine_id=1,
        queue_sequence=2,
        planned_start=HORIZON_END + timedelta(hours=8),
        planned_end=HORIZON_END + timedelta(hours=10),
    )
    await seed.settle(db)
    return lot.id, inside.id, beyond.id


async def test_the_baseline_records_the_horizon_and_every_open_lot(db: AsyncSession) -> None:
    lot_id, inside_id, _beyond_id = await _seed_two_orders(db)

    plan = await build_record_plan_baseline(db).execute(now=MORNING)

    assert plan is not None
    stored = await SqlAlchemyProductionPlanRepository(db).get_by_day(PlanKind.BASELINE, THURSDAY)
    assert stored is not None
    assert [e.production_order_id for e in stored.entries] == [inside_id]
    [lot] = stored.lots
    assert lot.lot_id == lot_id
    # The lot finishes with its later order, beyond the horizon.
    assert lot.planned_finish is not None
    assert as_utc(lot.planned_finish) == HORIZON_END + timedelta(hours=10)
    assert (stored.kind, stored.scheduler_mode, stored.status) == (
        PlanKind.BASELINE,
        SchedulerMode.CURRENT,
        PlanStatus.RECORDED,
    )


async def test_a_day_gets_one_baseline(db: AsyncSession) -> None:
    await _seed_two_orders(db)
    await build_record_plan_baseline(db).execute(now=MORNING)

    again = await build_record_plan_baseline(db).execute(now=MORNING + timedelta(hours=4))

    assert again is None


async def test_nothing_is_recorded_before_half_past_midnight(db: AsyncSession) -> None:
    await _seed_two_orders(db)

    early = await build_record_plan_baseline(db).execute(
        now=datetime(2026, 3, 5, 0, 15, tzinfo=ZONE)
    )

    assert early is None
    assert not await SqlAlchemyProductionPlanRepository(db).exists_for(PlanKind.BASELINE, THURSDAY)


async def test_plans_older_than_the_retention_are_purged(db: AsyncSession) -> None:
    repo = SqlAlchemyProductionPlanRepository(db)

    def baseline(day: date) -> ProductionPlan:
        return ProductionPlan(
            id=0,
            kind=PlanKind.BASELINE,
            scheduler_mode=SchedulerMode.CURRENT,
            engine="forward_walk",
            engine_version="1",
            plan_day=day,
            created=MORNING,
            status=PlanStatus.RECORDED,
        )

    # The seeded retention is 400 days.
    await repo.add(baseline(THURSDAY - timedelta(days=401)))
    await repo.add(baseline(THURSDAY - timedelta(days=400)))
    await db.commit()

    deleted = await build_purge_expired_plans(db).execute(now=MORNING)

    assert deleted == 1
    assert not await repo.exists_for(PlanKind.BASELINE, THURSDAY - timedelta(days=401))
    assert await repo.exists_for(PlanKind.BASELINE, THURSDAY - timedelta(days=400))
