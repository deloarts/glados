"""
A lifecycle reconciler over the order and order line fakes of a unit test.
Use case tests keep their own fakes, which offer get_by_id, get_by_order_id
and save. This module wraps them into the repositories the reconciler reads,
locks and writes, gives every other aggregate an empty stand-in, and switches
the reconciler on for order lines and orders, so a test of an order use case
sees the statuses the reconciler derives. The reconciler publishes on a bus of
its own unless the test passes one, so the events a test counts on the use
case's bus stay those of the use case.

A seeded row keeps its status through the reconciler only when its facts
give that status. give_order_facts and give_order_item_facts stamp the
intents a stored status stands for; delivered quantities stay as the test
set them.
"""

from dataclasses import dataclass
from dataclasses import field
from datetime import UTC
from datetime import datetime
from typing import Any

from src.modules.fulfillment.application.services.lifecycle_loader import LifecycleRepositories
from src.modules.fulfillment.application.services.lifecycle_lock_plan import LockPlan
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus

ORDER_AGGREGATES = frozenset({LifecycleAggregate.ORDER_ITEMS, LifecycleAggregate.ORDERS})

LockLog = list[tuple[LifecycleAggregate, tuple[int, ...]]]

# When a seeded intent was recorded.
_SEEDED_AT = datetime(2026, 1, 1, tzinfo=UTC)

_ORDERED_ORDERS = frozenset(
    {
        OrderStatus.ORDERED.value,
        OrderStatus.PARTIALLY_DELIVERED.value,
        OrderStatus.DELIVERED.value,
    }
)
_ORDERED_LINES = frozenset(
    {
        OrderItemStatus.ORDERED.value,
        OrderItemStatus.PARTIALLY_DELIVERED.value,
        OrderItemStatus.DELIVERED.value,
    }
)


def give_order_facts(order: Order) -> Order:
    """Stamps the intent the order's stored status stands for: canceled_at
    for CANCELED, ordered_date from ORDERED on, requested_at for REQUESTED.
    An intent the test set already is kept."""
    if order.status == OrderStatus.CANCELED.value:
        order.canceled_at = order.canceled_at or _SEEDED_AT
    elif order.status in _ORDERED_ORDERS:
        order.ordered_date = order.ordered_date or _SEEDED_AT
    elif order.status == OrderStatus.REQUESTED.value:
        order.requested_at = order.requested_at or _SEEDED_AT
    return order


def give_order_item_facts(item: OrderItem) -> OrderItem:
    """Stamps the intent the line's stored status stands for: canceled_at
    for CANCELED, ordered_date from ORDERED on, requested_at for REQUESTED.
    An intent the test set already is kept, and so are the delivered
    quantities, which a delivered status needs from the test."""
    if item.status == OrderItemStatus.CANCELED.value:
        item.canceled_at = item.canceled_at or _SEEDED_AT
    elif item.status in _ORDERED_LINES:
        item.ordered_date = item.ordered_date or _SEEDED_AT
    elif item.status == OrderItemStatus.REQUESTED.value:
        item.requested_at = item.requested_at or _SEEDED_AT
    return item


class RecordingBus:
    """The reconciler's bus: keeps what it publishes."""

    def __init__(self) -> None:
        self.published: list[Any] = []

    async def publish(self, event: Any) -> None:
        self.published.append(event)


class ReconcilerOrders:
    """A test's order fake as the reconciler's order repository."""

    def __init__(self, fake: Any, lock_log: LockLog | None = None) -> None:
        self._fake = fake
        self._lock_log: LockLog = lock_log if lock_log is not None else []

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[Any]:
        found = [await self._fake.get_by_id(i) for i in ids]
        return [order for order in found if order is not None]

    async def lock_for_update(self, ids: list[int]) -> None:
        self._lock_log.append((LifecycleAggregate.ORDERS, tuple(ids)))

    async def get_ids_after(self, after_id: int, limit: int) -> list[int]:
        return []

    async def save(self, order: Any) -> Any:
        return await self._fake.save(order)


class ReconcilerOrderItems:
    """A test's order line fake as the reconciler's order item repository."""

    def __init__(self, fake: Any, lock_log: LockLog | None = None) -> None:
        self._fake = fake
        self._lock_log: LockLog = lock_log if lock_log is not None else []

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[Any]:
        found = [await self._fake.get_by_id(i) for i in ids]
        return [item for item in found if item is not None]

    async def get_by_order_ids(self, order_ids: list[int], *, refresh: bool = False) -> list[Any]:
        lines: list[Any] = []
        for order_id in order_ids:
            lines.extend(await self._fake.get_by_order_id(order_id))
        return lines

    async def get_by_lot_position_ids(
        self, position_ids: list[int], *, refresh: bool = False
    ) -> list[Any]:
        by_position = getattr(self._fake, "get_by_lot_position_id", None)
        if by_position is None:
            return []
        found = [await by_position(p) for p in position_ids]
        return [item for item in found if item is not None]

    async def lock_for_update(self, ids: list[int]) -> None:
        self._lock_log.append((LifecycleAggregate.ORDER_ITEMS, tuple(ids)))

    async def save(self, item: Any) -> Any:
        return await self._fake.save(item)


class EmptyRows:
    """An aggregate the reconciler of a test does not write: reads find
    nothing and locks are only logged."""

    def __init__(
        self, aggregate: LifecycleAggregate | None = None, lock_log: LockLog | None = None
    ) -> None:
        self._aggregate = aggregate
        self._lock_log: LockLog = lock_log if lock_log is not None else []

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[Any]:
        return []

    async def get_positions_by_ids(self, position_ids: list[int]) -> list[Any]:
        return []

    async def get_by_lot_position_ids(
        self, position_ids: list[int], *, refresh: bool = False
    ) -> list[Any]:
        return []

    async def get_by_order_item_ids(
        self, order_item_ids: list[int], *, refresh: bool = False
    ) -> list[Any]:
        return []

    async def get_by_demand_item_ids(
        self, demand_item_ids: list[int], *, refresh: bool = False
    ) -> list[Any]:
        return []

    async def get_by_lot_ids(self, lot_ids: list[int], *, refresh: bool = False) -> list[Any]:
        return []

    async def get_ids_after(self, after_id: int, limit: int) -> list[int]:
        return []

    async def lock_for_update(self, ids: list[int]) -> None:
        if self._aggregate is not None:
            self._lock_log.append((self._aggregate, tuple(ids)))

    async def record_event(self, event: Any) -> Any:
        return event


@dataclass
class OrderReconciler:
    """The reconciler of a test with what it locked and published."""

    reconciler: LifecycleReconciler
    bus: RecordingBus
    lock_log: LockLog = field(default_factory=list)


def order_reconciler_harness(
    orders: Any, order_items: Any, *, bus: Any | None = None
) -> OrderReconciler:
    """A reconciler of order lines and orders over the test's own order and
    order line fakes, see the module docstring."""
    lock_log: LockLog = []
    nothing = EmptyRows(None, lock_log)
    repositories = LifecycleRepositories(
        lots=EmptyRows(LifecycleAggregate.LOTS, lock_log),
        production_orders=EmptyRows(LifecycleAggregate.PRODUCTION_ORDERS, lock_log),
        orders=ReconcilerOrders(orders, lock_log),
        order_items=ReconcilerOrderItems(order_items, lock_log),
        bought_demands=EmptyRows(LifecycleAggregate.BOUGHT_DEMANDS, lock_log),
        bought_allocations=nothing,
        made_demands=EmptyRows(LifecycleAggregate.MADE_DEMANDS, lock_log),
        made_allocations=nothing,
        source_demands=EmptyRows(LifecycleAggregate.SOURCE_DEMANDS, lock_log),
        source_allocations=nothing,
        quote_requests=EmptyRows(LifecycleAggregate.QUOTE_REQUESTS, lock_log),
    )
    recording = bus if bus is not None else RecordingBus()
    reconciler = LifecycleReconciler(
        repositories,
        recording,
        aggregates=ORDER_AGGREGATES,
        lock_plan=LockPlan(repositories),
    )
    return OrderReconciler(reconciler=reconciler, bus=recording, lock_log=lock_log)


def order_reconciler(
    orders: Any, order_items: Any, *, bus: Any | None = None
) -> LifecycleReconciler:
    """The reconciler of order_reconciler_harness alone."""
    return order_reconciler_harness(orders, order_items, bus=bus).reconciler
