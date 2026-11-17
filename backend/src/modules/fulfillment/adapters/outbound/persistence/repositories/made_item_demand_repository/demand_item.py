"""
Concrete SQLAlchemy implementation for the MadeItemDemandItem aggregate.
Mirrors bought_item_repository/demand_item.py, swapping the joined
catalogue table (made_item instead of bought_item, no manufacturer join).
"""

from datetime import date
from datetime import tzinfo
from typing import Any

from sqlalchemy import ColumnElement
from sqlalchemy import Select
from sqlalchemy import and_
from sqlalchemy import asc
from sqlalchemy import desc
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.catalogue.adapters.outbound.persistence.models.made_item_model import (
    MadeItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.made_item_process_model import (
    MadeItemProcessOrmModel,
)
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.adapters.outbound.persistence.allocation_filters import bucket_clause
from src.modules.fulfillment.adapters.outbound.persistence.allocation_filters import (
    demand_not_fully_allocated,
)
from src.modules.fulfillment.adapters.outbound.persistence.allocation_filters import (
    demand_secondary_sort,
)
from src.modules.fulfillment.adapters.outbound.persistence.allocation_filters import (
    demand_status_counts,
)
from src.modules.fulfillment.adapters.outbound.persistence.allocation_filters import (
    demand_todo_candidate,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.made_item_allocation_model import (
    MadeItemAllocationOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.made_item_demand_bucket_model import (
    MadeItemDemandBucketOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.made_item_demand_item_model import (
    MadeItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories._lifecycle_rows import (
    ids_after,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories._lifecycle_rows import (
    lock_rows,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.made_item_demand_repository._mappers import (
    demand_entity_to_dict,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.made_item_demand_repository._mappers import (
    demand_load_options,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.made_item_demand_repository._mappers import (
    demand_orm_to_entity,
)
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    MadeItemDemandFilterDto,
)
from src.modules.platform.adapters.outbound.persistence.date_range import day_after_utc
from src.modules.platform.adapters.outbound.persistence.date_range import day_start_utc
from src.modules.platform.adapters.outbound.persistence.like_escape import contains_ci
from src.modules.platform.adapters.outbound.persistence.models.user_model import UserOrmModel
from src.modules.platform.adapters.outbound.persistence.query_filters import FilterSpec
from src.modules.platform.adapters.outbound.persistence.query_filters import apply_filters
from src.modules.platform.adapters.outbound.persistence.query_filters import when
from src.modules.platform.adapters.outbound.persistence.query_filters import when_not_none
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.adapters.outbound.persistence.statements import fetch_page
from src.modules.platform.adapters.outbound.persistence.tenant_zone import date_filter_zone
from src.modules.platform.adapters.outbound.persistence.tenant_zone import read_tenant_zone
from src.modules.platform.domain.exceptions import ConcurrentModificationError
from src.modules.workspace.adapters.outbound.persistence.mappers.product_projects import (
    in_product_projects,
)
from src.modules.workspace.adapters.outbound.persistence.models.project_model import ProjectOrmModel

# ══════════════════════════════════════════════════════════════════════
# DemandItem repository
# ══════════════════════════════════════════════════════════════════════

# Referencing MadeItemOrmModel/MadeItemDemandBucketOrmModel columns here has
# no join dependency of its own: a plain attribute reference is only ever
# turned into SQL once it reaches .filter()/.order_by(), by which point
# get_multi's join step has already run.
_SORT_COLUMNS: dict[str, Any] = {
    "id": MadeItemDemandItemOrmModel.id,
    "article_name": MadeItemOrmModel.article_name,
    "desired_delivery_date": MadeItemDemandItemOrmModel.desired_delivery_date,
    "created": MadeItemDemandItemOrmModel.created,
    "bucket_name": MadeItemDemandBucketOrmModel.name,
    "project_number": ProjectOrmModel.project_number,
}


def _status_clause(filters: MadeItemDemandFilterDto) -> ColumnElement[bool]:
    """Only called once the caller already knows one of the two is set."""
    if filters.statuses:
        return MadeItemDemandItemOrmModel.status.in_(filters.statuses)
    return MadeItemDemandItemOrmModel.status == filters.status


def _process_method_clause(filters: MadeItemDemandFilterDto) -> ColumnElement[bool]:
    """The two method lists OR'ed together, so a routing step matches when it
    uses any of the chosen methods of either kind. Wrapped in an EXISTS by
    the repository, which alone knows the session to query with."""
    conditions: list[ColumnElement[bool]] = []
    if filters.process_fabrication_method_id:
        conditions.append(
            MadeItemProcessOrmModel.fabrication_method_id.in_(filters.process_fabrication_method_id)
        )
    if filters.process_inspection_method_id:
        conditions.append(
            MadeItemProcessOrmModel.inspection_method_id.in_(filters.process_inspection_method_id)
        )
    return or_(*conditions)


class SqlAlchemyMadeItemDemandItemRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def _reload(self, id: int) -> MadeItemDemandItemOrmModel:
        return (
            await self._db.scalars(
                by_id(MadeItemDemandItemOrmModel, id, *demand_load_options(), refresh=True)
            )
        ).one()

    async def get_by_id(self, id: int) -> MadeItemDemandItem | None:
        orm = await self._db.scalar(by_id(MadeItemDemandItemOrmModel, id, *demand_load_options()))
        return demand_orm_to_entity(orm) if orm else None

    async def get_by_id_for_update(self, id: int) -> MadeItemDemandItem | None:
        orm = await self._db.scalar(
            by_id(
                MadeItemDemandItemOrmModel,
                id,
                *demand_load_options(),
                for_update=True,
                refresh=True,
            ).limit(1)
        )
        return demand_orm_to_entity(orm) if orm else None

    async def get_by_ids(
        self, ids: list[int], *, refresh: bool = False
    ) -> list[MadeItemDemandItem]:
        if not ids:
            return []
        rows = (
            await self._db.scalars(
                select(MadeItemDemandItemOrmModel)
                .where(MadeItemDemandItemOrmModel.id.in_(ids))
                .options(*demand_load_options())
                .execution_options(populate_existing=refresh)
            )
        ).all()
        return [demand_orm_to_entity(r) for r in rows]

    async def lock_for_update(self, ids: list[int]) -> None:
        await lock_rows(self._db, MadeItemDemandItemOrmModel, MadeItemDemandItemOrmModel.id, ids)

    async def get_ids_after(self, after_id: int, limit: int) -> list[int]:
        return await ids_after(self._db, MadeItemDemandItemOrmModel.id, after_id, limit)

    async def get_by_project_id(self, project_id: int) -> list[MadeItemDemandItem]:
        rows = (
            await self._db.scalars(
                select(MadeItemDemandItemOrmModel)
                .where(
                    MadeItemDemandItemOrmModel.project_id == project_id,
                    MadeItemDemandItemOrmModel.status.notin_(
                        [MadeItemDemandStatus.CANCELED.value, MadeItemDemandStatus.FULFILLED.value]
                    ),
                )
                .options(*demand_load_options())
            )
        ).all()
        return [demand_orm_to_entity(r) for r in rows]

    async def get_by_statuses(self, statuses: list[str]) -> list[MadeItemDemandItem]:
        if not statuses:
            return []
        rows = (
            await self._db.scalars(
                select(MadeItemDemandItemOrmModel)
                .where(MadeItemDemandItemOrmModel.status.in_(statuses))
                .options(*demand_load_options())
                .order_by(
                    desc(MadeItemDemandItemOrmModel.high_priority),
                    asc(MadeItemDemandItemOrmModel.desired_delivery_date),
                    MadeItemDemandItemOrmModel.id,
                )
            )
        ).all()
        return [demand_orm_to_entity(r) for r in rows]

    async def get_pipeline(self, terminal_since: date) -> list[MadeItemDemandItem]:
        """
        Returns every demand item that is still "in flight" (open/allocated/ordered)
        plus any demand item that reached a terminal status (fulfilled/canceled) on
        or after `terminal_since`, a day in the tenant's timezone. It is a
        single-query source for the made-item procurement pipeline view.
        Demands of a deleted project are left out.
        """
        in_flight = {
            MadeItemDemandStatus.OPEN.value,
            MadeItemDemandStatus.ALLOCATED.value,
            MadeItemDemandStatus.ORDERED.value,
        }
        terminal = {
            MadeItemDemandStatus.FULFILLED.value,
            MadeItemDemandStatus.CANCELED.value,
        }
        zone = await read_tenant_zone(self._db)
        rows = (
            await self._db.scalars(
                select(MadeItemDemandItemOrmModel)
                .where(
                    or_(
                        MadeItemDemandItemOrmModel.status.in_(in_flight),
                        and_(
                            MadeItemDemandItemOrmModel.status.in_(terminal),
                            MadeItemDemandItemOrmModel.changed
                            >= day_start_utc(terminal_since, zone),
                        ),
                    ),
                    MadeItemDemandItemOrmModel.project.has(deleted=False),
                )
                .options(*demand_load_options())
            )
        ).all()
        return [demand_orm_to_entity(r) for r in rows]

    def _lot_allocation_exists(self, lot_id: list[int]) -> ColumnElement[bool]:
        """EXISTS rather than a join: a demand can hold several allocations
        and a join would multiply the demand row."""
        return (
            select(MadeItemAllocationOrmModel.id)
            .where(
                MadeItemAllocationOrmModel.demand_item_id == MadeItemDemandItemOrmModel.id,
                MadeItemAllocationOrmModel.lot_id.in_(lot_id),
            )
            .exists()
        )

    def _process_method_exists(self, filters: MadeItemDemandFilterDto) -> ColumnElement[bool]:
        return (
            select(MadeItemProcessOrmModel.id)
            .where(
                MadeItemProcessOrmModel.made_item_id == MadeItemDemandItemOrmModel.made_item_id,
                _process_method_clause(filters),
            )
            .exists()
        )

    def _filter_specs(self, filters: MadeItemDemandFilterDto, zone: tzinfo) -> list[FilterSpec]:
        # The created window is a pair of days in `zone`, the tenant's.
        return [
            when(filters.ids, lambda ids: MadeItemDemandItemOrmModel.id.in_(ids)),
            when(filters.statuses or filters.status, lambda _: _status_clause(filters)),
            when(
                filters.project_id,
                lambda project_id: MadeItemDemandItemOrmModel.project_id == project_id,
            ),
            when(
                filters.product_id,
                lambda product_id: in_product_projects(
                    MadeItemDemandItemOrmModel.project_id, product_id
                ),
            ),
            when(
                filters.made_item_id,
                lambda made_item_id: MadeItemDemandItemOrmModel.made_item_id == made_item_id,
            ),
            when(
                filters.creator_id,
                lambda creator_id: MadeItemDemandItemOrmModel.creator_id == creator_id,
            ),
            when(
                filters.changed_by_id,
                lambda changed_by_id: MadeItemDemandItemOrmModel.changed_by_id == changed_by_id,
            ),
            when_not_none(
                filters.high_priority,
                lambda high_priority: MadeItemDemandItemOrmModel.high_priority.is_(high_priority),
            ),
            when(
                filters.project_number,
                lambda project_number: contains_ci(ProjectOrmModel.project_number, project_number),
            ),
            when(
                filters.desired_from,
                lambda desired_from: (
                    MadeItemDemandItemOrmModel.desired_delivery_date >= desired_from
                ),
            ),
            when(
                filters.desired_to,
                lambda desired_to: MadeItemDemandItemOrmModel.desired_delivery_date <= desired_to,
            ),
            when(
                filters.created_from,
                lambda created_from: (
                    MadeItemDemandItemOrmModel.created >= day_start_utc(created_from, zone)
                ),
            ),
            when(
                filters.created_to,
                lambda created_to: (
                    MadeItemDemandItemOrmModel.created < day_after_utc(created_to, zone)
                ),
            ),
            when(
                filters.ignore_fulfilled,
                lambda _: MadeItemDemandItemOrmModel.status != MadeItemDemandStatus.FULFILLED.value,
            ),
            when(
                filters.ignore_canceled,
                lambda _: MadeItemDemandItemOrmModel.status != MadeItemDemandStatus.CANCELED.value,
            ),
            when(
                filters.not_fully_allocated,
                lambda _: demand_not_fully_allocated(
                    demand_id=MadeItemDemandItemOrmModel.id,
                    demand_quantity=MadeItemDemandItemOrmModel.quantity,
                    demand_status=MadeItemDemandItemOrmModel.status,
                    allocation_demand_item_id=MadeItemAllocationOrmModel.demand_item_id,
                    allocation_quantity=MadeItemAllocationOrmModel.quantity,
                    terminal_statuses=[
                        MadeItemDemandStatus.FULFILLED.value,
                        MadeItemDemandStatus.CANCELED.value,
                    ],
                ),
            ),
            when(filters.lot_id, lambda lot_id: self._lot_allocation_exists(lot_id)),
            when(
                filters.process_fabrication_method_id or filters.process_inspection_method_id,
                lambda _: self._process_method_exists(filters),
            ),
            when(
                filters.bucket_id or filters.include_unbucketed,
                lambda _: bucket_clause(
                    MadeItemDemandItemOrmModel.bucket_id,
                    filters.bucket_id,
                    filters.include_unbucketed,
                ),
            ),
            when(
                filters.todo_horizon,
                lambda horizon: demand_todo_candidate(
                    demand_status=MadeItemDemandItemOrmModel.status,
                    desired_delivery_date=MadeItemDemandItemOrmModel.desired_delivery_date,
                    open_status=MadeItemDemandStatus.OPEN.value,
                    horizon=horizon,
                ),
            ),
        ]

    def _apply_item_join_and_search(
        self, q: Select[Any], filters: MadeItemDemandFilterDto
    ) -> Select[Any]:
        needs_item_join = any(
            [
                filters.item_article_name,
                filters.item_part_number,
                filters.search,
                filters.order_by == "article_name",
            ]
        )
        if needs_item_join:
            q = q.join(MadeItemOrmModel, MadeItemDemandItemOrmModel.item)

        if filters.order_by == "bucket_name":
            q = q.outerjoin(
                MadeItemDemandBucketOrmModel,
                MadeItemDemandItemOrmModel.bucket_id == MadeItemDemandBucketOrmModel.id,
            )

        if filters.item_article_name:
            q = q.where(contains_ci(MadeItemOrmModel.article_name, filters.item_article_name))
        if filters.item_part_number:
            q = q.where(contains_ci(MadeItemOrmModel.part_number, filters.item_part_number))

        if filters.search:
            term = filters.search
            q = q.join(UserOrmModel, MadeItemDemandItemOrmModel.creator)
            q = q.where(
                or_(
                    contains_ci(MadeItemOrmModel.article_name, term),
                    contains_ci(MadeItemOrmModel.part_number, term),
                    contains_ci(ProjectOrmModel.project_number, term),
                    contains_ci(MadeItemDemandItemOrmModel.note, term),
                    func.similarity(MadeItemOrmModel.article_name, term) > 0.25,
                    func.similarity(ProjectOrmModel.project_number, term) > 0.25,
                    func.similarity(UserOrmModel.full_name, term) > 0.25,
                )
            )
        return q

    async def count_by_status(self) -> dict[str, int]:
        return await demand_status_counts(self._db, MadeItemDemandItemOrmModel.status)

    async def get_multi(
        self, filters: MadeItemDemandFilterDto
    ) -> tuple[int, list[MadeItemDemandItem]]:
        q: Select[Any] = select(MadeItemDemandItemOrmModel).join(
            ProjectOrmModel, MadeItemDemandItemOrmModel.project
        )
        zone = await date_filter_zone(self._db, filters.created_from, filters.created_to)
        q = apply_filters(q, self._filter_specs(filters, zone))
        q = self._apply_item_join_and_search(q, filters)

        secondary = demand_secondary_sort(
            filters.order_by,
            filters.order_dir,
            _SORT_COLUMNS,
            MadeItemDemandItemOrmModel.id,
        )
        total, rows = await fetch_page(
            self._db,
            q,
            filters.skip,
            filters.limit,
            desc(MadeItemDemandItemOrmModel.high_priority),
            secondary,
            desc(MadeItemDemandItemOrmModel.id),
            options=demand_load_options(),
            min_limit=len(filters.ids) if filters.ids else None,
        )
        return total, [demand_orm_to_entity(r) for r in rows]

    async def save(self, demand: MadeItemDemandItem) -> MadeItemDemandItem:
        if demand.id == 0:
            orm = MadeItemDemandItemOrmModel(**demand_entity_to_dict(demand))
            self._db.add(orm)
            await self._db.flush()
            return demand_orm_to_entity(await self._reload(orm.id))
        existing = await self._db.get(MadeItemDemandItemOrmModel, demand.id)
        if not existing:
            raise ConcurrentModificationError(
                f"MadeItemDemandItemOrmModel id={demand.id} was removed"
                " while this request worked on it; reload and try again."
            )
        orm = existing
        for k, v in demand_entity_to_dict(demand).items():
            setattr(orm, k, v)
        await self._db.flush()
        return demand_orm_to_entity(await self._reload(orm.id))

    async def delete(self, demand: MadeItemDemandItem) -> None:
        orm = await self._db.get(MadeItemDemandItemOrmModel, demand.id)
        if orm:
            await self._db.delete(orm)
            await self._db.flush()
