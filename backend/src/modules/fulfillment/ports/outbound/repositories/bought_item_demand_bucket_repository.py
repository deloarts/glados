"""
Abstract interface for bought-item demand bucket persistence.
The application layer depends on this, never on the SQLAlchemy implementation.
"""

from dataclasses import dataclass
from typing import Protocol
from typing import runtime_checkable

from src.modules.fulfillment.domain.entities.bought_item_demand_bucket import BoughtItemDemandBucket


@dataclass
class BoughtItemDemandBucketFilterDto:
    skip: int | None = None
    limit: int | None = None
    search: str | None = None
    order_by: str | None = None
    order_dir: str | None = None


@runtime_checkable
class IBoughtItemDemandBucketRepository(Protocol):
    async def get_by_id(self, id: int) -> BoughtItemDemandBucket | None: ...

    async def get_by_name(self, name: str) -> BoughtItemDemandBucket | None:
        """Case-insensitive lookup (uniqueness is case-insensitive, see
        DemandBucketRules/CreateBucket/UpdateBucket)."""
        ...

    async def get_multi(
        self, filters: BoughtItemDemandBucketFilterDto
    ) -> tuple[int, list[BoughtItemDemandBucket]]: ...

    async def save(self, bucket: BoughtItemDemandBucket) -> BoughtItemDemandBucket:
        """Insert (id == 0) or update (id > 0)."""
        ...

    async def delete(self, bucket: BoughtItemDemandBucket) -> None:
        """Hard delete. Nulls `bucket_id` on every demand assigned to this
        bucket in the same transaction before deleting the row (SQLite,
        used by the hermetic test suite, doesn't enforce ON DELETE SET
        NULL)."""
        ...
