"""SQLAlchemy repository for the ProductionLot aggregate with its steps,
positions, provisions and events.

The SQL behind the lots table filters lives in _filters.py, and the
read enrichment that copies other aggregates' fields onto loaded lots and
positions lives in _read_model.py, mixed into the repository class.
"""

from collections.abc import Mapping
from datetime import datetime
from datetime import tzinfo
from typing import Any
from typing import cast
from uuid import UUID

from sqlalchemy import CursorResult
from sqlalchemy import Select
from sqlalchemy import desc
from sqlalchemy import exists
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.orm import selectinload

from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model import (
    BoughtItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.made_item_model import (
    MadeItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.source_item_model import (
    SourceItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.source_item_type_model import (
    SourceItemTypeOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_event_model import (
    LotEventOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model import (
    LotPositionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_provision_model import (
    LotPositionProvisionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_step_model import (
    LotStepOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_file_model import (
    ProductionOrderFileOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_order_model import (
    ProductionOrderOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.quote_request_model import (
    QuoteRequestLineOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories._lifecycle_rows import (
    ids_after,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories._lifecycle_rows import (
    lock_rows,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories._raw_material_coverage import (
    compute_raw_material_arrived_quantities,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories._raw_material_coverage import (
    compute_raw_material_arrived_quantity,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository._external import (
    external_work_page,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository._filters import (
    _actionable_lot_exists,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository._filters import (
    _coverable_by_clause,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository._filters import (
    _date_in_range,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository._filters import (
    _external_work_position,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository._filters import (
    _live_lot,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository._filters import (
    _source_delivery_exists,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository._filters import (
    _source_dimension_predicate,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository._filters import (
    _source_status_exists,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository._filters import (
    _source_text_predicate,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository._filters import (
    _source_type_predicate,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository._filters import (
    _status_clause,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository._filters import (
    _step_exists,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository._filters import (
    _target_date_expr,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository._filters import (
    _todo_candidate_clause,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository._mappers import (
    event_entity_to_dict,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository._mappers import (
    event_orm_to_entity,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository._mappers import (
    lot_entity_to_dict,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository._mappers import (
    lot_load_options,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository._mappers import (
    lot_orm_to_entity,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository._mappers import (
    position_entity_to_dict,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository._mappers import (
    position_load_options,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository._mappers import (
    position_orm_to_entity,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository._mappers import (
    provision_entity_to_dict,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository._mappers import (
    provision_load_options,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository._mappers import (
    provision_orm_to_entity,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository._mappers import (
    step_entity_to_dict,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository._mappers import (
    step_load_options,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository._mappers import (
    step_orm_to_entity,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository._read_model import (
    LotReadModelMixin,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.quote_request_repository._cleanup import (
    delete_quote_request_lines,
)
from src.modules.fulfillment.domain.entities.lot_event import LotEvent
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_position_provision import LotPositionProvision
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.errors import LotPositionInUseError
from src.modules.fulfillment.domain.services.scheduling import ExternalForecast
from src.modules.fulfillment.domain.value_objects.lot_status import TERMINAL_LOT_STATUSES
from src.modules.fulfillment.domain.value_objects.source_approval_status import SourceApprovalStatus
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    ExternalWorkFilterDto,
)
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    LotFilterDto,
)
from src.modules.platform.adapters.outbound.persistence.advisory_lock import AdvisoryLockKey
from src.modules.platform.adapters.outbound.persistence.date_range import day_after_utc
from src.modules.platform.adapters.outbound.persistence.date_range import day_start_utc
from src.modules.platform.adapters.outbound.persistence.grouped_attribute_writes import (
    flush_grouped_attribute_writes,
)
from src.modules.platform.adapters.outbound.persistence.like_escape import contains_ci
from src.modules.platform.adapters.outbound.persistence.number_counters import NumberFamily
from src.modules.platform.adapters.outbound.persistence.number_counters import draw_number
from src.modules.platform.adapters.outbound.persistence.query_filters import FilterSpec
from src.modules.platform.adapters.outbound.persistence.query_filters import apply_filters
from src.modules.platform.adapters.outbound.persistence.query_filters import when
from src.modules.platform.adapters.outbound.persistence.query_filters import when_not_none
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.adapters.outbound.persistence.statements import fetch_page
from src.modules.platform.adapters.outbound.persistence.statements import order_term
from src.modules.platform.adapters.outbound.persistence.tenant_zone import date_filter_zone
from src.modules.platform.domain.exceptions import ConcurrentModificationError
from src.modules.workspace.adapters.outbound.persistence.models.project_model import ProjectOrmModel


class SqlAlchemyProductionLotRepository(LotReadModelMixin):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Lot ──────────────────────────────────────────────────────────

    async def get_by_id(self, id: int) -> ProductionLot | None:
        orm = await self._db.scalar(by_id(ProductionLotOrmModel, id, *lot_load_options()).limit(1))
        if not orm:
            return None
        lot = lot_orm_to_entity(orm)
        await self._enrich_positions_with_order_info(lot.positions)
        await self._enrich_positions_with_production_orders(lot.positions)
        await self._enrich_lots_with_demand_info([lot])
        await self._enrich_lots_with_lineage_info([lot])
        return lot

    async def get_by_public_id(self, public_id: UUID) -> ProductionLot | None:
        lot_id = await self._db.scalar(
            select(ProductionLotOrmModel.id).where(ProductionLotOrmModel.public_id == public_id)
        )
        return await self.get_by_id(lot_id) if lot_id is not None else None

    async def get_by_id_for_update(self, id: int) -> ProductionLot | None:
        """get_by_id with a row lock on the lot, the aggregate root the lock
        ordering rule names. SQLite ignores FOR UPDATE. Every row it returns
        is re-read (populate_existing), the positions' production orders and
        order items included, because the session may still hold copies
        loaded before the lock."""
        orm = await self._db.scalar(
            by_id(
                ProductionLotOrmModel, id, *lot_load_options(), for_update=True, refresh=True
            ).limit(1)
        )
        if not orm:
            return None
        lot = lot_orm_to_entity(orm)
        await self._enrich_positions_with_order_info(lot.positions, refresh=True)
        await self._enrich_positions_with_production_orders(lot.positions, refresh=True)
        await self._enrich_lots_with_demand_info([lot], refresh=True)
        await self._enrich_lots_with_lineage_info([lot])
        return lot

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[ProductionLot]:
        """With refresh, the lots and their positions are re-read even where
        the session holds them already. The position enrichment is not, since
        it only fills display fields the reconciler does not read."""
        if not ids:
            return []
        rows = (
            await self._db.scalars(
                select(ProductionLotOrmModel)
                .where(ProductionLotOrmModel.id.in_(ids))
                .options(*lot_load_options())
                .execution_options(populate_existing=refresh)
            )
        ).all()
        lots = [lot_orm_to_entity(r) for r in rows]
        await self._enrich_lots_with_position_info(lots)
        await self._enrich_lots_with_demand_info(lots)
        await self._enrich_lots_with_lineage_info(lots)
        return lots

    async def lock_for_update(self, ids: list[int]) -> None:
        await lock_rows(self._db, ProductionLotOrmModel, ProductionLotOrmModel.id, ids)

    async def get_ids_after(self, after_id: int, limit: int) -> list[int]:
        return await ids_after(self._db, ProductionLotOrmModel.id, after_id, limit)

    async def get_external_work_page(
        self, filters: ExternalWorkFilterDto
    ) -> tuple[int, list[tuple[int, int]]]:
        return await external_work_page(self._db, filters)

    async def get_ids_with_external_work(self) -> list[int]:
        lp = LotPositionOrmModel
        ids = await self._db.scalars(
            select(ProductionLotOrmModel.id)
            .where(
                _live_lot(),
                exists().where(lp.lot_id == ProductionLotOrmModel.id, _external_work_position(lp)),
            )
            .order_by(ProductionLotOrmModel.id)
        )
        return list(ids.all())

    async def get_by_project_id(
        self, project_id: int, *, refresh: bool = False
    ) -> list[ProductionLot]:
        ids = (
            await self._db.scalars(
                select(ProductionLotOrmModel.id)
                .where(ProductionLotOrmModel.project_id == project_id)
                .order_by(ProductionLotOrmModel.id)
            )
        ).all()
        return sorted(await self.get_by_ids(list(ids), refresh=refresh), key=lambda lot: lot.id)

    async def lock_time_budgets(self, project_id: int) -> None:
        """A transaction-scoped advisory lock per project, see the port."""
        if self._db.bind is None or self._db.bind.dialect.name != "postgresql":
            return
        await self._db.execute(
            text("SELECT pg_advisory_xact_lock(:namespace, :project_id)"),
            {"namespace": int(AdvisoryLockKey.TIME_BUDGET_NAMESPACE), "project_id": project_id},
        )

    async def save_step_time_budgets(self, budgets: Mapping[int, float | None]) -> None:
        for step_id, budget in sorted(budgets.items()):
            await self._db.execute(
                update(LotStepOrmModel)
                .where(LotStepOrmModel.id == step_id)
                .values(time_budget_per_piece=budget)
                .execution_options(synchronize_session="fetch")
            )
        await self._db.flush()

    async def get_force_completed_since(self, since: datetime) -> list[ProductionLot]:
        ids = (
            await self._db.scalars(
                select(ProductionLotOrmModel.id)
                .where(ProductionLotOrmModel.force_completed_at >= since)
                .order_by(ProductionLotOrmModel.force_completed_at, ProductionLotOrmModel.id)
            )
        ).all()
        return await self.get_by_ids(list(ids))

    def _filter_specs(self, filters: LotFilterDto, zone: tzinfo) -> list[FilterSpec]:
        # `created` is a timestamp, half-open bounds over days in `zone`, the
        # tenant's, keep the `_to` day whole instead of clipping it at
        # midnight (see date_range.py).
        step_clause = _step_exists(filters, zone)
        return [
            when(filters.ids, lambda ids: ProductionLotOrmModel.id.in_(ids)),
            when(filters.statuses or filters.status, lambda _: _status_clause(filters)),
            when(
                filters.actionable_for,
                lambda actionable_for: _actionable_lot_exists(actionable_for),
            ),
            when(
                filters.source_approval_status,
                lambda source_approval_status: (
                    ProductionLotOrmModel.source_approval_status == source_approval_status
                ),
            ),
            when(
                filters.coverable_by_machine_id is not None
                or filters.coverable_by_pool_id is not None
                or bool(filters.coverable_by_any_pool),
                lambda _: _coverable_by_clause(filters),
            ),
            when(
                filters.made_item_id,
                lambda made_item_id: ProductionLotOrmModel.made_item_id == made_item_id,
            ),
            when(
                filters.project_id,
                lambda project_id: ProductionLotOrmModel.project_id == project_id,
            ),
            when(filters.priority, lambda priority: ProductionLotOrmModel.priority == priority),
            when(
                filters.creator_id,
                lambda creator_id: ProductionLotOrmModel.creator_id == creator_id,
            ),
            when(
                filters.changed_by_id,
                lambda changed_by_id: ProductionLotOrmModel.changed_by_id == changed_by_id,
            ),
            when(
                filters.created_from,
                lambda created_from: (
                    ProductionLotOrmModel.created >= day_start_utc(created_from, zone)
                ),
            ),
            when(
                filters.created_to,
                lambda created_to: ProductionLotOrmModel.created < day_after_utc(created_to, zone),
            ),
            when(
                filters.changed_from,
                lambda changed_from: (
                    ProductionLotOrmModel.changed >= day_start_utc(changed_from, zone)
                ),
            ),
            when(
                filters.changed_to,
                lambda changed_to: ProductionLotOrmModel.changed < day_after_utc(changed_to, zone),
            ),
            when(
                filters.lot_number,
                lambda lot_number: contains_ci(ProductionLotOrmModel.lot_number, lot_number),
            ),
            when(
                filters.target_date_from or filters.target_date_to,
                lambda _: _date_in_range(
                    _target_date_expr(), filters.target_date_from, filters.target_date_to
                ),
            ),
            when_not_none(
                filters.quantity_min,
                lambda quantity_min: ProductionLotOrmModel.quantity >= quantity_min,
            ),
            when_not_none(
                filters.quantity_max,
                lambda quantity_max: ProductionLotOrmModel.quantity <= quantity_max,
            ),
            when(filters.source_status, lambda source_status: _source_status_exists(source_status)),
            when(
                filters.source_delivery_from or filters.source_delivery_to,
                lambda _: _source_delivery_exists(
                    filters.source_delivery_from, filters.source_delivery_to, zone
                ),
            ),
            when_not_none(step_clause, lambda clause: clause),
            when(filters.todo_horizon, _todo_candidate_clause),
        ]

    def _apply_source_text_join(self, q: "Select[Any]", filters: LotFilterDto) -> "Select[Any]":
        """Outer-joins the material sources once, and only when one of the
        source text filters is set."""
        if not (filters.source_text or filters.source_dimension or filters.source_type):
            return q
        source_made_item = aliased(MadeItemOrmModel)
        q = (
            q.outerjoin(
                BoughtItemOrmModel,
                ProductionLotOrmModel.source_bought_item_id == BoughtItemOrmModel.id,
            )
            .outerjoin(
                SourceItemOrmModel, ProductionLotOrmModel.source_item_id == SourceItemOrmModel.id
            )
            .outerjoin(
                SourceItemTypeOrmModel, SourceItemOrmModel.type_id == SourceItemTypeOrmModel.id
            )
            .outerjoin(
                source_made_item, ProductionLotOrmModel.source_made_item_id == source_made_item.id
            )
        )
        if filters.source_text:
            q = q.where(_source_text_predicate(filters.source_text, source_made_item))
        if filters.source_dimension:
            q = q.where(_source_dimension_predicate(filters.source_dimension, source_made_item))
        if filters.source_type:
            q = q.where(_source_type_predicate(filters.source_type))
        return q

    def _apply_item_and_search_join(self, q: "Select[Any]", filters: LotFilterDto) -> "Select[Any]":
        """item_article_name, item_part_number and search share the same
        MadeItemOrmModel join, made at most once whichever of them are set."""
        needs_item_join = bool(
            filters.item_article_name or filters.item_part_number or filters.search
        )
        if needs_item_join:
            q = q.join(MadeItemOrmModel, ProductionLotOrmModel.made_item)
        if filters.item_article_name:
            q = q.where(contains_ci(MadeItemOrmModel.article_name, filters.item_article_name))
        if filters.item_part_number:
            q = q.where(contains_ci(MadeItemOrmModel.part_number, filters.item_part_number))
        if filters.search:
            term = filters.search
            q = q.where(
                or_(
                    contains_ci(ProductionLotOrmModel.lot_number, term),
                    contains_ci(MadeItemOrmModel.article_name, term),
                    contains_ci(MadeItemOrmModel.part_number, term),
                )
            )
        return q

    def _apply_project_number_join(self, q: "Select[Any]", filters: LotFilterDto) -> "Select[Any]":
        if not filters.project_number:
            return q
        q = q.join(ProjectOrmModel, ProductionLotOrmModel.project)
        return q.where(contains_ci(ProjectOrmModel.project_number, filters.project_number))

    async def count_by_status(self) -> dict[str, int]:
        rows = await self._db.execute(
            select(ProductionLotOrmModel.status, func.count()).group_by(
                ProductionLotOrmModel.status
            )
        )
        return {status: count for status, count in rows.tuples()}

    async def get_multi(self, filters: LotFilterDto) -> tuple[int, list[ProductionLot]]:
        zone = await date_filter_zone(
            self._db,
            filters.created_from,
            filters.created_to,
            filters.changed_from,
            filters.changed_to,
            filters.source_delivery_from,
            filters.source_delivery_to,
            filters.step_planned_start_from,
            filters.step_planned_start_to,
            filters.step_planned_end_from,
            filters.step_planned_end_to,
            filters.step_delivery_from,
            filters.step_delivery_to,
        )
        q = select(ProductionLotOrmModel)
        q = apply_filters(q, self._filter_specs(filters, zone))
        q = self._apply_source_text_join(q, filters)
        q = self._apply_item_and_search_join(q, filters)
        q = self._apply_project_number_join(q, filters)

        _sort_column_map = {
            "id": ProductionLotOrmModel.id,
            "lot_number": ProductionLotOrmModel.lot_number,
            "created": ProductionLotOrmModel.created,
            "quantity": ProductionLotOrmModel.quantity,
        }
        if filters.order_by and filters.order_by in _sort_column_map:
            secondary = order_term(
                _sort_column_map[filters.order_by], filters.order_dir, default="desc"
            )
        else:
            secondary = desc(ProductionLotOrmModel.created)

        total, rows = await fetch_page(
            self._db,
            q,
            filters.skip,
            filters.limit,
            secondary,
            desc(ProductionLotOrmModel.id),
            options=lot_load_options(),
            min_limit=len(filters.ids) if filters.ids else None,
        )
        lots = [lot_orm_to_entity(r) for r in rows]
        await self._enrich_lots_with_position_info(lots)
        await self._enrich_lots_with_demand_info(lots)
        await self._enrich_lots_with_lineage_info(lots)
        return total, lots

    async def save(self, lot: ProductionLot) -> ProductionLot:
        orm = await self._save_lot_orm(lot)
        await self._db.flush()
        saved = lot_orm_to_entity(await self._reload_lot(orm.id))
        await self._enrich_positions_with_order_info(saved.positions)
        await self._enrich_positions_with_production_orders(saved.positions)
        await self._enrich_lots_with_demand_info([saved])
        await self._enrich_lots_with_lineage_info([saved])
        return saved

    async def _reload_lot(self, id: int) -> ProductionLotOrmModel:
        """Re-selects a just-written lot with its mapper's loads.
        populate_existing re-reads every column (server defaults arrive as
        with refresh) and applies the loader options to the instance that
        is already in the identity map."""
        return (
            await self._db.scalars(
                by_id(ProductionLotOrmModel, id, *lot_load_options(), refresh=True)
            )
        ).one()

    async def _save_lot_orm(self, lot: ProductionLot) -> ProductionLotOrmModel:
        if lot.id == 0:
            orm = ProductionLotOrmModel(**lot_entity_to_dict(lot))
            self._db.add(orm)
            return orm
        existing = await self._db.scalar(
            select(ProductionLotOrmModel).where(ProductionLotOrmModel.id == lot.id).limit(1)
        )
        if not existing:
            raise ConcurrentModificationError(
                f"ProductionLotOrmModel id={lot.id} was removed"
                " while this request worked on it; reload and try again."
            )
        for k, v in lot_entity_to_dict(lot).items():
            setattr(existing, k, v)
        return existing

    async def next_lot_number(self, template: str) -> str:
        """Draws the next lot number per the admin-configured template (see
        src.modules.platform.domain.services.numbering_format) from the lot counter
        (persistence/number_counters.py)."""
        return await draw_number(
            self._db,
            NumberFamily.LOT,
            template,
            column=ProductionLotOrmModel.lot_number,
        )

    async def get_raw_material_arrived_quantity(self, demand_id: int) -> float:
        return await compute_raw_material_arrived_quantity(self._db, demand_id)

    async def get_raw_material_arrived_quantities(self, demand_ids: list[int]) -> dict[int, float]:
        return await compute_raw_material_arrived_quantities(self._db, demand_ids)

    async def reset_source_approval_for_setting_change(self, enabled: bool) -> int:
        """One bulk UPDATE for the approval toggle, without commit. Turning
        it on moves open source-item lots without a demand to pending;
        turning it off moves pending back. Recorded decisions never change."""
        if enabled:
            result = cast(
                CursorResult[Any],
                await self._db.execute(
                    update(ProductionLotOrmModel)
                    .where(
                        ProductionLotOrmModel.source_approval_status
                        == SourceApprovalStatus.NOT_REQUIRED.value,
                        ProductionLotOrmModel.source_item_id.isnot(None),
                        ProductionLotOrmModel.input_demand_id.is_(None),
                        ProductionLotOrmModel.status.notin_(sorted(TERMINAL_LOT_STATUSES)),
                    )
                    .values({"source_approval_status": SourceApprovalStatus.PENDING.value})
                ),
            )
            count = result.rowcount
        else:
            result = cast(
                CursorResult[Any],
                await self._db.execute(
                    update(ProductionLotOrmModel)
                    .where(
                        ProductionLotOrmModel.source_approval_status
                        == SourceApprovalStatus.PENDING.value
                    )
                    .values({"source_approval_status": SourceApprovalStatus.NOT_REQUIRED.value})
                ),
            )
            count = result.rowcount
        return count

    async def get_steps(self, lot_id: int) -> list[LotStep]:
        rows = (
            await self._db.scalars(
                select(LotStepOrmModel)
                .where(LotStepOrmModel.lot_id == lot_id)
                .options(*step_load_options())
                .order_by(LotStepOrmModel.sequence)
            )
        ).all()
        return [step_orm_to_entity(r) for r in rows]

    async def get_step_by_id(self, step_id: int) -> LotStep | None:
        orm = await self._db.scalar(by_id(LotStepOrmModel, step_id, *step_load_options()).limit(1))
        return step_orm_to_entity(orm) if orm else None

    async def save_step(self, step: LotStep) -> LotStep:
        orm = await self._save_step_orm(step)
        await self._db.flush()
        return step_orm_to_entity(await self._reload_step(orm.id))

    async def _reload_step(self, id: int) -> LotStepOrmModel:
        """Step counterpart to _reload_lot."""
        return (
            await self._db.scalars(by_id(LotStepOrmModel, id, *step_load_options(), refresh=True))
        ).one()

    async def _save_step_orm(self, step: LotStep) -> LotStepOrmModel:
        if step.id == 0:
            orm = LotStepOrmModel(**step_entity_to_dict(step))
            self._db.add(orm)
            return orm
        existing = await self._db.scalar(
            select(LotStepOrmModel).where(LotStepOrmModel.id == step.id).limit(1)
        )
        if not existing:
            raise ConcurrentModificationError(
                f"LotStepOrmModel id={step.id} was removed"
                " while this request worked on it; reload and try again."
            )
        for k, v in step_entity_to_dict(step).items():
            setattr(existing, k, v)
        return existing

    async def delete_step(self, step: LotStep) -> None:
        orm = await self._db.scalar(
            select(LotStepOrmModel).where(LotStepOrmModel.id == step.id).limit(1)
        )
        if orm:
            await self._db.delete(orm)
            await self._db.flush()

    async def reorder_steps(self, lot_id: int, ordered_step_ids: list[int]) -> list[LotStep]:
        rows = {
            r.id: r
            for r in (
                await self._db.scalars(
                    select(LotStepOrmModel).where(LotStepOrmModel.lot_id == lot_id)
                )
            ).all()
        }
        # UNIQUE(lot_id, sequence) is not deferrable and rows update one at a
        # time, so park them on negative values first, then write the real ones.
        for offset, step_id in enumerate(ordered_step_ids, start=1):
            rows[step_id].sequence = -offset
        await self._db.flush()
        for sequence, step_id in enumerate(ordered_step_ids, start=1):
            rows[step_id].sequence = sequence
        await self._db.flush()
        return await self.get_steps(lot_id)

    async def reorder_positions(
        self, lot_id: int, ordered_position_ids: list[int]
    ) -> list[LotPosition]:
        """Same negative parking as reorder_steps."""
        rows = {
            r.id: r
            for r in (
                await self._db.scalars(
                    select(LotPositionOrmModel).where(LotPositionOrmModel.lot_id == lot_id)
                )
            ).all()
        }
        for offset, position_id in enumerate(ordered_position_ids, start=1):
            rows[position_id].sequence = -offset
        await self._db.flush()
        for sequence, position_id in enumerate(ordered_position_ids, start=1):
            rows[position_id].sequence = sequence
        await self._db.flush()
        return await self.get_positions(lot_id)

    # ── Positions ────────────────────────────────────────────────────

    async def get_positions(self, lot_id: int) -> list[LotPosition]:
        rows = (
            await self._db.scalars(
                select(LotPositionOrmModel)
                .where(LotPositionOrmModel.lot_id == lot_id)
                .options(*position_load_options())
                .order_by(LotPositionOrmModel.sequence)
            )
        ).all()
        positions = [position_orm_to_entity(r) for r in rows]
        await self._enrich_positions_with_order_info(positions)
        await self._enrich_positions_with_production_orders(positions)
        return positions

    async def get_position_by_id(self, position_id: int) -> LotPosition | None:
        orm = await self._db.scalar(
            by_id(LotPositionOrmModel, position_id, *position_load_options()).limit(1)
        )
        if not orm:
            return None
        position = position_orm_to_entity(orm)
        await self._enrich_positions_with_order_info([position])
        await self._enrich_positions_with_production_orders([position])
        return position

    async def get_positions_by_ids(self, position_ids: list[int]) -> list[LotPosition]:
        if not position_ids:
            return []
        rows = (
            await self._db.scalars(
                select(LotPositionOrmModel)
                .where(LotPositionOrmModel.id.in_(position_ids))
                .options(*position_load_options())
            )
        ).all()
        positions = [position_orm_to_entity(r) for r in rows]
        await self._enrich_positions_with_order_info(positions)
        await self._enrich_positions_with_production_orders(positions)
        return positions

    async def save_position(self, position: LotPosition) -> LotPosition:
        orm = await self._save_position_orm(position)
        await self._db.flush()
        result = position_orm_to_entity(await self._reload_position(orm.id))
        await self._enrich_positions_with_order_info([result])
        await self._enrich_positions_with_production_orders([result])
        return result

    async def save_position_forecasts(self, forecasts: list[ExternalForecast]) -> None:
        """Writes the forecasts; only real changes become UPDATEs."""
        if not forecasts:
            return
        rows = (
            await self._db.scalars(
                select(LotPositionOrmModel)
                .where(LotPositionOrmModel.id.in_([f.position_id for f in forecasts]))
                .execution_options(populate_existing=True)
            )
        ).all()
        rows_by_id = {row.id: row for row in rows}
        await flush_grouped_attribute_writes(
            self._db,
            (
                (
                    rows_by_id[forecast.position_id],
                    {
                        "planned_pickup_date": forecast.planned_pickup_date,
                        "planned_delivery_date": forecast.planned_delivery_date,
                        "latest_pickup_date": forecast.latest_pickup_date,
                        "latest_delivery_date": forecast.latest_delivery_date,
                    },
                )
                for forecast in forecasts
                if forecast.position_id in rows_by_id
            ),
        )

    async def _reload_position(self, id: int) -> LotPositionOrmModel:
        """Position counterpart to _reload_lot."""
        return (
            await self._db.scalars(
                by_id(LotPositionOrmModel, id, *position_load_options(), refresh=True)
            )
        ).one()

    async def _save_position_orm(self, position: LotPosition) -> LotPositionOrmModel:
        if position.id == 0:
            orm = LotPositionOrmModel(**position_entity_to_dict(position))
            self._db.add(orm)
            return orm
        existing = await self._db.scalar(
            select(LotPositionOrmModel).where(LotPositionOrmModel.id == position.id).limit(1)
        )
        if not existing:
            raise ConcurrentModificationError(
                f"LotPositionOrmModel id={position.id} was removed"
                " while this request worked on it; reload and try again."
            )
        for k, v in position_entity_to_dict(position).items():
            setattr(existing, k, v)
        return existing

    async def _refresh_steps_before_delete(self, orm: LotPositionOrmModel) -> LotPositionOrmModel:
        """Reloads the position's steps before a delete. The delete-orphan
        cascade acts on the in-memory collection, and a regroup repoints
        steps by column, so a stale collection would cascade-delete steps
        that now belong to another position."""
        await self._db.flush()
        return (
            await self._db.scalars(
                select(LotPositionOrmModel)
                .where(LotPositionOrmModel.id == orm.id)
                .options(selectinload(LotPositionOrmModel.steps))
                .execution_options(populate_existing=True)
            )
        ).one()

    async def delete_position(self, position: LotPosition) -> None:
        """Deletes a position and the quote request lines that name it.
        Callers must first check that no order item references it, the one
        FK without cascade; a race between check and
        delete just rolls back on the IntegrityError. A position whose
        production orders hold uploaded files is refused, since the delete
        would cascade to the file rows and leave their stored objects
        behind."""
        with_files = await self._db.scalar(
            select(ProductionOrderFileOrmModel.id)
            .join(
                ProductionOrderOrmModel,
                ProductionOrderOrmModel.id == ProductionOrderFileOrmModel.production_order_id,
            )
            .where(ProductionOrderOrmModel.lot_position_id == position.id)
            .limit(1)
        )
        if with_files is not None:
            raise LotPositionInUseError(
                f"Position #{position.id} has production orders with uploaded files; "
                "it keeps them and cannot be removed."
            )
        orm = await self._db.scalar(
            select(LotPositionOrmModel).where(LotPositionOrmModel.id == position.id).limit(1)
        )
        if orm:
            # The quote request lines that asked a supplier for the position
            # go with it; an awarded one keeps its order line.
            await delete_quote_request_lines(
                self._db, QuoteRequestLineOrmModel.lot_position_id == position.id
            )
            await self._db.delete(await self._refresh_steps_before_delete(orm))
            await self._db.flush()

    async def get_quote_request_ids_of_positions(self, position_ids: list[int]) -> list[int]:
        if not position_ids:
            return []
        rows = await self._db.scalars(
            select(QuoteRequestLineOrmModel.quote_request_id)
            .where(QuoteRequestLineOrmModel.lot_position_id.in_(position_ids))
            .distinct()
            .order_by(QuoteRequestLineOrmModel.quote_request_id)
        )
        return list(rows.all())

    # ── Provisions ───────────────────────────────────────────────────

    async def get_provisions(self, lot_position_id: int) -> list[LotPositionProvision]:
        rows = (
            await self._db.scalars(
                select(LotPositionProvisionOrmModel)
                .where(LotPositionProvisionOrmModel.lot_position_id == lot_position_id)
                .options(*provision_load_options())
                .order_by(LotPositionProvisionOrmModel.id)
            )
        ).all()
        return [provision_orm_to_entity(r) for r in rows]

    async def save_provision(self, provision: LotPositionProvision) -> LotPositionProvision:
        orm = LotPositionProvisionOrmModel(**provision_entity_to_dict(provision))
        self._db.add(orm)
        await self._db.flush()
        return provision_orm_to_entity(await self._reload_provision(orm.id))

    async def _reload_provision(self, id: int) -> LotPositionProvisionOrmModel:
        """Provision counterpart to _reload_lot."""
        return (
            await self._db.scalars(
                by_id(LotPositionProvisionOrmModel, id, *provision_load_options(), refresh=True)
            )
        ).one()

    # ── Events ───────────────────────────────────────────────────────

    async def get_events(self, lot_id: int) -> list[LotEvent]:
        rows = (
            await self._db.scalars(
                select(LotEventOrmModel)
                .where(LotEventOrmModel.lot_id == lot_id)
                .order_by(LotEventOrmModel.occurred_at, LotEventOrmModel.id)
            )
        ).all()
        return [event_orm_to_entity(r) for r in rows]

    async def record_event(self, event: LotEvent) -> LotEvent:
        orm = LotEventOrmModel(**event_entity_to_dict(event))
        self._db.add(orm)
        await self._db.flush()
        await self._db.refresh(orm)
        return event_orm_to_entity(orm)
