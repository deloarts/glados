"""SQLAlchemy repositories for production orders with their completions and
interruptions, including the queue_sequence scope locks."""

from datetime import datetime
from datetime import tzinfo
from functools import lru_cache
from typing import Any

from sqlalchemy import and_
from sqlalchemy import asc
from sqlalchemy import desc
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.catalogue.adapters.outbound.persistence.models.made_item_model import (
    MadeItemOrmModel,
)
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model import (
    LotPositionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_step_model import (
    LotStepOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.manufacturing_assessment_model import (
    ManufacturingAssessmentOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_completion_model import (
    ProductionOrderCompletionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_interruption_model import (
    ProductionOrderInterruptionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model import (
    ProductionOrderOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories._lifecycle_rows import (
    lock_rows,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories._lifecycle_rows import (
    lock_statement,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories._raw_material_coverage import (
    compute_raw_material_arrived_quantities,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.manufacturing_assessment_repository import (
    manufacturing_assessment_load_options,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.manufacturing_assessment_repository import (
    manufacturing_assessment_orm_to_entity,
)
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)
from src.modules.fulfillment.domain.entities.production_order_interruption import (
    ProductionOrderInterruption,
)
from src.modules.fulfillment.domain.value_objects.interruption_reason import InterruptionReason
from src.modules.fulfillment.domain.value_objects.production_status import (
    TERMINAL_PRODUCTION_ORDER_STATUSES,
)
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.domain.value_objects.scrap_reason import ScrapReason
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    ProductionOrderFilterDto,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    ProductionOrderPlanningFields,
)
from src.modules.platform.adapters.outbound.persistence.advisory_lock import AdvisoryLockKey
from src.modules.platform.adapters.outbound.persistence.date_range import day_after_utc
from src.modules.platform.adapters.outbound.persistence.date_range import day_start_utc
from src.modules.platform.adapters.outbound.persistence.grouped_attribute_writes import (
    flush_grouped_attribute_writes,
)
from src.modules.platform.adapters.outbound.persistence.like_escape import contains_ci
from src.modules.platform.adapters.outbound.persistence.mapping_common import changed_by_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import creator_kwargs
from src.modules.platform.adapters.outbound.persistence.number_counters import NumberFamily
from src.modules.platform.adapters.outbound.persistence.number_counters import draw_number
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.adapters.outbound.persistence.statements import fetch_page
from src.modules.platform.adapters.outbound.persistence.statements import order_term
from src.modules.platform.adapters.outbound.persistence.tenant_zone import date_filter_zone
from src.modules.platform.adapters.outbound.persistence.user_loading import load_user
from src.modules.platform.adapters.outbound.persistence.user_loading import user_orm_to_entity
from src.modules.platform.domain.exceptions import ConcurrentModificationError
from src.modules.workspace.adapters.outbound.persistence.models.project_model import ProjectOrmModel

# ── ORM <-> Entity converters ────────────────────────────────────────


def completion_orm_to_entity(orm: ProductionOrderCompletionOrmModel) -> ProductionOrderCompletion:
    return ProductionOrderCompletion(
        id=orm.id,
        public_id=orm.public_id,
        production_order_id=orm.production_order_id,
        quantity=orm.quantity,
        quantity_accepted=orm.quantity_accepted,
        quantity_rejected=orm.quantity_rejected,
        quantity_rework=orm.quantity_rework,
        quantity_scrap=orm.quantity_scrap,
        scrap_reason=_scrap_reason(orm.scrap_reason),
        reject_reason=_scrap_reason(orm.reject_reason),
        completion_date=orm.completion_date,
        note=orm.note,
        operator_id=orm.operator_id,
        recorded_by_id=orm.recorded_by_id,
        created=orm.created,
        operator=user_orm_to_entity(orm.operator) if orm.operator else None,
        recorded_by=user_orm_to_entity(orm.recorded_by) if orm.recorded_by else None,
        reverses_completion_id=orm.reverses_completion_id,
        machine_id=orm.machine_id,
    )


def _completion_entity_to_dict(c: ProductionOrderCompletion) -> dict[str, Any]:
    return {
        "production_order_id": c.production_order_id,
        "quantity": c.quantity,
        "quantity_accepted": c.quantity_accepted,
        "quantity_rejected": c.quantity_rejected,
        "quantity_rework": c.quantity_rework,
        "quantity_scrap": c.quantity_scrap,
        "scrap_reason": c.scrap_reason.value if c.scrap_reason is not None else None,
        "reverses_completion_id": c.reverses_completion_id,
        "machine_id": c.machine_id,
        "reject_reason": c.reject_reason.value if c.reject_reason is not None else None,
        "completion_date": c.completion_date,
        "note": c.note,
        "operator_id": c.operator_id,
        "recorded_by_id": c.recorded_by_id,
        "created": c.created,
    }


def interruption_orm_to_entity(
    orm: ProductionOrderInterruptionOrmModel,
) -> ProductionOrderInterruption:
    return ProductionOrderInterruption(
        id=orm.id,
        public_id=orm.public_id,
        production_order_id=orm.production_order_id,
        paused_at=orm.paused_at,
        resumed_at=orm.resumed_at,
        paused_by_id=orm.paused_by_id,
        resumed_by_id=orm.resumed_by_id,
        created=orm.created,
        reason=_interruption_reason(orm.reason),
        paused_operator_id=orm.paused_operator_id,
    )


def _scrap_reason(stored: str | None) -> ScrapReason | None:
    return ScrapReason(stored) if stored is not None else None


def _interruption_reason(stored: str) -> InterruptionReason:
    """The stored reason of an interruption. A reason no writer knows reads
    as a manual pause, so a row from another writer still pauses its order."""
    try:
        return InterruptionReason(stored)
    except ValueError:
        return InterruptionReason.MANUAL


def order_orm_to_entity(orm: ProductionOrderOrmModel) -> ProductionOrder:
    lot_position = orm.lot_position
    lot = lot_position.lot if lot_position else None
    return ProductionOrder(
        id=orm.id,
        public_id=orm.public_id,
        created=orm.created,
        changed=orm.changed,
        changes=list(orm.changes or []),
        production_order_number=orm.production_order_number,
        status=ProductionOrderStatus(orm.status),
        priority=UrgencyClass(orm.priority),
        pinned=orm.pinned,
        queue_sequence=orm.queue_sequence,
        quantity=orm.quantity,
        quantity_completed=orm.quantity_completed,
        estimated_duration_minutes=orm.estimated_duration_minutes,
        note=orm.note,
        planned_start=orm.planned_start,
        planned_end=orm.planned_end,
        not_before=orm.not_before,
        actual_start=orm.actual_start,
        actual_end=orm.actual_end,
        **creator_kwargs(orm.creator_id, orm.creator),
        **changed_by_kwargs(orm.changed_by_id, orm.changed_by),
        machine_id=orm.machine_id,
        machine_pool_id=orm.machine_pool_id,
        lot_position_id=orm.lot_position_id,
        planned_by_id=orm.planned_by_id,
        started_operator_id=orm.started_operator_id,
        planned_end_at_start=orm.planned_end_at_start,
        canceled_at=orm.canceled_at,
        edit_version=orm.edit_version,
        version=orm.version,
        planned_by=user_orm_to_entity(orm.planned_by) if orm.planned_by else None,
        started_operator=(
            user_orm_to_entity(orm.started_operator) if orm.started_operator else None
        ),
        machine_internal_name=orm.machine.internal_name if orm.machine else "",
        machine_pool_name=orm.machine_pool.name if orm.machine_pool else "",
        lot_id=lot.id if lot else 0,
        lot_number=lot.lot_number if lot else "",
        lot_public_id=lot.public_id if lot else None,
        made_item_public_id=(lot.made_item.public_id if lot and lot.made_item else None),
        project_id=(lot.project_id if lot else None),
        project_number=(lot.project.project_number if lot and lot.project else ""),
        product_id=(lot.project.product_id if lot and lot.project else None),
        product_number=(
            lot.project.product.product_number
            if lot and lot.project and lot.project.product
            else None
        ),
        made_item_part_number=((lot.made_item.part_number or "") if lot and lot.made_item else ""),
        made_item_id=(lot.made_item_id if lot else 0),
        made_item_revision=(lot.made_item.revision if lot and lot.made_item else ""),
        made_item_article_name=(lot.made_item.article_name if lot and lot.made_item else ""),
        made_item_material=(lot.made_item.material if lot and lot.made_item else None),
        made_item_mass=(lot.made_item.mass if lot and lot.made_item else None),
        made_item_base_size=(lot.made_item.base_size if lot and lot.made_item else None),
        lot_position_sequence=lot_position.sequence if lot_position else 0,
        completions=[completion_orm_to_entity(c) for c in orm.completions],
    )


# Load options for everything the mappers read. They are built lazily,
# because configuring mappers at import time fails before every model is
# registered. selectinload throughout, because it is neutral to LIMIT while
# joinedload would wrap or widen the paged query.
@lru_cache(maxsize=1)
def completion_load_options() -> tuple[ORMOption, ...]:
    """Everything completion_orm_to_entity dereferences."""
    return (
        load_user(ProductionOrderCompletionOrmModel.operator),
        load_user(ProductionOrderCompletionOrmModel.recorded_by),
    )


@lru_cache(maxsize=1)
def production_order_load_options() -> tuple[ORMOption, ...]:
    """Everything order_orm_to_entity dereferences."""
    return (
        selectinload(ProductionOrderOrmModel.lot_position)
        .selectinload(LotPositionOrmModel.lot)
        .selectinload(ProductionLotOrmModel.made_item),
        selectinload(ProductionOrderOrmModel.lot_position)
        .selectinload(LotPositionOrmModel.lot)
        .selectinload(ProductionLotOrmModel.project)
        .selectinload(ProjectOrmModel.product),
        load_user(ProductionOrderOrmModel.creator),
        load_user(ProductionOrderOrmModel.changed_by),
        load_user(ProductionOrderOrmModel.planned_by),
        load_user(ProductionOrderOrmModel.started_operator),
        selectinload(ProductionOrderOrmModel.machine),
        selectinload(ProductionOrderOrmModel.machine_pool),
        load_user(ProductionOrderOrmModel.completions, ProductionOrderCompletionOrmModel.operator),
        load_user(
            ProductionOrderOrmModel.completions, ProductionOrderCompletionOrmModel.recorded_by
        ),
    )


def _order_entity_to_dict(o: ProductionOrder) -> dict[str, Any]:
    return {
        "created": o.created,
        "changed": o.changed,
        "changes": o.changes,
        "production_order_number": o.production_order_number,
        "status": o.status.value,
        "priority": o.priority.value,
        "pinned": o.pinned,
        "queue_sequence": o.queue_sequence,
        "quantity": o.quantity,
        "quantity_completed": o.quantity_completed,
        "estimated_duration_minutes": o.estimated_duration_minutes,
        "note": o.note,
        "planned_start": o.planned_start,
        "planned_end": o.planned_end,
        "not_before": o.not_before,
        "actual_start": o.actual_start,
        "actual_end": o.actual_end,
        "creator_id": o.creator_id,
        "machine_id": o.machine_id,
        "machine_pool_id": o.machine_pool_id,
        "lot_position_id": o.lot_position_id,
        "planned_by_id": o.planned_by_id,
        "started_operator_id": o.started_operator_id,
        "planned_end_at_start": o.planned_end_at_start,
        "canceled_at": o.canceled_at,
        "edit_version": o.edit_version,
    }


# ══════════════════════════════════════════════════════════════════════
# ProductionOrder repository
# ══════════════════════════════════════════════════════════════════════


class SqlAlchemyProductionOrderRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _to_entity(
        self, orm: ProductionOrderOrmModel, *, refresh: bool = False
    ) -> ProductionOrder:
        """With refresh, the assessment and interruption rows the session
        already holds are re-read (populate_existing), as the locked read
        needs."""
        entity = order_orm_to_entity(orm)
        await self._enrich_waiting_on_raw_material([entity])
        await self._enrich_lot_position_count([entity])
        await self._enrich_assessments([entity], refresh=refresh)
        await self._enrich_interruptions([entity], refresh=refresh)
        return entity

    async def _to_entities(
        self, rows: list[ProductionOrderOrmModel], *, refresh: bool = False
    ) -> list[ProductionOrder]:
        """With refresh, the assessment and interruption rows the session
        already holds are re-read, as for _to_entity."""
        entities = [order_orm_to_entity(r) for r in rows]
        await self._enrich_waiting_on_raw_material(entities)
        await self._enrich_lot_position_count(entities)
        await self._enrich_assessments(entities, refresh=refresh)
        await self._enrich_interruptions(entities, refresh=refresh)
        return entities

    async def _enrich_interruptions(
        self, orders: list[ProductionOrder], *, refresh: bool = False
    ) -> None:
        """Interruptions for the whole page in one query."""
        order_ids = [o.id for o in orders if o.id]
        if not order_ids:
            return
        rows = (
            await self._db.scalars(
                select(ProductionOrderInterruptionOrmModel)
                .where(ProductionOrderInterruptionOrmModel.production_order_id.in_(order_ids))
                .order_by(ProductionOrderInterruptionOrmModel.id)
                .execution_options(populate_existing=refresh)
            )
        ).all()
        interruptions_by_order: dict[int, list[ProductionOrderInterruption]] = {}
        for row in rows:
            interruptions_by_order.setdefault(row.production_order_id, []).append(
                interruption_orm_to_entity(row)
            )
        for order in orders:
            order.interruptions = interruptions_by_order.get(order.id, [])

    async def _enrich_assessments(
        self, orders: list[ProductionOrder], *, refresh: bool = False
    ) -> None:
        """Assessments for the whole page in one query."""
        order_ids = [o.id for o in orders if o.id]
        if not order_ids:
            return
        rows = (
            await self._db.scalars(
                select(ManufacturingAssessmentOrmModel)
                .where(ManufacturingAssessmentOrmModel.production_order_id.in_(order_ids))
                .options(*manufacturing_assessment_load_options())
                .execution_options(populate_existing=refresh)
            )
        ).all()
        assessment_by_order = {
            row.production_order_id: manufacturing_assessment_orm_to_entity(row) for row in rows
        }
        for order in orders:
            order.assessment = assessment_by_order.get(order.id)

    async def _enrich_lot_position_count(self, orders: list[ProductionOrder]) -> None:
        """Position counts per lot in one grouped query."""
        lot_ids = {o.lot_id for o in orders if o.lot_id}
        if not lot_ids:
            return
        rows = (
            await self._db.execute(
                select(LotPositionOrmModel.lot_id, func.count(LotPositionOrmModel.id))
                .where(LotPositionOrmModel.lot_id.in_(lot_ids))
                .group_by(LotPositionOrmModel.lot_id)
            )
        ).all()
        count_by_lot = {row[0]: row[1] for row in rows}
        for order in orders:
            order.lot_position_count = count_by_lot.get(order.lot_id, 0)

    async def _enrich_waiting_on_raw_material(self, orders: list[ProductionOrder]) -> None:
        """Batched; only orders on a first position with a raw-material
        demand cost queries."""
        position_ids = [o.lot_position_id for o in orders]
        if not position_ids:
            return
        rows = (
            await self._db.execute(
                select(
                    LotPositionOrmModel.id,
                    LotPositionOrmModel.sequence,
                    ProductionLotOrmModel.input_demand_id,
                )
                .join(ProductionLotOrmModel, LotPositionOrmModel.lot_id == ProductionLotOrmModel.id)
                .where(LotPositionOrmModel.id.in_(position_ids))
            )
        ).all()
        demand_by_position = {r[0]: r[2] for r in rows if r[1] == 1 and r[2] is not None}
        if not demand_by_position:
            return

        arrived_by_demand = await compute_raw_material_arrived_quantities(
            self._db, sorted(set(demand_by_position.values()))
        )
        for order in orders:
            demand_id = demand_by_position.get(order.lot_position_id)
            if demand_id is None:
                continue
            order.waiting_on_raw_material = arrived_by_demand[demand_id] <= 0

    async def get_by_id(self, id: int) -> ProductionOrder | None:
        orm = await self._db.scalar(
            by_id(ProductionOrderOrmModel, id, *production_order_load_options()).limit(1)
        )
        return await self._to_entity(orm) if orm else None

    async def get_by_id_for_update(self, id: int) -> ProductionOrder | None:
        orm = await self._db.scalar(
            by_id(
                ProductionOrderOrmModel,
                id,
                *production_order_load_options(),
                for_update=True,
                refresh=True,
            ).limit(1)
        )
        return await self._to_entity(orm, refresh=True) if orm else None

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[ProductionOrder]:
        if not ids:
            return []
        rows = (
            await self._db.scalars(
                select(ProductionOrderOrmModel)
                .options(*production_order_load_options())
                .where(ProductionOrderOrmModel.id.in_(ids))
                .execution_options(populate_existing=refresh)
            )
        ).all()
        return await self._to_entities(list(rows), refresh=refresh)

    async def lock_for_update(self, ids: list[int]) -> None:
        await lock_rows(self._db, ProductionOrderOrmModel, ProductionOrderOrmModel.id, ids)

    async def get_by_lot_position_id(self, lot_position_id: int) -> list[ProductionOrder]:
        rows = (
            await self._db.scalars(
                select(ProductionOrderOrmModel)
                .options(*production_order_load_options())
                .where(ProductionOrderOrmModel.lot_position_id == lot_position_id)
                .order_by(ProductionOrderOrmModel.id)
            )
        ).all()
        return await self._to_entities(list(rows))

    async def get_by_lot_position_ids(
        self, lot_position_ids: list[int], *, refresh: bool = False
    ) -> list[ProductionOrder]:
        """get_by_lot_position_id for many positions in one query."""
        if not lot_position_ids:
            return []
        rows = (
            await self._db.scalars(
                select(ProductionOrderOrmModel)
                .options(*production_order_load_options())
                .where(ProductionOrderOrmModel.lot_position_id.in_(lot_position_ids))
                .order_by(ProductionOrderOrmModel.id)
                .execution_options(populate_existing=refresh)
            )
        ).all()
        return await self._to_entities(list(rows), refresh=refresh)

    async def get_by_machine_id(self, machine_id: int | None) -> list[ProductionOrder]:
        machine_filter = (
            ProductionOrderOrmModel.machine_id.is_(None)
            if machine_id is None
            else ProductionOrderOrmModel.machine_id == machine_id
        )
        rows = (
            await self._db.scalars(
                select(ProductionOrderOrmModel)
                .options(*production_order_load_options())
                .where(machine_filter)
                .order_by(ProductionOrderOrmModel.queue_sequence)
            )
        ).all()
        return await self._to_entities(list(rows))

    async def get_live_by_machine_ids(self, machine_ids: list[int | None]) -> list[ProductionOrder]:
        """The orders of the machines, None for the machine-less ones, that
        are not completed or canceled."""
        concrete_ids = sorted({m for m in machine_ids if m is not None})
        conditions = []
        if concrete_ids:
            conditions.append(ProductionOrderOrmModel.machine_id.in_(concrete_ids))
        if None in machine_ids:
            conditions.append(ProductionOrderOrmModel.machine_id.is_(None))
        if not conditions:
            return []
        rows = (
            await self._db.scalars(
                select(ProductionOrderOrmModel)
                .options(*production_order_load_options())
                .where(
                    or_(*conditions),
                    ProductionOrderOrmModel.status.notin_(TERMINAL_PRODUCTION_ORDER_STATUSES),
                )
                .order_by(ProductionOrderOrmModel.queue_sequence, ProductionOrderOrmModel.id)
            )
        ).all()
        return await self._to_entities(list(rows))

    async def count_live_by_machine_ids(self, machine_ids: list[int]) -> dict[int, int]:
        """The queued, in-progress and paused orders of each machine that has
        any, in one grouped query."""
        if not machine_ids:
            return {}
        rows = await self._db.execute(
            select(ProductionOrderOrmModel.machine_id, func.count(ProductionOrderOrmModel.id))
            .where(
                ProductionOrderOrmModel.machine_id.in_(sorted(set(machine_ids))),
                ProductionOrderOrmModel.status.notin_(TERMINAL_PRODUCTION_ORDER_STATUSES),
            )
            .group_by(ProductionOrderOrmModel.machine_id)
        )
        return {machine_id: count for machine_id, count in rows.tuples() if machine_id is not None}

    async def get_active_by_machine_ids(
        self, machine_ids: list[int]
    ) -> dict[int, list[ProductionOrder]]:
        """Active orders of many machines in one query."""
        if not machine_ids:
            return {}
        rows = (
            await self._db.scalars(
                select(ProductionOrderOrmModel)
                .options(*production_order_load_options())
                .where(
                    ProductionOrderOrmModel.machine_id.in_(machine_ids),
                    ProductionOrderOrmModel.status.in_(
                        [
                            ProductionOrderStatus.IN_PROGRESS.value,
                            ProductionOrderStatus.PAUSED.value,
                        ]
                    ),
                )
                .order_by(ProductionOrderOrmModel.queue_sequence)
            )
        ).all()
        grouped: dict[int, list[ProductionOrder]] = {}
        for order in await self._to_entities(list(rows)):
            if order.machine_id is not None:
                grouped.setdefault(order.machine_id, []).append(order)
        return grouped

    async def get_all_non_terminal(self) -> list[ProductionOrder]:
        """Every non-terminal order, unpaginated, for the global schedule
        walk. Orders of archived machines are included, since they are never
        reassigned. The rows are re-read (populate_existing), because the walk
        runs on its caller's session after that caller committed, and copies
        loaded earlier would hide what other transactions committed since. The
        interruptions are re-read too, because the walk anchors a running order
        at its last resume."""
        rows = (
            await self._db.scalars(
                select(ProductionOrderOrmModel)
                .options(*production_order_load_options())
                .where(
                    ProductionOrderOrmModel.status.notin_(
                        [
                            ProductionOrderStatus.COMPLETED.value,
                            ProductionOrderStatus.CANCELED.value,
                        ]
                    )
                )
                .order_by(ProductionOrderOrmModel.queue_sequence, ProductionOrderOrmModel.id)
                .execution_options(populate_existing=True)
            )
        ).all()
        return await self._to_entities(list(rows), refresh=True)

    async def get_multi(
        self, filters: ProductionOrderFilterDto
    ) -> tuple[int, list[ProductionOrder]]:
        q = select(ProductionOrderOrmModel)

        if filters.status:
            q = q.where(ProductionOrderOrmModel.status == filters.status)
        if filters.statuses:
            q = q.where(ProductionOrderOrmModel.status.in_(filters.statuses))
        if filters.step_role:
            # EXISTS rather than a join: a position can hold several steps and
            # a join would multiply the order row per matching step.
            q = q.where(
                select(LotStepOrmModel)
                .where(
                    LotStepOrmModel.position_id == ProductionOrderOrmModel.lot_position_id,
                    LotStepOrmModel.role == filters.step_role,
                )
                .exists()
            )
        if filters.changed_from is not None:
            q = q.where(
                func.coalesce(ProductionOrderOrmModel.changed, ProductionOrderOrmModel.created)
                >= filters.changed_from
            )
        if filters.machine_id:
            q = q.where(ProductionOrderOrmModel.machine_id == filters.machine_id)
        if filters.lot_position_id:
            q = q.where(ProductionOrderOrmModel.lot_position_id == filters.lot_position_id)
        if filters.lot_id:
            q = q.join(LotPositionOrmModel, ProductionOrderOrmModel.lot_position).where(
                LotPositionOrmModel.lot_id == filters.lot_id
            )
        if filters.search:
            term = filters.search
            q = q.where(or_(contains_ci(ProductionOrderOrmModel.production_order_number, term)))

        zone = await date_filter_zone(
            self._db,
            filters.planned_start_from,
            filters.planned_start_to,
            filters.actual_end_from,
            filters.actual_end_to,
        )
        q = self._apply_row_filters(q, filters, zone)

        _sort_column_map = {
            "id": ProductionOrderOrmModel.id,
            "production_order_number": ProductionOrderOrmModel.production_order_number,
            "created": ProductionOrderOrmModel.created,
            "queue_sequence": ProductionOrderOrmModel.queue_sequence,
            "planned_start": ProductionOrderOrmModel.planned_start,
        }
        if filters.order_by and filters.order_by in _sort_column_map:
            secondary = order_term(
                _sort_column_map[filters.order_by], filters.order_dir, default="desc"
            )
            if filters.order_by == "planned_start":
                # SQLite and Postgres disagree on where NULL sorts, and an
                # undated order belongs after every dated one either way.
                secondary = secondary.nulls_last()
        else:
            secondary = asc(ProductionOrderOrmModel.queue_sequence)

        total, rows = await fetch_page(
            self._db,
            q,
            filters.skip,
            filters.limit,
            secondary,
            desc(ProductionOrderOrmModel.id),
            options=production_order_load_options(),
        )
        return total, await self._to_entities(list(rows))

    def _apply_row_filters(self, q: Any, filters: ProductionOrderFilterDto, zone: tzinfo) -> Any:
        """The QA worklist's column filters, as one correlated EXISTS so rows
        never multiply. The date filters are days in `zone`, the tenant's."""
        order = ProductionOrderOrmModel
        if filters.step_inspection_method_ids:
            q = q.where(
                select(LotStepOrmModel)
                .where(
                    LotStepOrmModel.position_id == order.lot_position_id,
                    LotStepOrmModel.role == StepRole.INSPECTION.value,
                    LotStepOrmModel.inspection_method_id.in_(filters.step_inspection_method_ids),
                )
                .exists()
            )

        lot_predicates: list[Any] = []
        if filters.lot_number:
            lot_predicates.append(contains_ci(ProductionLotOrmModel.lot_number, filters.lot_number))
        if filters.project_number:
            lot_predicates.append(
                contains_ci(ProjectOrmModel.project_number, filters.project_number)
            )
        if filters.item_text:
            lot_predicates.append(
                or_(
                    contains_ci(MadeItemOrmModel.part_number, filters.item_text),
                    contains_ci(MadeItemOrmModel.article_name, filters.item_text),
                )
            )
        if lot_predicates:
            q = q.where(
                select(LotPositionOrmModel)
                .join(ProductionLotOrmModel, ProductionLotOrmModel.id == LotPositionOrmModel.lot_id)
                .join(ProjectOrmModel, ProjectOrmModel.id == ProductionLotOrmModel.project_id)
                .join(MadeItemOrmModel, MadeItemOrmModel.id == ProductionLotOrmModel.made_item_id)
                .where(LotPositionOrmModel.id == order.lot_position_id, *lot_predicates)
                .exists()
            )

        if filters.quantity_min is not None:
            q = q.where(order.quantity >= filters.quantity_min)
        if filters.quantity_max is not None:
            q = q.where(order.quantity <= filters.quantity_max)
        if filters.planned_start_from is not None:
            q = q.where(order.planned_start >= day_start_utc(filters.planned_start_from, zone))
        if filters.planned_start_to is not None:
            q = q.where(order.planned_start < day_after_utc(filters.planned_start_to, zone))
        if filters.actual_end_from is not None:
            q = q.where(order.actual_end >= day_start_utc(filters.actual_end_from, zone))
        if filters.actual_end_to is not None:
            q = q.where(order.actual_end < day_after_utc(filters.actual_end_to, zone))
        if filters.finished_by_ids:
            q = q.where(
                select(ProductionOrderCompletionOrmModel)
                .where(
                    ProductionOrderCompletionOrmModel.production_order_id == order.id,
                    ProductionOrderCompletionOrmModel.operator_id.in_(filters.finished_by_ids),
                )
                .exists()
            )
        return q

    async def save(self, order: ProductionOrder) -> ProductionOrder:
        orm = await self._save_order_orm(order)
        await self._db.flush()
        saved = await self._to_entity(await self._reload(orm.id))
        # The caller's copy is now at the row's new version, so the same
        # copy can be saved again in this transaction.
        order.version = saved.version
        return saved

    async def save_schedule(self, orders: list[ProductionOrder]) -> None:
        """Writes the schedule fields. The rows are locked and re-read first
        (lock_statement): the re-read refreshes rows a Core bulk update left
        stale, or an apparently unchanged value would be skipped, and the lock
        keeps the row as read until the commit, so the write skips the version
        check (grouped_attribute_writes.py). The lot position is loaded for
        change tracking."""
        if not orders:
            return
        rows = (
            await self._db.scalars(
                lock_statement(
                    ProductionOrderOrmModel,
                    ProductionOrderOrmModel.id,
                    [o.id for o in orders],
                ).options(selectinload(ProductionOrderOrmModel.lot_position))
            )
        ).all()
        rows_by_id = {row.id: row for row in rows}
        await flush_grouped_attribute_writes(
            self._db,
            (
                (
                    rows_by_id[order.id],
                    {
                        "machine_id": order.machine_id,
                        "machine_pool_id": order.machine_pool_id,
                        "queue_sequence": order.queue_sequence,
                        "pinned": order.pinned,
                        "planned_start": order.planned_start,
                        "planned_end": order.planned_end,
                        "planned_by_id": order.planned_by_id,
                    },
                )
                for order in orders
                if order.id in rows_by_id
            ),
        )

    async def save_planning_fields(self, plans: list[ProductionOrderPlanningFields]) -> None:
        """Writes the planned window and author of each plan. The rows are
        locked and re-read first (lock_statement), so a value is written only
        where it differs from the row, no other column is touched, and the
        write skips the version check under those row locks
        (grouped_attribute_writes.py). A row whose pin or queue place no longer
        matches the one the plan was computed from is skipped, since the move
        dropped its window for the next walk, and so is a row that turned
        completed or canceled since the walk read it, whose window the
        reconciler cleared.
        The lot position is loaded up front, so change tracking finds each
        row's lot without a query per row."""
        if not plans:
            return
        rows = (
            await self._db.scalars(
                lock_statement(
                    ProductionOrderOrmModel,
                    ProductionOrderOrmModel.id,
                    [plan.order_id for plan in plans],
                ).options(selectinload(ProductionOrderOrmModel.lot_position))
            )
        ).all()
        rows_by_id = {row.id: row for row in rows}
        await flush_grouped_attribute_writes(
            self._db,
            (
                (
                    rows_by_id[plan.order_id],
                    {
                        "planned_start": plan.planned_start,
                        "planned_end": plan.planned_end,
                        "planned_by_id": plan.planned_by_id,
                    },
                )
                for plan in plans
                if plan.order_id in rows_by_id
                and _unchanged_since_read(rows_by_id[plan.order_id], plan)
            ),
        )

    async def _reload(self, id: int) -> ProductionOrderOrmModel:
        """Re-selects a just-written order with its mapper's loads.
        populate_existing re-reads every column (server defaults arrive as
        with refresh) and applies the loader options to the instance that
        is already in the identity map."""
        return (
            await self._db.scalars(
                by_id(ProductionOrderOrmModel, id, *production_order_load_options(), refresh=True)
            )
        ).one()

    async def _save_order_orm(self, order: ProductionOrder) -> ProductionOrderOrmModel:
        if order.id == 0:
            orm = ProductionOrderOrmModel(**_order_entity_to_dict(order))
            self._db.add(orm)
            return orm
        # Re-read, so a value a Core bulk update changed meanwhile (the
        # queue shift of a reorder) is not taken for the one being written,
        # which would skip the write of an apparently unchanged column.
        existing = await self._db.scalar(
            select(ProductionOrderOrmModel)
            .where(ProductionOrderOrmModel.id == order.id)
            .limit(1)
            .execution_options(populate_existing=True)
        )
        if not existing:
            raise ConcurrentModificationError(
                f"ProductionOrderOrmModel id={order.id} was removed"
                " while this request worked on it; reload and try again."
            )
        # The re-read holds the row's current version, so the mapper's own
        # version check would always pass; the copy's version is compared
        # here instead.
        if order.version and existing.version != order.version:
            raise ConcurrentModificationError(
                f"Production order #{order.id} was changed while this request worked on it;"
                " reload and try again."
            )
        for k, v in _order_entity_to_dict(order).items():
            setattr(existing, k, v)
        return existing

    async def next_production_order_number(self, template: str) -> str:
        """Draws the next production order number from the production order
        counter (persistence/number_counters.py)."""
        return await draw_number(
            self._db,
            NumberFamily.PRODUCTION_ORDER,
            template,
            column=ProductionOrderOrmModel.production_order_number,
        )

    async def next_queue_sequence(
        self, machine_id: int | None, machine_pool_id: int | None = None
    ) -> int:
        if machine_id is not None:
            scope_filter = ProductionOrderOrmModel.machine_id == machine_id
        elif machine_pool_id is not None:
            scope_filter = and_(
                ProductionOrderOrmModel.machine_id.is_(None),
                ProductionOrderOrmModel.machine_pool_id == machine_pool_id,
            )
        else:
            # Neither machine nor pool.
            scope_filter = and_(
                ProductionOrderOrmModel.machine_id.is_(None),
                ProductionOrderOrmModel.machine_pool_id.is_(None),
            )
        last = (
            await self._db.execute(
                select(ProductionOrderOrmModel.queue_sequence)
                .where(scope_filter)
                .order_by(desc(ProductionOrderOrmModel.queue_sequence))
                .limit(1)
            )
        ).first()
        return (last[0] + 1) if last else 1

    async def lock_queue_scope(
        self, machine_id: int | None, machine_pool_id: int | None = None
    ) -> None:
        """Transaction-scoped advisory lock on a queue scope: +machine_id,
        -machine_pool_id, or 0 for neither, so the spaces stay disjoint."""
        if self._db.bind is None or self._db.bind.dialect.name != "postgresql":
            # SQLite has no advisory locks and nothing to serialize.
            return
        if machine_id is not None:
            scope_key = machine_id
        elif machine_pool_id is not None:
            scope_key = -machine_pool_id
        else:
            scope_key = 0
        # Waiting here is the point of the lock (auto-plan holds a scope for
        # its whole run), so lock_timeout is lifted for this one statement
        # and restored for the rest of the caller's transaction; the wait is
        # still capped by statement_timeout.
        await self._db.execute(text("SET LOCAL lock_timeout = 0"))
        await self._db.execute(
            text("SELECT pg_advisory_xact_lock(:namespace, :scope)"),
            {"namespace": int(AdvisoryLockKey.QUEUE_SEQUENCE_NAMESPACE), "scope": scope_key},
        )
        await self._db.execute(text("SET LOCAL lock_timeout TO DEFAULT"))
        # A transaction holding a queue lock may compute for a while between
        # statements (auto-plan's placement loop). It is expected to run long,
        # so the server-wide idle limit is raised for it alone; a leaked
        # session holding the lock is still closed eventually.
        await self._db.execute(text("SET LOCAL idle_in_transaction_session_timeout = '10min'"))

    async def shift_queue_sequence(self, order_ids: list[int]) -> None:
        """Sets queue_sequence to -id in one UPDATE; negative distinct
        values can never collide. The caller holds the rows locked and has
        checked them under those locks."""
        if not order_ids:
            return
        await self._db.execute(
            update(ProductionOrderOrmModel)
            .where(ProductionOrderOrmModel.id.in_(order_ids))
            .values({ProductionOrderOrmModel.queue_sequence: -ProductionOrderOrmModel.id}),
            execution_options={"synchronize_session": False},
        )
        await self._db.flush()

    # ── Completions ──────────────────────────────────────────────────

    async def get_completions(self, production_order_id: int) -> list[ProductionOrderCompletion]:
        rows = (
            await self._db.scalars(
                select(ProductionOrderCompletionOrmModel)
                .options(*completion_load_options())
                .where(ProductionOrderCompletionOrmModel.production_order_id == production_order_id)
                .order_by(ProductionOrderCompletionOrmModel.id)
            )
        ).all()
        return [completion_orm_to_entity(r) for r in rows]

    async def save_completion(
        self, completion: ProductionOrderCompletion
    ) -> ProductionOrderCompletion:
        orm = ProductionOrderCompletionOrmModel(**_completion_entity_to_dict(completion))
        self._db.add(orm)
        await self._db.flush()
        return completion_orm_to_entity(await self._reload_completion(orm.id))

    async def get_completion_by_id(self, completion_id: int) -> ProductionOrderCompletion | None:
        orm = await self._db.scalar(
            by_id(
                ProductionOrderCompletionOrmModel, completion_id, *completion_load_options()
            ).limit(1)
        )
        return completion_orm_to_entity(orm) if orm else None

    async def _reload_completion(self, id: int) -> ProductionOrderCompletionOrmModel:
        """Completion counterpart to _reload."""
        return (
            await self._db.scalars(
                by_id(
                    ProductionOrderCompletionOrmModel, id, *completion_load_options(), refresh=True
                )
            )
        ).one()


# ══════════════════════════════════════════════════════════════════════
# ProductionOrderInterruption repository, a separate class only because it
# is its own port
# ══════════════════════════════════════════════════════════════════════


class SqlAlchemyProductionOrderInterruptionRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def add(self, interruption: ProductionOrderInterruption) -> ProductionOrderInterruption:
        orm = ProductionOrderInterruptionOrmModel(
            production_order_id=interruption.production_order_id,
            paused_at=interruption.paused_at,
            resumed_at=interruption.resumed_at,
            paused_by_id=interruption.paused_by_id,
            paused_operator_id=interruption.paused_operator_id,
            resumed_by_id=interruption.resumed_by_id,
            created=interruption.created,
            reason=interruption.reason.value,
        )
        self._db.add(orm)
        await self._db.flush()
        return interruption_orm_to_entity(orm)

    async def close_open(
        self,
        production_order_id: int,
        resumed_at: datetime,
        resumed_by_id: int,
        *,
        reason: InterruptionReason | None = None,
    ) -> ProductionOrderInterruption | None:
        query = select(ProductionOrderInterruptionOrmModel).where(
            ProductionOrderInterruptionOrmModel.production_order_id == production_order_id,
            ProductionOrderInterruptionOrmModel.resumed_at.is_(None),
        )
        if reason is not None:
            query = query.where(ProductionOrderInterruptionOrmModel.reason == reason.value)
        orm = await self._db.scalar(
            query.order_by(ProductionOrderInterruptionOrmModel.id.desc()).limit(1)
        )
        if orm is None:
            return None
        orm.resumed_at = resumed_at
        orm.resumed_by_id = resumed_by_id
        await self._db.flush()
        return interruption_orm_to_entity(orm)

    async def get_by_order_ids(self, order_ids: list[int]) -> list[ProductionOrderInterruption]:
        if not order_ids:
            return []
        rows = (
            await self._db.scalars(
                select(ProductionOrderInterruptionOrmModel)
                .where(ProductionOrderInterruptionOrmModel.production_order_id.in_(order_ids))
                .order_by(ProductionOrderInterruptionOrmModel.id)
            )
        ).all()
        return [interruption_orm_to_entity(r) for r in rows]

    async def sum_minutes_by_order_ids(self, order_ids: list[int]) -> dict[int, int]:
        """Minutes of closed interruptions per order, summed in Python
        because datetime subtraction is not portable to SQLite."""
        if not order_ids:
            return {}
        rows = (
            await self._db.scalars(
                select(ProductionOrderInterruptionOrmModel).where(
                    ProductionOrderInterruptionOrmModel.production_order_id.in_(order_ids),
                    ProductionOrderInterruptionOrmModel.resumed_at.isnot(None),
                )
            )
        ).all()
        totals: dict[int, int] = {}
        for row in rows:
            assert row.resumed_at is not None  # filtered above
            minutes = round((row.resumed_at - row.paused_at).total_seconds() / 60)
            totals[row.production_order_id] = totals.get(row.production_order_id, 0) + minutes
        return totals


def _unchanged_since_read(
    row: ProductionOrderOrmModel, plan: ProductionOrderPlanningFields
) -> bool:
    """Whether the locked row still is the order the walk planned: the same
    pin, the same queue place where the plan names one, and not ended."""
    if row.pinned != plan.pinned_when_read:
        return False
    if row.status in TERMINAL_PRODUCTION_ORDER_STATUSES:
        return False
    place = (row.machine_id, row.machine_pool_id, row.queue_sequence)
    return plan.place_when_read is None or place == plan.place_when_read
