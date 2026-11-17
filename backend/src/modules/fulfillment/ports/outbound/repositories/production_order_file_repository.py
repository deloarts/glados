"""
Repository interface for ProductionOrderFile persistence.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.fulfillment.domain.entities.production_order_file import ProductionOrderFile
from src.modules.fulfillment.domain.value_objects.production_order_file_category import (
    ProductionOrderFileCategory,
)


@runtime_checkable
class IProductionOrderFileRepository(Protocol):
    async def get_by_id(self, id: int) -> ProductionOrderFile | None: ...
    async def get_by_item_id(self, item_id: int) -> list[ProductionOrderFile]: ...
    async def get_by_item_ids(self, item_ids: list[int]) -> list[ProductionOrderFile]: ...
    async def get_by_item_id_and_category(
        self, item_id: int, category: ProductionOrderFileCategory
    ) -> list[ProductionOrderFile]: ...
    async def save(self, file: ProductionOrderFile) -> ProductionOrderFile: ...
    async def delete(self, file: ProductionOrderFile) -> None: ...
