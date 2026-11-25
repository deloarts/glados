"""
LockPlan takes the row locks of the lifecycle aggregates in the one lock
order every writer follows: lots, production orders, orders, order items,
bought demands, made demands, source demands, quote requests, and ascending
ids within each. Quote requests come last because the reconciler reaches a
request from the order lines its award created, so it locks the request
after everything a change to those lines locks; a quote request writer
that takes nothing else locks it first and still keeps the order.
Two transactions that lock in this order wait for each other instead of
deadlocking. A lot's lock also covers its positions, which have no lock of
their own.

There is one plan per request (get_lifecycle_lock_plan), shared by the use
case and its lifecycle reconciler, so the plan knows every lock the
transaction took through it. A lock already held is not taken again. A row
that sorts before a row the plan has already locked is refused with
LockOrderError, because taking it now would invert the order: it is a
programming error, and a use case avoids it by locking everything its intent
needs in one acquisition before it reads what it checks, the reconciler's
targets included (LifecycleReconciler.lock_touched).

The locks end with the transaction. A use case that commits and then goes
on in a new transaction of the same request tells the plan so
(transaction_ended) before it locks again.

A row the transaction inserted itself needs no lock and takes no part in the
order: until the commit no other transaction sees it, so none can lock it or
wait for its lock. record_created marks such rows as held without locking
them and without the order check, and they never count against a later
acquisition either. A use case records every row it inserts, through the
reconciler's `touch_*(..., created=True)` or directly, so a line it adds
after locking its order and demands is not refused.

A number (order, lot, production order, part or document number) is drawn
only after every lock the transaction takes through the plan, because the
counter row it draws from (persistence/number_counters.py) is a lock outside
this order: a transaction that held a counter while waiting for a lifecycle
row could close a cycle with one that holds the row and then draws. The
project's time budget lock (time_budget_propagation.py) is such a lock as
well and is taken after the reconciler's run, for the same reason.

The one exception to the order is acquire_late. When the reconciler reads
again under its locks and finds a target that a concurrent transaction added
after its first reading, that target can only be locked late, possibly out of
order; two transactions that then wait on each other are resolved by
Postgres, which aborts one of them with a deadlock error; the server runs a
request that committed nothing once more (LostRaceRetryMiddleware), and one
that loses again answers a retryable 503. The material follow-up of the
reconciler's run (lot_material_followup.py) takes it too, for a lot's raw
material demand and its lines that its lock step could not lock in order.
"""

from collections.abc import Awaitable
from collections.abc import Callable

from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_loader import LifecycleRepositories
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate

LOCK_ORDER: tuple[LifecycleAggregate, ...] = (
    LifecycleAggregate.LOTS,
    LifecycleAggregate.PRODUCTION_ORDERS,
    LifecycleAggregate.ORDERS,
    LifecycleAggregate.ORDER_ITEMS,
    LifecycleAggregate.BOUGHT_DEMANDS,
    LifecycleAggregate.MADE_DEMANDS,
    LifecycleAggregate.SOURCE_DEMANDS,
    LifecycleAggregate.QUOTE_REQUESTS,
)


class LockOrderError(RuntimeError):
    """A lock requested after a row that sorts later in the lock order; see
    the module docstring."""


def _rank(aggregate: LifecycleAggregate, row_id: int) -> tuple[int, int]:
    return LOCK_ORDER.index(aggregate), row_id


class LockPlan:
    """The row locks one transaction holds on lifecycle aggregates."""

    def __init__(self, repositories: LifecycleRepositories) -> None:
        self._lockers: dict[LifecycleAggregate, Callable[[list[int]], Awaitable[None]]] = {
            LifecycleAggregate.LOTS: repositories.lots.lock_for_update,
            LifecycleAggregate.PRODUCTION_ORDERS: repositories.production_orders.lock_for_update,
            LifecycleAggregate.ORDERS: repositories.orders.lock_for_update,
            LifecycleAggregate.ORDER_ITEMS: repositories.order_items.lock_for_update,
            LifecycleAggregate.BOUGHT_DEMANDS: repositories.bought_demands.lock_for_update,
            LifecycleAggregate.MADE_DEMANDS: repositories.made_demands.lock_for_update,
            LifecycleAggregate.SOURCE_DEMANDS: repositories.source_demands.lock_for_update,
            LifecycleAggregate.QUOTE_REQUESTS: repositories.quote_requests.lock_for_update,
        }
        self._held: dict[LifecycleAggregate, frozenset[int]] = {}
        self._created: dict[LifecycleAggregate, frozenset[int]] = {}

    @property
    def held(self) -> AggregateIds:
        """The rows this plan has locked so far and the rows this transaction
        created, none of which is locked again."""
        return AggregateIds.of(self._held).union(AggregateIds.of(self._created))

    def record_created(self, ids: AggregateIds) -> None:
        """Marks rows this transaction inserted as held, without a lock and
        without the order check; see the module docstring."""
        for aggregate in LOCK_ORDER:
            rows = ids.get(aggregate)
            if rows:
                self._created[aggregate] = self._created.get(aggregate, frozenset()) | rows

    def transaction_ended(self) -> None:
        """Forgets what this plan held, because a commit or a rollback
        released the locks. A use case that goes on in a new transaction
        after its commit calls it before it locks again, or the plan would
        take rows as held that no lock protects any more."""
        self._held = {}
        self._created = {}

    def _new_rows(self, ids: AggregateIds) -> dict[LifecycleAggregate, list[int]]:
        """The lockable rows of `ids` not held yet, ascending per aggregate.
        Lot positions are locked through their lot, so their ids are left
        out."""
        new = {
            aggregate: sorted(
                ids.get(aggregate)
                - self._held.get(aggregate, frozenset())
                - self._created.get(aggregate, frozenset())
            )
            for aggregate in LOCK_ORDER
        }
        return {aggregate: rows for aggregate, rows in new.items() if rows}

    def in_order(self, ids: AggregateIds) -> bool:
        """Whether acquire could lock the rows of `ids` without a
        LockOrderError: none of those not held yet sorts before a row the
        plan has locked."""
        new = self._new_rows(ids)
        held = [_rank(a, row_id) for a, rows in self._held.items() for row_id in rows]
        if not new or not held:
            return True
        return min(_rank(a, rows[0]) for a, rows in new.items()) >= max(held)

    async def acquire(self, ids: AggregateIds) -> None:
        """Locks the rows of `ids` this plan does not hold yet, in the lock
        order. Raises LockOrderError when one of them sorts before a row the
        plan has locked; rows recorded as created do not count."""
        new = self._new_rows(ids)
        if not new:
            return
        if not self.in_order(ids):
            held = [_rank(a, row_id) for a, rows in self._held.items() for row_id in rows]
            first = min(_rank(a, rows[0]) for a, rows in new.items())
            raise LockOrderError(
                "A lifecycle lock was requested after a row that sorts later in the lock "
                f"order: {LOCK_ORDER[first[0]].value} #{first[1]} after "
                f"{LOCK_ORDER[max(held)[0]].value} #{max(held)[1]}. Lock what the intent "
                "needs, the reconciler's targets included, before reading what it checks."
            )
        await self._lock(new)

    async def acquire_late(self, ids: AggregateIds) -> None:
        """Locks rows that a concurrent transaction added to the reconciler's
        targets after its first reading, in the lock order among themselves
        even where they sort before rows already held. Only the reconciler's
        reading under its own locks and its material follow-up call it; see
        the module docstring."""
        new = self._new_rows(ids)
        if new:
            await self._lock(new)

    async def _lock(self, new: dict[LifecycleAggregate, list[int]]) -> None:
        for aggregate in LOCK_ORDER:
            rows = new.get(aggregate)
            if rows:
                await self._lockers[aggregate](rows)
                self._held[aggregate] = self._held.get(aggregate, frozenset()) | frozenset(rows)
