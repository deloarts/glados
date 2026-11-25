"""
LifecycleLoader reads what the lifecycle reconciler and the lifecycle drift
report derive, through the batch reads of the lifecycle repositories.

`widen` turns a set of touched aggregates into the targets a change can
alter: the touched aggregates and their dependents, following only the edges
along which a derived value reads another aggregate. An order item adds its
order, its lot position (a MADE line), the demands allocated to it in both
families and the quote request whose award created it; a production order
adds its position; a position adds its lot; a
lot adds its positions, which read the lot's cancel intent, and the made
demands allocated to the lot. A touched demand adds the other demands
allocated on its lines and lots, of every family, because the pieces that
reach each of them depend on what the allocations ahead of it in the fill
order hold; the demands found that way are not followed further, since a
demand's status moves no other demand's pieces. Orders and quote requests
have no dependents.
Nothing is widened downward: a use case whose intent writes facts on other
aggregates, such as a lot cancel that cancels lines and orders, touches them
itself. A caller can keep the widening inside a set of aggregates, as the
reconciler does with the ones it writes; the allocations behind the demand
edges are then read only for the demand families it keeps.

`load_facts` then reads every fact the targets' derivations need: all lines
of an order, the positions of a lot with their lines and production orders,
the allocations of a demand with the lines and lots they draw on, and every
other allocation on those lines and lots, which comes before or after it in
their fill order, and a quote request with its lines, each of which carries
whether the order lines of its award are still live. Facts that
are not targets are read, not locked, and derive from their own facts like
everything else, so a target is never derived from another row's stored
drift.

With refresh, every read re-reads rows the session already holds, because a
row loaded earlier in the request may be older than what another transaction
has committed since, and the reconciler writes what it derives.
"""

from collections.abc import Iterable
from collections.abc import Iterator
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field

from src.modules.fulfillment.domain.entities.bought_item_allocation import (
    BoughtItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequest
from src.modules.fulfillment.domain.entities.source_item_allocation import (
    SourceItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.services.lifecycle.snapshot import LifecycleSnapshot
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import DEMAND_AGGREGATES
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemDemandItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemDemandItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemDeliveryRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.quote_request_repository import (
    IQuoteRequestRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemDemandRepository,
)

_A = LifecycleAggregate


@dataclass(frozen=True)
class LifecycleRepositories:
    """The repositories the lifecycle reconciler and drift report read and
    write, all on one session. `deliveries` lets the drift report compare
    each order line's delivery totals with its delivery rows; without it
    that comparison is left out."""

    lots: IProductionLotRepository
    production_orders: IProductionOrderRepository
    orders: IOrderRepository
    order_items: IOrderItemRepository
    bought_demands: IBoughtItemDemandItemRepository
    bought_allocations: IBoughtItemAllocationRepository
    made_demands: IMadeItemDemandItemRepository
    made_allocations: IMadeItemAllocationRepository
    source_demands: ISourceItemDemandRepository
    source_allocations: ISourceItemAllocationRepository
    quote_requests: IQuoteRequestRepository
    deliveries: IOrderItemDeliveryRepository | None = None


@dataclass(frozen=True)
class AggregateIds:
    """Row ids per lifecycle aggregate."""

    by_aggregate: Mapping[LifecycleAggregate, frozenset[int]] = field(default_factory=dict)

    @classmethod
    def of(cls, mapping: Mapping[LifecycleAggregate, Iterable[int]]) -> "AggregateIds":
        return cls({a: frozenset(ids) for a, ids in mapping.items() if ids})

    def get(self, aggregate: LifecycleAggregate) -> frozenset[int]:
        return self.by_aggregate.get(aggregate, frozenset())

    def __iter__(self) -> Iterator[tuple[LifecycleAggregate, frozenset[int]]]:
        return iter(sorted(self.by_aggregate.items(), key=lambda item: list(_A).index(item[0])))

    def is_empty(self) -> bool:
        return not any(self.by_aggregate.values())

    def union(self, other: "AggregateIds") -> "AggregateIds":
        return AggregateIds.of(
            {a: self.get(a) | other.get(a) for a in {*self.by_aggregate, *other.by_aggregate}}
        )

    def minus(self, other: "AggregateIds") -> "AggregateIds":
        return AggregateIds.of({a: ids - other.get(a) for a, ids in self.by_aggregate.items()})

    def restricted_to(self, aggregates: Iterable[LifecycleAggregate]) -> "AggregateIds":
        keep = frozenset(aggregates)
        return AggregateIds.of({a: ids for a, ids in self.by_aggregate.items() if a in keep})

    def issubset(self, other: "AggregateIds") -> bool:
        return all(ids <= other.get(a) for a, ids in self.by_aggregate.items())


def _allocation_key(demand_item_id: int, ref_id: int | None) -> tuple[int, int | None]:
    """An allocation row is unique per demand and line (or lot); a demand's
    stock row has no reference."""
    return demand_item_id, ref_id


class LifecycleLoader:
    """Reads rows once per loader and keeps them, so widening and loading
    facts share what they read. One loader serves one pass; a pass after
    taking locks uses a new one."""

    def __init__(self, repositories: LifecycleRepositories, *, refresh: bool) -> None:
        self._repos = repositories
        self._refresh = refresh
        self._lots: dict[int, ProductionLot] = {}
        self._production_orders: dict[int, ProductionOrder] = {}
        self._order_items: dict[int, OrderItem] = {}
        self._orders: dict[int, Order] = {}
        self._bought_demands: dict[int, BoughtItemDemandItem] = {}
        self._made_demands: dict[int, MadeItemDemandItem] = {}
        self._source_demands: dict[int, SourceItemDemandItem] = {}
        self._bought_allocations: dict[tuple[int, int | None], BoughtItemDemandAllocation] = {}
        self._made_allocations: dict[tuple[int, int | None], MadeItemDemandAllocation] = {}
        self._source_allocations: dict[tuple[int, int | None], SourceItemDemandAllocation] = {}
        self._quote_requests: dict[int, QuoteRequest] = {}
        self._position_lot: dict[int, int] = {}
        # Ids whose batch read already ran, so no read repeats.
        self._lines_of_orders: set[int] = set()
        self._children_of_lots: set[int] = set()
        self._allocations_of_lines: dict[LifecycleAggregate, set[int]] = {
            _A.BOUGHT_DEMANDS: set(),
            _A.SOURCE_DEMANDS: set(),
        }
        self._allocations_of_lots: set[int] = set()
        self._allocations_of_demands: dict[LifecycleAggregate, set[int]] = {
            a: set() for a in DEMAND_AGGREGATES
        }

    # ── Widening ─────────────────────────────────────────────────────

    async def widen(
        self,
        touched: AggregateIds,
        *,
        within: Iterable[LifecycleAggregate] | None = None,
        allocated_on: AggregateIds | None = None,
    ) -> AggregateIds:
        """The touched aggregates and their dependents, iterated to a fixed
        point, see the module docstring. Loads the rows the edges need. With
        `within`, rows of other aggregates are neither kept nor followed, and
        their rows are not read. `allocated_on` names order lines and lots
        whose allocated demands join the targets, without the lines and
        lots themselves, whose rows are not read."""
        keep = frozenset(LifecycleAggregate if within is None else within)
        found = touched.restricted_to(keep)
        found = found.union(await self._sharing_demands(found, keep))
        if allocated_on is not None:
            found = found.union(
                await self._demands_on(
                    allocated_on.get(_A.ORDER_ITEMS), allocated_on.get(_A.LOTS), keep
                )
            )
        frontier = found
        while not frontier.is_empty():
            await self._load_edges(frontier, keep)
            frontier = self._dependents(frontier).restricted_to(keep).minus(found)
            found = found.union(frontier)
        return found

    async def _load_edges(self, ids: AggregateIds, keep: frozenset[LifecycleAggregate]) -> None:
        """Reads the rows the edges out of `ids` follow, the allocations only
        for the demand families in `keep`."""
        await self._ensure_order_items(ids.get(_A.ORDER_ITEMS))
        for family in (_A.BOUGHT_DEMANDS, _A.SOURCE_DEMANDS):
            if family in keep:
                await self._ensure_line_allocations(family, ids.get(_A.ORDER_ITEMS))
        await self._ensure_production_orders(ids.get(_A.PRODUCTION_ORDERS))
        await self._ensure_position_lots(ids.get(_A.LOT_POSITIONS))
        await self._ensure_lots(ids.get(_A.LOTS))
        if _A.MADE_DEMANDS in keep:
            await self._ensure_lot_allocations(ids.get(_A.LOTS))

    async def neighbours(
        self, ids: AggregateIds, *, within: Iterable[LifecycleAggregate]
    ) -> AggregateIds:
        """The demands in `within` allocated on the lines and lots that the
        demands of `ids` are allocated on, the demands of `ids` among them.
        A use case that touches a demand makes them targets, so the
        reconciler locks them before the use case reads what it checks."""
        return await self._sharing_demands(ids, frozenset(within))

    async def source_lines_of(self, demand_ids: Iterable[int]) -> frozenset[int]:
        """The order lines the source demands hold allocations on."""
        demand_ids = set(demand_ids)
        await self._ensure_demand_allocations(_A.SOURCE_DEMANDS, demand_ids)
        return frozenset(
            a.order_item_id
            for a in self._source_allocations.values()
            if a.demand_item_id in demand_ids and a.order_item_id is not None
        )

    async def _sharing_demands(
        self, ids: AggregateIds, keep: frozenset[LifecycleAggregate]
    ) -> AggregateIds:
        """The demands in `keep` allocated on the lines and lots that the
        demands of `ids` are allocated on, see the module docstring."""
        lines: set[int] = set()
        lots: set[int] = set()
        for family in DEMAND_AGGREGATES:
            demand_ids = ids.get(family)
            if not demand_ids or family not in keep:
                continue
            await self._ensure_demand_allocations(family, demand_ids)
            for allocation in self._allocations_of(family):
                if allocation.demand_item_id not in demand_ids:
                    continue
                if isinstance(allocation, MadeItemDemandAllocation):
                    if allocation.lot_id is not None:
                        lots.add(allocation.lot_id)
                elif allocation.order_item_id is not None:
                    lines.add(allocation.order_item_id)
        return await self._demands_on(lines, lots, keep)

    async def _demands_on(
        self, lines: Iterable[int], lots: Iterable[int], keep: frozenset[LifecycleAggregate]
    ) -> AggregateIds:
        """The demands in `keep` allocated on the lines and lots."""
        lines = set(lines)
        lots = set(lots)
        found: dict[LifecycleAggregate, set[int]] = {}
        for family in (_A.BOUGHT_DEMANDS, _A.SOURCE_DEMANDS):
            if family in keep and lines:
                await self._ensure_line_allocations(family, lines)
                found[family] = {
                    a.demand_item_id
                    for a in self._allocations_of(family)
                    if not isinstance(a, MadeItemDemandAllocation) and a.order_item_id in lines
                }
        if _A.MADE_DEMANDS in keep and lots:
            await self._ensure_lot_allocations(lots)
            found[_A.MADE_DEMANDS] = {
                a.demand_item_id for a in self._made_allocations.values() if a.lot_id in lots
            }
        return AggregateIds.of(found)

    def _allocations_of(
        self, family: LifecycleAggregate
    ) -> Iterable[
        BoughtItemDemandAllocation | MadeItemDemandAllocation | SourceItemDemandAllocation
    ]:
        if family is _A.BOUGHT_DEMANDS:
            return self._bought_allocations.values()
        if family is _A.MADE_DEMANDS:
            return self._made_allocations.values()
        return self._source_allocations.values()

    def _dependents(self, ids: AggregateIds) -> AggregateIds:
        found: dict[LifecycleAggregate, set[int]] = {a: set() for a in _A}
        self._add_line_dependents(ids, found)
        self._add_lot_dependents(ids, found)
        return AggregateIds.of(found)

    def _add_line_dependents(
        self, ids: AggregateIds, found: dict[LifecycleAggregate, set[int]]
    ) -> None:
        for item_id in ids.get(_A.ORDER_ITEMS):
            item = self._order_items.get(item_id)
            if item is None:
                continue
            found[_A.ORDERS].add(item.order_id)
            if item.lot_position_id is not None:
                found[_A.LOT_POSITIONS].add(item.lot_position_id)
            if item.quote_request_id is not None:
                found[_A.QUOTE_REQUESTS].add(item.quote_request_id)
        found[_A.BOUGHT_DEMANDS].update(
            a.demand_item_id
            for a in self._bought_allocations.values()
            if a.order_item_id in ids.get(_A.ORDER_ITEMS)
        )
        found[_A.SOURCE_DEMANDS].update(
            a.demand_item_id
            for a in self._source_allocations.values()
            if a.order_item_id in ids.get(_A.ORDER_ITEMS)
        )

    def _add_lot_dependents(
        self, ids: AggregateIds, found: dict[LifecycleAggregate, set[int]]
    ) -> None:
        for order_id in ids.get(_A.PRODUCTION_ORDERS):
            order = self._production_orders.get(order_id)
            if order is not None:
                found[_A.LOT_POSITIONS].add(order.lot_position_id)
        found[_A.LOTS].update(
            self._position_lot[p] for p in ids.get(_A.LOT_POSITIONS) if p in self._position_lot
        )
        for lot_id in ids.get(_A.LOTS):
            lot = self._lots.get(lot_id)
            if lot is not None:
                found[_A.LOT_POSITIONS].update(p.id for p in lot.positions)
        found[_A.MADE_DEMANDS].update(
            a.demand_item_id
            for a in self._made_allocations.values()
            if a.lot_id is not None and a.lot_id in ids.get(_A.LOTS)
        )

    # ── Facts ────────────────────────────────────────────────────────

    async def load_facts(self, targets: AggregateIds) -> LifecycleSnapshot:
        """Reads every fact the targets' derivations need, see the module
        docstring, and returns everything read so far."""
        await self._ensure_order_items(targets.get(_A.ORDER_ITEMS))
        await self._ensure_production_orders(targets.get(_A.PRODUCTION_ORDERS))
        await self._ensure_orders(targets.get(_A.ORDERS))
        await self._ensure_lines_of_orders(targets.get(_A.ORDERS))
        await self._ensure_position_lots(targets.get(_A.LOT_POSITIONS))
        lot_ids = targets.get(_A.LOTS) | {
            self._position_lot[p] for p in targets.get(_A.LOT_POSITIONS) if p in self._position_lot
        }
        await self._ensure_lots(lot_ids)
        for aggregate in DEMAND_AGGREGATES:
            await self._ensure_demands(aggregate, targets.get(aggregate))
            await self._ensure_demand_allocations(aggregate, targets.get(aggregate))
        covering_lines = {
            a.order_item_id for a in self._bought_allocations.values() if a.order_item_id
        } | {a.order_item_id for a in self._source_allocations.values() if a.order_item_id}
        await self._ensure_order_items(covering_lines)
        # Every allocation on a covering line or lot, of other demands too,
        # since arrived pieces fill them in one order (lifecycle/demand.py).
        for family in (_A.BOUGHT_DEMANDS, _A.SOURCE_DEMANDS):
            await self._ensure_line_allocations(family, covering_lines)
        covering_lots = {a.lot_id for a in self._made_allocations.values() if a.lot_id is not None}
        await self._ensure_lots(covering_lots)
        await self._ensure_lot_allocations(covering_lots)
        await self._ensure_lot_children(set(self._lots))
        await self._ensure_quote_requests(targets.get(_A.QUOTE_REQUESTS))
        return self.snapshot()

    def snapshot(self) -> LifecycleSnapshot:
        return LifecycleSnapshot(
            lots=dict(self._lots),
            production_orders=dict(self._production_orders),
            order_items=dict(self._order_items),
            orders=dict(self._orders),
            bought_demands=dict(self._bought_demands),
            made_demands=dict(self._made_demands),
            source_demands=dict(self._source_demands),
            bought_allocations=tuple(self._bought_allocations.values()),
            made_allocations=tuple(self._made_allocations.values()),
            source_allocations=tuple(self._source_allocations.values()),
            quote_requests=dict(self._quote_requests),
        )

    # ── Reads ────────────────────────────────────────────────────────

    async def _ensure_order_items(self, ids: Iterable[int]) -> None:
        missing = sorted(set(ids) - set(self._order_items))
        if missing:
            self._add_order_items(
                await self._repos.order_items.get_by_ids(missing, refresh=self._refresh)
            )

    def _add_order_items(self, items: Iterable[OrderItem]) -> None:
        for item in items:
            self._order_items.setdefault(item.id, item)
            if item.lot_position_id is not None and item.lot_id is not None:
                self._position_lot.setdefault(item.lot_position_id, item.lot_id)

    async def _ensure_quote_requests(self, ids: Iterable[int]) -> None:
        missing = sorted(set(ids) - set(self._quote_requests))
        if missing:
            for request in await self._repos.quote_requests.get_by_ids(
                missing, refresh=self._refresh
            ):
                self._quote_requests.setdefault(request.id, request)

    async def _ensure_lines_of_orders(self, order_ids: Iterable[int]) -> None:
        missing = sorted(set(order_ids) - self._lines_of_orders)
        if missing:
            self._add_order_items(
                await self._repos.order_items.get_by_order_ids(missing, refresh=self._refresh)
            )
            self._lines_of_orders.update(missing)

    async def _ensure_orders(self, ids: Iterable[int]) -> None:
        missing = sorted(set(ids) - set(self._orders))
        if missing:
            for order in await self._repos.orders.get_by_ids(missing, refresh=self._refresh):
                self._orders.setdefault(order.id, order)

    async def _ensure_production_orders(self, ids: Iterable[int]) -> None:
        missing = sorted(set(ids) - set(self._production_orders))
        if missing:
            self._add_production_orders(
                await self._repos.production_orders.get_by_ids(missing, refresh=self._refresh)
            )

    def _add_production_orders(self, orders: Iterable[ProductionOrder]) -> None:
        for order in orders:
            self._production_orders.setdefault(order.id, order)
            if order.lot_id:
                self._position_lot.setdefault(order.lot_position_id, order.lot_id)

    async def _ensure_position_lots(self, position_ids: Iterable[int]) -> None:
        """Learns the lot of every position whose lot is not known yet."""
        unknown = sorted(set(position_ids) - set(self._position_lot))
        if unknown:
            for position in await self._repos.lots.get_positions_by_ids(unknown):
                self._position_lot.setdefault(position.id, position.lot_id)

    async def _ensure_lots(self, ids: Iterable[int]) -> None:
        missing = sorted(set(ids) - set(self._lots))
        if missing:
            for lot in await self._repos.lots.get_by_ids(missing, refresh=self._refresh):
                self._lots.setdefault(lot.id, lot)
                for position in lot.positions:
                    self._position_lot[position.id] = lot.id

    async def _ensure_lot_children(self, lot_ids: Iterable[int]) -> None:
        """The order lines and production orders of every position of the
        lots."""
        missing = sorted(set(lot_ids) - self._children_of_lots)
        if not missing:
            return
        position_ids = sorted(
            p.id for lot_id in missing if lot_id in self._lots for p in self._lots[lot_id].positions
        )
        if position_ids:
            self._add_order_items(
                await self._repos.order_items.get_by_lot_position_ids(
                    position_ids, refresh=self._refresh
                )
            )
            self._add_production_orders(
                await self._repos.production_orders.get_by_lot_position_ids(
                    position_ids, refresh=self._refresh
                )
            )
        self._children_of_lots.update(missing)

    async def _ensure_line_allocations(
        self, family: LifecycleAggregate, order_item_ids: Iterable[int]
    ) -> None:
        """The allocations of one demand family, bought or source, that draw
        on the lines."""
        missing = sorted(set(order_item_ids) - self._allocations_of_lines[family])
        if not missing:
            return
        if family is _A.BOUGHT_DEMANDS:
            for bought in await self._repos.bought_allocations.get_by_order_item_ids(
                missing, refresh=self._refresh
            ):
                key = _allocation_key(bought.demand_item_id, bought.order_item_id)
                self._bought_allocations.setdefault(key, bought)
        else:
            for source in await self._repos.source_allocations.get_by_order_item_ids(
                missing, refresh=self._refresh
            ):
                key = _allocation_key(source.demand_item_id, source.order_item_id)
                self._source_allocations.setdefault(key, source)
        self._allocations_of_lines[family].update(missing)

    async def _ensure_lot_allocations(self, lot_ids: Iterable[int]) -> None:
        missing = sorted(set(lot_ids) - self._allocations_of_lots)
        if not missing:
            return
        for made in await self._repos.made_allocations.get_by_lot_ids(
            missing, refresh=self._refresh
        ):
            self._made_allocations.setdefault(
                _allocation_key(made.demand_item_id, made.lot_id), made
            )
        self._allocations_of_lots.update(missing)

    async def _ensure_demands(self, aggregate: LifecycleAggregate, ids: Iterable[int]) -> None:
        if aggregate is _A.BOUGHT_DEMANDS:
            missing = sorted(set(ids) - set(self._bought_demands))
            if missing:
                for bought in await self._repos.bought_demands.get_by_ids(
                    missing, refresh=self._refresh
                ):
                    self._bought_demands.setdefault(bought.id, bought)
        elif aggregate is _A.MADE_DEMANDS:
            missing = sorted(set(ids) - set(self._made_demands))
            if missing:
                for made in await self._repos.made_demands.get_by_ids(
                    missing, refresh=self._refresh
                ):
                    self._made_demands.setdefault(made.id, made)
        else:
            missing = sorted(set(ids) - set(self._source_demands))
            if missing:
                for source in await self._repos.source_demands.get_by_ids(
                    missing, refresh=self._refresh
                ):
                    self._source_demands.setdefault(source.id, source)

    async def _ensure_demand_allocations(
        self, aggregate: LifecycleAggregate, ids: Iterable[int]
    ) -> None:
        missing = sorted(set(ids) - self._allocations_of_demands[aggregate])
        if not missing:
            return
        if aggregate is _A.BOUGHT_DEMANDS:
            for bought in await self._repos.bought_allocations.get_by_demand_item_ids(
                missing, refresh=self._refresh
            ):
                key = _allocation_key(bought.demand_item_id, bought.order_item_id)
                self._bought_allocations.setdefault(key, bought)
        elif aggregate is _A.MADE_DEMANDS:
            for made in await self._repos.made_allocations.get_by_demand_item_ids(
                missing, refresh=self._refresh
            ):
                self._made_allocations.setdefault(
                    _allocation_key(made.demand_item_id, made.lot_id), made
                )
        else:
            for source in await self._repos.source_allocations.get_by_demand_item_ids(
                missing, refresh=self._refresh
            ):
                key = _allocation_key(source.demand_item_id, source.order_item_id)
                self._source_allocations.setdefault(key, source)
        self._allocations_of_demands[aggregate].update(missing)
