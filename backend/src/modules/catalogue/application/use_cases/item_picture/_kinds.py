"""
What differs between the picture use cases of made, bought and source
items: the kind the pictures are stored under, the wording, the error for
a missing item and the write permission. A picture needs the same
permission as editing its item, like the item's files.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from src.modules.catalogue.domain.errors import BoughtItemNotFoundError
from src.modules.catalogue.domain.errors import MadeItemNotFoundError
from src.modules.catalogue.domain.errors import SourceItemNotFoundError
from src.modules.catalogue.domain.policies.bought_item_rules import BoughtItemCatalogueRules
from src.modules.catalogue.domain.policies.made_item_rules import MadeItemCatalogueRules
from src.modules.catalogue.domain.policies.source_item_rules import SourceItemCatalogueRules
from src.modules.catalogue.domain.value_objects.item_kind import ItemKind
from src.modules.platform.domain.entities.user import User


class PictureItemRepo(Protocol):
    """The one method the picture use cases call on an item repository, to
    check the item exists before touching its pictures."""

    async def get_by_id(self, id: int) -> object | None: ...


@dataclass(frozen=True)
class PictureKind:
    kind: ItemKind
    item_label: str  # lowercase, e.g. "bought item"
    item_not_found_error: type[Exception]
    write_rule: Callable[[User], None]

    def not_found(self, item_id: int) -> Exception:
        return self.item_not_found_error(f"{self.item_label.capitalize()} #{item_id} not found.")


MADE_ITEM_PICTURES = PictureKind(
    kind=ItemKind.MADE,
    item_label="made item",
    item_not_found_error=MadeItemNotFoundError,
    write_rule=MadeItemCatalogueRules.assert_can_update,
)
BOUGHT_ITEM_PICTURES = PictureKind(
    kind=ItemKind.BOUGHT,
    item_label="bought item",
    item_not_found_error=BoughtItemNotFoundError,
    write_rule=BoughtItemCatalogueRules.assert_can_update,
)
SOURCE_ITEM_PICTURES = PictureKind(
    kind=ItemKind.SOURCE,
    item_label="source item",
    item_not_found_error=SourceItemNotFoundError,
    write_rule=SourceItemCatalogueRules.assert_can_update,
)
