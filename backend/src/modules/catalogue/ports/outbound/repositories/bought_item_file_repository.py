"""
Abstract interface for bought item file persistence.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.catalogue.domain.entities.bought_item_file import BoughtItemFile
from src.modules.catalogue.domain.value_objects.bought_item_file_category import (
    BoughtItemFileCategory,
)


@runtime_checkable
class IBoughtItemFileRepository(Protocol):
    async def get_by_id(self, id: int) -> BoughtItemFile | None: ...
    async def get_by_item_id(self, item_id: int) -> list[BoughtItemFile]: ...
    async def get_by_item_ids(self, item_ids: list[int]) -> list[BoughtItemFile]: ...
    async def get_by_item_id_and_category(
        self, item_id: int, category: BoughtItemFileCategory
    ) -> list[BoughtItemFile]: ...
    async def save(self, file: BoughtItemFile) -> BoughtItemFile: ...
    async def delete(self, file: BoughtItemFile) -> None: ...
    async def reassign(self, file_id: int, target_item_id: int) -> None: ...
