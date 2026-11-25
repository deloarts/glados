"""
LifecycleReconciler stores what the lifecycle derivation says. The protocol a
use case follows (touch, lock_touched, write facts and intents, run before its
own events and the commit) is docs/reference/lifecycle.md:

    reconciler.touch_order_items([line.id])
    await reconciler.lock_touched()
    ...  # read under the locks, check, write the facts
    result = await reconciler.run(actor, now)

The reconciler widens the touched rows only along the edges a derivation reads
(lifecycle_loader.py) and only inside RECONCILED_AGGREGATES, so a delivery on
one line of a shared order locks neither the other lines nor their lots. It
locks through the request's LockPlan, and when the read under the locks finds
a target the first read missed, it locks that one late and reads again. The
lock step also locks the neighbours of the demands among its targets, the
other demands on their lines and lots, because a use case may touch such a
demand once it has written its facts, and the run widens a touched demand to
its neighbours; a neighbour that sorts before a demand already held could
not be locked by then. Only
fields that differ from the derivation are written. The re-reads discard
unflushed changes because the session does not autoflush, so a use case
writes only through repositories, whose saves flush. A production order that
leaves COMPLETED or CANCELED first takes the next free place of its queue,
since it is live again for the queue_sequence unique indexes.

A quote request line keeps no state of its own that says its award was
voided: the award is void once the order line it created is canceled or
removed. So the lock step notes which lines of the quote requests it locks
hold a live award, and the run writes a changelog line on the request for
each of them it finds voided, also where the request's status stays, as on
a closed request.

A run can end with a material follow-up (lot_material_followup.py), which
the request's reconciler has and the repair job's has not. When the run
moved who does a lot's first position, the follow-up moves the lot's source
approval status and settles, resizes or creates its raw material demand,
and a second pass derives the demands it wrote. That demand and its lines
sort before rows a use case may hold by the end of its run, so the lock
step locks them with the use case's locks whenever the touched rows reach
a first position whose lot waits for material: the position, a line of it
or a production order of it. Where that would break the lock order, they
are left out, and the follow-up locks them late when it acts on them. The
second pass changes no position, so it never needs another follow-up.
"""

from collections.abc import Iterable
from collections.abc import Mapping
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from src.modules.fulfillment.application.services.lifecycle_effects import lifecycle_effects
from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_loader import LifecycleLoader
from src.modules.fulfillment.application.services.lifecycle_loader import LifecycleRepositories
from src.modules.fulfillment.application.services.lifecycle_lock_plan import LOCK_ORDER
from src.modules.fulfillment.application.services.lifecycle_lock_plan import LockPlan
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.services.lifecycle.quote_request import award_voided_note
from src.modules.fulfillment.domain.services.lifecycle.snapshot import LifecycleSnapshot
from src.modules.fulfillment.domain.services.lifecycle.snapshot import SnapshotDerivation
from src.modules.fulfillment.domain.services.lifecycle.snapshot import derive_snapshot
from src.modules.fulfillment.domain.services.lifecycle.stored import FieldChange
from src.modules.fulfillment.domain.services.lifecycle.stored import LifecycleField
from src.modules.fulfillment.domain.services.lifecycle.stored import apply_demand_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import apply_lot_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import apply_order_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import apply_order_item_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import apply_position_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import apply_production_order_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import apply_quote_request_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import apply_source_demand_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import demand_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import lot_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import order_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import order_item_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import position_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import production_order_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import quote_request_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import source_demand_changes
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import DEMAND_AGGREGATES
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LIFECYCLE_INPUTS
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.production_status import (
    TERMINAL_PRODUCTION_ORDER_STATUSES,
)
from src.modules.fulfillment.domain.value_objects.quote_request_status import QuoteRequestLineState
from src.modules.platform.domain.entities.user import User
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.shared_kernel.domain.services.changelog_service import append_changelog

_A = LifecycleAggregate

# The aggregates whose stored lifecycle fields the reconciler writes.
RECONCILED_AGGREGATES: frozenset[LifecycleAggregate] = frozenset(
    {
        _A.PRODUCTION_ORDERS,
        _A.ORDER_ITEMS,
        _A.ORDERS,
        _A.LOT_POSITIONS,
        _A.LOTS,
        _A.BOUGHT_DEMANDS,
        _A.MADE_DEMANDS,
        _A.SOURCE_DEMANDS,
        _A.QUOTE_REQUESTS,
    }
)

DEFAULT_REASON = "derived from recorded facts"

# Dependency order, so an aggregate is written after what it reads.
_WRITE_ORDER: tuple[LifecycleAggregate, ...] = (
    _A.ORDER_ITEMS,
    _A.PRODUCTION_ORDERS,
    _A.LOT_POSITIONS,
    _A.LOTS,
    _A.ORDERS,
    _A.BOUGHT_DEMANDS,
    _A.MADE_DEMANDS,
    _A.SOURCE_DEMANDS,
    _A.QUOTE_REQUESTS,
)

# Changes the production schedule reads.
_SCHEDULE_FIELDS = frozenset(
    {
        (_A.PRODUCTION_ORDERS, LifecycleField.STATUS),
        (_A.LOT_POSITIONS, LifecycleField.STATUS),
        (_A.LOT_POSITIONS, LifecycleField.KIND),
        (_A.LOTS, LifecycleField.STATUS),
    }
)


def assert_reconcilable(aggregates: Iterable[LifecycleAggregate]) -> None:
    """Raises ValueError unless every aggregate's derivation reads only
    aggregates of the same set, since the reconciler derives a written
    aggregate from inputs whose intents are kept."""
    enabled = frozenset(aggregates)
    for aggregate in enabled:
        missing = LIFECYCLE_INPUTS[aggregate] - enabled
        if missing:
            names = ", ".join(sorted(a.value for a in missing))
            raise ValueError(
                f"{aggregate.value} reads {names}, which the reconciler does not write."
            )


@dataclass(frozen=True)
class ReconcileResult:
    """The fields a run wrote."""

    changes: tuple[FieldChange, ...] = ()

    def changed_ids(self, aggregate: LifecycleAggregate) -> frozenset[int]:
        return frozenset(c.id for c in self.changes if c.aggregate is aggregate)

    def new_status(self, aggregate: LifecycleAggregate, row_id: int) -> str | None:
        """The status the run wrote for the row, None when it left it."""
        return next(
            (
                str(c.value)
                for c in self.changes
                if c.aggregate is aggregate and c.id == row_id and c.field is LifecycleField.STATUS
            ),
            None,
        )

    @property
    def schedule_relevant(self) -> bool:
        """True when a status or kind the production schedule reads changed.
        No use case reads it yet: each one that can move a date requests a
        schedule walk after its commit unconditionally, which costs one
        outbox row since the walk runs in the background."""
        return any((c.aggregate, c.field) in _SCHEDULE_FIELDS for c in self.changes)


@dataclass(frozen=True)
class FollowUpTouches:
    """The source demands a material follow-up changed or created and the
    order lines whose allocations it wrote, which the run derives in a
    second pass."""

    demands: frozenset[int] = frozenset()
    created: frozenset[int] = frozenset()
    lines: frozenset[int] = frozenset()

    def is_empty(self) -> bool:
        return not (self.demands or self.created or self.lines)


class MaterialFollowUp(Protocol):
    """What a run does to lots' raw material when it moves who does their
    first position; see the module docstring."""

    def lock_demands(self, snapshot: LifecycleSnapshot, touched: AggregateIds) -> frozenset[int]:
        """The raw material demands the lock step locks with the touched
        rows, from what it read."""
        ...

    async def apply(
        self,
        actor: User,
        now: datetime,
        *,
        changes: Sequence[FieldChange],
        snapshot: LifecycleSnapshot,
        derivation: SnapshotDerivation,
        touched: AggregateIds,
        lock_plan: LockPlan,
    ) -> FollowUpTouches:
        """Writes what the run's changes mean for the lots' material and
        returns the rows the second pass derives."""
        ...


# The aggregates a material follow-up reads or writes.
_MATERIAL_AGGREGATES = frozenset({_A.LOT_POSITIONS, _A.LOTS, _A.ORDER_ITEMS, _A.SOURCE_DEMANDS})


@dataclass(frozen=True)
class _Pass:
    """What one derivation pass of a run wrote, and the facts it read."""

    changes: list[FieldChange]
    snapshot: LifecycleSnapshot
    derivation: SnapshotDerivation


class _LoggedAt(Protocol):
    changed: datetime | None
    changes: list[str]


class _Writer:
    """Writes the changes of one run, aggregate by aggregate."""

    def __init__(
        self,
        repositories: LifecycleRepositories,
        snapshot: LifecycleSnapshot,
        derivation: SnapshotDerivation,
        actor: User,
        now: datetime,
        reason: str,
        live_awards: Mapping[int, frozenset[int]],
    ) -> None:
        self._repos = repositories
        self._snapshot = snapshot
        self._derivation = derivation
        self._actor = actor
        self._now = now
        self._reason = reason
        self._positions = snapshot.positions()
        self._live_awards = live_awards

    def _log_at(self, entity: _LoggedAt, changes: list[FieldChange]) -> None:
        for change in changes:
            entity.changes = append_changelog(
                entity.changes, self._actor.full_name, change.note(self._reason)
            )
        entity.changed = self._now

    async def write(self, aggregate: LifecycleAggregate, row_id: int) -> list[FieldChange]:
        if aggregate is _A.ORDER_ITEMS:
            return await self._order_item(row_id)
        if aggregate is _A.PRODUCTION_ORDERS:
            return await self._production_order(row_id)
        if aggregate is _A.LOT_POSITIONS:
            return await self._position(row_id)
        if aggregate is _A.LOTS:
            return await self._lot(row_id)
        if aggregate is _A.ORDERS:
            return await self._order(row_id)
        if aggregate is _A.SOURCE_DEMANDS:
            return await self._source_demand(row_id)
        if aggregate is _A.QUOTE_REQUESTS:
            return await self._quote_request(row_id)
        return await self._bought_or_made_demand(aggregate, row_id)

    async def _order_item(self, row_id: int) -> list[FieldChange]:
        item = self._snapshot.order_items.get(row_id)
        derived = self._derivation.order_items.get(row_id)
        if item is None or derived is None:
            return []
        changes = order_item_changes(item, derived)
        if changes:
            apply_order_item_changes(item, changes)
            self._log_at(item, changes)
            await self._repos.order_items.save(item)
        return changes

    async def _production_order(self, row_id: int) -> list[FieldChange]:
        order = self._snapshot.production_orders.get(row_id)
        derived = self._derivation.production_orders.get(row_id)
        if order is None or derived is None:
            return []
        changes = production_order_changes(order, derived, now=self._now)
        if changes:
            await self._free_queue_place_when_revived(order, changes)
            apply_production_order_changes(order, changes)
            self._log_at(order, changes)
            await self._repos.production_orders.save(order)
        return changes

    async def _free_queue_place_when_revived(
        self, order: ProductionOrder, changes: list[FieldChange]
    ) -> None:
        """Gives an order that leaves COMPLETED or CANCELED the next free
        place of its queue, under the queue's lock: its old place may belong
        to a live order by now, see the module docstring."""
        status = next((c for c in changes if c.field is LifecycleField.STATUS), None)
        # Terminal statuses sit outside the partial unique indexes on
        # production_order.queue_sequence.
        if status is None or status.old not in TERMINAL_PRODUCTION_ORDER_STATUSES:
            return
        if status.new in TERMINAL_PRODUCTION_ORDER_STATUSES:
            return
        orders = self._repos.production_orders
        await orders.lock_queue_scope(order.machine_id, order.machine_pool_id)
        order.queue_sequence = await orders.next_queue_sequence(
            order.machine_id, order.machine_pool_id
        )

    async def _position(self, row_id: int) -> list[FieldChange]:
        position = self._positions.get(row_id)
        derived = self._derivation.positions.get(row_id)
        if position is None or derived is None:
            return []
        changes = position_changes(position, derived)
        if changes:
            apply_position_changes(position, changes)
            self._log_at(position, changes)
            await self._repos.lots.save_position(position)
        return changes

    async def _lot(self, row_id: int) -> list[FieldChange]:
        lot = self._snapshot.lots.get(row_id)
        derived = self._derivation.lots.get(row_id)
        if lot is None or derived is None:
            return []
        changes = lot_changes(lot, derived, now=self._now)
        if changes:
            apply_lot_changes(lot, changes)
            self._log_at(lot, changes)
            await self._repos.lots.save(lot)
        return changes

    async def _order(self, row_id: int) -> list[FieldChange]:
        order = self._snapshot.orders.get(row_id)
        derived = self._derivation.orders.get(row_id)
        if order is None or derived is None:
            return []
        changes = order_changes(order, derived, now=self._now)
        if changes:
            apply_order_changes(order, changes)
            self._log_at(order, changes)
            await self._repos.orders.save(order)
        return changes

    async def _bought_or_made_demand(
        self, aggregate: LifecycleAggregate, row_id: int
    ) -> list[FieldChange]:
        if aggregate is _A.BOUGHT_DEMANDS:
            bought = self._snapshot.bought_demands.get(row_id)
            bought_derived = self._derivation.bought_demands.get(row_id)
            if bought is None or bought_derived is None:
                return []
            changes = demand_changes(aggregate, bought, bought_derived)
            if changes:
                apply_demand_changes(bought, changes)
                self._log_at(bought, changes)
                await self._repos.bought_demands.save(bought)
            return changes
        made = self._snapshot.made_demands.get(row_id)
        made_derived = self._derivation.made_demands.get(row_id)
        if made is None or made_derived is None:
            return []
        changes = demand_changes(aggregate, made, made_derived)
        if changes:
            apply_demand_changes(made, changes)
            self._log_at(made, changes)
            await self._repos.made_demands.save(made)
        return changes

    async def _source_demand(self, row_id: int) -> list[FieldChange]:
        demand = self._snapshot.source_demands.get(row_id)
        derived = self._derivation.source_demands.get(row_id)
        if demand is None or derived is None:
            return []
        changes = source_demand_changes(demand, derived)
        if changes:
            apply_source_demand_changes(demand, changes)
            self._log_at(demand, changes)
            await self._repos.source_demands.save(demand)
        return changes

    async def _quote_request(self, row_id: int) -> list[FieldChange]:
        request = self._snapshot.quote_requests.get(row_id)
        derived = self._derivation.quote_requests.get(row_id)
        if request is None or derived is None:
            return []
        changes = quote_request_changes(request, derived)
        live = self._live_awards.get(row_id, frozenset())
        voided = [line for line in request.lines if line.award_voided and line.id in live]
        for line in voided:
            request.changes = append_changelog(
                request.changes, self._actor.full_name, award_voided_note(request, line)
            )
        if changes:
            apply_quote_request_changes(request, changes)
            self._log_at(request, changes)
        if changes or voided:
            request.changed = self._now
            await self._repos.quote_requests.save(request)
        return changes


class LifecycleReconciler:
    """One per request or job; see the module docstring."""

    def __init__(
        self,
        repositories: LifecycleRepositories,
        bus: IEventBus,
        *,
        aggregates: Iterable[LifecycleAggregate] | None = None,
        lock_plan: LockPlan | None = None,
        material_followup: MaterialFollowUp | None = None,
    ) -> None:
        self._repositories = repositories
        self._bus = bus
        self._aggregates = frozenset(RECONCILED_AGGREGATES if aggregates is None else aggregates)
        assert_reconcilable(self._aggregates)
        if material_followup is not None and not self._aggregates >= _MATERIAL_AGGREGATES:
            raise ValueError("A material follow-up needs the positions, lots, lines and demands.")
        self._material = material_followup
        self._lock_plan = lock_plan or LockPlan(repositories)
        self._lockable = self._aggregates & frozenset(LOCK_ORDER)
        self._touched: dict[LifecycleAggregate, set[int]] = {}
        self._locked_targets = AggregateIds()
        self._allocated_on = AggregateIds()
        # The lines with a live award of each quote request the lock step
        # locked, by request id, read before the use case wrote its facts.
        self._live_awards: dict[int, frozenset[int]] = {}

    @property
    def aggregates(self) -> frozenset[LifecycleAggregate]:
        """The aggregates this reconciler writes."""
        return self._aggregates

    @property
    def lock_plan(self) -> LockPlan:
        """The lock plan this reconciler locks through, the request's one."""
        return self._lock_plan

    def transaction_ended(self) -> None:
        """Forgets what was touched and what the lock plan held, because a
        rollback discarded the writes and released the locks. A use case
        that repeats its write after a rollback, such as the numbering
        retry, calls it before it starts again."""
        self._touched = {}
        self._locked_targets = AggregateIds()
        self._allocated_on = AggregateIds()
        self._live_awards = {}
        self._lock_plan.transaction_ended()

    def _touch(self, aggregate: LifecycleAggregate, ids: Iterable[int], *, created: bool) -> None:
        """Registers rows of one aggregate. `created` marks rows this
        transaction inserted, which the lock plan holds without a lock; see
        the module docstring."""
        rows = set(ids)
        self._touched.setdefault(aggregate, set()).update(rows)
        if created:
            self._lock_plan.record_created(AggregateIds.of({aggregate: rows}))

    def touch_lots(self, ids: Iterable[int], *, created: bool = False) -> None:
        self._touch(_A.LOTS, ids, created=created)

    def touch_positions(self, ids: Iterable[int], *, created: bool = False) -> None:
        self._touch(_A.LOT_POSITIONS, ids, created=created)

    def touch_production_orders(self, ids: Iterable[int], *, created: bool = False) -> None:
        self._touch(_A.PRODUCTION_ORDERS, ids, created=created)

    def touch_orders(self, ids: Iterable[int], *, created: bool = False) -> None:
        self._touch(_A.ORDERS, ids, created=created)

    def touch_order_items(self, ids: Iterable[int], *, created: bool = False) -> None:
        self._touch(_A.ORDER_ITEMS, ids, created=created)

    def touch_quote_requests(self, ids: Iterable[int], *, created: bool = False) -> None:
        """Registers quote requests whose lines a use case wrote, or whose
        lines go away with the lot positions they name."""
        self._touch(_A.QUOTE_REQUESTS, ids, created=created)

    def touch_allocations_on(
        self, *, order_item_ids: Iterable[int] = (), lot_ids: Iterable[int] = ()
    ) -> None:
        """Registers order lines and lots whose allocations a use case
        writes, so every demand allocated on them is a target: an allocation
        written on a line or lot moves the pieces that reach the demands
        behind it in the fill order. The lines and lots are not targets
        themselves."""
        self._allocated_on = self._allocated_on.union(
            AggregateIds.of(
                {LifecycleAggregate.ORDER_ITEMS: order_item_ids, LifecycleAggregate.LOTS: lot_ids}
            )
        )

    def touch_demands(
        self, family: LifecycleAggregate, ids: Iterable[int], *, created: bool = False
    ) -> None:
        """Registers demands of one family: bought, made or source demands."""
        if family not in DEMAND_AGGREGATES:
            raise ValueError(f"{family.value} is not a demand family.")
        self._touch(family, ids, created=created)

    async def lock_touched(self, *, also: AggregateIds | None = None) -> None:
        """Locks the targets of what has been touched so far that this
        reconciler writes, together with `also`, rows the use case needs
        locked besides, and the neighbours of every demand among them, in
        one acquisition in the lock order. It reads the targets again under
        those locks and locks late what a concurrent change added, so
        everything the use case then reads is locked, and a demand it
        touches afterwards widens to nothing unlocked. A use case calls it
        before it reads what it checks; see the module docstring."""
        touched = AggregateIds.of(self._touched)
        also = also or AggregateIds()
        if not self._aggregates or (
            touched.is_empty()
            and self._allocated_on.is_empty()
            and also.restricted_to(DEMAND_AGGREGATES).is_empty()
        ):
            await self._lock_plan.acquire(also)
            return
        _, targets = await self._lock_targets(touched, also=also, allocated_on=self._allocated_on)
        # What was locked as a target stays one, so the run derives it even
        # where the edge that led to it is gone by then, as when the use case
        # deletes the allocation that tied a demand to the others on its line.
        # It is derived, not widened from again.
        self._locked_targets = self._locked_targets.union(targets)
        await self._note_live_awards(targets.get(_A.QUOTE_REQUESTS))

    async def _note_live_awards(self, request_ids: Iterable[int]) -> None:
        """Notes the lines with a live award of quote requests first locked
        in this transaction, read under their locks before the use case
        writes, so the run can tell an award its write voided; see the
        module docstring."""
        missing = sorted(set(request_ids) - self._live_awards.keys())
        if not missing:
            return
        for request in await self._repositories.quote_requests.get_by_ids(missing, refresh=True):
            self._live_awards[request.id] = frozenset(
                line.id for line in request.lines if line.state is QuoteRequestLineState.AWARDED
            )

    async def run(
        self, actor: User, now: datetime, *, reason: str = DEFAULT_REASON
    ) -> ReconcileResult:
        """Recomputes the targets of everything touched since the last run,
        writes what differs and publishes the events, followed by the
        material follow-up and its second pass; see the module docstring.
        `reason` closes every changelog line it writes."""
        touched = AggregateIds.of(self._touched)
        kept = self._locked_targets
        live_awards = self._live_awards
        allocated_on = self._allocated_on
        self._touched = {}
        self._locked_targets = AggregateIds()
        self._live_awards = {}
        self._allocated_on = AggregateIds()
        if not self._aggregates or touched.is_empty():
            return ReconcileResult()
        first = await self._pass(
            actor,
            now,
            reason,
            touched,
            kept=kept,
            allocated_on=allocated_on,
            live_awards=live_awards,
        )
        if first is None:
            return ReconcileResult()
        changes = list(first.changes)
        if self._material is not None:
            follow = await self._material.apply(
                actor,
                now,
                changes=first.changes,
                snapshot=first.snapshot,
                derivation=first.derivation,
                touched=touched,
                lock_plan=self._lock_plan,
            )
            if not follow.is_empty():
                self._lock_plan.record_created(AggregateIds.of({_A.SOURCE_DEMANDS: follow.created}))
                second = await self._pass(
                    actor,
                    now,
                    reason,
                    AggregateIds.of({_A.SOURCE_DEMANDS: follow.demands | follow.created}),
                    allocated_on=AggregateIds.of({_A.ORDER_ITEMS: follow.lines}),
                    late=True,
                )
                if second is not None:
                    changes += second.changes
        return ReconcileResult(tuple(changes))

    async def _pass(
        self,
        actor: User,
        now: datetime,
        reason: str,
        touched: AggregateIds,
        *,
        kept: AggregateIds | None = None,
        allocated_on: AggregateIds | None = None,
        live_awards: Mapping[int, frozenset[int]] | None = None,
        late: bool = False,
    ) -> _Pass | None:
        """Locks and derives the targets of `touched`, together with `kept`,
        writes what differs and publishes the events. None when nothing was
        a target. `late` locks what is not held yet late, as the follow-up's
        second pass does."""
        loader, targets = await self._lock_targets(touched, allocated_on=allocated_on, late=late)
        if kept is not None:
            targets = targets.union(kept.restricted_to(self._aggregates))
        if targets.is_empty():
            return None
        snapshot = await loader.load_facts(targets)
        derivation = derive_snapshot(snapshot)
        writer = _Writer(
            self._repositories, snapshot, derivation, actor, now, reason, live_awards or {}
        )
        changes: list[FieldChange] = []
        for aggregate in _WRITE_ORDER:
            for row_id in sorted(targets.get(aggregate)):
                changes += await writer.write(aggregate, row_id)
        effects = lifecycle_effects(
            changes, snapshot, actor, touched_order_items=touched.get(_A.ORDER_ITEMS)
        )
        for event in effects.events:
            await self._bus.publish(event)
        for lot_event in effects.lot_events:
            await self._repositories.lots.record_event(lot_event)
        return _Pass(changes, snapshot, derivation)

    async def _lock_targets(
        self,
        touched: AggregateIds,
        *,
        also: AggregateIds | None = None,
        allocated_on: AggregateIds | None = None,
        late: bool = False,
    ) -> tuple[LifecycleLoader, AggregateIds]:
        """Widens the touched set, locks the targets this reconciler writes
        and widens again until a reading under the locks finds nothing new
        to lock. The first acquisition keeps the lock order with what the
        plan holds, unless `late`; later ones lock what a concurrent change
        added. Returns the loader of the last reading and the targets of the
        written aggregates.

        With `also`, the lock step of lock_touched, it locks `also` and the
        neighbours of every demand among the targets and in `also` besides,
        without making them targets: the use case may touch such a demand
        once it has written its facts, as a line cancel touches the demands
        it deallocates, and the run then widens it to those neighbours. A
        neighbour that sorts before a demand already held could not be
        locked by then. The lock step also locks the raw material demands
        the material follow-up may act on, with their lines and neighbours,
        where the lock order allows it; see the module docstring."""
        first = True
        material_in_order = True
        while True:
            loader = LifecycleLoader(self._repositories, refresh=True)
            targets = await loader.widen(
                touched, within=self._aggregates, allocated_on=allocated_on
            )
            to_lock = targets.restricted_to(self._lockable)
            if also is not None:
                demands = targets.union(also).restricted_to(DEMAND_AGGREGATES)
                neighbours = await loader.neighbours(demands, within=self._aggregates)
                to_lock = to_lock.union(also).union(neighbours.restricted_to(self._lockable))
                if material_in_order:
                    material = await self._material_locks(loader, touched)
                    if first and not self._lock_plan.in_order(to_lock.union(material)):
                        material_in_order = False
                    else:
                        to_lock = to_lock.union(material)
            if to_lock.issubset(self._lock_plan.held):
                return loader, targets
            if first and not late:
                await self._lock_plan.acquire(to_lock)
            else:
                await self._lock_plan.acquire_late(to_lock)
            first = False

    async def _material_locks(self, loader: LifecycleLoader, touched: AggregateIds) -> AggregateIds:
        """The raw material demands the follow-up may act on, from what the
        loader read, with the lines they are allocated on and their
        neighbours."""
        if self._material is None:
            return AggregateIds()
        demand_ids = self._material.lock_demands(loader.snapshot(), touched)
        if not demand_ids:
            return AggregateIds()
        demands = AggregateIds.of({_A.SOURCE_DEMANDS: demand_ids})
        neighbours = await loader.neighbours(demands, within=self._aggregates)
        lines = AggregateIds.of({_A.ORDER_ITEMS: await loader.source_lines_of(demand_ids)})
        return demands.union(neighbours).union(lines).restricted_to(self._lockable)
