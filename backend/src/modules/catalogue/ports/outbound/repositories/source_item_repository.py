"""
Repository interface for the SourceItem catalogue aggregate.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from typing import runtime_checkable

from src.modules.catalogue.domain.entities.source_item import SourceItem


@dataclass
class SourceItemFilterDto:
    skip: int | None = None
    limit: int | None = None
    ids: list[int] | None = None  # live row-sync: refetch specific rows, ignore paging
    search: str | None = None
    id: int | None = None
    status: str | None = None
    type_id: int | None = None
    material: str | None = None
    dimension: str | None = None
    note: str | None = None
    order_code_1: str | None = None
    order_code_2: str | None = None
    successor_item_id: int | None = None
    manufacturer_id: int | None = None
    creator_id: int | None = None
    changed_by_id: int | None = None
    approver_id: int | None = None
    include_archived: bool = False
    created_from: datetime | None = None
    created_to: datetime | None = None
    changed_from: datetime | None = None
    changed_to: datetime | None = None
    order_by: str | None = None
    order_dir: str | None = None


@runtime_checkable
class ISourceItemRepository(Protocol):
    async def get_by_id(self, id: int) -> SourceItem | None:
        """Regardless of `archived`, references must resolve."""
        ...

    async def lock_for_update(self, id: int) -> None:
        """Locks the row until the transaction ends. An edit takes the lock
        before it reads the row, so the edit version it checks is the one it
        overwrites."""
        ...

    async def get_by_spec_candidates(
        self,
        type_id: int,
        material: str,
        manufacturer_id: int | None,
    ) -> list[SourceItem]:
        """Live (non-archived) rows only, matches the scope of the two
        `uq_source_item_spec_*` partial indexes."""
        ...

    async def get_multi(self, filters: SourceItemFilterDto) -> tuple[int, list[SourceItem]]: ...

    async def get_aggregate(self) -> tuple[int, datetime | None]:
        """(row count, max(changed)) over every row, archived rows included. It
        is a cheap aggregate for the ETag of GET /pat/lookups and loads no row."""
        ...

    async def save(self, item: SourceItem) -> SourceItem: ...
    async def delete(self, item: SourceItem) -> None: ...
