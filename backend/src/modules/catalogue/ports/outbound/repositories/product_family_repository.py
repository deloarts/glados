"""
Abstract interface for product family persistence.
The application layer depends on this, never on the SQLAlchemy implementation.
"""

from datetime import datetime
from typing import Protocol
from typing import runtime_checkable

from src.modules.catalogue.domain.entities.product_family import ProductFamily
from src.modules.catalogue.ports.outbound.catalogue_queries import ProductFamilyFilterDto
from src.shared_kernel.domain.services.list_order import ListEntry


@runtime_checkable
class IProductFamilyRepository(Protocol):
    async def get_by_id(self, id: int) -> ProductFamily | None:
        """Regardless of `archived`, references must resolve."""
        ...

    async def get_by_name(self, name: str) -> ProductFamily | None:
        """Live (non-archived) rows only, matches the scope of
        `uq_product_family_name_active`."""
        ...

    async def get_by_ids(self, ids: list[int]) -> list[ProductFamily]:
        """Regardless of `archived`, references must resolve."""
        ...

    async def get_multi(
        self, filters: ProductFamilyFilterDto
    ) -> tuple[int, list[ProductFamily]]: ...

    async def get_aggregate(self) -> tuple[int, datetime | None]:
        """(row count, max(changed)) over every row, archived rows included. It
        is a cheap aggregate for the ETag of GET /pat/lookups and loads no row."""
        ...

    async def save(self, product_family: ProductFamily) -> ProductFamily:
        """Insert (id == 0) or update (id > 0)."""
        ...

    async def delete(self, product_family: ProductFamily) -> None: ...

    async def get_list_order(self) -> list[ListEntry]:
        """Every row's place in the hand-kept order, archived rows included."""
        ...

    async def next_sort_order(self) -> int:
        """The place after the last row, where a new row goes."""
        ...

    async def set_sort_orders(self, sort_orders: dict[int, int]) -> None:
        """Writes the `sort_order` of each row by id and nothing else."""
        ...
