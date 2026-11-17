"""
Concrete SQLAlchemy implementation for the BoughtItemDemandItem aggregate.
"""

from datetime import date
from datetime import tzinfo
from typing import Any

from sqlalchemy import ColumnElement
from sqlalchemy import Select
from sqlalchemy import and_
from sqlalchemy import desc
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model import (
    BoughtItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.supplier_model import (
    SupplierOrmModel,
)
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
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
from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_allocation_model import (
    BoughtItemAllocationOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_demand_bucket_model import (
    BoughtItemDemandBucketOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.bought_item_demand_item_model import (
    BoughtItemDemandItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.quote_request_model import (
    QuoteRequestLineDemandOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories._lifecycle_rows import (
    ids_after,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories._lifecycle_rows import (
    lock_rows,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_repository._demand_mappers import (
    bought_item_demand_load_options,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_repository._demand_mappers import (
    demand_entity_to_dict,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.bought_item_repository._demand_mappers import (
    demand_orm_to_entity,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.quote_request_repository._cleanup import (
    delete_demand_shares,
)
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    DemandItemFilterDto,
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

# Referencing BoughtItemOrmModel/SupplierOrmModel/BoughtItemDemandBucketOrmModel
# columns here has no join dependency of its own: a plain attribute
# reference only turns into SQL once it reaches .where()/.order_by(), by
# which point get_multi's join step has already run.
_SORT_COLUMNS: dict[str, Any] = {
    "id": BoughtItemDemandItemOrmModel.id,
    "article_name": BoughtItemOrmModel.article_name,
    "manufacturer_name": SupplierOrmModel.name,
    "desired_delivery_date": BoughtItemDemandItemOrmModel.desired_delivery_date,
    "created": BoughtItemDemandItemOrmModel.created,
    "bucket_name": BoughtItemDemandBucketOrmModel.name,
    "project_number": ProjectOrmModel.project_number,
}


class SqlAlchemyBoughtItemDemandItemRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, id: int) -> BoughtItemDemandItem | None:
        orm = await self._db.scalar(
            by_id(BoughtItemDemandItemOrmModel, id, *bought_item_demand_load_options()).limit(1)
        )
        return demand_orm_to_entity(orm) if orm else None

    async def get_by_id_for_update(self, id: int) -> BoughtItemDemandItem | None:
        orm = await self._db.scalar(
            by_id(
                BoughtItemDemandItemOrmModel,
                id,
                *bought_item_demand_load_options(),
                for_update=True,
                refresh=True,
            ).limit(1)
        )
        return demand_orm_to_entity(orm) if orm else None

    async def get_by_ids(
        self, ids: list[int], *, refresh: bool = False
    ) -> list[BoughtItemDemandItem]:
        if not ids:
            return []
        rows = (
            await self._db.scalars(
                select(BoughtItemDemandItemOrmModel)
                .where(BoughtItemDemandItemOrmModel.id.in_(ids))
                .options(*bought_item_demand_load_options())
                .execution_options(populate_existing=refresh)
            )
        ).all()
        return [demand_orm_to_entity(r) for r in rows]

    async def lock_for_update(self, ids: list[int]) -> None:
        await lock_rows(
            self._db, BoughtItemDemandItemOrmModel, BoughtItemDemandItemOrmModel.id, ids
        )

    async def get_ids_after(self, after_id: int, limit: int) -> list[int]:
        return await ids_after(self._db, BoughtItemDemandItemOrmModel.id, after_id, limit)

    async def get_by_project_id(self, project_id: int) -> list[BoughtItemDemandItem]:
        rows = (
            await self._db.scalars(
                select(BoughtItemDemandItemOrmModel)
                .where(
                    BoughtItemDemandItemOrmModel.project_id == project_id,
                    BoughtItemDemandItemOrmModel.status.notin_(
                        [
                            BoughtItemDemandStatus.CANCELED.value,
                            BoughtItemDemandStatus.FULFILLED.value,
                        ]
                    ),
                )
                .options(*bought_item_demand_load_options())
            )
        ).all()
        return [demand_orm_to_entity(r) for r in rows]

    async def get_pipeline(self, terminal_since: date) -> list[BoughtItemDemandItem]:
        """
        Returns every demand item that is still "in flight" (open/allocated/ordered)
        plus any demand item that reached a terminal status (fulfilled/canceled) on
        or after `terminal_since`, a day in the tenant's timezone. It is a
        single-query source for the procurement pipeline view. Demands of a deleted project are
        left out.
        """
        in_flight = {
            BoughtItemDemandStatus.OPEN.value,
            BoughtItemDemandStatus.ALLOCATED.value,
            BoughtItemDemandStatus.ORDERED.value,
        }
        terminal = {
            BoughtItemDemandStatus.FULFILLED.value,
            BoughtItemDemandStatus.CANCELED.value,
        }
        zone = await read_tenant_zone(self._db)
        rows = (
            await self._db.scalars(
                select(BoughtItemDemandItemOrmModel)
                .where(
                    or_(
                        BoughtItemDemandItemOrmModel.status.in_(in_flight),
                        and_(
                            BoughtItemDemandItemOrmModel.status.in_(terminal),
                            BoughtItemDemandItemOrmModel.changed
                            >= day_start_utc(terminal_since, zone),
                        ),
                    ),
                    BoughtItemDemandItemOrmModel.project.has(deleted=False),
                )
                .options(*bought_item_demand_load_options())
            )
        ).all()
        return [demand_orm_to_entity(r) for r in rows]

    def _order_allocation_exists(self, order_id: list[int]) -> ColumnElement[bool]:
        """EXISTS rather than a join: a demand can hold several allocations
        and a join would multiply the demand row."""
        return (
            select(BoughtItemAllocationOrmModel.id)
            .join(
                OrderItemOrmModel,
                OrderItemOrmModel.id == BoughtItemAllocationOrmModel.order_item_id,
            )
            .where(
                BoughtItemAllocationOrmModel.demand_item_id == BoughtItemDemandItemOrmModel.id,
                OrderItemOrmModel.order_id.in_(order_id),
            )
            .exists()
        )

    def _filter_specs(self, filters: DemandItemFilterDto, zone: tzinfo) -> list[FilterSpec]:
        # The created window is a pair of days in `zone`, the tenant's.
        return [
            when(filters.ids, lambda ids: BoughtItemDemandItemOrmModel.id.in_(ids)),
            when(filters.status, lambda status: BoughtItemDemandItemOrmModel.status == status),
            when(
                filters.project_id,
                lambda project_id: BoughtItemDemandItemOrmModel.project_id == project_id,
            ),
            when(
                filters.product_id,
                lambda product_id: in_product_projects(
                    BoughtItemDemandItemOrmModel.project_id, product_id
                ),
            ),
            when(filters.item_id, lambda item_id: BoughtItemDemandItemOrmModel.item_id == item_id),
            when(
                filters.creator_id,
                lambda creator_id: BoughtItemDemandItemOrmModel.creator_id == creator_id,
            ),
            when(
                filters.changed_by_id,
                lambda changed_by_id: BoughtItemDemandItemOrmModel.changed_by_id == changed_by_id,
            ),
            when_not_none(
                filters.high_priority,
                lambda high_priority: BoughtItemDemandItemOrmModel.high_priority.is_(high_priority),
            ),
            when(
                filters.project_number,
                lambda project_number: contains_ci(ProjectOrmModel.project_number, project_number),
            ),
            when(
                filters.desired_from,
                lambda desired_from: (
                    BoughtItemDemandItemOrmModel.desired_delivery_date >= desired_from
                ),
            ),
            when(
                filters.desired_to,
                lambda desired_to: BoughtItemDemandItemOrmModel.desired_delivery_date <= desired_to,
            ),
            when(
                filters.created_from,
                lambda created_from: (
                    BoughtItemDemandItemOrmModel.created >= day_start_utc(created_from, zone)
                ),
            ),
            when(
                filters.created_to,
                lambda created_to: (
                    BoughtItemDemandItemOrmModel.created < day_after_utc(created_to, zone)
                ),
            ),
            when(
                filters.ignore_fulfilled,
                lambda _: (
                    BoughtItemDemandItemOrmModel.status != BoughtItemDemandStatus.FULFILLED.value
                ),
            ),
            when(
                filters.ignore_canceled,
                lambda _: (
                    BoughtItemDemandItemOrmModel.status != BoughtItemDemandStatus.CANCELED.value
                ),
            ),
            when(
                filters.not_fully_allocated,
                lambda _: demand_not_fully_allocated(
                    demand_id=BoughtItemDemandItemOrmModel.id,
                    demand_quantity=BoughtItemDemandItemOrmModel.quantity,
                    demand_status=BoughtItemDemandItemOrmModel.status,
                    allocation_demand_item_id=BoughtItemAllocationOrmModel.demand_item_id,
                    allocation_quantity=BoughtItemAllocationOrmModel.quantity,
                    terminal_statuses=[
                        BoughtItemDemandStatus.FULFILLED.value,
                        BoughtItemDemandStatus.CANCELED.value,
                    ],
                ),
            ),
            when(filters.order_id, lambda order_id: self._order_allocation_exists(order_id)),
            when(
                filters.bucket_id or filters.include_unbucketed,
                lambda _: bucket_clause(
                    BoughtItemDemandItemOrmModel.bucket_id,
                    filters.bucket_id,
                    filters.include_unbucketed,
                ),
            ),
            when(
                filters.todo_horizon,
                lambda horizon: demand_todo_candidate(
                    demand_status=BoughtItemDemandItemOrmModel.status,
                    desired_delivery_date=BoughtItemDemandItemOrmModel.desired_delivery_date,
                    open_status=BoughtItemDemandStatus.OPEN.value,
                    horizon=horizon,
                ),
            ),
        ]

    def _apply_item_join_and_search(
        self, q: Select[tuple[BoughtItemDemandItemOrmModel]], filters: DemandItemFilterDto
    ) -> Select[tuple[BoughtItemDemandItemOrmModel]]:
        needs_item_join = any(
            [
                filters.item_order_code_1,
                filters.item_order_code_2,
                filters.item_article_name,
                filters.item_part_number,
                filters.item_manufacturer_name,
                filters.item_manufacturer_id,
                filters.search,
                filters.order_by in ("article_name", "manufacturer_name"),
            ]
        )
        if needs_item_join:
            q = q.join(BoughtItemOrmModel, BoughtItemDemandItemOrmModel.item)

        needs_supplier_join = any(
            [
                filters.item_manufacturer_name,
                filters.search,
                filters.order_by == "manufacturer_name",
            ]
        )
        if needs_supplier_join:
            q = q.join(SupplierOrmModel, BoughtItemOrmModel.manufacturer)

        if filters.order_by == "bucket_name":
            q = q.outerjoin(
                BoughtItemDemandBucketOrmModel,
                BoughtItemDemandItemOrmModel.bucket_id == BoughtItemDemandBucketOrmModel.id,
            )

        if filters.item_order_code_1:
            q = q.where(contains_ci(BoughtItemOrmModel.order_code_1, filters.item_order_code_1))
        if filters.item_order_code_2:
            q = q.where(contains_ci(BoughtItemOrmModel.order_code_2, filters.item_order_code_2))
        if filters.item_article_name:
            q = q.where(contains_ci(BoughtItemOrmModel.article_name, filters.item_article_name))
        if filters.item_part_number:
            q = q.where(contains_ci(BoughtItemOrmModel.part_number, filters.item_part_number))
        if filters.item_manufacturer_name:
            q = q.where(contains_ci(SupplierOrmModel.name, filters.item_manufacturer_name))
        if filters.item_manufacturer_id:
            q = q.where(BoughtItemOrmModel.manufacturer_id == filters.item_manufacturer_id)

        if filters.search:
            term = filters.search
            q = q.join(UserOrmModel, BoughtItemDemandItemOrmModel.creator)
            q = q.where(
                or_(
                    contains_ci(BoughtItemOrmModel.order_code_1, term),
                    contains_ci(BoughtItemOrmModel.article_name, term),
                    contains_ci(BoughtItemOrmModel.order_code_2, term),
                    contains_ci(BoughtItemOrmModel.part_number, term),
                    contains_ci(SupplierOrmModel.name, term),
                    contains_ci(ProjectOrmModel.project_number, term),
                    contains_ci(BoughtItemDemandItemOrmModel.note, term),
                    func.similarity(BoughtItemOrmModel.order_code_1, term) > 0.25,
                    func.similarity(BoughtItemOrmModel.article_name, term) > 0.25,
                    func.similarity(SupplierOrmModel.name, term) > 0.25,
                    func.similarity(ProjectOrmModel.project_number, term) > 0.25,
                    func.similarity(UserOrmModel.full_name, term) > 0.25,
                )
            )
        return q

    async def count_by_status(self) -> dict[str, int]:
        return await demand_status_counts(self._db, BoughtItemDemandItemOrmModel.status)

    async def get_multi(
        self, filters: DemandItemFilterDto
    ) -> tuple[int, list[BoughtItemDemandItem]]:
        q = select(BoughtItemDemandItemOrmModel).join(
            ProjectOrmModel, BoughtItemDemandItemOrmModel.project
        )
        zone = await date_filter_zone(self._db, filters.created_from, filters.created_to)
        q = apply_filters(q, self._filter_specs(filters, zone))
        q = self._apply_item_join_and_search(q, filters)

        secondary = demand_secondary_sort(
            filters.order_by,
            filters.order_dir,
            _SORT_COLUMNS,
            BoughtItemDemandItemOrmModel.id,
        )
        total, rows = await fetch_page(
            self._db,
            q,
            filters.skip,
            filters.limit,
            desc(BoughtItemDemandItemOrmModel.high_priority),
            secondary,
            desc(BoughtItemDemandItemOrmModel.id),
            options=bought_item_demand_load_options(),
            min_limit=len(filters.ids) if filters.ids else None,
        )
        return total, [demand_orm_to_entity(r) for r in rows]

    async def _reload(self, id: int) -> BoughtItemDemandItemOrmModel:
        """Re-reads a just written row with everything the mapper needs.
        populate_existing refreshes every column, so server defaults arrive
        as they would through refresh(), and applies the loader options to
        the instance already in the session."""
        return (
            await self._db.scalars(
                by_id(
                    BoughtItemDemandItemOrmModel,
                    id,
                    *bought_item_demand_load_options(),
                    refresh=True,
                )
            )
        ).one()

    async def _get_for_delete(self, id: int) -> BoughtItemDemandItemOrmModel | None:
        """The flush that deletes the row nulls the FK on its allocations,
        so that collection is loaded up front."""
        return await self._db.get(
            BoughtItemDemandItemOrmModel,
            id,
            options=[selectinload(BoughtItemDemandItemOrmModel.allocations)],
            populate_existing=True,
        )

    async def save(self, demand: BoughtItemDemandItem) -> BoughtItemDemandItem:
        if demand.id == 0:
            orm = BoughtItemDemandItemOrmModel(**demand_entity_to_dict(demand))
            self._db.add(orm)
            await self._db.flush()
            return demand_orm_to_entity(await self._reload(orm.id))
        existing = await self._db.get(BoughtItemDemandItemOrmModel, demand.id)
        if not existing:
            raise ConcurrentModificationError(
                f"BoughtItemDemandItemOrmModel id={demand.id} was removed"
                " while this request worked on it; reload and try again."
            )
        orm = existing
        for k, v in demand_entity_to_dict(demand).items():
            setattr(orm, k, v)
        await self._db.flush()
        return demand_orm_to_entity(await self._reload(orm.id))

    async def delete(self, demand: BoughtItemDemandItem) -> None:
        orm = await self._get_for_delete(demand.id)
        if orm:
            # A quote request line keeps standing; only the share is gone.
            await delete_demand_shares(
                self._db, QuoteRequestLineDemandOrmModel.bought_demand_item_id == demand.id
            )
            await self._db.delete(orm)
            await self._db.flush()
