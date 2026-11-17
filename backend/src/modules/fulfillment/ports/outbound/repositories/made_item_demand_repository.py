"""
Repository interfaces for the MadeItemDemandItem and MadeItemDemandAllocation
aggregates. Mirrors bought_item_repository.py's demand/allocation protocols.
"""

from dataclasses import dataclass
from datetime import date
from typing import Protocol
from typing import runtime_checkable

from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem


@dataclass
class MadeItemDemandFilterDto:
    skip: int | None = None
    limit: int | None = None
    ids: list[int] | None = None  # live row-sync: refetch specific rows, ignore paging
    search: str | None = None
    status: str | None = None
    statuses: list[str] | None = None
    project_id: int | None = None
    # Demands of any project built on this product.
    product_id: int | None = None
    project_number: str | None = None
    made_item_id: int | None = None
    item_part_number: str | None = None
    item_article_name: str | None = None
    creator_id: int | None = None
    changed_by_id: int | None = None
    high_priority: bool | None = None
    desired_from: date | None = None
    desired_to: date | None = None
    created_from: date | None = None
    created_to: date | None = None
    ignore_fulfilled: bool | None = None
    ignore_canceled: bool | None = None
    # Quantity-derived, not a status comparison, see
    # persistence/allocation_filters.demand_not_fully_allocated.
    not_fully_allocated: bool | None = None
    # Any-of: demands holding an allocation from one of these lots.
    lot_id: list[int] | None = None
    # Any-of across both lists: demands whose made item has a routing
    # process using one of these fabrication or inspection methods.
    process_fabrication_method_id: list[int] | None = None
    process_inspection_method_id: list[int] | None = None
    # Display state only (see DemandBucketRules), never a
    # business-logic filter.
    # No predicate at all when both are empty/falsy; otherwise
    # `bucket_id IN (...) OR bucket_id IS NULL`, built only from the parts
    # given.
    bucket_id: list[int] | None = None
    include_unbucketed: bool | None = None
    order_by: str | None = None
    order_dir: str | None = None
    # Only the rows that can give a Todo task on or before this day, the
    # tenant's horizon of the Todo page (see GetTodoSources). A wider set
    # than the tasks themselves: the page decides the buckets.
    todo_horizon: date | None = None


@runtime_checkable
class IMadeItemDemandItemRepository(Protocol):
    async def get_by_id(self, id: int) -> MadeItemDemandItem | None: ...
    async def get_by_id_for_update(self, id: int) -> MadeItemDemandItem | None:
        """Same as get_by_id but takes a row lock held until the
        surrounding transaction commits/rolls back, Postgres-only effect
        (SQLite, used by the hermetic test suite, ignores FOR UPDATE).
        Use at the top of a use case that reads this demand's allocated
        total and then writes a new allocation quantity back onto it, so
        two concurrent allocation writes against the same demand
        serialize instead of both overshooting its quantity. The read
        refreshes the row and everything loaded with it, so the caller
        writes the entity it got here, never one it read before the
        lock."""
        ...

    async def get_by_ids(
        self, ids: list[int], *, refresh: bool = False
    ) -> list[MadeItemDemandItem]:
        """With refresh, rows the session already holds are re-read, as the
        lifecycle reconciler needs."""
        ...

    async def lock_for_update(self, ids: list[int]) -> None:
        """Takes row locks on the demands, in ascending id order, held until
        the transaction ends (Postgres only; SQLite ignores FOR UPDATE), and
        re-reads them. The lifecycle lock plan calls it, after the bought
        demands and before the source demands."""
        ...

    async def get_ids_after(self, after_id: int, limit: int) -> list[int]:
        """Up to `limit` demand ids above `after_id`, ascending, for walking
        every demand in pages."""
        ...

    async def get_by_project_id(self, project_id: int) -> list[MadeItemDemandItem]: ...
    async def get_by_statuses(self, statuses: list[str]) -> list[MadeItemDemandItem]:
        """Every demand in one of `statuses`, unpaged, high priority first,
        then by desired delivery date and id, for the batch jobs that must
        see all of them."""
        ...

    async def get_multi(
        self, filters: MadeItemDemandFilterDto
    ) -> tuple[int, list[MadeItemDemandItem]]: ...
    async def get_pipeline(self, terminal_since: date) -> list[MadeItemDemandItem]: ...
    async def count_by_status(self) -> dict[str, int]:
        """How many rows the unfiltered list holds per stored status."""
        ...

    async def save(self, demand: MadeItemDemandItem) -> MadeItemDemandItem: ...
    async def delete(self, demand: MadeItemDemandItem) -> None: ...


@runtime_checkable
class IMadeItemAllocationRepository(Protocol):
    async def get_by_demand_item_id(
        self, demand_item_id: int
    ) -> list[MadeItemDemandAllocation]: ...
    async def get_by_demand_item_ids(
        self, demand_item_ids: list[int], *, refresh: bool = False
    ) -> list[MadeItemDemandAllocation]:
        """With refresh, rows the session already holds are re-read, as the
        lifecycle reconciler needs."""
        ...

    async def get_by_lot_id(self, lot_id: int) -> list[MadeItemDemandAllocation]: ...
    async def get_by_lot_ids(
        self, lot_ids: list[int], *, refresh: bool = False
    ) -> list[MadeItemDemandAllocation]:
        """Every allocation against any of `lot_ids`, in one query. With
        refresh, rows the session already holds are re-read."""
        ...

    async def get_allocated_quantity(self, demand_item_id: int) -> float: ...
    async def save(self, allocation: MadeItemDemandAllocation) -> MadeItemDemandAllocation: ...
    async def delete(self, allocation: MadeItemDemandAllocation) -> None: ...
