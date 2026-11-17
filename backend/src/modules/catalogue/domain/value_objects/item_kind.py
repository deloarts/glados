"""The three catalogue item families that carry pictures: made, bought and
source items. Their values match the `kind` strings the PDM code already
uses for made and bought items."""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class ItemKind(StrValueEnum):
    MADE = "made"
    BOUGHT = "bought"
    SOURCE = "source"
