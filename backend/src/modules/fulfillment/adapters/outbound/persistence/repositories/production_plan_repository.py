"""
SQLAlchemy implementation of IProductionPlanRepository. The order and lot
rows are written with their plan and read back by its id; they have no ORM
relationship, so a plan read never loads them by accident.
"""

from datetime import date

from sqlalchemy import delete
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.models.production_plan_model import (
    ProductionPlanEntryOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_plan_model import (
    ProductionPlanLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_plan_model import (
    ProductionPlanOrmModel,
)
from src.modules.fulfillment.domain.entities.production_plan import ProductionPlan
from src.modules.fulfillment.domain.entities.production_plan import ProductionPlanEntry
from src.modules.fulfillment.domain.entities.production_plan import ProductionPlanLot
from src.modules.fulfillment.domain.value_objects.plan_kind import PlanKind
from src.modules.fulfillment.domain.value_objects.plan_kind import PlanStatus
from src.modules.fulfillment.domain.value_objects.plan_kind import SchedulerMode


def _plan_to_entity(
    orm: ProductionPlanOrmModel,
    entries: list[ProductionPlanEntryOrmModel],
    lots: list[ProductionPlanLotOrmModel],
) -> ProductionPlan:
    return ProductionPlan(
        id=orm.id,
        public_id=orm.public_id,
        kind=PlanKind(orm.kind),
        scheduler_mode=SchedulerMode(orm.scheduler_mode),
        engine=orm.engine,
        engine_version=orm.engine_version,
        plan_day=orm.plan_day,
        created=orm.created,
        status=PlanStatus(orm.status),
        entries=[_entry_to_entity(e) for e in entries],
        lots=[_lot_to_entity(lot) for lot in lots],
    )


def _entry_to_entity(orm: ProductionPlanEntryOrmModel) -> ProductionPlanEntry:
    return ProductionPlanEntry(
        id=orm.id,
        public_id=orm.public_id,
        production_order_id=orm.production_order_id,
        lot_position_id=orm.lot_position_id,
        lot_id=orm.lot_id,
        position_sequence=orm.position_sequence,
        production_order_number=orm.production_order_number,
        machine_id=orm.machine_id,
        machine_pool_id=orm.machine_pool_id,
        queue_sequence=orm.queue_sequence,
        planned_start=orm.planned_start,
        planned_end=orm.planned_end,
        duration_minutes=orm.duration_minutes,
    )


def _lot_to_entity(orm: ProductionPlanLotOrmModel) -> ProductionPlanLot:
    return ProductionPlanLot(
        id=orm.id,
        public_id=orm.public_id,
        lot_id=orm.lot_id,
        lot_number=orm.lot_number,
        target_date=orm.target_date,
        planned_finish=orm.planned_finish,
    )


class SqlAlchemyProductionPlanRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def add(self, plan: ProductionPlan) -> ProductionPlan:
        orm = ProductionPlanOrmModel(
            created=plan.created,
            kind=plan.kind.value,
            scheduler_mode=plan.scheduler_mode.value,
            engine=plan.engine,
            engine_version=plan.engine_version,
            plan_day=plan.plan_day,
            status=plan.status.value,
        )
        self._db.add(orm)
        await self._db.flush()
        entries = [
            ProductionPlanEntryOrmModel(
                plan_id=orm.id,
                production_order_id=e.production_order_id,
                lot_position_id=e.lot_position_id,
                lot_id=e.lot_id,
                position_sequence=e.position_sequence,
                production_order_number=e.production_order_number,
                machine_id=e.machine_id,
                machine_pool_id=e.machine_pool_id,
                queue_sequence=e.queue_sequence,
                planned_start=e.planned_start,
                planned_end=e.planned_end,
                duration_minutes=e.duration_minutes,
            )
            for e in plan.entries
        ]
        lots = [
            ProductionPlanLotOrmModel(
                plan_id=orm.id,
                lot_id=lot.lot_id,
                lot_number=lot.lot_number,
                target_date=lot.target_date,
                planned_finish=lot.planned_finish,
            )
            for lot in plan.lots
        ]
        self._db.add_all([*entries, *lots])
        await self._db.flush()
        return _plan_to_entity(orm, entries, lots)

    async def get_by_day(self, kind: PlanKind, plan_day: date) -> ProductionPlan | None:
        orm = await self._db.scalar(
            select(ProductionPlanOrmModel)
            .where(
                ProductionPlanOrmModel.kind == kind.value,
                ProductionPlanOrmModel.plan_day == plan_day,
            )
            .order_by(ProductionPlanOrmModel.id.desc())
            .limit(1)
        )
        if orm is None:
            return None
        entries = (
            await self._db.scalars(
                select(ProductionPlanEntryOrmModel)
                .where(ProductionPlanEntryOrmModel.plan_id == orm.id)
                .order_by(ProductionPlanEntryOrmModel.id)
            )
        ).all()
        lots = (
            await self._db.scalars(
                select(ProductionPlanLotOrmModel)
                .where(ProductionPlanLotOrmModel.plan_id == orm.id)
                .order_by(ProductionPlanLotOrmModel.id)
            )
        ).all()
        return _plan_to_entity(orm, list(entries), list(lots))

    async def exists_for(self, kind: PlanKind, plan_day: date) -> bool:
        count = await self._db.scalar(
            select(func.count(ProductionPlanOrmModel.id)).where(
                ProductionPlanOrmModel.kind == kind.value,
                ProductionPlanOrmModel.plan_day == plan_day,
            )
        )
        return bool(count)

    async def delete_before(self, plan_day: date) -> int:
        plan_ids = list(
            (
                await self._db.scalars(
                    select(ProductionPlanOrmModel.id).where(
                        ProductionPlanOrmModel.plan_day < plan_day
                    )
                )
            ).all()
        )
        if not plan_ids:
            return 0
        # Deleted explicitly, since SQLite does not cascade without its
        # foreign key pragma.
        await self._db.execute(
            delete(ProductionPlanEntryOrmModel).where(
                ProductionPlanEntryOrmModel.plan_id.in_(plan_ids)
            )
        )
        await self._db.execute(
            delete(ProductionPlanLotOrmModel).where(ProductionPlanLotOrmModel.plan_id.in_(plan_ids))
        )
        await self._db.execute(
            delete(ProductionPlanOrmModel).where(ProductionPlanOrmModel.id.in_(plan_ids))
        )
        return len(plan_ids)
