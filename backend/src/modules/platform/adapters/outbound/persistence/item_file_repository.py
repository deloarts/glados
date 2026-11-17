"""
Shared SQLAlchemy repository for the file attachment tables of bought, made
and source items, products, orders and production orders.

All six tables have the same columns apart from the foreign key to their
parent row, and their domain entities mirror that shape. Each concrete
repository is therefore a subclass that only names its ORM model, entity,
category enum and foreign key column; the queries live here once. The
parent id is called `item_id` throughout, whatever the parent is.

Writes only flush; the caller's unit of work commits them.
"""

from collections.abc import Callable
from datetime import datetime
from enum import Enum
from typing import Any
from typing import ClassVar
from typing import Generic
from typing import Protocol
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware
from src.modules.platform.adapters.outbound.persistence.statements import by_id


class _FileEntity(Protocol):
    """The fields every file entity shares. The parent foreign key differs
    per family and is read through `_fk_field` instead."""

    @property
    def id(self) -> int: ...
    @property
    def file_name(self) -> str: ...
    @property
    def stored_name(self) -> str: ...
    @property
    def mime_type(self) -> str: ...
    @property
    def size_bytes(self) -> int: ...
    @property
    def storage_path(self) -> str: ...
    @property
    def sha256(self) -> str: ...
    @property
    def category(self) -> Enum: ...
    @property
    def created(self) -> datetime: ...
    @property
    def uploaded_by_user_id(self) -> int: ...


TEntity = TypeVar("TEntity", bound=_FileEntity)


def file_orm_to_entity(
    orm: Any, entity_cls: Callable[..., TEntity], category_cls: type[Enum], fk_field: str
) -> TEntity:
    """Map a file row of any family to its entity. `fk_field` names the
    parent foreign key, which is spelled the same on the row and the entity."""
    return entity_cls(
        id=orm.id,
        public_id=orm.public_id,
        file_name=orm.file_name,
        stored_name=orm.stored_name,
        mime_type=orm.mime_type,
        size_bytes=orm.size_bytes,
        storage_path=orm.storage_path,
        sha256=orm.sha256,
        category=category_cls(orm.category),
        created=utc_aware(orm.created),
        uploaded_by_user_id=orm.uploaded_by_user_id,
        **{fk_field: getattr(orm, fk_field)},
    )


class SqlAlchemyItemFileRepository(Generic[TEntity]):
    _model: ClassVar[type[Any]]
    _entity_cls: ClassVar[type[Any]]
    _category_cls: ClassVar[type[Enum]]
    # Name of the parent foreign key, identical on the ORM model and the entity.
    _fk_field: ClassVar[str]

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    def _orm_to_entity(self, orm: Any) -> TEntity:
        entity: TEntity = file_orm_to_entity(
            orm, self._entity_cls, self._category_cls, self._fk_field
        )
        return entity

    def _new_orm(self, file: TEntity) -> Any:
        return self._model(
            file_name=file.file_name,
            stored_name=file.stored_name,
            mime_type=file.mime_type,
            size_bytes=file.size_bytes,
            storage_path=file.storage_path,
            sha256=file.sha256,
            category=file.category.value,
            created=file.created,
            uploaded_by_user_id=file.uploaded_by_user_id,
            **{self._fk_field: getattr(file, self._fk_field)},
        )

    @property
    def _fk_column(self) -> Any:
        return getattr(self._model, self._fk_field)

    async def get_by_id(self, id: int) -> TEntity | None:
        orm = await self._db.scalar(by_id(self._model, id).limit(1))
        return self._orm_to_entity(orm) if orm else None

    async def get_by_item_id(self, item_id: int) -> list[TEntity]:
        rows = (
            await self._db.scalars(
                select(self._model)
                .where(self._fk_column == item_id)
                .order_by(self._model.created.asc())
            )
        ).all()
        return [self._orm_to_entity(r) for r in rows]

    async def get_by_item_ids(self, item_ids: list[int]) -> list[TEntity]:
        """The batched counterpart to get_by_item_id, for callers rendering
        many parents at once (a table of thumbnails) that would otherwise
        issue one request per row."""
        if not item_ids:
            return []
        rows = (
            await self._db.scalars(
                select(self._model)
                .where(self._fk_column.in_(item_ids))
                .order_by(self._model.created.asc())
            )
        ).all()
        return [self._orm_to_entity(r) for r in rows]

    async def get_by_item_id_and_category(self, item_id: int, category: Any) -> list[TEntity]:
        rows = (
            await self._db.scalars(
                select(self._model).where(
                    self._fk_column == item_id,
                    self._model.category == category.value,
                )
            )
        ).all()
        return [self._orm_to_entity(r) for r in rows]

    async def save(self, file: TEntity) -> TEntity:
        """Inserts a new file (id 0) or renames an existing one; the file
        name is the only mutable field of a stored file."""
        if file.id == 0:
            orm = self._new_orm(file)
            self._db.add(orm)
            await self._db.flush()
            await self._db.refresh(orm)
            return self._orm_to_entity(orm)

        existing = await self._db.get(self._model, file.id)
        if not existing:
            raise ValueError(f"{self._entity_cls.__name__} id={file.id} not found.")
        existing.file_name = file.file_name
        await self._db.flush()
        await self._db.refresh(existing)
        return self._orm_to_entity(existing)

    async def delete(self, file: TEntity) -> None:
        orm = await self._db.get(self._model, file.id)
        if orm:
            await self._db.delete(orm)
            await self._db.flush()

    async def reassign(self, file_id: int, target_item_id: int) -> None:
        orm = await self._db.get(self._model, file_id)
        if orm:
            setattr(orm, self._fk_field, target_item_id)
            await self._db.flush()
