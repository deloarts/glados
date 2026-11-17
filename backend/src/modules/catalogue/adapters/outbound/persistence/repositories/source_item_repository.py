"""
Concrete implementation of ISourceItemRepository using SQLAlchemy + Postgres.
"""

from datetime import datetime
from functools import lru_cache
from typing import Any

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.catalogue.adapters.outbound.persistence.mappers.source_item_mappers import (
    source_item_orm_to_entity,
)
from src.modules.catalogue.adapters.outbound.persistence.models.source_item_model import (
    SourceItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.source_item_type_model import (
    SourceItemTypeOrmModel,
)
from src.modules.catalogue.domain.entities.source_item import SourceItem
from src.modules.catalogue.ports.outbound.repositories.source_item_repository import (
    ISourceItemRepository,
)
from src.modules.catalogue.ports.outbound.repositories.source_item_repository import (
    SourceItemFilterDto,
)
from src.modules.platform.adapters.outbound.persistence.like_escape import contains_ci
from src.modules.platform.adapters.outbound.persistence.localized_text_sql import localized_contains
from src.modules.platform.adapters.outbound.persistence.mapping_common import archived_kwargs
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.adapters.outbound.persistence.statements import fetch_page
from src.modules.platform.adapters.outbound.persistence.statements import lock_row
from src.modules.platform.adapters.outbound.persistence.statements import order_term
from src.modules.platform.adapters.outbound.persistence.user_loading import load_user

# ── Mapping helpers ───────────────────────────────────────────────────


# Every relationship source_item_orm_to_entity reads. The models default to
# lazy="raise_on_sql", so each select whose rows reach the mapper names its
# loads explicitly through this function. Built lazily, since constructing a
# loader option configures the mappers, which needs every model registered.
@lru_cache(maxsize=1)
def source_item_load_options() -> tuple[ORMOption, ...]:
    return (
        load_user(SourceItemOrmModel.creator),
        load_user(SourceItemOrmModel.changed_by),
        selectinload(SourceItemOrmModel.type),
        selectinload(SourceItemOrmModel.manufacturer),
    )


def _entity_to_dict(item: SourceItem) -> dict[str, Any]:
    return {
        "created": item.created,
        "type_id": item.type_id,
        "dimension": item.dimension,
        "material": item.material,
        "mass": item.mass,
        "note": item.note,
        "order_code_1": item.order_code_1,
        "order_code_2": item.order_code_2,
        "status": item.status.value,
        "creator_id": item.creator_id,
        "approver_id": item.approver_id,
        "manufacturer_id": item.manufacturer_id,
        "successor_item_id": item.successor_item_id,
        "over_delivery_tolerance_percent": item.over_delivery_tolerance_percent,
        "under_delivery_tolerance_percent": item.under_delivery_tolerance_percent,
        **archived_kwargs(item.changed, item.changes, item.archived),
    }


# ── Repository ────────────────────────────────────────────────────────


class SqlAlchemySourceItemRepository(ISourceItemRepository):
    """Implements ISourceItemRepository."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, id: int) -> SourceItem | None:
        orm = await self._db.scalar(
            by_id(SourceItemOrmModel, id, *source_item_load_options()).limit(1)
        )
        return source_item_orm_to_entity(orm) if orm else None

    async def lock_for_update(self, id: int) -> None:
        await lock_row(self._db, SourceItemOrmModel, id)

    async def get_by_spec_candidates(
        self,
        type_id: int,
        material: str,
        manufacturer_id: int | None,
    ) -> list[SourceItem]:
        """Finds every non-archived source item sharing type/material/
        manufacturer, the same grouping the DB's partial unique indexes
        enforce (a full match on manufacturer when one is set, or a match
        among manufacturer-less items when it isn't). Dimension is left to
        the caller: create/update use cases compare dimension_spec.py's
        canonical form across these candidates, since permutation-
        equivalent dimensions (e.g. "100 × 200" vs "200 × 100") aren't
        equal as raw strings."""
        q = select(SourceItemOrmModel).where(
            SourceItemOrmModel.archived.is_(False),
            SourceItemOrmModel.type_id == type_id,
            SourceItemOrmModel.material == material,
        )
        q = q.where(
            SourceItemOrmModel.manufacturer_id == manufacturer_id
            if manufacturer_id is not None
            else SourceItemOrmModel.manufacturer_id.is_(None)
        )
        q = q.options(*source_item_load_options())
        return [source_item_orm_to_entity(orm) for orm in (await self._db.scalars(q)).all()]

    async def get_multi(self, filters: SourceItemFilterDto) -> tuple[int, list[SourceItem]]:
        q = select(SourceItemOrmModel)
        if not filters.include_archived:
            q = q.where(SourceItemOrmModel.archived.is_(False))

        if filters.id is not None:
            q = q.where(SourceItemOrmModel.id == filters.id)
        if filters.status:
            q = q.where(SourceItemOrmModel.status == filters.status)
        if filters.type_id is not None:
            q = q.where(SourceItemOrmModel.type_id == filters.type_id)
        if filters.material:
            q = q.where(contains_ci(SourceItemOrmModel.material, filters.material))
        if filters.dimension:
            q = q.where(contains_ci(SourceItemOrmModel.dimension, filters.dimension))
        if filters.note:
            q = q.where(contains_ci(SourceItemOrmModel.note, filters.note))
        if filters.order_code_1:
            q = q.where(contains_ci(SourceItemOrmModel.order_code_1, filters.order_code_1))
        if filters.order_code_2:
            q = q.where(contains_ci(SourceItemOrmModel.order_code_2, filters.order_code_2))
        if filters.successor_item_id is not None:
            q = q.where(SourceItemOrmModel.successor_item_id == filters.successor_item_id)
        if filters.manufacturer_id is not None:
            q = q.where(SourceItemOrmModel.manufacturer_id == filters.manufacturer_id)
        if filters.creator_id is not None:
            q = q.where(SourceItemOrmModel.creator_id == filters.creator_id)
        if filters.changed_by_id is not None:
            q = q.where(SourceItemOrmModel.changed_by_id == filters.changed_by_id)
        if filters.approver_id is not None:
            q = q.where(SourceItemOrmModel.approver_id == filters.approver_id)
        if filters.created_from:
            q = q.where(SourceItemOrmModel.created >= filters.created_from)
        if filters.created_to:
            q = q.where(SourceItemOrmModel.created <= filters.created_to)
        if filters.changed_from:
            q = q.where(SourceItemOrmModel.changed >= filters.changed_from)
        if filters.changed_to:
            q = q.where(SourceItemOrmModel.changed <= filters.changed_to)
        if filters.search:
            term = filters.search
            q = q.join(
                SourceItemTypeOrmModel, SourceItemOrmModel.type_id == SourceItemTypeOrmModel.id
            )
            q = q.where(
                (localized_contains(SourceItemTypeOrmModel.name, term))
                | (contains_ci(SourceItemOrmModel.dimension, term))
                | (contains_ci(SourceItemOrmModel.material, term))
                | (contains_ci(SourceItemOrmModel.note, term))
                | (contains_ci(SourceItemOrmModel.order_code_1, term))
                | (contains_ci(SourceItemOrmModel.order_code_2, term))
            )

        _sort_column_map = {
            "id": SourceItemOrmModel.id,
            "changed": SourceItemOrmModel.changed,
            "created": SourceItemOrmModel.created,
        }
        sort_col = _sort_column_map.get(filters.order_by or "id", SourceItemOrmModel.id)
        # Eager-load the relationships the mapper dereferences, so a page is a
        # handful of queries instead of one-per-row-per-relationship (N+1).
        total, rows = await fetch_page(
            self._db,
            q,
            filters.skip,
            filters.limit,
            order_term(sort_col, filters.order_dir, default="desc"),
            options=source_item_load_options(),
        )
        return total, [source_item_orm_to_entity(r) for r in rows]

    async def get_aggregate(self) -> tuple[int, datetime | None]:
        count, max_changed = (
            await self._db.execute(
                select(func.count(SourceItemOrmModel.id), func.max(SourceItemOrmModel.changed))
            )
        ).one()
        return count, max_changed

    async def _reload(self, id: int) -> SourceItemOrmModel:
        """Re-reads a just written row with everything the mapper needs.
        populate_existing refreshes every column, so server defaults arrive
        as they would through refresh(), and applies the loader options to
        the instance already in the session."""
        return (
            await self._db.scalars(
                by_id(SourceItemOrmModel, id, *source_item_load_options(), refresh=True)
            )
        ).one()

    async def save(self, item: SourceItem) -> SourceItem:
        if item.id == 0:
            orm = SourceItemOrmModel(**_entity_to_dict(item))
            self._db.add(orm)
            await self._db.flush()
            return source_item_orm_to_entity(await self._reload(orm.id))
        existing = await self._db.get(SourceItemOrmModel, item.id)
        if not existing:
            raise ValueError(f"SourceItemOrmModel id={item.id} not found.")
        orm = existing
        for key, value in _entity_to_dict(item).items():
            setattr(orm, key, value)
        await self._db.flush()
        return source_item_orm_to_entity(await self._reload(orm.id))

    async def delete(self, item: SourceItem) -> None:
        """Hard delete. Archiving through save() is the usual way to remove a row."""
        # The flush that deletes the row nulls the FK on its files, so that
        # collection is loaded up front.
        orm = await self._db.get(
            SourceItemOrmModel,
            item.id,
            options=[selectinload(SourceItemOrmModel.files)],
            populate_existing=True,
        )
        if orm:
            await self._db.delete(orm)
            await self._db.flush()
