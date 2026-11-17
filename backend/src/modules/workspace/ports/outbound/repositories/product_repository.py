"""
Abstract interface for product persistence.
"""

from dataclasses import dataclass
from datetime import date
from typing import Protocol
from typing import runtime_checkable

from src.modules.workspace.domain.entities.product import Product


@dataclass
class ProductFilterDto:
    id: int | None = None
    product_number: str | None = None
    customer_id: int | None = None
    description: str | None = None
    is_active: bool | None = None
    designated_user_id: int | None = None
    creator_id: int | None = None
    # Calendar-day bounds, both inclusive.
    created_from: date | None = None
    created_to: date | None = None
    skip: int | None = None
    limit: int | None = None
    search: str | None = None
    include_archived: bool = False
    order_by: str | None = None
    order_dir: str | None = None


@runtime_checkable
class IProductRepository(Protocol):
    async def get_by_id(self, id: int) -> Product | None:
        """Regardless of `archived`, references must resolve."""
        ...

    async def lock_for_update(self, id: int) -> None:
        """Locks the row until the transaction ends. An edit takes the lock
        before it reads the row, so the edit version it checks is the one it
        overwrites."""
        ...

    async def get_by_product_number(self, product_number: str) -> Product | None:
        """Live (non-archived) rows only, matches the scope of
        `uq_product_product_number_active`."""
        ...

    async def get_by_designated_user_id(self, user_id: int) -> list[Product]: ...

    async def get_multi(self, filters: ProductFilterDto) -> tuple[int, list[Product]]: ...

    async def get_active(self, limit: int) -> list[Product]:
        """Live products marked active, by product number, at most `limit`."""
        ...

    async def save(self, product: Product) -> Product:
        """Insert (id == 0) or update (id > 0)."""
        ...

    async def delete(self, product: Product) -> None: ...
