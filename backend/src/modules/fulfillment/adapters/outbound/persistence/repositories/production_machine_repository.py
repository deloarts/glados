"""
Concrete implementation of IProductionMachineRepository using SQLAlchemy + Postgres.
"""

from functools import lru_cache
from typing import Any

from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.catalogue.adapters.outbound.persistence.mappers.catalogue_mappers import (
    fabrication_method_orm_to_entity,
)
from src.modules.catalogue.adapters.outbound.persistence.models.fabrication_method_model import (
    FabricationMethodOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_machine_model import (
    ProductionMachineOrmModel,
)
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.ports.outbound.repositories.production_machine_repository import (
    ProductionMachineFilterDto,
)
from src.modules.platform.adapters.outbound.persistence.like_escape import contains_ci
from src.modules.platform.adapters.outbound.persistence.mapping_common import archived_kwargs
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.adapters.outbound.persistence.statements import fetch_page
from src.modules.platform.adapters.outbound.persistence.statements import load_by_ids
from src.modules.platform.adapters.outbound.persistence.statements import order_term
from src.modules.platform.adapters.outbound.persistence.user_loading import load_user
from src.shared_kernel.domain.services.list_order import ListEntry


@lru_cache(maxsize=1)
def production_machine_load_options() -> tuple[ORMOption, ...]:
    """Everything production_machine_orm_to_entity() dereferences, including the nested
    fabrication method mapper. Built on first call rather than at import,
    because constructing a loader option configures the mapper registry before
    every model module is registered."""
    return (
        load_user(ProductionMachineOrmModel.creator),
        load_user(ProductionMachineOrmModel.changed_by),
        load_user(ProductionMachineOrmModel.fabrication_methods, FabricationMethodOrmModel.creator),
        load_user(
            ProductionMachineOrmModel.fabrication_methods, FabricationMethodOrmModel.changed_by
        ),
    )


def production_machine_orm_to_entity(orm: ProductionMachineOrmModel) -> ProductionMachine:
    return ProductionMachine(
        id=orm.id,
        public_id=orm.public_id,
        created=utc_aware(orm.created),
        **archived_kwargs(utc_aware(orm.changed), orm.changes, orm.archived),
        internal_name=orm.internal_name,
        vendor=orm.vendor,
        model=orm.model,
        fabrication_method_ids=[fm.id for fm in orm.fabrication_methods],
        max_part_dimension=orm.max_part_dimension,
        note=orm.note,
        is_qa_machine=orm.is_qa_machine,
        sort_order=orm.sort_order,
        creator_id=orm.creator_id,
        creator_full_name=orm.creator.full_name if orm.creator else "",
        changed_by_id=orm.changed_by_id,
        changed_by_full_name=orm.changed_by.full_name if orm.changed_by else None,
        fabrication_methods=[
            fabrication_method_orm_to_entity(fm) for fm in orm.fabrication_methods
        ],
    )


def _entity_to_dict(item: ProductionMachine) -> dict[str, Any]:
    return {
        "created": item.created,
        "changed": item.changed,
        "changes": item.changes,
        "archived": item.archived,
        "internal_name": item.internal_name,
        "vendor": item.vendor,
        "model": item.model,
        "max_part_dimension": item.max_part_dimension,
        "note": item.note,
        "is_qa_machine": item.is_qa_machine,
        "sort_order": item.sort_order,
        "creator_id": item.creator_id,
    }


# ── Repository ────────────────────────────────────────────────────────


class SqlAlchemyProductionMachineRepository:
    """Implements IProductionMachineRepository."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, id: int) -> ProductionMachine | None:
        orm = await self._db.scalar(
            by_id(ProductionMachineOrmModel, id, *production_machine_load_options()).limit(1)
        )
        return production_machine_orm_to_entity(orm) if orm else None

    async def get_by_ids(self, ids: list[int]) -> list[ProductionMachine]:
        if not ids:
            return []
        rows = (
            await self._db.scalars(
                select(ProductionMachineOrmModel)
                .where(ProductionMachineOrmModel.id.in_(ids))
                .options(*production_machine_load_options())
            )
        ).all()
        return [production_machine_orm_to_entity(r) for r in rows]

    async def get_multi(
        self, filters: ProductionMachineFilterDto
    ) -> tuple[int, list[ProductionMachine]]:
        q = select(ProductionMachineOrmModel)
        if not filters.include_archived:
            q = q.where(ProductionMachineOrmModel.archived.is_(False))

        if filters.id:
            q = q.where(ProductionMachineOrmModel.id == filters.id)
        if filters.internal_name:
            q = q.where(contains_ci(ProductionMachineOrmModel.internal_name, filters.internal_name))
        if filters.vendor:
            q = q.where(contains_ci(ProductionMachineOrmModel.vendor, filters.vendor))
        if filters.model:
            q = q.where(contains_ci(ProductionMachineOrmModel.model, filters.model))
        if filters.creator_id:
            q = q.where(ProductionMachineOrmModel.creator_id == filters.creator_id)
        if filters.changed_by_id:
            q = q.where(ProductionMachineOrmModel.changed_by_id == filters.changed_by_id)
        if filters.fabrication_method_id:
            q = q.where(
                ProductionMachineOrmModel.fabrication_methods.any(
                    FabricationMethodOrmModel.id == filters.fabrication_method_id
                )
            )
        if filters.search:
            term = filters.search
            q = q.where(
                or_(
                    contains_ci(ProductionMachineOrmModel.internal_name, term),
                    contains_ci(ProductionMachineOrmModel.vendor, term),
                    contains_ci(ProductionMachineOrmModel.model, term),
                    func.similarity(ProductionMachineOrmModel.internal_name, term) > 0.25,
                )
            )

        _sort_column_map = {
            "id": ProductionMachineOrmModel.id,
            "internal_name": ProductionMachineOrmModel.internal_name,
            "vendor": ProductionMachineOrmModel.vendor,
            "model": ProductionMachineOrmModel.model,
            "changed": ProductionMachineOrmModel.changed,
            "created": ProductionMachineOrmModel.created,
        }
        # Without an explicit sort the machines come in their hand-kept order.
        sort_col = _sort_column_map.get(filters.order_by or "")
        order = (
            order_term(sort_col, filters.order_dir, default="desc")
            if sort_col is not None
            else order_term(ProductionMachineOrmModel.sort_order, filters.order_dir, default="asc")
        )
        total, rows = await fetch_page(
            self._db,
            q,
            filters.skip,
            filters.limit,
            order,
            ProductionMachineOrmModel.id,
            options=production_machine_load_options(),
        )
        return total, [production_machine_orm_to_entity(r) for r in rows]

    async def get_all(self) -> list[ProductionMachine]:
        """unpaginated: deliberately bypasses clamp_page, unlike
        get_multi above. Scheduling hot paths (auto-plan, schedule board)
        need every active machine to consider, not a UI page of them;
        see IProductionMachineRepository.get_all's docstring."""
        rows = (
            await self._db.scalars(
                select(ProductionMachineOrmModel)
                .where(ProductionMachineOrmModel.archived.is_(False))
                .options(*production_machine_load_options())
                .order_by(ProductionMachineOrmModel.sort_order, ProductionMachineOrmModel.id)
            )
        ).all()
        return [production_machine_orm_to_entity(r) for r in rows]

    async def get_list_order(self) -> list[ListEntry]:
        m = ProductionMachineOrmModel
        rows = (await self._db.execute(select(m.id, m.sort_order, m.archived))).all()
        return [ListEntry(id_, sort_order, archived) for id_, sort_order, archived in rows]

    async def next_sort_order(self) -> int:
        current = await self._db.scalar(select(func.max(ProductionMachineOrmModel.sort_order)))
        return 0 if current is None else current + 1

    async def set_sort_orders(self, sort_orders: dict[int, int]) -> None:
        """Writes through the ORM, so live updates see the change."""
        for row_id, sort_order in sort_orders.items():
            orm = await self._db.get(ProductionMachineOrmModel, row_id)
            if orm is not None:
                orm.sort_order = sort_order
        await self._db.flush()

    async def _sync_fabrication_methods(
        self, orm: ProductionMachineOrmModel, fabrication_method_ids: list[int]
    ) -> None:
        orm.fabrication_methods = await load_by_ids(
            self._db, FabricationMethodOrmModel, fabrication_method_ids
        )

    async def save(self, item: ProductionMachine) -> ProductionMachine:
        if item.id == 0:
            orm = ProductionMachineOrmModel(**_entity_to_dict(item))
            await self._sync_fabrication_methods(orm, item.fabrication_method_ids)
            self._db.add(orm)
            await self._db.flush()
            new_id = orm.id
            return production_machine_orm_to_entity(await self._reload(new_id))
        existing = await self._fetch_for_update(item.id)
        if not existing:
            raise ValueError(f"ProductionMachineOrmModel id={item.id} not found.")
        orm = existing
        for k, v in _entity_to_dict(item).items():
            setattr(orm, k, v)
        await self._sync_fabrication_methods(orm, item.fabrication_method_ids)
        await self._db.flush()
        return production_machine_orm_to_entity(await self._reload(item.id))

    async def _fetch_for_update(self, id: int) -> ProductionMachineOrmModel | None:
        """Loads fabrication_methods with the row, since
        _sync_fabrication_methods() reassigns the collection and assignment
        reads the old one first."""
        orm: ProductionMachineOrmModel | None = await self._db.scalar(
            select(ProductionMachineOrmModel)
            .where(ProductionMachineOrmModel.id == id)
            .options(selectinload(ProductionMachineOrmModel.fabrication_methods))
            .execution_options(populate_existing=True)
            .limit(1)
        )
        return orm

    async def _reload(self, id: int) -> ProductionMachineOrmModel:
        return (
            await self._db.scalars(
                by_id(
                    ProductionMachineOrmModel, id, *production_machine_load_options(), refresh=True
                )
            )
        ).one()

    async def delete(self, item: ProductionMachine) -> None:
        """Soft delete, sets archived=True and saves."""
        item.archived = True
        await self.save(item)
