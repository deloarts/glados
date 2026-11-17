"""
Shared SQLAlchemy repository for the demand bucket tables of bought items,
made items and source items. The three tables have the same columns and
their entities mirror that shape, so each concrete repository is a subclass
that only names its bucket ORM model, its entity and the demand ORM model
whose `bucket_id` points at the bucket; the queries live here once.

Writes only flush; the caller's unit of work commits them.
"""

from collections.abc import Callable
from datetime import datetime
from typing import Any
from typing import ClassVar
from typing import Generic
from typing import Protocol
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.outbound.persistence.repositories._lifecycle_rows import (
    lock_statement,
)
from src.modules.platform.adapters.outbound.persistence.like_escape import contains_ci
from src.modules.platform.adapters.outbound.persistence.like_escape import escape_like
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.adapters.outbound.persistence.statements import fetch_page
from src.modules.platform.adapters.outbound.persistence.statements import order_term
from src.modules.platform.domain.exceptions import ConcurrentModificationError


class _DemandBucketEntity(Protocol):
    @property
    def id(self) -> int: ...
    @property
    def created(self) -> datetime: ...
    @property
    def name(self) -> str: ...
    @property
    def color(self) -> str: ...
    @property
    def creator_id(self) -> int: ...


class _DemandBucketFilter(Protocol):
    @property
    def skip(self) -> int | None: ...
    @property
    def limit(self) -> int | None: ...
    @property
    def search(self) -> str | None: ...
    @property
    def order_by(self) -> str | None: ...
    @property
    def order_dir(self) -> str | None: ...


TEntity = TypeVar("TEntity", bound=_DemandBucketEntity)


class DemandBucketRepositoryBase(Generic[TEntity]):
    _model: ClassVar[type[Any]]
    _entity_cls: ClassVar[Callable[..., Any]]
    # The demand ORM model whose nullable `bucket_id` references `_model`.
    _demand_model: ClassVar[type[Any]]

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    def _orm_to_entity(self, orm: Any) -> TEntity:
        entity: TEntity = self._entity_cls(
            id=orm.id,
            public_id=orm.public_id,
            created=utc_aware(orm.created),
            name=orm.name,
            color=orm.color,
            creator_id=orm.creator_id,
        )
        return entity

    def _entity_to_dict(self, bucket: TEntity) -> dict[str, Any]:
        return {
            "created": bucket.created,
            "name": bucket.name,
            "color": bucket.color,
            "creator_id": bucket.creator_id,
        }

    async def get_by_id(self, id: int) -> TEntity | None:
        orm = await self._db.scalar(by_id(self._model, id).limit(1))
        return self._orm_to_entity(orm) if orm else None

    async def get_by_name(self, name: str) -> TEntity | None:
        orm = await self._db.scalar(
            select(self._model)
            .where(self._model.name.ilike(escape_like(name), escape="\\"))
            .limit(1)
        )
        return self._orm_to_entity(orm) if orm else None

    async def get_multi(self, filters: _DemandBucketFilter) -> tuple[int, list[TEntity]]:
        q = select(self._model)

        if filters.search:
            q = q.where(contains_ci(self._model.name, filters.search))

        sort_column_map = {
            "id": self._model.id,
            "name": self._model.name,
            "created": self._model.created,
        }
        sort_col = sort_column_map.get(filters.order_by or "name", self._model.name)
        total, rows = await fetch_page(
            self._db,
            q,
            filters.skip,
            filters.limit,
            order_term(sort_col, filters.order_dir, default="asc"),
        )
        return total, [self._orm_to_entity(r) for r in rows]

    async def save(self, bucket: TEntity) -> TEntity:
        """Insert (id == 0) or update (id > 0)."""
        if bucket.id == 0:
            orm = self._model(**self._entity_to_dict(bucket))
            self._db.add(orm)
            await self._db.flush()
            await self._db.refresh(orm)
            return self._orm_to_entity(orm)
        existing = await self._db.get(self._model, bucket.id)
        if not existing:
            raise ConcurrentModificationError(
                f"{self._model.__name__} id={bucket.id} was removed"
                " while this request worked on it; reload and try again."
            )
        orm = existing
        for key, value in self._entity_to_dict(bucket).items():
            setattr(orm, key, value)
        await self._db.flush()
        await self._db.refresh(orm)
        return self._orm_to_entity(orm)

    async def delete(self, bucket: TEntity) -> None:
        """Hard delete. Clears bucket_id on every referencing demand in the
        same transaction first, because SQLite, used by the hermetic test
        suite, does not enforce the FK's ON DELETE SET NULL. The demands are
        locked in ascending id order like every lifecycle lock and cleared
        through the ORM, so their version moves and a concurrent save of a
        stale copy fails instead of writing the deleted bucket back."""
        demand_id = self._demand_model.id
        ids = (
            await self._db.scalars(
                select(demand_id).where(self._demand_model.bucket_id == bucket.id)
            )
        ).all()
        for demand in (
            await self._db.scalars(lock_statement(self._demand_model, demand_id, ids))
        ).all():
            if demand.bucket_id == bucket.id:
                demand.bucket_id = None
        orm = await self._db.get(self._model, bucket.id)
        if orm:
            await self._db.delete(orm)
        await self._db.flush()
