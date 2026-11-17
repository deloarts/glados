"""
LifecycleDriftReport compares the stored lifecycle fields of every lot, lot
position, production order, order, order item, demand and quote request with
their derivation from the recorded facts and intents, and lists each field that
differs. It reads through LifecycleLoader, the reconciler's reader, and
compares through lifecycle/stored.py, the reconciler's comparison, so a field
it lists is exactly a field the reconciler would write once the aggregate is
reconciled. It never writes.

The tables are walked in keyset pages of ids: lots, together with their
positions and the positions' production orders; orders, together with their
lines; the demands of each family; and quote requests. A position whose facts give it more
completed pieces than its quantity is listed as well, as a fact anomaly: its
stored count is held at the quantity, so only the facts can be wrong there.
So is an order line whose stored delivery totals differ from the sums over
its delivery rows (lifecycle/delivery_totals.py), when the repositories
include the deliveries.

The full report also lists every part number a made or bought item carries
whose registry entry is missing or names the other catalogue
(add_part_number_registry_anomalies), as a fact anomaly: the registry is the
uniqueness ledger of part numbers, and only the facts can settle a number
held without its entry.

The lifecycle repair (lifecycle_repair.py) walks the same pages and compares
them the same way, through `pages`, `load_page` and `compare_page`, with a
collector of its own, so the repair writes exactly what the report lists.
"""

import dataclasses
from collections.abc import AsyncIterator
from collections.abc import Awaitable
from collections.abc import Callable
from collections.abc import Collection
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from enum import Enum
from typing import Protocol
from uuid import UUID

from src.modules.catalogue.ports.outbound.catalogue_queries import IPartNumberRegistryQueries
from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.lifecycle_loader import LifecycleLoader
from src.modules.fulfillment.application.services.lifecycle_loader import LifecycleRepositories
from src.modules.fulfillment.domain.services.lifecycle.delivery_totals import DELIVERY_TOTALS_RULE
from src.modules.fulfillment.domain.services.lifecycle.delivery_totals import DeliveryTotals
from src.modules.fulfillment.domain.services.lifecycle.delivery_totals import (
    delivery_totals_differences,
)
from src.modules.fulfillment.domain.services.lifecycle.delivery_totals import stored_totals
from src.modules.fulfillment.domain.services.lifecycle.snapshot import LifecycleSnapshot
from src.modules.fulfillment.domain.services.lifecycle.snapshot import SnapshotDerivation
from src.modules.fulfillment.domain.services.lifecycle.snapshot import derive_snapshot
from src.modules.fulfillment.domain.services.lifecycle.stored import COMPLETED_OVER_QUANTITY_RULE
from src.modules.fulfillment.domain.services.lifecycle.stored import FieldChange
from src.modules.fulfillment.domain.services.lifecycle.stored import LifecycleField
from src.modules.fulfillment.domain.services.lifecycle.stored import completed_over_quantity
from src.modules.fulfillment.domain.services.lifecycle.stored import demand_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import lot_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import order_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import order_item_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import position_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import production_order_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import quote_request_changes
from src.modules.fulfillment.domain.services.lifecycle.stored import source_demand_changes
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.shared_kernel.domain.services.clock import now_utc

_A = LifecycleAggregate
_BATCH_SIZE = 500

LIFECYCLE_DRIFT_AGGREGATES: tuple[LifecycleAggregate, ...] = tuple(LifecycleAggregate)

PART_NUMBER_REGISTRY_TABLE = "part_number_registry"
PART_NUMBER_REGISTRY_RULE = (
    "fact anomaly: a part number an item carries is not registered to the item's catalogue"
)

_LOT_SIDE = frozenset({_A.LOTS, _A.LOT_POSITIONS, _A.PRODUCTION_ORDERS})
_ORDER_SIDE = frozenset({_A.ORDERS, _A.ORDER_ITEMS})


@dataclass(frozen=True)
class DriftRow:
    """One stored field that differs from its derivation. `table` is the
    aggregate's name, `rule` says where the derived value comes from and
    `facts` what the derivation read. An anomaly row reports facts that
    contradict each other rather than a stored field."""

    table: str
    id: int
    public_id: UUID
    field: str
    stored: str
    derived: str
    rule: str
    facts: Mapping[str, object]
    anomaly: bool = False


@dataclass
class DriftTally:
    """Per aggregate: rows compared and the fields listed for them."""

    checked: int = 0
    drift: int = 0


@dataclass
class DriftReport:
    rows: list[DriftRow] = field(default_factory=list)
    tallies: dict[str, DriftTally] = field(default_factory=dict)

    @property
    def has_drift(self) -> bool:
        return bool(self.rows)


class DriftCollector(Protocol):
    """Receives the comparison of a page: the differing fields of each row
    compared, and the fact anomalies. `chosen` names the aggregates to
    compare."""

    @property
    def chosen(self) -> frozenset[LifecycleAggregate]: ...

    def add(
        self,
        aggregate: LifecycleAggregate,
        public_id: UUID,
        changes: list[FieldChange],
        facts: object,
    ) -> None: ...

    def anomaly(self, row: DriftRow) -> None: ...


@dataclass(frozen=True)
class DriftPage:
    """One page of the walk: `aggregate` is the table paged (lots, orders or
    a demand family), `ids` its rows, `snapshot` every fact their
    derivations read, and `delivery_totals` the sums over the delivery rows
    of an order page's lines, None when they are not compared."""

    aggregate: LifecycleAggregate
    ids: tuple[int, ...]
    snapshot: LifecycleSnapshot
    delivery_totals: Mapping[int, DeliveryTotals] | None = None


def _plain(value: object) -> object:
    """A JSON-friendly copy of a facts value."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(item) for item in value]
    return value


def facts_dict(facts: object) -> dict[str, object]:
    """The facts dataclass as a dictionary of plain values."""
    if not dataclasses.is_dataclass(facts) or isinstance(facts, type):
        return {}
    return {key: _plain(value) for key, value in dataclasses.asdict(facts).items()}


class _Collector:
    """Collects the rows and tallies of one report."""

    def __init__(self, report: DriftReport, chosen: frozenset[LifecycleAggregate]) -> None:
        self._report = report
        self.chosen = chosen

    def add(
        self,
        aggregate: LifecycleAggregate,
        public_id: UUID,
        changes: list[FieldChange],
        facts: object,
    ) -> None:
        tally = self._report.tallies[aggregate.value]
        tally.checked += 1
        tally.drift += len(changes)
        self._report.rows.extend(
            DriftRow(
                table=aggregate.value,
                id=change.id,
                public_id=public_id,
                field=change.field.value,
                stored=change.old,
                derived=change.new,
                rule=change.rule,
                facts=facts_dict(facts),
            )
            for change in changes
        )

    def anomaly(self, row: DriftRow) -> None:
        self._report.tallies[row.table].drift += 1
        self._report.rows.append(row)


class LifecycleDriftReport:
    """Walks the chosen aggregates page by page, see the module docstring."""

    def __init__(
        self, repositories: LifecycleRepositories, *, batch_size: int = _BATCH_SIZE
    ) -> None:
        self._repos = repositories
        self._batch_size = batch_size

    async def run(
        self,
        aggregates: Collection[LifecycleAggregate] = LIFECYCLE_DRIFT_AGGREGATES,
        *,
        now: datetime | None = None,
    ) -> DriftReport:
        chosen = frozenset(aggregates)
        moment = now or now_utc()
        report = DriftReport(
            tallies={a.value: DriftTally() for a in LIFECYCLE_DRIFT_AGGREGATES if a in chosen}
        )
        collector = _Collector(report, chosen)
        async for page in self.pages(chosen):
            compare_page(collector, page, moment)
        return report

    async def pages(self, chosen: frozenset[LifecycleAggregate]) -> AsyncIterator[DriftPage]:
        """The pages that hold the chosen aggregates, in the report's order:
        lots, orders, the demands of each family, then quote requests."""
        if chosen & _LOT_SIDE:
            async for ids in self._pages(self._repos.lots.get_ids_after):
                yield await self.load_page(_A.LOTS, ids, chosen)
        if chosen & _ORDER_SIDE:
            async for ids in self._pages(self._repos.orders.get_ids_after):
                yield await self.load_page(_A.ORDERS, ids, chosen)
        for family, fetch in (
            (_A.BOUGHT_DEMANDS, self._repos.bought_demands.get_ids_after),
            (_A.MADE_DEMANDS, self._repos.made_demands.get_ids_after),
            (_A.SOURCE_DEMANDS, self._repos.source_demands.get_ids_after),
        ):
            if family in chosen:
                async for ids in self._pages(fetch):
                    yield await self.load_page(family, ids, chosen)
        if _A.QUOTE_REQUESTS in chosen:
            async for ids in self._pages(self._repos.quote_requests.get_ids_after):
                yield await self.load_page(_A.QUOTE_REQUESTS, ids, chosen)

    async def load_page(
        self,
        aggregate: LifecycleAggregate,
        ids: Collection[int],
        chosen: frozenset[LifecycleAggregate],
    ) -> DriftPage:
        """Reads one page of `aggregate`, lots, orders, a demand family or
        quote requests."""
        page = list(ids)
        snapshot = await self._load(aggregate, page)
        totals = None
        if aggregate is _A.ORDERS and _A.ORDER_ITEMS in chosen:
            totals = await self._delivery_totals(snapshot, page)
        return DriftPage(aggregate, tuple(page), snapshot, totals)

    async def _delivery_totals(
        self, snapshot: LifecycleSnapshot, page: list[int]
    ) -> Mapping[int, DeliveryTotals] | None:
        """The delivery totals summed over the rows of the page's lines, None
        without a delivery repository, which leaves the comparison out."""
        if self._repos.deliveries is None:
            return None
        page_ids = set(page)
        line_ids = [i.id for i in snapshot.order_items.values() if i.order_id in page_ids]
        return await self._repos.deliveries.get_totals_by_order_item_ids(line_ids)

    async def _load(self, aggregate: LifecycleAggregate, ids: list[int]) -> LifecycleSnapshot:
        loader = LifecycleLoader(self._repos, refresh=False)
        return await loader.load_facts(AggregateIds.of({aggregate: ids}))

    async def _pages(
        self, fetch: Callable[[int, int], Awaitable[list[int]]]
    ) -> AsyncIterator[list[int]]:
        after_id = 0
        while True:
            page = await fetch(after_id, self._batch_size)
            if page:
                yield page
            if len(page) < self._batch_size:
                return
            after_id = page[-1]


def compare_page(collector: DriftCollector, page: DriftPage, now: datetime) -> None:
    """Compares one page, handing every differing field and every fact
    anomaly to the collector. `now` dates a stamp the derivation enters."""
    derivation = derive_snapshot(page.snapshot)
    ids = list(page.ids)
    if page.aggregate is _A.LOTS:
        _compare_lots(collector, page.snapshot, derivation, ids, now)
    elif page.aggregate is _A.ORDERS:
        _compare_orders(collector, page.snapshot, derivation, ids, now, page.delivery_totals)
    elif page.aggregate is _A.QUOTE_REQUESTS:
        _compare_quote_requests(collector, page.snapshot, derivation, ids)
    else:
        _compare_demands(collector, page.aggregate, page.snapshot, derivation)


def _compare_lots(
    collector: DriftCollector,
    snapshot: LifecycleSnapshot,
    derivation: SnapshotDerivation,
    page: list[int],
    now: datetime,
) -> None:
    chosen = collector.chosen
    position_ids: set[int] = set()
    for lot_id in page:
        lot = snapshot.lots.get(lot_id)
        if lot is None:
            continue
        derived = derivation.lots[lot.id]
        if _A.LOTS in chosen:
            collector.add(
                _A.LOTS, lot.public_id, lot_changes(lot, derived, now=now), derived.status.facts
            )
        for position in lot.positions:
            position_ids.add(position.id)
            if _A.LOT_POSITIONS not in chosen:
                continue
            derived_position = derivation.positions[position.id]
            facts = derived_position.status.facts
            collector.add(
                _A.LOT_POSITIONS,
                position.public_id,
                position_changes(position, derived_position),
                facts,
            )
            if completed_over_quantity(position, derived_position):
                collector.anomaly(
                    DriftRow(
                        table=_A.LOT_POSITIONS.value,
                        id=position.id,
                        public_id=position.public_id,
                        field=LifecycleField.QUANTITY_COMPLETED.value,
                        stored=f"{position.quantity_completed:g}",
                        derived=f"{derived_position.quantity_completed:g}",
                        rule=COMPLETED_OVER_QUANTITY_RULE,
                        facts=facts_dict(facts),
                        anomaly=True,
                    )
                )
    if _A.PRODUCTION_ORDERS not in chosen:
        return
    for order in sorted(snapshot.production_orders.values(), key=lambda o: o.id):
        if order.lot_position_id not in position_ids:
            continue
        derived_order = derivation.production_orders[order.id]
        collector.add(
            _A.PRODUCTION_ORDERS,
            order.public_id,
            production_order_changes(order, derived_order, now=now),
            derived_order.facts,
        )


def _compare_orders(
    collector: DriftCollector,
    snapshot: LifecycleSnapshot,
    derivation: SnapshotDerivation,
    page: list[int],
    now: datetime,
    from_rows: Mapping[int, DeliveryTotals] | None,
) -> None:
    chosen = collector.chosen
    page_ids = set(page)
    if _A.ORDERS in chosen:
        for order_id in page:
            order = snapshot.orders.get(order_id)
            if order is None:
                continue
            derived = derivation.orders[order.id]
            collector.add(
                _A.ORDERS, order.public_id, order_changes(order, derived, now=now), derived.facts
            )
    if _A.ORDER_ITEMS not in chosen:
        return
    for item in sorted(snapshot.order_items.values(), key=lambda i: i.id):
        if item.order_id not in page_ids:
            continue
        derived_item = derivation.order_items[item.id]
        collector.add(
            _A.ORDER_ITEMS,
            item.public_id,
            order_item_changes(item, derived_item),
            derived_item.facts,
        )
        if from_rows is None:
            continue
        for difference in delivery_totals_differences(
            stored_totals(item), from_rows.get(item.id, DeliveryTotals())
        ):
            collector.anomaly(
                DriftRow(
                    table=_A.ORDER_ITEMS.value,
                    id=item.id,
                    public_id=item.public_id,
                    field=difference.field,
                    stored=f"{difference.stored:g}",
                    derived=f"{difference.from_rows:g}",
                    rule=DELIVERY_TOTALS_RULE,
                    facts=facts_dict(derived_item.facts),
                    anomaly=True,
                )
            )


def _compare_quote_requests(
    collector: DriftCollector,
    snapshot: LifecycleSnapshot,
    derivation: SnapshotDerivation,
    page: list[int],
) -> None:
    for request_id in page:
        request = snapshot.quote_requests.get(request_id)
        derived = derivation.quote_requests.get(request_id)
        if request is None or derived is None:
            continue
        collector.add(
            _A.QUOTE_REQUESTS,
            request.public_id,
            quote_request_changes(request, derived),
            derived.facts,
        )


def _compare_demands(
    collector: DriftCollector,
    family: LifecycleAggregate,
    snapshot: LifecycleSnapshot,
    derivation: SnapshotDerivation,
) -> None:
    if family is _A.BOUGHT_DEMANDS:
        for bought in sorted(snapshot.bought_demands.values(), key=lambda d: d.id):
            derived_bought = derivation.bought_demands[bought.id]
            collector.add(
                family,
                bought.public_id,
                demand_changes(family, bought, derived_bought),
                derived_bought.facts,
            )
    elif family is _A.MADE_DEMANDS:
        for made in sorted(snapshot.made_demands.values(), key=lambda d: d.id):
            derived_made = derivation.made_demands[made.id]
            collector.add(
                family,
                made.public_id,
                demand_changes(family, made, derived_made),
                derived_made.facts,
            )
    else:
        for source in sorted(snapshot.source_demands.values(), key=lambda d: d.id):
            derived_source = derivation.source_demands[source.id]
            collector.add(
                family,
                source.public_id,
                source_demand_changes(source, derived_source),
                derived_source.facts,
            )


async def add_part_number_registry_anomalies(
    report: DriftReport, registry: IPartNumberRegistryQueries
) -> None:
    """Adds one anomaly row per part number an item carries without its
    registry entry, or under an entry of the other catalogue. The row names
    the item with the lowest id among those carrying the number; `stored` is
    the kind the registry names, `-` without an entry, and `derived` the
    item's catalogue."""
    found = await registry.find_unregistered_holders()
    report.tallies[PART_NUMBER_REGISTRY_TABLE] = DriftTally(checked=len(found), drift=len(found))
    report.rows.extend(
        DriftRow(
            table=PART_NUMBER_REGISTRY_TABLE,
            id=entry.item_id,
            public_id=entry.item_public_id,
            field="part_number",
            stored=entry.registered_kind.value if entry.registered_kind else "-",
            derived=entry.kind.value,
            rule=PART_NUMBER_REGISTRY_RULE,
            facts={
                "part_number": entry.part_number,
                "item": f"{entry.kind.value} item #{entry.item_id}",
            },
            anomaly=True,
        )
        for entry in found
    )
