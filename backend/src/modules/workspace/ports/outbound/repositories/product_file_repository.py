"""
Repository interface for ProductFile persistence.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.workspace.domain.entities.product_file import ProductFile
from src.modules.workspace.domain.value_objects.product_file_category import ProductFileCategory


@runtime_checkable
class IProductFileRepository(Protocol):
    async def get_by_id(self, id: int) -> ProductFile | None: ...
    async def get_by_item_id(self, item_id: int) -> list[ProductFile]: ...
    async def get_by_item_ids(self, item_ids: list[int]) -> list[ProductFile]: ...
    async def get_by_item_id_and_category(
        self, item_id: int, category: ProductFileCategory
    ) -> list[ProductFile]: ...
    async def save(self, file: ProductFile) -> ProductFile: ...
    async def delete(self, file: ProductFile) -> None: ...
