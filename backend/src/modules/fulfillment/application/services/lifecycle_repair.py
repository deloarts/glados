"""
LifecycleRepair writes what the lifecycle drift report lists: every stored
status, kind, completed count and stamp that differs from its derivation.
Fact anomalies, a position with more completed pieces than its quantity and
a line whose delivery totals differ from its delivery rows, are listed for a
manual step and left alone, because only the facts can be wrong there.

It walks the drift report's pages and compares them with the report's own
comparison (`LifecycleDriftReport.pages` and `compare_page`), so a dry run
lists exactly the drift report's rows. With `apply`, each page that has
anything to write is repaired in a transaction of its own: a fresh lock plan
and reconciler touch only the rows that differ, lock them in the one lock
order, read them again under the locks, and let the reconciler write the
derivation through its apply functions, one changelog line per field closed
by "lifecycle repair", before the page commits. A page with nothing to write
takes no lock. A page that loses a race (a lock timeout, a deadlock, a stale
version) is rolled back, read again and retried, at most three times; pages
committed before stay committed, and a second run finds nothing left,
because the repair only ever writes derived values.

The repair publishes no events. Its changes put drifted rows in order and are
no news to anyone: the status events would mail "fulfilled" for demands that
were fulfilled long ago, print completion labels and call webhooks. Lot
timeline rows are written as for any status change.
"""

from collections import defaultdict
from collections.abc import Callable
from collections.abc import Collection
from collections.abc import Iterable
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from enum import Enum
from enum import unique
from uuid import UUID

from src.modules.fulfillment.application.services.lifecycle_drift import LIFECYCLE_DRIFT_AGGREGATES
from src.modules.fulfillment.application.services.lifecycle_drift import DriftPage
from src.modules.fulfillment.application.services.lifecycle_drift import DriftRow
from src.modules.fulfillment.application.services.lifecycle_drift import LifecycleDriftReport
from src.modules.fulfillment.application.services.lifecycle_drift import compare_page
from src.modules.fulfillment.application.services.lifecycle_loader import LifecycleRepositories
from src.modules.fulfillment.application.services.lifecycle_lock_plan import LockPlan
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.domain.services.lifecycle.snapshot import LifecycleSnapshot
from src.modules.fulfillment.domain.services.lifecycle.stored import FieldChange
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.platform.domain.entities.user import User
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.shared_kernel.domain.events.base import DomainEvent
from src.shared_kernel.domain.services.clock import now_utc

_A = LifecycleAggregate

REPAIR_REASON = "lifecycle repair"
_ATTEMPTS = 3


@unique
class RepairAction(str, Enum):
    """What a repair row does: a stored field set to its derivation, or a
    fact anomaly left for a manual step."""

    DERIVED = "derived"
    MANUAL = "manual"


@dataclass(frozen=True)
class RepairRow:
    """One row of the repair's output. `stored` is the value before and
    `repaired` the value after the repair; a manual row keeps the drift
    report's derived value there."""

    action: RepairAction
    table: str
    id: int
    public_id: UUID | None
    field: str
    stored: str
    repaired: str
    rule: str


@dataclass
class RepairReport:
    """The rows the repair planned (dry run) or wrote and listed for a manual
    step (apply), and after an apply what the drift report still lists."""

    applied: bool
    rows: list[RepairRow] = field(default_factory=list)
    left: list[DriftRow] = field(default_factory=list)

    @property
    def needs_attention(self) -> bool:
        """True when a dry run found anything to do, or when rows differ from
        their derivation after an apply, the manual ones included."""
        return bool(self.left) if self.applied else bool(self.rows)


class _DroppedEvents:
    """An event bus that publishes nothing; see the module docstring."""

    async def publish(self, event: DomainEvent) -> None:
        return None


@dataclass
class _PageCollector:
    """Collects a page's differing fields and anomalies, see DriftCollector."""

    chosen: frozenset[LifecycleAggregate]
    changes: list[FieldChange] = field(default_factory=list)
    anomalies: list[DriftRow] = field(default_factory=list)

    def add(
        self,
        aggregate: LifecycleAggregate,
        public_id: UUID,
        changes: list[FieldChange],
        facts: object,
    ) -> None:
        self.changes.extend(changes)

    def anomaly(self, row: DriftRow) -> None:
        self.anomalies.append(row)


@dataclass(frozen=True)
class _PagePlan:
    changes: list[FieldChange]
    anomalies: list[DriftRow]

    @property
    def has_writes(self) -> bool:
        return bool(self.changes)

    def targets(self) -> dict[LifecycleAggregate, set[int]]:
        """The rows to touch: every row with a differing field."""
        targets: defaultdict[LifecycleAggregate, set[int]] = defaultdict(set)
        for change in self.changes:
            targets[change.aggregate].add(change.id)
        return targets


class LifecycleRepair:
    """Plans or applies the repair page by page; see the module docstring.
    `retryable` tells a lost race from a failure."""

    def __init__(
        self,
        repositories: LifecycleRepositories,
        uow: IUnitOfWork,
        *,
        batch_size: int,
        retryable: Callable[[Exception], bool] = lambda _: False,
    ) -> None:
        self._repos = repositories
        self._uow = uow
        self._batch_size = batch_size
        self._retryable = retryable

    def _report(self) -> LifecycleDriftReport:
        return LifecycleDriftReport(self._repos, batch_size=self._batch_size)

    async def plan(
        self, aggregates: Collection[LifecycleAggregate] = LIFECYCLE_DRIFT_AGGREGATES
    ) -> RepairReport:
        """What the repair would write and what it would leave for a manual
        step. Writes nothing."""
        chosen = frozenset(aggregates)
        report = RepairReport(applied=False)
        now = now_utc()
        async for page in self._report().pages(chosen):
            plan = _plan_page(page, chosen, now)
            report.rows += _change_rows(plan.changes, _public_ids(page.snapshot))
            report.rows += [_manual_row(row) for row in plan.anomalies]
        return report

    async def apply(
        self,
        actor: User,
        aggregates: Collection[LifecycleAggregate] = LIFECYCLE_DRIFT_AGGREGATES,
    ) -> RepairReport:
        """Repairs page by page as `actor`, then lists what the drift report
        still finds. Raises what a page raised once its attempts are spent."""
        chosen = frozenset(aggregates)
        report = RepairReport(applied=True)
        drift = self._report()
        async for page in drift.pages(chosen):
            report.rows += await self._repair_page(drift, page, chosen, actor)
        report.left = (await drift.run(chosen)).rows
        log.info(
            f"Lifecycle repair wrote {len(report.rows)} change(s); "
            f"{len(report.left)} row(s) still differ."
        )
        return report

    async def _repair_page(
        self,
        drift: LifecycleDriftReport,
        page: DriftPage,
        chosen: frozenset[LifecycleAggregate],
        actor: User,
    ) -> list[RepairRow]:
        attempt = 1
        while True:
            now = now_utc()
            plan = _plan_page(page, chosen, now)
            if not plan.has_writes:
                return []
            try:
                rows = await self._apply_page(page, plan, actor, now)
                await self._uow.commit()
                return rows
            except Exception as exc:
                await self._uow.rollback()
                if attempt >= _ATTEMPTS or not self._retryable(exc):
                    raise
                log.warning(
                    f"Lifecycle repair retries a {page.aggregate.value} page after "
                    f"{type(exc).__name__} (attempt {attempt} of {_ATTEMPTS})."
                )
                attempt += 1
                page = await drift.load_page(page.aggregate, page.ids, chosen)

    async def _apply_page(
        self, page: DriftPage, plan: _PagePlan, actor: User, now: datetime
    ) -> list[RepairRow]:
        reconciler = LifecycleReconciler(
            self._repos, _DroppedEvents(), lock_plan=LockPlan(self._repos)
        )
        targets = plan.targets()
        for aggregate, ids in targets.items():
            _touch(reconciler, aggregate, ids)
        await reconciler.lock_touched()
        result = await reconciler.run(actor, now, reason=REPAIR_REASON)
        return _change_rows(result.changes, _public_ids(page.snapshot))


# ── Planning ─────────────────────────────────────────────────────────


def _plan_page(page: DriftPage, chosen: frozenset[LifecycleAggregate], now: datetime) -> _PagePlan:
    """The page's differing fields and fact anomalies."""
    collector = _PageCollector(chosen)
    compare_page(collector, page, now)
    return _PagePlan(collector.changes, collector.anomalies)


def _touch(
    reconciler: LifecycleReconciler, aggregate: LifecycleAggregate, ids: Iterable[int]
) -> None:
    if aggregate is _A.LOTS:
        reconciler.touch_lots(ids)
    elif aggregate is _A.LOT_POSITIONS:
        reconciler.touch_positions(ids)
    elif aggregate is _A.PRODUCTION_ORDERS:
        reconciler.touch_production_orders(ids)
    elif aggregate is _A.ORDERS:
        reconciler.touch_orders(ids)
    elif aggregate is _A.ORDER_ITEMS:
        reconciler.touch_order_items(ids)
    elif aggregate is _A.QUOTE_REQUESTS:
        reconciler.touch_quote_requests(ids)
    else:
        reconciler.touch_demands(aggregate, ids)


# ── Output rows ──────────────────────────────────────────────────────


def _public_ids(snapshot: LifecycleSnapshot) -> dict[tuple[LifecycleAggregate, int], UUID]:
    ids: dict[tuple[LifecycleAggregate, int], UUID] = {}
    for aggregate, rows in (
        (_A.LOTS, snapshot.lots.values()),
        (_A.LOT_POSITIONS, snapshot.positions().values()),
        (_A.PRODUCTION_ORDERS, snapshot.production_orders.values()),
        (_A.ORDERS, snapshot.orders.values()),
        (_A.ORDER_ITEMS, snapshot.order_items.values()),
        (_A.BOUGHT_DEMANDS, snapshot.bought_demands.values()),
        (_A.MADE_DEMANDS, snapshot.made_demands.values()),
        (_A.SOURCE_DEMANDS, snapshot.source_demands.values()),
        (_A.QUOTE_REQUESTS, snapshot.quote_requests.values()),
    ):
        ids.update(((aggregate, row.id), row.public_id) for row in rows)
    return ids


def _value_text(change: FieldChange) -> str:
    if isinstance(change.value, datetime):
        return change.value.isoformat(timespec="seconds")
    return change.new


def _change_rows(
    changes: Iterable[FieldChange], public_ids: Mapping[tuple[LifecycleAggregate, int], UUID]
) -> list[RepairRow]:
    return [
        RepairRow(
            action=RepairAction.DERIVED,
            table=c.aggregate.value,
            id=c.id,
            public_id=public_ids.get((c.aggregate, c.id)),
            field=c.field.value,
            stored=c.old,
            repaired=_value_text(c),
            rule=c.rule,
        )
        for c in changes
    ]


def _manual_row(row: DriftRow) -> RepairRow:
    return RepairRow(
        action=RepairAction.MANUAL,
        table=row.table,
        id=row.id,
        public_id=row.public_id,
        field=row.field,
        stored=row.stored,
        repaired=row.derived,
        rule=row.rule,
    )
