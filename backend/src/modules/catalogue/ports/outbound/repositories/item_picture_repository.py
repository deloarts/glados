"""
Abstract interface for item picture persistence, one store for the
pictures of made, bought and source items, addressed by (kind, item id).
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.catalogue.domain.entities.item_picture import ItemPicture
from src.modules.catalogue.domain.value_objects.item_kind import ItemKind
from src.modules.catalogue.domain.value_objects.item_picture_source import ItemPictureSource


@runtime_checkable
class IItemPictureRepository(Protocol):
    async def get_by_item(self, kind: ItemKind, item_id: int) -> list[ItemPicture]: ...

    async def get_by_items(self, kind: ItemKind, item_ids: list[int]) -> list[ItemPicture]:
        """The pictures of many items in one query, for a table of
        thumbnails."""
        ...

    async def get_by_source(
        self, kind: ItemKind, item_id: int, source: ItemPictureSource
    ) -> ItemPicture | None: ...

    async def save(self, picture: ItemPicture) -> ItemPicture:
        """Inserts a new picture (id 0). A stored picture is never changed
        in place; a new one of the same source replaces it."""
        ...

    async def delete(self, picture: ItemPicture) -> None: ...

    async def reassign(self, picture_id: int, target_item_id: int) -> None:
        """Moves a picture to another item of the same kind, for a merge."""
        ...
