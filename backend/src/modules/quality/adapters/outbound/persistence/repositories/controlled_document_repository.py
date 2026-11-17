"""
Shared SQLAlchemy repository for the controlled document tables:
calculations, checklists and sequences. All carry the document control
columns (models/controlled_document_columns.py) and a product owner, all
but sequences a project owner too, and their lookups, lineage, document
numbers, writes and most of the list filter, visibility rule and sort are
the same queries. Each concrete repository is a subclass that names its ORM
model and supplies its ORM to entity mapper, its write payload, the filters
and the sort columns only its kind has.

Writes only flush; the caller's unit of work commits them.
"""

from collections.abc import Callable
from functools import lru_cache
from typing import Any
from typing import ClassVar
from typing import Generic
from typing import Protocol
from typing import TypeVar
from uuid import UUID

from sqlalchemy import ColumnElement
from sqlalchemy import and_
from sqlalchemy import desc
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.interfaces import ORMOption

from src.modules.platform.adapters.outbound.persistence.like_escape import contains_ci
from src.modules.platform.adapters.outbound.persistence.number_counters import NumberFamily
from src.modules.platform.adapters.outbound.persistence.number_counters import draw_number
from src.modules.platform.adapters.outbound.persistence.query_filters import FilterSpec
from src.modules.platform.adapters.outbound.persistence.query_filters import apply_filters
from src.modules.platform.adapters.outbound.persistence.query_filters import when
from src.modules.platform.adapters.outbound.persistence.query_filters import when_not_none
from src.modules.platform.adapters.outbound.persistence.statements import by_id
from src.modules.platform.adapters.outbound.persistence.statements import fetch_page
from src.modules.quality.adapters.outbound.persistence.repositories.controlled_document_mapping import (
    lineage_order,
)
from src.modules.quality.adapters.outbound.persistence.repositories.controlled_document_mapping import (
    user_load_options,
)
from src.modules.quality.domain.entities.controlled_document import ControlledDocument
from src.modules.workspace.adapters.outbound.persistence.models.project_model import ProjectOrmModel


class _DocumentFilter(Protocol):
    """The list filter fields every kind's filter DTO has."""

    @property
    def skip(self) -> int | None: ...
    @property
    def limit(self) -> int | None: ...
    @property
    def project_id(self) -> int | None: ...
    @property
    def product_id(self) -> int | None: ...
    @property
    def related_product_id(self) -> int | None: ...
    @property
    def creator_id(self) -> int | None: ...
    @property
    def owner(self) -> str | None: ...
    @property
    def released(self) -> bool | None: ...
    @property
    def search(self) -> str | None: ...
    @property
    def latest_only(self) -> bool: ...
    @property
    def lineage(self) -> UUID | None: ...
    @property
    def visible_to_user_id(self) -> int | None: ...
    @property
    def order_by(self) -> str | None: ...
    @property
    def order_dir(self) -> str | None: ...


TEntity = TypeVar("TEntity", bound=ControlledDocument)
TFilter = TypeVar("TFilter", bound=_DocumentFilter)


@lru_cache(maxsize=8)
def _load_options(model: Any) -> tuple[ORMOption, ...]:
    """Everything a kind's `_orm_to_entity` dereferences. Built on first call
    rather than at import, because constructing a loader option configures the
    mapper registry before every model module is registered."""
    projects = (selectinload(model.project),) if hasattr(model, "project") else ()
    return (
        *projects,
        selectinload(model.product),
        *user_load_options(model),
    )


class ControlledDocumentRepositoryBase(Generic[TEntity, TFilter]):
    # The ORM model class. Typed Any because its columns are read by name.
    _model: ClassVar[Any]
    # The counter new documents of the kind draw their numbers from.
    _number_family: ClassVar[NumberFamily]
    # The column searched and sorted as the document's title.
    _title_column: ClassVar[str] = "title"
    # False for a kind that always belongs to a product and has no project
    # column; it is visible to everyone, so it has no visibility rule.
    _has_project: ClassVar[bool] = True

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Hooks ─────────────────────────────────────────────────────────

    def _orm_to_entity(self, orm: Any) -> TEntity:
        raise NotImplementedError

    def _entity_to_dict(self, item: TEntity) -> dict[str, Any]:
        """The column values a write sets, without `id` and `public_id`."""
        raise NotImplementedError

    def _kind_filters(self, filters: TFilter) -> list[FilterSpec]:
        """The list filters only this kind has."""
        return []

    def _kind_load_options(self) -> tuple[ORMOption, ...]:
        """Load options for the relationships only this kind's
        `_orm_to_entity` dereferences."""
        return ()

    def _options(self) -> tuple[ORMOption, ...]:
        return (*_load_options(self._model), *self._kind_load_options())

    def _kind_sort_columns(self) -> dict[str, Any]:
        """The `order_by` values only this kind has, with their columns."""
        return {}

    # ── Reads ─────────────────────────────────────────────────────────

    async def get_by_id(self, id: int) -> TEntity | None:
        orm = await self._db.scalar(by_id(self._model, id, *self._options()).limit(1))
        return self._orm_to_entity(orm) if orm else None

    async def get_for_update(self, id: int) -> TEntity | None:
        m = self._model
        lineage = select(m.lineage).where(m.id == id).scalar_subquery()
        (
            await self._db.scalars(
                select(m.id)
                .where(m.lineage == lineage)
                .order_by(m.id)
                .with_for_update(key_share=True)
            )
        ).all()
        orm = await self._db.scalar(by_id(m, id, *self._options(), refresh=True).limit(1))
        return self._orm_to_entity(orm) if orm else None

    async def get_by_public_id(self, public_id: UUID) -> TEntity | None:
        orm = await self._db.scalar(
            select(self._model)
            .where(self._model.public_id == public_id)
            .options(*self._options())
            .limit(1)
        )
        return self._orm_to_entity(orm) if orm else None

    async def get_multi(self, filters: TFilter) -> tuple[int, list[TEntity]]:
        m = self._model
        q = apply_filters(
            select(m),
            [
                when_not_none(filters.product_id, lambda product_id: m.product_id == product_id),
                when_not_none(filters.creator_id, lambda creator_id: m.creator_id == creator_id),
                *(self._owner_filters(filters) if self._has_project else []),
                *self._kind_filters(filters),
                when_not_none(
                    filters.released,
                    lambda released: (
                        m.released_at.is_not(None) if released else m.released_at.is_(None)
                    ),
                ),
                when(
                    filters.search,
                    lambda search: or_(
                        contains_ci(getattr(m, self._title_column), search),
                        contains_ci(m.document_number, search),
                    ),
                ),
                when(filters.latest_only, lambda _: m.is_latest.is_(True)),
                when_not_none(filters.lineage, lambda lineage: m.lineage == lineage),
            ],
        )

        total, rows = await fetch_page(
            self._db,
            q,
            filters.skip,
            filters.limit,
            *self._ordering(filters),
            options=self._options(),
        )
        return total, [self._orm_to_entity(r) for r in rows]

    def _owner_filters(self, filters: TFilter) -> list[FilterSpec]:
        """The project and owner kind filters and the visibility rule, for
        kinds that may belong to a project or to nobody."""
        m = self._model
        owner_clauses: dict[str, Callable[[], ColumnElement[bool]]] = {
            "personal": lambda: and_(m.project_id.is_(None), m.product_id.is_(None)),
            "project": lambda: m.project_id.is_not(None),
            "product": lambda: m.product_id.is_not(None),
        }

        def related_to_product(product_id: int) -> ColumnElement[bool]:
            projects = select(ProjectOrmModel.id).where(ProjectOrmModel.product_id == product_id)
            return or_(m.product_id == product_id, m.project_id.in_(projects))

        return [
            when_not_none(filters.project_id, lambda project_id: m.project_id == project_id),
            when_not_none(filters.related_product_id, related_to_product),
            when(owner_clauses.get(filters.owner or ""), lambda build: build()),
            # Another user's personal document stays hidden.
            when_not_none(
                filters.visible_to_user_id,
                lambda user_id: or_(
                    m.project_id.is_not(None),
                    m.product_id.is_not(None),
                    m.creator_id == user_id,
                ),
            ),
        ]

    def _ordering(self, filters: TFilter) -> list[Any]:
        """The requested sort, or the most recently changed first; the id
        keeps pages stable. A document that is not released has no release
        time, so sorting by it puts those together, after the released ones
        when ascending."""
        m = self._model
        last_change = func.coalesce(m.changed, m.created)
        columns: dict[str, Any] = {
            "title": func.lower(getattr(m, self._title_column)),
            "number": m.document_number,
            "created": m.created,
            "changed": last_change,
            "released": m.released_at,
            **self._kind_sort_columns(),
        }
        column = columns.get(filters.order_by or "")
        if column is None:
            return [desc(last_change), desc(m.id)]
        if filters.order_dir == "desc":
            return [column.desc().nulls_last(), desc(m.id)]
        return [column.asc().nulls_last(), m.id]

    async def get_lineage(self, lineage: UUID) -> list[TEntity]:
        rows = (
            await self._db.scalars(
                select(self._model)
                .where(self._model.lineage == lineage)
                .options(*self._options())
                .order_by(*lineage_order(self._model))
            )
        ).all()
        return [self._orm_to_entity(r) for r in rows]

    async def next_document_number(self, template: str) -> str:
        """Draws the number of a new document from the kind's counter
        (persistence/number_counters.py). Every revision of a document keeps
        its number, so only a new document draws one."""
        return await draw_number(
            self._db,
            self._number_family,
            template,
            column=self._model.document_number,
        )

    # ── Writes ────────────────────────────────────────────────────────

    async def save(self, item: TEntity) -> TEntity:
        """Insert (id == 0) or update (id > 0), then re-read the row."""
        if item.id == 0:
            orm = self._model(**self._entity_to_dict(item))
            self._db.add(orm)
            await self._db.flush()
            return self._orm_to_entity(await self._reload(orm.id))
        existing = await self._db.scalar(
            select(self._model).where(self._model.id == item.id).limit(1)
        )
        if not existing:
            raise ValueError(f"{self._model.__name__} id={item.id} not found.")
        for k, v in self._entity_to_dict(item).items():
            setattr(existing, k, v)
        await self._db.flush()
        return self._orm_to_entity(await self._reload(item.id))

    async def _reload(self, id: int) -> Any:
        return (
            await self._db.scalars(by_id(self._model, id, *self._options(), refresh=True))
        ).one()

    async def delete(self, item: TEntity) -> None:
        orm = await self._db.scalar(select(self._model).where(self._model.id == item.id).limit(1))
        if orm:
            await self._db.delete(orm)
            await self._db.flush()
