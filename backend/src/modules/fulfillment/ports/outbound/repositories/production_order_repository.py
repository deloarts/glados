"""
Repository interface for the ProductionOrder aggregate together with its
owned ProductionOrderCompletion children, which are always fetched with it.
"""

from dataclasses import dataclass
from datetime import date
from datetime import datetime
from typing import Protocol
from typing import runtime_checkable

from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)


@dataclass
class ProductionOrderFilterDto:
    skip: int | None = None
    limit: int | None = None
    search: str | None = None
    status: str | None = None
    # Multi-value counterpart to `status`, so the QA worklist can ask for
    # queued, in_progress and paused at once. Applied in addition to `status`.
    statuses: list[str] | None = None
    # Keeps only orders whose lot position has at least one step with this
    # StepRole ('inspection' selects the QA worklist). Matched with EXISTS,
    # so an order is returned once regardless of how many steps match.
    step_role: str | None = None
    machine_id: int | None = None
    lot_position_id: int | None = None
    lot_id: int | None = None
    order_by: str | None = None
    order_dir: str | None = None
    # Row filters of the QA worklist. Text filters are case-insensitive
    # substring matches. The inspection method matches any inspection step
    # of the order's position. Date bounds are inclusive calendar days in
    # UTC over the order's timestamps. finished_by_ids matches any recorded
    # completion by one of those operators, not only the latest one.
    step_inspection_method_ids: list[int] | None = None
    lot_number: str | None = None
    project_number: str | None = None
    item_text: str | None = None
    quantity_min: float | None = None
    quantity_max: float | None = None
    planned_start_from: date | None = None
    planned_start_to: date | None = None
    actual_end_from: date | None = None
    actual_end_to: date | None = None
    finished_by_ids: list[int] | None = None
    # Orders last changed, or created when never changed, at or after this
    # instant.
    changed_from: datetime | None = None


@dataclass(frozen=True)
class ProductionOrderPlanningFields:
    """What the schedule recompute writes for one persisted order: the planned
    window and its author, plus the pin flag and the queue place (machine,
    pool and sequence) the order had when the recompute read it. Nothing
    else of the order can be written through it. Without a queue place the
    place is not compared."""

    order_id: int
    planned_start: datetime | None
    planned_end: datetime | None
    planned_by_id: int | None
    pinned_when_read: bool
    place_when_read: tuple[int | None, int | None, int] | None = None


@runtime_checkable
class IProductionOrderRepository(Protocol):
    async def get_by_id(self, id: int) -> ProductionOrder | None: ...
    async def get_by_id_for_update(self, id: int) -> ProductionOrder | None:
        """Same as get_by_id but takes a row lock on the order, held until
        the surrounding transaction commits or rolls back (Postgres only;
        SQLite ignores FOR UPDATE). The read refreshes the order and
        everything loaded with it, so the caller works on the committed
        state and writes the entity it got here, never one it read before
        the lock. Taken after the lock of the order's lot
        (IProductionLotRepository.get_by_id_for_update), as
        RecordProductionOrderCompletion and ScrapProductionPieces do before
        they read the processed total."""
        ...

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[ProductionOrder]:
        """The orders with their completions and interruptions. With
        refresh, rows the session already holds are re-read, as the
        lifecycle reconciler needs."""
        ...

    async def lock_for_update(self, ids: list[int]) -> None:
        """Takes row locks on the orders, in ascending id order, held until
        the transaction ends (Postgres only; SQLite ignores FOR UPDATE), and
        re-reads them. The lifecycle lock plan calls it, after the locks of
        the orders' lots."""
        ...

    # All production orders (across machines) assigned to one INTERNAL
    # lot position, for Sigma-quantity/completion aggregation.
    async def get_by_lot_position_id(self, lot_position_id: int) -> list[ProductionOrder]: ...

    # Batch counterpart in one query, so the scheduler avoids an N+1. With
    # refresh, rows the session already holds are re-read, as the lifecycle
    # reconciler needs.
    async def get_by_lot_position_ids(
        self, lot_position_ids: list[int], *, refresh: bool = False
    ) -> list[ProductionOrder]: ...

    # Machine queue listing (ordered by queue_sequence).
    async def get_by_machine_id(self, machine_id: int | None) -> list[ProductionOrder]: ...

    async def get_live_by_machine_ids(self, machine_ids: list[int | None]) -> list[ProductionOrder]:
        """Every order on any of the listed machines that is not completed or
        canceled, in one query. A None entry selects the machine-less ones.
        Ordered by (queue_sequence, id)."""
        ...

    async def count_live_by_machine_ids(self, machine_ids: list[int]) -> dict[int, int]:
        """The number of queued, in-progress and paused orders per machine,
        machines without any left out."""
        ...

    # The in_progress and paused orders of the given machines in one query,
    # grouped by machine_id, for the machine table's computed status column
    # (production_machine_status_rules).
    async def get_active_by_machine_ids(
        self, machine_ids: list[int]
    ) -> dict[int, list[ProductionOrder]]: ...

    # Every order that is not COMPLETED or CANCELED, in every queue, archived
    # machines included since archiving does not reassign orders. Unpaged on
    # purpose: the global schedule walk needs every live order in one pass to
    # keep cross-queue capacity honest. Ordered by (queue_sequence, id) for a
    # deterministic input, although the walk re-sorts each queue itself.
    async def get_all_non_terminal(self) -> list[ProductionOrder]: ...

    async def get_multi(
        self, filters: ProductionOrderFilterDto
    ) -> tuple[int, list[ProductionOrder]]: ...

    async def save(self, order: ProductionOrder) -> ProductionOrder: ...
    async def save_schedule(self, orders: list[ProductionOrder]) -> None:
        """Writes only the scheduling fields of already persisted orders
        (machine_id, machine_pool_id, queue_sequence, pinned, planned_start,
        planned_end, planned_by_id) and flushes once, without reloading or
        returning them. For Auto-Plan, which places orders under the
        queue-scope locks of every scope it may touch (lock_queue_scope) and
        keeps working with its own entities. The rows are locked in ascending
        id order before they are written, and the write skips the version
        check, which the row locks make unnecessary. Unchanged rows are not
        updated, and ids that no longer exist are skipped."""
        ...

    async def save_planning_fields(self, plans: list[ProductionOrderPlanningFields]) -> None:
        """Writes planned_start, planned_end and planned_by_id of persisted
        orders and flushes, for the schedule recompute, which reads every order
        long before it writes. The rows are locked and re-read in ascending id
        order, so only differing values are written and the version check is
        skipped. A row whose pin no longer matches pinned_when_read keeps the
        window a person pinned meanwhile, and missing ids are skipped."""
        ...

    async def next_production_order_number(self, template: str) -> str: ...

    # The next number in one queue scope: the machine's queue when machine_id
    # is set, otherwise the pool's own queue when machine_pool_id is set,
    # otherwise the shared space of orders with neither.
    async def next_queue_sequence(
        self, machine_id: int | None, machine_pool_id: int | None = None
    ) -> int: ...

    async def lock_queue_scope(
        self, machine_id: int | None, machine_pool_id: int | None = None
    ) -> None:
        """Serializes every writer of one queue's `queue_sequence` space, over the same
        three scopes next_queue_sequence resolves (machine, pool with no machine, neither).

        next_queue_sequence reads the maximum and adds one without a lock, so two concurrent
        assigns could get the same number, and a reorder or Auto-Plan rewrite could interleave
        with them. The partial unique indexes on queue_sequence are only a last-resort net. On
        Postgres this is a transaction-scoped advisory lock released on commit or rollback; on
        SQLite it is a no-op."""
        ...

    async def shift_queue_sequence(self, order_ids: list[int]) -> None:
        """First step of a two-step queue_sequence rewrite: moves every listed order to
        the negative value -id in one UPDATE, then flushes.

        The partial unique indexes on queue_sequence cannot be deferred, so a multi-row rewrite
        must never let two rows hold the same value in between. Live values are never negative,
        so after this shift the per-row saves of the final values cannot collide with each
        other or with untouched rows. The caller must still hold lock_queue_scope for every
        touched scope, since this does not serialize against other transactions."""
        ...

    # ── Completions (owned children) ────────────────────────────────
    async def get_completions(
        self, production_order_id: int
    ) -> list[ProductionOrderCompletion]: ...
    async def get_completion_by_id(
        self, completion_id: int
    ) -> ProductionOrderCompletion | None: ...
    async def save_completion(
        self, completion: ProductionOrderCompletion
    ) -> ProductionOrderCompletion: ...
