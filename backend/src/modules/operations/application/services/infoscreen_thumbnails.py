"""
Thumbnail links for the rows of an infoscreen feed. A row names a made,
bought or source item; its link points at the picture the app shows for
that item (pick_picture), in the thumbnail variant, through a signed token
the display can load without any credential. The machine detail widget also
links to the full-size picture and to the item's drawing the same way.

One linker serves one feed. Each widget prefetches the pictures of all its
items of one kind in a single query, so no row costs a query of its own,
and an item looked up once is not looked up again.
"""

from collections.abc import Iterable
from datetime import datetime

from src.modules.catalogue.domain.entities.item_picture import ItemPicture
from src.modules.catalogue.domain.policies.item_picture_selection import pick_picture
from src.modules.catalogue.domain.value_objects.item_kind import ItemKind
from src.modules.catalogue.domain.value_objects.item_picture_variant import ItemPictureVariant
from src.modules.catalogue.ports.outbound.catalogue_queries import IItemPictureQueries
from src.modules.operations.infrastructure.security.terminal_auth import create_drawing_token
from src.modules.operations.infrastructure.security.terminal_auth import create_thumbnail_token
from src.modules.platform.const import API_WEB

THUMBNAIL_PATH = f"{API_WEB}/terminal-device/thumbnails"
DRAWING_PATH = f"{API_WEB}/terminal-device/drawings"


def thumbnail_url(kind: ItemKind, item_id: int, now: datetime) -> str:
    return picture_url(kind, item_id, ItemPictureVariant.THUMBNAIL, now)


def picture_url(kind: ItemKind, item_id: int, variant: ItemPictureVariant, now: datetime) -> str:
    token = create_thumbnail_token(kind.value, item_id, variant.value, now)
    return f"{THUMBNAIL_PATH}/{token}"


def drawing_url(made_item_id: int, file_id: int, now: datetime) -> str:
    return f"{DRAWING_PATH}/{create_drawing_token(made_item_id, file_id, now)}"


class ThumbnailLinker:
    def __init__(self, picture_repo: IItemPictureQueries, now: datetime) -> None:
        self._pictures = picture_repo
        self._now = now
        self._known: dict[tuple[ItemKind, int], str | None] = {}

    async def prefetch(self, kind: ItemKind, item_ids: Iterable[int | None]) -> None:
        """Looks up the pictures of every item not seen yet, in one query."""
        wanted = sorted({i for i in item_ids if i and (kind, i) not in self._known})
        if not wanted:
            return
        by_item: dict[int, list[ItemPicture]] = {}
        for picture in await self._pictures.get_by_items(kind, wanted):
            by_item.setdefault(picture.item_id, []).append(picture)
        for item_id in wanted:
            shown = pick_picture(by_item.get(item_id, []))
            has_thumbnail = shown is not None and shown.blob(ItemPictureVariant.THUMBNAIL)
            self._known[(kind, item_id)] = (
                thumbnail_url(kind, item_id, self._now) if has_thumbnail else None
            )

    def url(self, kind: ItemKind, item_id: int | None) -> str | None:
        """The link of a prefetched item, None without a thumbnail."""
        if not item_id:
            return None
        return self._known.get((kind, item_id))

    def drawing_url(self, made_item_id: int, file_id: int) -> str:
        """The signed link of one drawing file of a made item."""
        return drawing_url(made_item_id, file_id, self._now)

    async def image_url(self, kind: ItemKind, item_id: int | None) -> str | None:
        """The link of the full-size picture of one item, the thumbnail when
        only that exists, None without a picture."""
        if not item_id:
            return None
        shown = pick_picture(await self._pictures.get_by_item(kind, item_id))
        if shown is None:
            return None
        for variant in (ItemPictureVariant.IMAGE, ItemPictureVariant.THUMBNAIL):
            if shown.blob(variant):
                return picture_url(kind, item_id, variant, self._now)
        return None
