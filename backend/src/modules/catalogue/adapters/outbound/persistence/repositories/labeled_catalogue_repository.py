"""
Shared SQLAlchemy repository for the labeled catalogue tables: article
groups, source item types, fabrication methods and inspection methods. The
four tables share the id, name, label, description, creator, changer, archived and
created/changed columns, and their reads, list filter, aggregate and writes
are the same queries, so each concrete repository is a subclass that names
its ORM model and supplies its load options, its ORM to entity mapper and
its write payload. Lookups only one family has stay on that subclass.

Every family is a hand-ordered list: a list without an explicit sort comes
in `sort_order`, the order pickers offer, and a move rewrites the
`sort_order` of the rows it shifts.

The four labeled families store `name` and `description` as language maps
(JSON), searched in every language and sorted in the filter's languages.
Product families keep plain strings; their subclass sets `_localized` to
False.

Writes only flush; the caller's unit of work commits them.
"""

from datetime import datetime
from typing import Any
from typing import ClassVar
from typing import Generic
from typing import Protocol
from typing import TypeVar

from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.platform.adapters.outbound.persistence.like_escape import contains_ci
from src.modules.platform.adapters.outbound.persistence.localized_text_sql import localized_contains
from src.modules.platform.adapters.outbound.persistence.localized_text_sql import localized_sort_key
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.adapters.outbound.persistence.statements import fetch_page
from src.modules.platform.adapters.outbound.persistence.statements import order_term
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from src.shared_kernel.domain.services.list_order import ListEntry


class _LabeledCatalogueEntity(Protocol):
    @property
    def id(self) -> int: ...


class _LabeledCatalogueFilter(Protocol):
    @property
    def skip(self) -> int | None: ...
    @property
    def limit(self) -> int | None: ...
    @property
    def search(self) -> str | None: ...
    @property
    def id(self) -> int | None: ...
    @property
    def name(self) -> str | None: ...
    @property
    def creator_id(self) -> int | None: ...
    @property
    def changed_by_id(self) -> int | None: ...
    @property
    def include_archived(self) -> bool: ...
    @property
    def created_from(self) -> datetime | None: ...
    @property
    def created_to(self) -> datetime | None: ...
    @property
    def changed_from(self) -> datetime | None: ...
    @property
    def changed_to(self) -> datetime | None: ...
    @property
    def order_by(self) -> str | None: ...
    @property
    def order_dir(self) -> str | None: ...
    @property
    def languages(self) -> tuple[str, ...]: ...


TEntity = TypeVar("TEntity", bound=_LabeledCatalogueEntity)


class LabeledCatalogueRepositoryBase(Generic[TEntity]):
    _model: ClassVar[type[Any]]
    _localized: ClassVar[bool] = True

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Hooks ─────────────────────────────────────────────────────────

    def _load_options(self) -> tuple[ORMOption, ...]:
        """The load options every query that feeds `_orm_to_entity` applies."""
        raise NotImplementedError

    def _orm_to_entity(self, orm: Any) -> TEntity:
        raise NotImplementedError

    def _entity_to_dict(self, entity: TEntity) -> dict[str, Any]:
        """The column values a write sets, without `id` and `public_id`."""
        raise NotImplementedError

    def _contains(self, column: Any, term: str) -> Any:
        if self._localized:
            return localized_contains(column, term)
        return contains_ci(column, term)

    async def _flush(self) -> None:
        """Flushes a write. A subclass overrides it to turn a constraint
        violation it expects into a domain error."""
        await self._db.flush()

    # ── Reads ─────────────────────────────────────────────────────────

    async def get_by_id(self, id: int) -> TEntity | None:
        orm = await self._db.scalar(by_id(self._model, id, *self._load_options()).limit(1))
        return self._orm_to_entity(orm) if orm else None

    async def get_by_name(self, name: str) -> TEntity | None:
        """The live (not archived) row with exactly this plain name, for the
        families whose name is one string."""
        orm = await self._db.scalar(
            select(self._model)
            .where(self._model.name == name, self._model.archived.is_(False))
            .options(*self._load_options())
            .limit(1)
        )
        return self._orm_to_entity(orm) if orm else None

    async def get_live_names(self) -> list[tuple[int, LocalizedText]]:
        """The id and name of every live (not archived) row, for the
        per-language name uniqueness check. The tables hold a handful of
        hand-maintained rows, so loading them all is cheap."""
        rows = (
            await self._db.execute(
                select(self._model.id, self._model.name).where(self._model.archived.is_(False))
            )
        ).all()
        return [(id_, LocalizedText(values=dict(name or {}))) for id_, name in rows]

    async def get_multi(self, filters: _LabeledCatalogueFilter) -> tuple[int, list[TEntity]]:
        m = self._model
        q = select(m)
        if not filters.include_archived:
            q = q.where(m.archived.is_(False))

        if filters.id is not None:
            q = q.where(m.id == filters.id)
        if filters.name:
            q = q.where(self._contains(m.name, filters.name))
        if filters.creator_id is not None:
            q = q.where(m.creator_id == filters.creator_id)
        if filters.changed_by_id is not None:
            q = q.where(m.changed_by_id == filters.changed_by_id)
        if filters.created_from:
            q = q.where(m.created >= filters.created_from)
        if filters.created_to:
            q = q.where(m.created <= filters.created_to)
        if filters.changed_from:
            q = q.where(m.changed >= filters.changed_from)
        if filters.changed_to:
            q = q.where(m.changed <= filters.changed_to)
        if filters.search:
            term = filters.search
            q = q.where(self._contains(m.name, term) | self._contains(m.description, term))

        name_key = localized_sort_key(m.name, filters.languages) if self._localized else m.name
        sort_column_map = {
            "id": m.id,
            "name": name_key,
            "created": m.created,
            "changed": m.changed,
        }
        sort_col = sort_column_map.get(filters.order_by or "", m.sort_order)
        total, rows = await fetch_page(
            self._db,
            q,
            filters.skip,
            filters.limit,
            order_term(sort_col, filters.order_dir, default="asc"),
            m.id,
            options=self._load_options(),
        )
        return total, [self._orm_to_entity(r) for r in rows]

    async def get_aggregate(self) -> tuple[int, datetime | None]:
        """Row count and newest `changed` value over all rows, archived ones
        included."""
        count, max_changed = (
            await self._db.execute(
                select(func.count(self._model.id), func.max(self._model.changed))
            )
        ).one()
        return count, max_changed

    async def get_list_order(self) -> list[ListEntry]:
        """Every row's place in the hand-kept order, archived rows included."""
        m = self._model
        rows = (await self._db.execute(select(m.id, m.sort_order, m.archived))).all()
        return [ListEntry(id_, sort_order, archived) for id_, sort_order, archived in rows]

    async def next_sort_order(self) -> int:
        """The place after the last row, where a new row goes."""
        current = await self._db.scalar(select(func.max(self._model.sort_order)))
        return 0 if current is None else current + 1

    # ── Writes ────────────────────────────────────────────────────────

    async def set_sort_orders(self, sort_orders: dict[int, int]) -> None:
        """Writes the `sort_order` of each row by id and nothing else. The
        rows are written through the ORM, so live updates see the change."""
        for row_id, sort_order in sort_orders.items():
            orm = await self._db.get(self._model, row_id)
            if orm is not None:
                orm.sort_order = sort_order
        await self._db.flush()

    async def save(self, entity: TEntity) -> TEntity:
        """Insert (id == 0) or update (id > 0), then re-read the row."""
        if entity.id == 0:
            orm = self._model(**self._entity_to_dict(entity))
            self._db.add(orm)
            await self._flush()
            return self._orm_to_entity(await self._reload(orm.id))
        existing = await self._db.get(self._model, entity.id)
        if not existing:
            raise ValueError(f"{self._model.__name__} id={entity.id} not found.")
        for key, value in self._entity_to_dict(entity).items():
            setattr(existing, key, value)
        await self._flush()
        return self._orm_to_entity(await self._reload(entity.id))

    async def _reload(self, id: int) -> Any:
        return (
            await self._db.scalars(by_id(self._model, id, *self._load_options(), refresh=True))
        ).one()

    async def delete(self, entity: TEntity) -> None:
        """Hard delete. Archiving through save() is the usual way to remove a row."""
        orm = await self._db.get(self._model, entity.id)
        if orm:
            await self._db.delete(orm)
            await self._db.flush()
