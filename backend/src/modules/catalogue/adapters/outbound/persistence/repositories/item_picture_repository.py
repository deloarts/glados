"""SQLAlchemy repository for item pictures. The item kind picks which of the
table's three item foreign keys a query filters on. Writes only flush; the
caller's unit of work commits them."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.catalogue.adapters.outbound.persistence.models.item_picture_model import (
    ItemPictureOrmModel,
)
from src.modules.catalogue.domain.entities.item_picture import ItemPicture
from src.modules.catalogue.domain.value_objects.item_kind import ItemKind
from src.modules.catalogue.domain.value_objects.item_picture_source import ItemPictureSource
from src.modules.platform.adapters.outbound.persistence.mapping_common import utc_aware

_FK_FIELDS: dict[ItemKind, str] = {
    ItemKind.MADE: "made_item_id",
    ItemKind.BOUGHT: "bought_item_id",
    ItemKind.SOURCE: "source_item_id",
}


def _kind_of(orm: ItemPictureOrmModel) -> tuple[ItemKind, int]:
    for kind, field in _FK_FIELDS.items():
        item_id = getattr(orm, field)
        if item_id is not None:
            return kind, item_id
    raise ValueError(f"Item picture #{orm.id} belongs to no item.")


def _orm_to_entity(orm: ItemPictureOrmModel) -> ItemPicture:
    kind, item_id = _kind_of(orm)
    return ItemPicture(
        id=orm.id,
        public_id=orm.public_id,
        item_kind=kind,
        item_id=item_id,
        source=ItemPictureSource(orm.source),
        file_name=orm.file_name,
        image_path=orm.image_path,
        image_mime_type=orm.image_mime_type,
        image_size_bytes=orm.image_size_bytes,
        thumbnail_path=orm.thumbnail_path,
        thumbnail_mime_type=orm.thumbnail_mime_type,
        thumbnail_size_bytes=orm.thumbnail_size_bytes,
        sha256=orm.sha256,
        created=utc_aware(orm.created),
        uploaded_by_user_id=orm.uploaded_by_user_id,
    )


def _fk_column(kind: ItemKind) -> Any:
    return getattr(ItemPictureOrmModel, _FK_FIELDS[kind])


class SqlAlchemyItemPictureRepository:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_item(self, kind: ItemKind, item_id: int) -> list[ItemPicture]:
        return await self.get_by_items(kind, [item_id])

    async def get_by_items(self, kind: ItemKind, item_ids: list[int]) -> list[ItemPicture]:
        if not item_ids:
            return []
        rows = (
            await self._db.scalars(
                select(ItemPictureOrmModel)
                .where(_fk_column(kind).in_(item_ids))
                .order_by(ItemPictureOrmModel.id.asc())
            )
        ).all()
        return [_orm_to_entity(r) for r in rows]

    async def get_by_source(
        self, kind: ItemKind, item_id: int, source: ItemPictureSource
    ) -> ItemPicture | None:
        orm = await self._db.scalar(
            select(ItemPictureOrmModel)
            .where(_fk_column(kind) == item_id, ItemPictureOrmModel.source == source.value)
            .limit(1)
        )
        return _orm_to_entity(orm) if orm else None

    async def save(self, picture: ItemPicture) -> ItemPicture:
        if picture.id != 0:
            raise ValueError(
                f"Item picture #{picture.id} is stored already; pictures are replaced."
            )
        orm = ItemPictureOrmModel(
            source=picture.source.value,
            file_name=picture.file_name,
            image_path=picture.image_path,
            image_mime_type=picture.image_mime_type,
            image_size_bytes=picture.image_size_bytes,
            thumbnail_path=picture.thumbnail_path,
            thumbnail_mime_type=picture.thumbnail_mime_type,
            thumbnail_size_bytes=picture.thumbnail_size_bytes,
            sha256=picture.sha256,
            created=picture.created,
            uploaded_by_user_id=picture.uploaded_by_user_id,
            **{_FK_FIELDS[picture.item_kind]: picture.item_id},
        )
        self._db.add(orm)
        await self._db.flush()
        await self._db.refresh(orm)
        return _orm_to_entity(orm)

    async def delete(self, picture: ItemPicture) -> None:
        orm = await self._db.get(ItemPictureOrmModel, picture.id)
        if orm:
            await self._db.delete(orm)
            await self._db.flush()

    async def reassign(self, picture_id: int, target_item_id: int) -> None:
        orm = await self._db.get(ItemPictureOrmModel, picture_id)
        if orm:
            kind, _ = _kind_of(orm)
            setattr(orm, _FK_FIELDS[kind], target_item_id)
            await self._db.flush()
