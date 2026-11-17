"""
Concrete implementation of IMachinePoolRepository using SQLAlchemy + Postgres.
"""

from functools import lru_cache
from typing import Any

from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.catalogue.adapters.outbound.persistence.models.fabrication_method_model import (
    FabricationMethodOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.machine_pool_model import (
    MachinePoolOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_machine_model import (
    ProductionMachineOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_machine_repository import (
    production_machine_orm_to_entity,
)
from src.modules.fulfillment.domain.entities.machine_pool import MachinePool
from src.modules.fulfillment.ports.outbound.repositories.machine_pool_repository import (
    MachinePoolFilterDto,
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
def _load_options() -> tuple[ORMOption, ...]:
    """Everything _orm_to_entity() dereferences, including the nested
    production machine mapper. Built on first call rather than at import,
    because constructing a loader option configures the mapper registry before
    every model module is registered."""
    return (
        load_user(MachinePoolOrmModel.creator),
        load_user(MachinePoolOrmModel.changed_by),
        load_user(MachinePoolOrmModel.machines, ProductionMachineOrmModel.creator),
        load_user(MachinePoolOrmModel.machines, ProductionMachineOrmModel.changed_by),
        load_user(
            MachinePoolOrmModel.machines,
            ProductionMachineOrmModel.fabrication_methods,
            FabricationMethodOrmModel.creator,
        ),
        load_user(
            MachinePoolOrmModel.machines,
            ProductionMachineOrmModel.fabrication_methods,
            FabricationMethodOrmModel.changed_by,
        ),
    )


def _orm_to_entity(orm: MachinePoolOrmModel) -> MachinePool:
    return MachinePool(
        id=orm.id,
        public_id=orm.public_id,
        created=utc_aware(orm.created),
        **archived_kwargs(utc_aware(orm.changed), orm.changes, orm.archived),
        name=orm.name,
        machine_ids=[m.id for m in orm.machines],
        note=orm.note,
        sort_order=orm.sort_order,
        creator_id=orm.creator_id,
        creator_full_name=orm.creator.full_name if orm.creator else "",
        changed_by_id=orm.changed_by_id,
        changed_by_full_name=orm.changed_by.full_name if orm.changed_by else None,
        machines=[production_machine_orm_to_entity(m) for m in orm.machines],
    )


def _entity_to_dict(item: MachinePool) -> dict[str, Any]:
    return {
        "created": item.created,
        "changed": item.changed,
        "changes": item.changes,
        "archived": item.archived,
        "name": item.name,
        "note": item.note,
        "sort_order": item.sort_order,
        "creator_id": item.creator_id,
    }


# ── Repository ────────────────────────────────────────────────────────


class SqlAlchemyMachinePoolRepository:
    """Implements IMachinePoolRepository."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_id(self, id: int) -> MachinePool | None:
        orm = await self._db.scalar(by_id(MachinePoolOrmModel, id, *_load_options()).limit(1))
        return _orm_to_entity(orm) if orm else None

    async def get_by_ids(self, ids: list[int]) -> list[MachinePool]:
        if not ids:
            return []
        rows = (
            await self._db.scalars(
                select(MachinePoolOrmModel)
                .where(MachinePoolOrmModel.id.in_(ids))
                .options(*_load_options())
            )
        ).all()
        return [_orm_to_entity(r) for r in rows]

    async def get_multi(self, filters: MachinePoolFilterDto) -> tuple[int, list[MachinePool]]:
        q = select(MachinePoolOrmModel)
        if not filters.include_archived:
            q = q.where(MachinePoolOrmModel.archived.is_(False))

        if filters.id:
            q = q.where(MachinePoolOrmModel.id == filters.id)
        if filters.name:
            q = q.where(contains_ci(MachinePoolOrmModel.name, filters.name))
        if filters.creator_id:
            q = q.where(MachinePoolOrmModel.creator_id == filters.creator_id)
        if filters.changed_by_id:
            q = q.where(MachinePoolOrmModel.changed_by_id == filters.changed_by_id)
        if filters.machine_id:
            q = q.where(
                MachinePoolOrmModel.machines.any(ProductionMachineOrmModel.id == filters.machine_id)
            )
        if filters.search:
            term = filters.search
            q = q.where(
                or_(
                    contains_ci(MachinePoolOrmModel.name, term),
                    func.similarity(MachinePoolOrmModel.name, term) > 0.25,
                )
            )

        _sort_column_map = {
            "id": MachinePoolOrmModel.id,
            "name": MachinePoolOrmModel.name,
            "changed": MachinePoolOrmModel.changed,
            "created": MachinePoolOrmModel.created,
        }
        # Without an explicit sort the pools come in their hand-kept order.
        sort_col = _sort_column_map.get(filters.order_by or "")
        order = (
            order_term(sort_col, filters.order_dir, default="desc")
            if sort_col is not None
            else order_term(MachinePoolOrmModel.sort_order, filters.order_dir, default="asc")
        )
        total, rows = await fetch_page(
            self._db,
            q,
            filters.skip,
            filters.limit,
            order,
            MachinePoolOrmModel.id,
            options=_load_options(),
        )
        return total, [_orm_to_entity(r) for r in rows]

    async def get_all(self) -> list[MachinePool]:
        """Unpaginated: scheduling hot path callers load entire pool, no benefit to
        pagination."""
        rows = (
            await self._db.scalars(
                select(MachinePoolOrmModel)
                .where(MachinePoolOrmModel.archived.is_(False))
                .options(*_load_options())
                .order_by(MachinePoolOrmModel.sort_order, MachinePoolOrmModel.id)
            )
        ).all()
        return [_orm_to_entity(r) for r in rows]

    async def get_list_order(self) -> list[ListEntry]:
        m = MachinePoolOrmModel
        rows = (await self._db.execute(select(m.id, m.sort_order, m.archived))).all()
        return [ListEntry(id_, sort_order, archived) for id_, sort_order, archived in rows]

    async def next_sort_order(self) -> int:
        current = await self._db.scalar(select(func.max(MachinePoolOrmModel.sort_order)))
        return 0 if current is None else current + 1

    async def set_sort_orders(self, sort_orders: dict[int, int]) -> None:
        """Writes through the ORM, so live updates see the change."""
        for row_id, sort_order in sort_orders.items():
            orm = await self._db.get(MachinePoolOrmModel, row_id)
            if orm is not None:
                orm.sort_order = sort_order
        await self._db.flush()

    async def _sync_machines(self, orm: MachinePoolOrmModel, machine_ids: list[int]) -> None:
        orm.machines = await load_by_ids(self._db, ProductionMachineOrmModel, machine_ids)

    async def save(self, item: MachinePool) -> MachinePool:
        if item.id == 0:
            orm = MachinePoolOrmModel(**_entity_to_dict(item))
            await self._sync_machines(orm, item.machine_ids)
            self._db.add(orm)
            await self._db.flush()
            new_id = orm.id
            return _orm_to_entity(await self._reload(new_id))
        existing = await self._fetch_for_update(item.id)
        if not existing:
            raise ValueError(f"MachinePoolOrmModel id={item.id} not found.")
        orm = existing
        for k, v in _entity_to_dict(item).items():
            setattr(orm, k, v)
        await self._sync_machines(orm, item.machine_ids)
        await self._db.flush()
        return _orm_to_entity(await self._reload(item.id))

    async def _fetch_for_update(self, id: int) -> MachinePoolOrmModel | None:
        """Loads machines with the row, since _sync_machines() reassigns the collection
        and assignment reads the old one first."""
        orm: MachinePoolOrmModel | None = await self._db.scalar(
            select(MachinePoolOrmModel)
            .where(MachinePoolOrmModel.id == id)
            .options(selectinload(MachinePoolOrmModel.machines))
            .execution_options(populate_existing=True)
            .limit(1)
        )
        return orm

    async def _reload(self, id: int) -> MachinePoolOrmModel:
        return (
            await self._db.scalars(by_id(MachinePoolOrmModel, id, *_load_options(), refresh=True))
        ).one()

    async def delete(self, item: MachinePool) -> None:
        """Soft delete, sets archived=True and saves."""
        item.archived = True
        await self.save(item)
