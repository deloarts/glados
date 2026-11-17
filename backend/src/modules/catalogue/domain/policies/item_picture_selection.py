"""
Chooses the picture shown for an item, everywhere one picture stands for
the item: table thumbnails, the main picture of a detail page, and the
part image on printed reports and labels.
"""

from collections.abc import Iterable

from src.modules.catalogue.domain.entities.item_picture import ItemPicture
from src.modules.catalogue.domain.value_objects.item_picture_source import PRECEDENCE


def pick_picture(pictures: Iterable[ItemPicture]) -> ItemPicture | None:
    """The picture of the highest-ranked source in PRECEDENCE among
    `pictures`, which all belong to one item; None without any."""
    by_source = {p.source: p for p in pictures}
    for source in PRECEDENCE:
        if source in by_source:
            return by_source[source]
    return None
