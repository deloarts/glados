"""
Repository interface for the manual PLC tags of a product.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.workspace.domain.entities.plc_manual_tag import PlcManualTag


@runtime_checkable
class IPlcManualTagRepository(Protocol):
    async def get_by_id(self, id: int) -> PlcManualTag | None: ...

    async def get_by_product(self, product_id: int) -> list[PlcManualTag]:
        """In their sort order."""
        ...

    async def next_sort_order(self, product_id: int) -> int: ...

    async def save(self, tag: PlcManualTag) -> PlcManualTag:
        """Insert (id == 0) or update (id > 0)."""
        ...

    async def delete(self, tag: PlcManualTag) -> None: ...
