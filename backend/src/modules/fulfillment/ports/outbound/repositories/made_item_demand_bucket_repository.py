"""
Abstract interface for made-item demand bucket persistence.
The application layer depends on this, never on the SQLAlchemy implementation.
"""

from dataclasses import dataclass
from typing import Protocol
from typing import runtime_checkable

from src.modules.fulfillment.domain.entities.made_item_demand_bucket import MadeItemDemandBucket


@dataclass
class MadeItemDemandBucketFilterDto:
    skip: int | None = None
    limit: int | None = None
    search: str | None = None
    order_by: str | None = None
    order_dir: str | None = None


@runtime_checkable
class IMadeItemDemandBucketRepository(Protocol):
    async def get_by_id(self, id: int) -> MadeItemDemandBucket | None: ...

    async def get_by_name(self, name: str) -> MadeItemDemandBucket | None:
        """Case-insensitive lookup (uniqueness is case-insensitive, see
        DemandBucketRules/CreateBucket/UpdateBucket)."""
        ...

    async def get_multi(
        self, filters: MadeItemDemandBucketFilterDto
    ) -> tuple[int, list[MadeItemDemandBucket]]: ...

    async def save(self, bucket: MadeItemDemandBucket) -> MadeItemDemandBucket:
        """Insert (id == 0) or update (id > 0)."""
        ...

    async def delete(self, bucket: MadeItemDemandBucket) -> None:
        """Hard delete. Nulls `bucket_id` on every demand assigned to this
        bucket in the same transaction before deleting the row (SQLite,
        used by the hermetic test suite, doesn't enforce ON DELETE SET
        NULL)."""
        ...
