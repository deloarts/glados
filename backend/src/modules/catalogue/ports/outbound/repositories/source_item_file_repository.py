"""
Repository interface for SourceItemFile persistence.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.catalogue.domain.entities.source_item_file import SourceItemFile
from src.modules.catalogue.domain.value_objects.source_item_file_category import (
    SourceItemFileCategory,
)


@runtime_checkable
class ISourceItemFileRepository(Protocol):
    async def get_by_id(self, id: int) -> SourceItemFile | None: ...
    async def get_by_item_id(self, item_id: int) -> list[SourceItemFile]: ...
    async def get_by_item_ids(self, item_ids: list[int]) -> list[SourceItemFile]: ...
    async def get_by_item_id_and_category(
        self, item_id: int, category: SourceItemFileCategory
    ) -> list[SourceItemFile]: ...
    async def save(self, file: SourceItemFile) -> SourceItemFile: ...
    async def delete(self, file: SourceItemFile) -> None: ...
