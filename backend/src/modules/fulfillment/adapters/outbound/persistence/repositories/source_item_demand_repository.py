"""
Concrete implementation of ISourceItemDemandRepository using SQLAlchemy +
Postgres. status is a real stored column, written by the lifecycle
reconciler from the derivation in domain/services/lifecycle/demand.py; this
repository is a thin ORM <-> entity mapper, no derivation logic.
"""

from functools import lru_cache
from typing import Any

from sqlalchemy import ColumnElement
from sqlalchemy import Select
from sqlalchemy import nulls_last
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.catalogue.adapters.outbound.persistence.mappers.bought_item_mappers import (
    item_orm_to_entity as bought_item_orm_to_entity,
)
from src.modules.catalogue.adapters.outbound.persistence.mappers.source_item_mappers import (
    source_item_orm_to_entity,
)
from src.modules.catalogue.adapters.outbound.persistence.models.article_group_model import (
    ArticleGroupOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model import (
    BoughtItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.source_item_model import (
    SourceItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.source_item_type_model import (
    SourceItemTypeOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.allocation_filters import bucket_clause
from src.modules.fulfillment.adapters.outbound.persistence.allocation_filters import (
    demand_not_fully_allocated,
)
from src.modules.fulfillment.adapters.outbound.persistence.allocation_filters import (
    demand_status_counts,
)
from src.modules.fulfillment.adapters.outbound.persistence.allocation_filters import (
    demand_todo_candidate,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_allocation_model import (
    SourceItemAllocationOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_demand_bucket_model import (
    SourceItemDemandBucketOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.source_item_demand_item_model import (
    SourceItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories._lifecycle_rows import (
    ids_after,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories._lifecycle_rows import (
    lock_rows,
)
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemDemandRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    SourceItemDemandFilterDto,
)
from src.modules.platform.adapters.outbound.persistence.like_escape import contains_ci
from src.modules.platform.adapters.outbound.persistence.localized_text_sql import localized_contains
from src.modules.platform.adapters.outbound.persistence.mapping_common import changed_by_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import creator_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.query_filters import FilterSpec
from src.modules.platform.adapters.outbound.persistence.query_filters import apply_filters
from src.modules.platform.adapters.outbound.persistence.query_filters import when
from src.modules.platform.adapters.outbound.persistence.query_filters import when_not_none
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.adapters.outbound.persistence.statements import fetch_page
from src.modules.platform.adapters.outbound.persistence.statements import order_term
from src.modules.platform.adapters.outbound.persistence.user_loading import load_user
from src.modules.platform.domain.exceptions import ConcurrentModificationError
from src.modules.workspace.adapters.outbound.persistence.mappers.product_projects import (
    in_product_projects,
)
from src.modules.workspace.adapters.outbound.persistence.models.project_model import ProjectOrmModel
from src.modules.workspace.domain.value_objects.project_status import ProjectStatus

# ── Mapping helpers ───────────────────────────────────────────────────


# Every relationship _orm_to_entity reads. The bought item and source item
# paths mirror bought_item_load_options() and source_item_load_options(), since
# the demand embeds both full items.
@lru_cache(maxsize=1)
def source_item_demand_load_options() -> tuple[ORMOption, ...]:
    return (
        load_user(SourceItemDemandItemOrmModel.creator),
        load_user(SourceItemDemandItemOrmModel.changed_by),
        selectinload(SourceItemDemandItemOrmModel.lot),
        selectinload(SourceItemDemandItemOrmModel.project).selectinload(ProjectOrmModel.customer),
        load_user(SourceItemDemandItemOrmModel.bought_item, BoughtItemOrmModel.creator),
        load_user(SourceItemDemandItemOrmModel.bought_item, BoughtItemOrmModel.changed_by),
        selectinload(SourceItemDemandItemOrmModel.bought_item).selectinload(
            BoughtItemOrmModel.manufacturer
        ),
        selectinload(SourceItemDemandItemOrmModel.bought_item).selectinload(
            BoughtItemOrmModel.product_family
        ),
        load_user(
            SourceItemDemandItemOrmModel.bought_item,
            BoughtItemOrmModel.article_groups,
            ArticleGroupOrmModel.creator,
        ),
        load_user(
            SourceItemDemandItemOrmModel.bought_item,
            BoughtItemOrmModel.article_groups,
            ArticleGroupOrmModel.changed_by,
        ),
        load_user(SourceItemDemandItemOrmModel.source_item, SourceItemOrmModel.creator),
        load_user(SourceItemDemandItemOrmModel.source_item, SourceItemOrmModel.changed_by),
        selectinload(SourceItemDemandItemOrmModel.source_item).selectinload(
            SourceItemOrmModel.type
        ),
        selectinload(SourceItemDemandItemOrmModel.source_item).selectinload(
            SourceItemOrmModel.manufacturer
        ),
    )


def _orm_to_entity(orm: SourceItemDemandItemOrmModel) -> SourceItemDemandItem:
    return SourceItemDemandItem(
        id=orm.id,
        public_id=orm.public_id,
        created=utc_aware(orm.created),
        changed=utc_aware(orm.changed),
        changes=list(orm.changes or []),
        status=SourceItemDemandStatus(orm.status),
        quantity=orm.quantity,
        unit=orm.unit,
        items_per_unit=orm.items_per_unit,
        high_priority=orm.high_priority,
        notify_on_delivery=orm.notify_on_delivery,
        note=orm.note,
        desired_delivery_date=orm.desired_delivery_date,
        **creator_kwargs(orm.creator_id, orm.creator),
        **changed_by_kwargs(orm.changed_by_id, orm.changed_by),
        bought_item_id=orm.bought_item_id,
        source_item_id=orm.source_item_id,
        lot_id=orm.lot_id,
        project_id=orm.project_id,
        bucket_id=orm.bucket_id,
        canceled_at=orm.canceled_at,
        fulfilled_manually_at=orm.fulfilled_manually_at,
        bought_item=bought_item_orm_to_entity(orm.bought_item) if orm.bought_item else None,
        source_item=source_item_orm_to_entity(orm.source_item) if orm.source_item else None,
        lot_number=orm.lot.lot_number if orm.lot else "",
        project_number=orm.project.project_number if orm.project else "",
        project_customer=orm.project.customer.name
        if (orm.project and orm.project.customer)
        else "",
        project_description=(orm.project.description or "") if orm.project else "",
        project_status=ProjectStatus(orm.project.status) if orm.project else ProjectStatus.ARCHIVED,
    )


def _entity_to_dict(d: SourceItemDemandItem) -> dict[str, Any]:
    return {
        "created": d.created,
        "changed": d.changed,
        "changes": d.changes,
        "status": d.status.value,
        "quantity": d.quantity,
        "unit": d.unit,
        "items_per_unit": d.items_per_unit,
        "high_priority": d.high_priority,
        "notify_on_delivery": d.notify_on_delivery,
        "note": d.note,
        "desired_delivery_date": d.desired_delivery_date,
        "creator_id": d.creator_id,
        "bought_item_id": d.bought_item_id,
        "source_item_id": d.source_item_id,
        "lot_id": d.lot_id,
        "project_id": d.project_id,
        "bucket_id": d.bucket_id,
        "canceled_at": d.canceled_at,
        "fulfilled_manually_at": d.fulfilled_manually_at,
    }


# ── get_multi filter/sort helpers ───────────────────────────────────────

# Referencing SourceItemDemandBucketOrmModel here has no join dependency of
# its own: a plain attribute reference only turns into SQL once it reaches
# .where()/.order_by(), by which point get_multi's join step has already run.
_SORT_COLUMNS: dict[str, Any] = {
    "id": SourceItemDemandItemOrmModel.id,
    "status": SourceItemDemandItemOrmModel.status,
    "created": SourceItemDemandItemOrmModel.created,
    "changed": SourceItemDemandItemOrmModel.changed,
    "desired_delivery_date": SourceItemDemandItemOrmModel.desired_delivery_date,
    "bucket_name": SourceItemDemandBucketOrmModel.name,
    "project_number": ProjectOrmModel.project_number,
}


def _resolve_sort(filters: SourceItemDemandFilterDto) -> ColumnElement[Any]:
    sort_col = _SORT_COLUMNS.get(filters.order_by or "id", SourceItemDemandItemOrmModel.id)
    term = order_term(sort_col, filters.order_dir, default="desc")
    if filters.order_by == "bucket_name":
        # Outer-joined column: NULLs (unbucketed demands) always sort
        # last, in both directions, per the API contract.
        return nulls_last(term)
    return term


# ── Repository ────────────────────────────────────────────────────────


class SqlAlchemySourceItemDemandRepository(ISourceItemDemandRepository):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, id: int) -> SourceItemDemandItem | None:
        orm = await self._db.scalar(
            by_id(SourceItemDemandItemOrmModel, id, *source_item_demand_load_options()).limit(1)
        )
        return _orm_to_entity(orm) if orm else None

    async def get_by_ids(
        self, ids: list[int], *, refresh: bool = False
    ) -> list[SourceItemDemandItem]:
        if not ids:
            return []
        rows = (
            await self._db.scalars(
                select(SourceItemDemandItemOrmModel)
                .where(SourceItemDemandItemOrmModel.id.in_(ids))
                .options(*source_item_demand_load_options())
                .execution_options(populate_existing=refresh)
            )
        ).all()
        return [_orm_to_entity(r) for r in rows]

    async def lock_for_update(self, ids: list[int]) -> None:
        await lock_rows(
            self._db, SourceItemDemandItemOrmModel, SourceItemDemandItemOrmModel.id, ids
        )

    async def get_ids_after(self, after_id: int, limit: int) -> list[int]:
        return await ids_after(self._db, SourceItemDemandItemOrmModel.id, after_id, limit)

    async def get_by_id_for_update(self, id: int) -> SourceItemDemandItem | None:
        orm = await self._db.scalar(
            by_id(
                SourceItemDemandItemOrmModel,
                id,
                *source_item_demand_load_options(),
                for_update=True,
                refresh=True,
            ).limit(1)
        )
        return _orm_to_entity(orm) if orm else None

    def _order_allocation_exists(self, order_id: list[int]) -> ColumnElement[bool]:
        """EXISTS rather than a join: a demand can hold several allocations
        and a join would multiply the demand row."""
        return (
            select(SourceItemAllocationOrmModel.id)
            .join(
                OrderItemOrmModel,
                OrderItemOrmModel.id == SourceItemAllocationOrmModel.order_item_id,
            )
            .where(
                SourceItemAllocationOrmModel.demand_item_id == SourceItemDemandItemOrmModel.id,
                OrderItemOrmModel.order_id.in_(order_id),
            )
            .exists()
        )

    def _filter_specs(self, filters: SourceItemDemandFilterDto) -> list[FilterSpec]:
        return [
            when(filters.ids, lambda ids: SourceItemDemandItemOrmModel.id.in_(ids)),
            when(filters.lot_id, lambda lot_id: SourceItemDemandItemOrmModel.lot_id.in_(lot_id)),
            when_not_none(
                filters.bought_item_id,
                lambda bought_item_id: (
                    SourceItemDemandItemOrmModel.bought_item_id == bought_item_id
                ),
            ),
            when_not_none(
                filters.source_item_id,
                lambda source_item_id: (
                    SourceItemDemandItemOrmModel.source_item_id == source_item_id
                ),
            ),
            when_not_none(
                filters.project_id,
                lambda project_id: SourceItemDemandItemOrmModel.project_id == project_id,
            ),
            when_not_none(
                filters.product_id,
                lambda product_id: in_product_projects(
                    SourceItemDemandItemOrmModel.project_id, product_id
                ),
            ),
            when(filters.order_id, lambda order_id: self._order_allocation_exists(order_id)),
            when_not_none(
                filters.creator_id,
                lambda creator_id: SourceItemDemandItemOrmModel.creator_id == creator_id,
            ),
            when_not_none(
                filters.changed_by_id,
                lambda changed_by_id: SourceItemDemandItemOrmModel.changed_by_id == changed_by_id,
            ),
            when_not_none(
                filters.high_priority,
                lambda high_priority: SourceItemDemandItemOrmModel.high_priority == high_priority,
            ),
            when(
                filters.desired_from,
                lambda desired_from: (
                    SourceItemDemandItemOrmModel.desired_delivery_date >= desired_from
                ),
            ),
            when(
                filters.desired_to,
                lambda desired_to: SourceItemDemandItemOrmModel.desired_delivery_date <= desired_to,
            ),
            when_not_none(
                filters.status, lambda status: SourceItemDemandItemOrmModel.status == status
            ),
            when(
                filters.ignore_fulfilled,
                lambda _: (
                    SourceItemDemandItemOrmModel.status != SourceItemDemandStatus.FULFILLED.value
                ),
            ),
            when(
                filters.ignore_canceled,
                lambda _: (
                    SourceItemDemandItemOrmModel.status != SourceItemDemandStatus.CANCELED.value
                ),
            ),
            when(
                filters.not_fully_allocated,
                lambda _: demand_not_fully_allocated(
                    demand_id=SourceItemDemandItemOrmModel.id,
                    demand_quantity=SourceItemDemandItemOrmModel.quantity,
                    demand_status=SourceItemDemandItemOrmModel.status,
                    allocation_demand_item_id=SourceItemAllocationOrmModel.demand_item_id,
                    allocation_quantity=SourceItemAllocationOrmModel.quantity,
                    terminal_statuses=[
                        SourceItemDemandStatus.FULFILLED.value,
                        SourceItemDemandStatus.CANCELED.value,
                    ],
                ),
            ),
            when(
                filters.bucket_id or filters.include_unbucketed,
                lambda _: bucket_clause(
                    SourceItemDemandItemOrmModel.bucket_id,
                    filters.bucket_id,
                    filters.include_unbucketed,
                ),
            ),
            when(
                filters.todo_horizon,
                lambda horizon: demand_todo_candidate(
                    demand_status=SourceItemDemandItemOrmModel.status,
                    desired_delivery_date=SourceItemDemandItemOrmModel.desired_delivery_date,
                    open_status=SourceItemDemandStatus.OPEN.value,
                    horizon=horizon,
                ),
            ),
        ]

    def _apply_project_and_item_joins(
        self, q: Select[tuple[SourceItemDemandItemOrmModel]], filters: SourceItemDemandFilterDto
    ) -> Select[tuple[SourceItemDemandItemOrmModel]]:
        search = filters.search
        if search or filters.project_number or filters.order_by == "project_number":
            q = q.join(ProjectOrmModel, SourceItemDemandItemOrmModel.project)
        if filters.project_number:
            q = q.where(contains_ci(ProjectOrmModel.project_number, filters.project_number))
        # The three item inputs read the source item side only, so a
        # bought-item-backed demand never matches them: its outer-joined
        # source item columns are NULL and fail the ILIKE.
        if search or filters.item_dimension or filters.item_material or filters.item_type:
            q = q.outerjoin(SourceItemOrmModel, SourceItemDemandItemOrmModel.source_item)
        if search or filters.item_type:
            q = q.outerjoin(SourceItemTypeOrmModel, SourceItemOrmModel.type)
        if filters.item_dimension:
            q = q.where(contains_ci(SourceItemOrmModel.dimension, filters.item_dimension))
        if filters.item_material:
            q = q.where(contains_ci(SourceItemOrmModel.material, filters.item_material))
        if filters.item_type:
            q = q.where(localized_contains(SourceItemTypeOrmModel.name, filters.item_type))
        if search:
            q = self._apply_search(q, search)
        if filters.order_by == "bucket_name":
            q = q.outerjoin(
                SourceItemDemandBucketOrmModel,
                SourceItemDemandItemOrmModel.bucket_id == SourceItemDemandBucketOrmModel.id,
            )
        return q

    @staticmethod
    def _apply_search(
        q: Select[tuple[SourceItemDemandItemOrmModel]], term: str
    ) -> Select[tuple[SourceItemDemandItemOrmModel]]:
        """Matches the term against what the list shows: the project, the
        lot, the material of either source kind and the note. The project and
        the source item with its type are joined by the caller."""
        q = q.outerjoin(ProductionLotOrmModel, SourceItemDemandItemOrmModel.lot)
        q = q.outerjoin(BoughtItemOrmModel, SourceItemDemandItemOrmModel.bought_item)
        return q.where(
            or_(
                contains_ci(ProjectOrmModel.project_number, term),
                contains_ci(ProductionLotOrmModel.lot_number, term),
                contains_ci(SourceItemOrmModel.dimension, term),
                contains_ci(SourceItemOrmModel.material, term),
                localized_contains(SourceItemTypeOrmModel.name, term),
                contains_ci(BoughtItemOrmModel.article_name, term),
                contains_ci(BoughtItemOrmModel.part_number, term),
                contains_ci(SourceItemDemandItemOrmModel.note, term),
            )
        )

    async def count_by_status(self) -> dict[str, int]:
        return await demand_status_counts(self._db, SourceItemDemandItemOrmModel.status)

    async def get_multi(
        self, filters: SourceItemDemandFilterDto
    ) -> tuple[int, list[SourceItemDemandItem]]:
        q = select(SourceItemDemandItemOrmModel)
        q = apply_filters(q, self._filter_specs(filters))
        q = self._apply_project_and_item_joins(q, filters)

        total, rows = await fetch_page(
            self._db,
            q,
            filters.skip,
            filters.limit,
            _resolve_sort(filters),
            options=source_item_demand_load_options(),
            min_limit=len(filters.ids) if filters.ids else None,
        )
        entities = [_orm_to_entity(r) for r in rows]

        return total, entities

    async def save(self, demand: SourceItemDemandItem) -> SourceItemDemandItem:
        if demand.id == 0:
            new_orm = SourceItemDemandItemOrmModel(**_entity_to_dict(demand))
            self._db.add(new_orm)
            await self._db.flush()
            return _orm_to_entity(await self._reload(new_orm.id))
        existing_orm = await self._get_orm(demand.id)
        if not existing_orm:
            raise ConcurrentModificationError(
                f"SourceItemDemandItemOrmModel id={demand.id} was removed"
                " while this request worked on it; reload and try again."
            )
        for key, value in _entity_to_dict(demand).items():
            setattr(existing_orm, key, value)
        await self._db.flush()
        return _orm_to_entity(await self._reload(existing_orm.id))

    async def _get_orm(self, id: int) -> SourceItemDemandItemOrmModel | None:
        return await self._db.get(SourceItemDemandItemOrmModel, id)

    async def _reload(self, id: int) -> SourceItemDemandItemOrmModel:
        """Re-reads a just written row with everything the mapper needs.
        populate_existing refreshes every column, so server defaults arrive
        as they would through refresh(), and applies the loader options to
        the instance already in the session."""
        return (
            await self._db.scalars(
                by_id(
                    SourceItemDemandItemOrmModel,
                    id,
                    *source_item_demand_load_options(),
                    refresh=True,
                )
            )
        ).one()
