"""
Carries an item's pictures over to the item it is merged into. Each item
holds one picture per source, so where both have one, the newer picture
is kept, the same rule the merge applies to identical files.
"""

from src.modules.catalogue.domain.value_objects.item_kind import ItemKind
from src.modules.catalogue.ports.outbound.repositories.item_picture_repository import (
    IItemPictureRepository,
)


async def merge_item_pictures(
    pictures: IItemPictureRepository, kind: ItemKind, source_id: int, target_id: int
) -> None:
    """Moves the source item's pictures to the target, without committing.
    A replaced picture's blobs stay in storage, like a merged-away file's."""
    target_by_source = {p.source: p for p in await pictures.get_by_item(kind, target_id)}
    for picture in await pictures.get_by_item(kind, source_id):
        existing = target_by_source.get(picture.source)
        if existing is None:
            await pictures.reassign(picture.id, target_id)
        elif picture.created > existing.created:
            await pictures.delete(existing)
            await pictures.reassign(picture.id, target_id)
        else:
            await pictures.delete(picture)
