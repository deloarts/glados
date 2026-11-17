"""
Abstract interface for customer persistence.
"""

from dataclasses import dataclass
from datetime import date
from datetime import datetime
from typing import Protocol

from src.modules.catalogue.domain.entities.customer import Customer


@dataclass
class CustomerFilterDto:
    id: int | None = None
    name: str | None = None
    legal_name: str | None = None
    vat_id: str | None = None
    level: str | None = None
    address: str | None = None
    country: str | None = None
    email: str | None = None
    creator_id: int | None = None
    changed_by_id: int | None = None
    created_from: date | None = None
    created_to: date | None = None
    changed_from: date | None = None
    changed_to: date | None = None
    skip: int | None = None
    limit: int | None = None
    search: str | None = None
    include_archived: bool = False
    order_by: str | None = None
    order_dir: str | None = None


class ICustomerRepository(Protocol):
    async def get_by_id(self, id: int) -> Customer | None:
        """Regardless of `archived`, references must resolve."""
        ...

    async def lock_for_update(self, id: int) -> None:
        """Locks the row until the transaction ends. An edit takes the lock
        before it reads the row, so the edit version it checks is the one it
        overwrites."""
        ...

    async def get_by_vat_id(self, vat_id: str) -> Customer | None:
        """Live (non-archived) rows only, matches the scope of
        `uq_customer_vat_id_active`."""
        ...

    async def get_multi(self, filters: CustomerFilterDto) -> tuple[int, list[Customer]]: ...

    async def get_aggregate(self) -> tuple[int, datetime | None]:
        """(row count, max(changed)) over every row, archived rows included. It
        is a cheap aggregate for the ETag of GET /pat/lookups and loads no row."""
        ...

    async def save(self, customer: Customer) -> Customer: ...
    async def delete(self, customer: Customer) -> None: ...
