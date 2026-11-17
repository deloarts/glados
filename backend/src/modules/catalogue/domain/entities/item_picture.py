"""
One picture of a made, bought or source item from one source (see
ItemPictureSource). A picture is stored as a full-size image and a
thumbnail derived from it. The image may be missing, since PDM's own
check-in rendering is only ever a thumbnail. A request for a missing
variant is served the other one instead.
"""

from dataclasses import dataclass
from datetime import datetime

from src.modules.catalogue.domain.value_objects.item_kind import ItemKind
from src.modules.catalogue.domain.value_objects.item_picture_source import ItemPictureSource
from src.modules.catalogue.domain.value_objects.item_picture_variant import ItemPictureVariant
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class ItemPicture(Entity):
    item_kind: ItemKind
    item_id: int
    source: ItemPictureSource

    file_name: str
    image_path: str | None
    image_mime_type: str | None
    image_size_bytes: int | None
    thumbnail_path: str | None
    thumbnail_mime_type: str | None
    thumbnail_size_bytes: int | None
    sha256: str

    created: datetime
    uploaded_by_user_id: int

    def blob(self, variant: ItemPictureVariant) -> tuple[str, str] | None:
        """The (storage path, content type) serving `variant`, falling back
        to the other variant when this picture lacks the one asked for."""
        image = (self.image_path, self.image_mime_type)
        thumbnail = (self.thumbnail_path, self.thumbnail_mime_type)
        order = (
            (thumbnail, image) if variant is ItemPictureVariant.THUMBNAIL else (image, thumbnail)
        )
        for path, mime_type in order:
            if path is not None:
                return path, mime_type or "application/octet-stream"
        return None

    def storage_paths(self) -> list[str]:
        return [p for p in (self.image_path, self.thumbnail_path) if p is not None]
