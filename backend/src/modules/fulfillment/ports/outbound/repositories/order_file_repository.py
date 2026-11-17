"""
Repository interface for OrderFile persistence.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.fulfillment.domain.entities.order_file import OrderFile
from src.modules.fulfillment.domain.value_objects.order_file_category import OrderFileCategory


@runtime_checkable
class IOrderFileRepository(Protocol):
    async def get_by_id(self, id: int) -> OrderFile | None: ...
    async def get_by_item_id(self, item_id: int) -> list[OrderFile]: ...
    async def get_by_item_ids(self, item_ids: list[int]) -> list[OrderFile]: ...
    async def get_by_item_id_and_category(
        self, item_id: int, category: OrderFileCategory
    ) -> list[OrderFile]: ...
    async def save(self, file: OrderFile) -> OrderFile: ...
    async def delete(self, file: OrderFile) -> None: ...
