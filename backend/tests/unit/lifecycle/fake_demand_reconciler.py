"""
A lifecycle reconciler over the demand, allocation, order line and lot fakes
of a unit test. Demand use case tests keep their own fakes, which offer
get_by_id and save for demands and get_by_demand_item_id (and, where the
test has them, get_by_order_item_id or get_by_lot_id) for allocations. This
module wraps them into the repositories the reconciler reads, locks and
writes, gives every aggregate the test has no fake for an empty stand-in,
and switches the reconciler on for every aggregate, as the app does, so a
test of a demand use case sees the statuses the derivation gives.

The reconciler publishes on a bus of its own unless the test passes one, so
the events a test counts on the use case's bus stay those of the use case.
"""

from dataclasses import dataclass
from dataclasses import field
from typing import Any

from src.modules.fulfillment.application.services.lifecycle_loader import LifecycleRepositories
from src.modules.fulfillment.application.services.lifecycle_lock_plan import LockPlan
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from tests.unit.lifecycle.fake_reconciler import EmptyRows
from tests.unit.lifecycle.fake_reconciler import LockLog
from tests.unit.lifecycle.fake_reconciler import ReconcilerOrderItems
from tests.unit.lifecycle.fake_reconciler import ReconcilerOrders
from tests.unit.lifecycle.fake_reconciler import RecordingBus


class ReconcilerDemands:
    """A test's demand fake of one family as the reconciler's demand
    repository."""

    def __init__(self, fake: Any, aggregate: LifecycleAggregate, lock_log: LockLog) -> None:
        self._fake = fake
        self._aggregate = aggregate
        self._lock_log = lock_log

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[Any]:
        found = [await self._fake.get_by_id(i) for i in ids]
        return [demand for demand in found if demand is not None]

    async def lock_for_update(self, ids: list[int]) -> None:
        self._lock_log.append((self._aggregate, tuple(ids)))

    async def get_ids_after(self, after_id: int, limit: int) -> list[int]:
        return []

    async def save(self, demand: Any) -> Any:
        return await self._fake.save(demand)


class ReconcilerAllocations:
    """A test's allocation fake of one family as the reconciler's batch
    reads; a read the fake cannot answer finds nothing."""

    def __init__(self, fake: Any) -> None:
        self._fake = fake

    async def _each(self, method: str, ids: list[int]) -> list[Any]:
        read = getattr(self._fake, method, None)
        if read is None:
            return []
        rows: list[Any] = []
        for row_id in ids:
            rows.extend(await read(row_id))
        return rows

    async def get_by_demand_item_ids(
        self, demand_item_ids: list[int], *, refresh: bool = False
    ) -> list[Any]:
        return await self._each("get_by_demand_item_id", demand_item_ids)

    async def get_by_order_item_ids(
        self, order_item_ids: list[int], *, refresh: bool = False
    ) -> list[Any]:
        return await self._each("get_by_order_item_id", order_item_ids)

    async def get_by_lot_ids(self, lot_ids: list[int], *, refresh: bool = False) -> list[Any]:
        return await self._each("get_by_lot_id", lot_ids)


class _OrderItemsWithoutOrders(ReconcilerOrderItems):
    """Order lines of a test without an order fake: lines of an order are
    read one by one only."""

    async def get_by_order_ids(self, order_ids: list[int], *, refresh: bool = False) -> list[Any]:
        if getattr(self._fake, "get_by_order_id", None) is None:
            return []
        return await super().get_by_order_ids(order_ids, refresh=refresh)


@dataclass
class DemandReconciler:
    """The reconciler of a test with what it locked and published."""

    reconciler: LifecycleReconciler
    bus: Any
    lock_log: LockLog = field(default_factory=list)


def demand_reconciler_harness(
    *,
    bought_demands: Any = None,
    bought_allocations: Any = None,
    made_demands: Any = None,
    made_allocations: Any = None,
    source_demands: Any = None,
    source_allocations: Any = None,
    order_items: Any = None,
    orders: Any = None,
    lots: Any = None,
    production_orders: Any = None,
    quote_requests: Any = None,
    bus: Any = None,
) -> DemandReconciler:
    """A reconciler of every aggregate over the given fakes, see the module
    docstring. `lots` and `production_orders` are fakes that serve the
    reconciler's lot and production order reads, such as the production
    order tests' FakeProductionLotRepository and
    FakeProductionOrderRepository; a lot's completed count derives from its
    production orders. `quote_requests` serves the reconciler's quote request
    reads and locks."""
    lock_log: LockLog = []
    nothing = EmptyRows(None, lock_log)

    def demands(fake: Any, aggregate: LifecycleAggregate) -> Any:
        if fake is None:
            return EmptyRows(aggregate, lock_log)
        return ReconcilerDemands(fake, aggregate, lock_log)

    def allocations(fake: Any) -> Any:
        return nothing if fake is None else ReconcilerAllocations(fake)

    repositories = LifecycleRepositories(
        lots=lots if lots is not None else EmptyRows(LifecycleAggregate.LOTS, lock_log),
        production_orders=(
            production_orders
            if production_orders is not None
            else EmptyRows(LifecycleAggregate.PRODUCTION_ORDERS, lock_log)
        ),
        orders=(
            ReconcilerOrders(orders, lock_log)
            if orders is not None
            else EmptyRows(LifecycleAggregate.ORDERS, lock_log)
        ),
        order_items=(
            _OrderItemsWithoutOrders(order_items, lock_log)
            if order_items is not None
            else EmptyRows(LifecycleAggregate.ORDER_ITEMS, lock_log)
        ),
        bought_demands=demands(bought_demands, LifecycleAggregate.BOUGHT_DEMANDS),
        bought_allocations=allocations(bought_allocations),
        made_demands=demands(made_demands, LifecycleAggregate.MADE_DEMANDS),
        made_allocations=allocations(made_allocations),
        source_demands=demands(source_demands, LifecycleAggregate.SOURCE_DEMANDS),
        source_allocations=allocations(source_allocations),
        quote_requests=(
            quote_requests
            if quote_requests is not None
            else EmptyRows(LifecycleAggregate.QUOTE_REQUESTS, lock_log)
        ),
    )
    recording = bus if bus is not None else RecordingBus()
    reconciler = LifecycleReconciler(repositories, recording, lock_plan=LockPlan(repositories))
    return DemandReconciler(reconciler=reconciler, bus=recording, lock_log=lock_log)


def demand_reconciler(**fakes: Any) -> LifecycleReconciler:
    """The reconciler of demand_reconciler_harness alone."""
    return demand_reconciler_harness(**fakes).reconciler
