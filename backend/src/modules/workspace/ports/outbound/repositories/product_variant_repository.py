"""
Persistence port for the variants of a product.
"""

from typing import Protocol
from typing import runtime_checkable

from src.modules.workspace.domain.entities.product_variant import ProductVariant


@runtime_checkable
class IProductVariantRepository(Protocol):
    async def get_by_product(self, product_id: int, include_archived: bool) -> list[ProductVariant]:
        """Ordered by `sort_order`, archived variants last."""
        ...

    async def save_all(
        self, product_id: int, variants: list[ProductVariant]
    ) -> list[ProductVariant]:
        """Inserts the variants with id 0 and updates the others; returns the
        product's variants afterwards, archived ones included."""
        ...
