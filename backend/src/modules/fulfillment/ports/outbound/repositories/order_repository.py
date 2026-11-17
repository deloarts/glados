"""
Repository interfaces for the generic Order/OrderItem/OrderItemDelivery vertical.
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import date
from datetime import datetime
from typing import Protocol
from typing import runtime_checkable

from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_extra_cost import OrderExtraCost
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.order_item_delivery import OrderItemDelivery
from src.modules.fulfillment.domain.services.extra_cost_rules import PricedLine
from src.modules.fulfillment.domain.services.lifecycle.delivery_totals import DeliveryTotals
from src.modules.workspace.api import ProjectSummaryRow


@dataclass
class OrderFilterDto:
    skip: int | None = None
    limit: int | None = None
    ids: list[int] | None = None  # live row-sync: refetch specific rows, ignore paging
    status: list[str] | None = None
    supplier_id: int | None = None
    creator_id: int | None = None
    changed_by_id: int | None = None
    # True keeps only orders with at least one invoice file, False only
    # orders without any; None leaves the file table out of the query.
    has_invoice: bool | None = None
    ordered_from: date | None = None
    ordered_to: date | None = None
    expected_delivery_from: date | None = None
    expected_delivery_to: date | None = None
    delivered_from: date | None = None
    delivered_to: date | None = None
    created_from: date | None = None
    created_to: date | None = None
    bought_item_id: int | None = None
    source_item_id: int | None = None
    made_item_id: int | None = None
    project_id: int | None = None
    # Orders with an item for any project built on this product.
    product_id: int | None = None
    order_number: str | None = None
    note: str | None = None
    storage_place: str | None = None
    search: str | None = None
    order_by: str | None = None
    order_dir: str | None = None
    # Only the rows that can give a Todo task on or before this day, the
    # tenant's horizon of the Todo page (see GetTodoSources). A wider set
    # than the tasks themselves: the page decides the buckets.
    todo_horizon: date | None = None


@dataclass
class OrderSpendFacts:
    """One order's placement instant, its lines as a line total reads them
    and its extra costs as (kind, amount) pairs, the facts its net total is
    computed from."""

    ordered_date: datetime
    lines: list[PricedLine] = field(default_factory=list)
    extra_costs: list[tuple[str, int]] = field(default_factory=list)


@runtime_checkable
class IOrderRepository(Protocol):
    async def get_by_id(self, id: int) -> Order | None: ...
    async def get_by_id_for_update(self, id: int) -> Order | None:
        """Same as get_by_id but takes a row lock on the order, held until
        the surrounding transaction commits or rolls back (Postgres only;
        SQLite ignores FOR UPDATE). The read refreshes the order and
        everything loaded with it, so the caller writes the entity it got
        here, never one it read before the lock. In the lock order the order
        comes after its lots and production orders and before its items."""
        ...

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[Order]:
        """With refresh, rows the session already holds are re-read, as the
        lifecycle reconciler needs."""
        ...

    async def lock_for_update(self, ids: list[int]) -> None:
        """Takes row locks on the orders, in ascending id order, held until
        the transaction ends (Postgres only; SQLite ignores FOR UPDATE), and
        re-reads them. The lifecycle lock plan calls it, after the lots and
        production orders and before the order items."""
        ...

    async def get_ids_after(self, after_id: int, limit: int) -> list[int]:
        """Up to `limit` order ids above `after_id`, ascending, for walking
        every order in pages."""
        ...

    async def get_by_order_number(self, order_number: str) -> Order | None: ...
    async def get_multi(self, filters: OrderFilterDto) -> tuple[int, list[Order]]: ...
    async def get_spend_facts(
        self, ordered_from: datetime, ordered_before: datetime
    ) -> list[OrderSpendFacts]:
        """What the net total of every order placed in the half-open window
        is computed from, the same orders the list's ordered_from and
        ordered_to filters return for the days that bound the window."""
        ...

    async def save(self, order: Order) -> Order: ...
    async def set_extra_costs(self, order_id: int, costs: list[OrderExtraCost]) -> None:
        """Makes `costs` the order's extra costs, in the given order: rows
        left out are deleted, the rest are written as new rows."""
        ...

    async def delete(self, order: Order) -> None: ...
    async def next_order_number(self, template: str) -> str: ...
    async def get_project_summary(self, project_id: int) -> ProjectSummaryRow: ...
    async def get_product_summary(self, product_id: int) -> ProjectSummaryRow:
        """The same rollup as get_project_summary, over all projects built
        on the product."""
        ...


@runtime_checkable
class IOrderItemRepository(Protocol):
    async def get_by_id(self, id: int) -> OrderItem | None: ...
    async def get_by_id_for_update(self, id: int) -> OrderItem | None:
        """Same as get_by_id but takes a row lock held until the
        surrounding transaction commits/rolls back, Postgres-only effect
        (SQLite, used by the hermetic test suite, ignores FOR UPDATE).
        Use at the top of a use case that reads-modifies-writes a
        quantity on this row (e.g. ProcessOrderItemDelivery), so two
        concurrent requests against the same item serialize instead of
        both reading the same pre-write quantity and overshooting it. The
        read refreshes the row and everything loaded with it, so the caller
        writes the entity it got here, never one it read before the lock."""
        ...

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[OrderItem]:
        """With refresh, rows the session already holds are re-read, as the
        lifecycle reconciler needs; the same holds for the refresh of the
        other batch reads below."""
        ...

    async def lock_for_update(self, ids: list[int]) -> None:
        """Takes row locks on the order items, in ascending id order, held
        until the transaction ends (Postgres only; SQLite ignores FOR
        UPDATE), and re-reads them. The lifecycle lock plan calls it, after
        the orders and before the demands."""
        ...

    async def get_by_order_id(self, order_id: int) -> list[OrderItem]: ...
    async def get_by_order_ids(
        self, order_ids: list[int], *, refresh: bool = False
    ) -> list[OrderItem]: ...
    async def get_by_bought_item_id(self, bought_item_id: int) -> list[OrderItem]: ...
    async def get_by_lot_position_id(self, lot_position_id: int) -> OrderItem | None: ...

    # Batch counterpart, one query for many positions instead of one query
    # per position, used by the scheduler's chain-walk prefetch
    # (_context._prefetch_order_items_by_position) to avoid an N+1 per
    # EXTERNAL/MIXED earlier position, per order, multiplied by chain depth
    # x order count, and by the lifecycle reconciler. It returns every line
    # of the positions, canceled ones included: a position holds at most one
    # open line, enforced by a unique index over the lines neither canceled
    # nor closed short, beside any number of canceled ones and lines closed
    # short, so a caller that keys by lot_position_id picks the newest live
    # line itself. Mirrors
    # IProductionOrderRepository.get_by_lot_position_ids.
    async def get_by_lot_position_ids(
        self, lot_position_ids: list[int], *, refresh: bool = False
    ) -> list[OrderItem]: ...

    async def get_by_source_item_id(self, source_item_id: int) -> list[OrderItem]: ...
    async def get_settled_short(self, limit: int) -> list[OrderItem]:
        """Up to `limit` bought and source lines that are not canceled and
        lost pieces at receipt or were closed short, the most recently
        changed first: the lines whose demands may have a rest open again."""
        ...

    async def next_position(self, order_id: int) -> int: ...
    async def save(self, item: OrderItem) -> OrderItem: ...
    async def delete(self, item: OrderItem) -> None: ...


@runtime_checkable
class IOrderItemDeliveryRepository(Protocol):
    async def get_by_id(self, id: int) -> OrderItemDelivery | None: ...
    async def get_by_order_item_id(self, order_item_id: int) -> list[OrderItemDelivery]: ...
    async def get_by_order_item_ids(self, order_item_ids: list[int]) -> list[OrderItemDelivery]: ...
    async def get_totals_by_order_item_ids(
        self, order_item_ids: list[int]
    ) -> dict[int, DeliveryTotals]:
        """Per order item, the accepted, rejected and lost pieces summed over
        its delivery rows; an item without rows has no entry."""
        ...

    async def save(self, delivery: OrderItemDelivery) -> OrderItemDelivery: ...
