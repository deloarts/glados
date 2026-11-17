"""
Lists an item's pictures, one per source in the order they are chosen,
marking the one shown for the item; and, for a table of thumbnails, which
picture is shown for each of many items, so a row without one requests
nothing.
"""

from src.modules.catalogue.application.dto.item_picture_dto import ItemPictureInUseResult
from src.modules.catalogue.application.dto.item_picture_dto import ItemPictureResult
from src.modules.catalogue.application.use_cases.item_picture._kinds import PictureItemRepo
from src.modules.catalogue.application.use_cases.item_picture._kinds import PictureKind
from src.modules.catalogue.domain.entities.item_picture import ItemPicture
from src.modules.catalogue.domain.policies.item_picture_selection import pick_picture
from src.modules.catalogue.domain.value_objects.item_picture_source import PRECEDENCE
from src.modules.catalogue.ports.outbound.repositories.item_picture_repository import (
    IItemPictureRepository,
)


class ListItemPictures:
    def __init__(
        self, kind: PictureKind, item_repo: PictureItemRepo, picture_repo: IItemPictureRepository
    ) -> None:
        self._kind = kind
        self._items = item_repo
        self._pictures = picture_repo

    async def execute(self, item_id: int) -> list[ItemPictureResult]:
        if not await self._items.get_by_id(item_id):
            raise self._kind.not_found(item_id)
        pictures = sorted(
            await self._pictures.get_by_item(self._kind.kind, item_id),
            key=lambda p: PRECEDENCE.index(p.source),
        )
        in_use = pick_picture(pictures)
        return [ItemPictureResult.of(p, in_use=p is in_use) for p in pictures]

    async def execute_in_use(self, item_ids: list[int]) -> list[ItemPictureInUseResult]:
        """The picture shown for each listed item that has one. An unknown
        item id is not an error, since a table may race a deletion."""
        by_item: dict[int, list[ItemPicture]] = {}
        for picture in await self._pictures.get_by_items(self._kind.kind, item_ids):
            by_item.setdefault(picture.item_id, []).append(picture)
        results: list[ItemPictureInUseResult] = []
        for item_id, pictures in by_item.items():
            shown = pick_picture(pictures)
            if shown is not None:
                results.append(
                    ItemPictureInUseResult(
                        item_id=item_id, picture_id=shown.id, source=shown.source
                    )
                )
        return results
