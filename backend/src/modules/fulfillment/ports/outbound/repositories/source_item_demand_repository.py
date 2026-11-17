"""
Repository interfaces for the SourceItemDemandItem aggregate and its
allocation-pool junction (SourceItemDemandAllocation).
"""

from dataclasses import dataclass
from datetime import date
from typing import Protocol
from typing import runtime_checkable

from src.modules.fulfillment.domain.entities.source_item_allocation import (
    SourceItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem


@dataclass
class SourceItemDemandFilterDto:
    skip: int | None = None
    limit: int | None = None
    ids: list[int] | None = None  # live row-sync: refetch specific rows, ignore paging
    # Any of project, lot, material, bought item or note contains it.
    search: str | None = None
    status: str | None = None
    ignore_fulfilled: bool | None = None
    ignore_canceled: bool | None = None
    # Quantity-derived, not a status comparison, see
    # persistence/allocation_filters.demand_not_fully_allocated.
    not_fully_allocated: bool | None = None
    # Any-of over the demand's own lot column.
    lot_id: list[int] | None = None
    bought_item_id: int | None = None
    source_item_id: int | None = None
    project_id: int | None = None
    # Demands of any project built on this product.
    product_id: int | None = None
    project_number: str | None = None
    # Match the source item side only; a bought-item-backed demand never
    # matches these three.
    item_dimension: str | None = None
    item_material: str | None = None
    item_type: str | None = None
    # Any-of: demands holding an allocation from an order item of one of
    # these orders.
    order_id: list[int] | None = None
    creator_id: int | None = None
    changed_by_id: int | None = None
    high_priority: bool | None = None
    desired_from: date | None = None
    desired_to: date | None = None
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
class ISourceItemDemandRepository(Protocol):
    async def get_by_id(self, id: int) -> SourceItemDemandItem | None: ...
    async def get_by_ids(
        self, ids: list[int], *, refresh: bool = False
    ) -> list[SourceItemDemandItem]:
        """Batch counterpart to get_by_id, one IN-query for a
        whole id list instead of one query per id, as
        GetSourceItemDemandSummaryBatch needs. Unknown ids are silently
        omitted, same as get_by_id returning None for one. With refresh, rows the session
        already holds are re-read, as the lifecycle reconciler needs."""
        ...

    async def lock_for_update(self, ids: list[int]) -> None:
        """Takes row locks on the demands, in ascending id order, held until
        the transaction ends (Postgres only; SQLite ignores FOR UPDATE), and
        re-reads them. The lifecycle lock plan calls it last."""
        ...

    async def get_ids_after(self, after_id: int, limit: int) -> list[int]:
        """Up to `limit` demand ids above `after_id`, ascending, for walking
        every demand in pages."""
        ...

    async def get_by_id_for_update(self, id: int) -> SourceItemDemandItem | None:
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

    async def get_multi(
        self, filters: SourceItemDemandFilterDto
    ) -> tuple[int, list[SourceItemDemandItem]]: ...
    async def count_by_status(self) -> dict[str, int]:
        """How many rows the unfiltered list holds per stored status."""
        ...

    async def save(self, demand: SourceItemDemandItem) -> SourceItemDemandItem: ...


@runtime_checkable
class ISourceItemAllocationRepository(Protocol):
    async def get_by_demand_item_id(
        self, demand_item_id: int
    ) -> list[SourceItemDemandAllocation]: ...
    async def get_by_demand_item_ids(
        self, demand_item_ids: list[int], *, refresh: bool = False
    ) -> list[SourceItemDemandAllocation]:
        """With refresh, rows the session already holds are re-read, as the
        lifecycle reconciler needs."""
        ...

    async def get_by_order_item_id(
        self, order_item_id: int
    ) -> list[SourceItemDemandAllocation]: ...
    async def get_by_order_item_ids(
        self, order_item_ids: list[int], *, refresh: bool = False
    ) -> list[SourceItemDemandAllocation]:
        """Every allocation on any of the order items, in one query. With
        refresh, rows the session already holds are re-read."""
        ...

    async def get_allocated_quantity(self, demand_item_id: int) -> float: ...
    async def get_allocated_quantity_for_order_item(self, order_item_id: int) -> float:
        """Everything allocated to the order item, summed over the bought
        and the source item allocation tables, since demands of both kinds
        can draw on the same bought line. A capacity check reads it after
        locking the line."""
        ...

    async def get_allocated_quantities_for_order_items(
        self, order_item_ids: list[int]
    ) -> dict[int, float]:
        """get_allocated_quantity_for_order_item for many order items in
        one query; an order item without any allocation maps to 0.0."""
        ...

    async def save(self, allocation: SourceItemDemandAllocation) -> SourceItemDemandAllocation: ...
    async def delete(self, allocation: SourceItemDemandAllocation) -> None: ...
