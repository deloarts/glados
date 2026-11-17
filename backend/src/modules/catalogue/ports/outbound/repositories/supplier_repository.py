"""
Abstract interface for supplier persistence.
The application layer depends on this, never on the SQLAlchemy implementation.
"""

from datetime import datetime
from typing import Protocol
from typing import runtime_checkable

from src.modules.catalogue.domain.entities.supplier import Supplier
from src.modules.catalogue.ports.outbound.catalogue_queries import SupplierFilterDto


@runtime_checkable
class ISupplierRepository(Protocol):
    async def get_by_id(self, id: int) -> Supplier | None:
        """Resolves regardless of `archived`, since references must resolve."""
        ...

    async def lock_for_update(self, id: int) -> None:
        """Locks the row until the transaction ends. An edit takes the lock
        before it reads the row, so the edit version it checks is the one it
        overwrites."""
        ...

    async def get_by_vat_id(self, vat_id: str) -> Supplier | None:
        """Live (non-archived) rows only, matches the scope of
        `uq_supplier_vat_id_active`."""
        ...

    async def get_by_edp_code(self, edp_code: str) -> Supplier | None:
        """The live supplier carrying this Data Portal code (stored upper
        case), matches the scope of `uq_supplier_edp_code_active`."""
        ...

    async def get_multi(self, filters: SupplierFilterDto) -> tuple[int, list[Supplier]]: ...

    async def get_aggregate(self) -> tuple[int, datetime | None]:
        """(row count, max(changed)) over every row, archived rows included. It
        is a cheap aggregate for the ETag of GET /pat/lookups and loads no row."""
        ...

    async def save(self, supplier: Supplier) -> Supplier:
        """Insert (id == 0) or update (id > 0)."""
        ...

    async def delete(self, supplier: Supplier) -> None: ...
