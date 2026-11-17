"""
In-memory stand-ins for the item picture repository and storage, shared by
the unit tests of everything that reads or writes item pictures.
"""

import io
from dataclasses import replace
from datetime import UTC
from datetime import datetime

from PIL import Image

from src.modules.catalogue.domain.entities.item_picture import ItemPicture
from src.modules.catalogue.domain.value_objects.item_kind import ItemKind
from src.modules.catalogue.domain.value_objects.item_picture_source import ItemPictureSource


def png_bytes(size: tuple[int, int] = (40, 30), color: str = "red") -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def make_picture(
    kind: ItemKind,
    item_id: int,
    source: ItemPictureSource,
    *,
    picture_id: int = 0,
    image_path: str | None = "pictures/image.png",
    thumbnail_path: str | None = "pictures/thumbnail.png",
    created: datetime | None = None,
    file_name: str = "picture.png",
) -> ItemPicture:
    return ItemPicture(
        id=picture_id,
        item_kind=kind,
        item_id=item_id,
        source=source,
        file_name=file_name,
        image_path=image_path,
        image_mime_type="image/png" if image_path else None,
        image_size_bytes=10 if image_path else None,
        thumbnail_path=thumbnail_path,
        thumbnail_mime_type="image/png" if thumbnail_path else None,
        thumbnail_size_bytes=5 if thumbnail_path else None,
        sha256="sha",
        created=created or datetime(2026, 1, 1, tzinfo=UTC),
        uploaded_by_user_id=1,
    )


class FakeItemPictureRepository:
    def __init__(self, pictures: list[ItemPicture] | None = None) -> None:
        self.pictures: dict[int, ItemPicture] = {}
        self._next_id = 1
        for picture in pictures or []:
            self._add(picture)

    def _add(self, picture: ItemPicture) -> ItemPicture:
        if picture.id == 0:
            picture = replace(picture, id=self._next_id)
        self._next_id = max(self._next_id, picture.id) + 1
        self.pictures[picture.id] = picture
        return picture

    async def get_by_item(self, kind: ItemKind, item_id: int) -> list[ItemPicture]:
        return await self.get_by_items(kind, [item_id])

    async def get_by_items(self, kind: ItemKind, item_ids: list[int]) -> list[ItemPicture]:
        return [p for p in self.pictures.values() if p.item_kind is kind and p.item_id in item_ids]

    async def get_by_source(
        self, kind: ItemKind, item_id: int, source: ItemPictureSource
    ) -> ItemPicture | None:
        matches = [p for p in await self.get_by_item(kind, item_id) if p.source is source]
        return matches[0] if matches else None

    async def save(self, picture: ItemPicture) -> ItemPicture:
        assert picture.id == 0
        assert await self.get_by_source(picture.item_kind, picture.item_id, picture.source) is None
        return self._add(picture)

    async def delete(self, picture: ItemPicture) -> None:
        self.pictures.pop(picture.id, None)

    async def reassign(self, picture_id: int, target_item_id: int) -> None:
        picture = self.pictures[picture_id]
        self.pictures[picture_id] = replace(picture, item_id=target_item_id)


class FakePictureStorage:
    def __init__(self, blobs: dict[str, bytes] | None = None) -> None:
        self.blobs: dict[str, tuple[bytes, str]] = {
            key: (data, "image/png") for key, data in (blobs or {}).items()
        }
        self.deleted: list[str] = []
        self.fail_upload = False

    async def upload(self, key: str, data: bytes, content_type: str) -> None:
        if self.fail_upload:
            raise OSError("storage down")
        self.blobs[key] = (data, content_type)

    async def download(self, key: str) -> tuple[bytes, str]:
        return self.blobs[key]

    async def delete(self, key: str) -> None:
        self.deleted.append(key)
        self.blobs.pop(key, None)
