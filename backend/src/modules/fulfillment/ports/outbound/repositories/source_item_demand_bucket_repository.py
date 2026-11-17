"""
Abstract interface for source-item demand bucket persistence.
The application layer depends on this, never on the SQLAlchemy implementation.
"""

from dataclasses import dataclass
from typing import Protocol
from typing import runtime_checkable

from src.modules.fulfillment.domain.entities.source_item_demand_bucket import SourceItemDemandBucket


@dataclass
class SourceItemDemandBucketFilterDto:
    skip: int | None = None
    limit: int | None = None
    search: str | None = None
    order_by: str | None = None
    order_dir: str | None = None


@runtime_checkable
class ISourceItemDemandBucketRepository(Protocol):
    async def get_by_id(self, id: int) -> SourceItemDemandBucket | None: ...

    async def get_by_name(self, name: str) -> SourceItemDemandBucket | None:
        """Case-insensitive lookup (uniqueness is case-insensitive, see
        DemandBucketRules/CreateBucket/UpdateBucket)."""
        ...

    async def get_multi(
        self, filters: SourceItemDemandBucketFilterDto
    ) -> tuple[int, list[SourceItemDemandBucket]]: ...

    async def save(self, bucket: SourceItemDemandBucket) -> SourceItemDemandBucket:
        """Insert (id == 0) or update (id > 0)."""
        ...

    async def delete(self, bucket: SourceItemDemandBucket) -> None:
        """Hard delete. Nulls `bucket_id` on every demand assigned to this
        bucket in the same transaction before deleting the row (SQLite,
        used by the hermetic test suite, doesn't enforce ON DELETE SET
        NULL)."""
        ...
