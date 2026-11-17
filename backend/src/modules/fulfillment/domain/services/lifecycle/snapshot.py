"""Derives every lifecycle aggregate in a set of loaded entities, from their
facts and intents, in dependency order.

A LifecycleSnapshot holds the entities the derivations read: lots with their
positions, the order lines and production orders linked to those positions,
orders with their lines, demands with their allocations and the lines and
lots those draw on, and quote requests with their lines. derive_snapshot
builds each aggregate's facts from the entities and derives it with the
tables of this package. Order items and production orders come first, then
positions, lots, orders and demands, so every derivation reads the derived
values of its inputs and never their stored statuses: a row whose stored
status drifted cannot pass its drift on. A quote request reads whether the
order lines its awards created are canceled, an intent its repository
carries on each line (QuoteRequestLine.award_live), so it reads no derived
value at all.

A reference to an entity the snapshot does not hold derives as facts.py
documents: an allocation without its line or lot covers nothing and is not
placed, a position without a linked line has none, an order's status reads
only the lines the snapshot holds. A caller that derives an order therefore
loads all of its lines.
"""

from collections import defaultdict
from collections.abc import Iterable
from collections.abc import Mapping
from dataclasses import dataclass
from dataclasses import field
from datetime import datetime
from enum import Enum
from typing import Protocol

from src.modules.catalogue.domain.value_objects.bought_item_status import AllocationSource
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemAllocationSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.domain.entities.bought_item_allocation import (
    BoughtItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.production_order_interruption import (
    ProductionOrderInterruption,
)
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequest
from src.modules.fulfillment.domain.entities.source_item_allocation import (
    SourceItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.services.lifecycle.demand import BOUGHT_DEMAND_STATUS
from src.modules.fulfillment.domain.services.lifecycle.demand import BOUGHT_FILL_RANK
from src.modules.fulfillment.domain.services.lifecycle.demand import MADE_DEMAND_STATUS
from src.modules.fulfillment.domain.services.lifecycle.demand import MADE_FILL_RANK
from src.modules.fulfillment.domain.services.lifecycle.demand import SOURCE_DEMAND_STATUS
from src.modules.fulfillment.domain.services.lifecycle.demand import SOURCE_FILL_RANK
from src.modules.fulfillment.domain.services.lifecycle.demand import FillEntry
from src.modules.fulfillment.domain.services.lifecycle.demand import pieces_ahead
from src.modules.fulfillment.domain.services.lifecycle.facts import AllocationFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import CoveringLineFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import CoveringLotFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import DemandFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import LotFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import LotPositionFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import OrderFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import OrderItemFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import PositionLineFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import PositionOrderFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import ProductionOrderFacts
from src.modules.fulfillment.domain.services.lifecycle.lot import LOT_STATUS
from src.modules.fulfillment.domain.services.lifecycle.lot import derive_lot_quantity_completed
from src.modules.fulfillment.domain.services.lifecycle.lot_position import POSITION_KIND
from src.modules.fulfillment.domain.services.lifecycle.lot_position import POSITION_STATUS
from src.modules.fulfillment.domain.services.lifecycle.lot_position import (
    derive_position_quantity_completed,
)
from src.modules.fulfillment.domain.services.lifecycle.order import ORDER_STATUS
from src.modules.fulfillment.domain.services.lifecycle.order_item import ORDER_ITEM_STATUS
from src.modules.fulfillment.domain.services.lifecycle.production_order import (
    PRODUCTION_ORDER_STATUS,
)
from src.modules.fulfillment.domain.services.lifecycle.quote_request import QUOTE_REQUEST_STATUS
from src.modules.fulfillment.domain.services.lifecycle.quote_request import QuoteRequestFacts
from src.modules.fulfillment.domain.services.lifecycle.quote_request import quote_request_facts
from src.modules.fulfillment.domain.services.lifecycle.rules import DerivationTable
from src.modules.fulfillment.domain.value_objects.interruption_reason import InterruptionReason
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.quote_request_status import QuoteRequestStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemAllocationSource,
)
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.domain.services.quantities import snapped_to


@dataclass(frozen=True)
class LifecycleSnapshot:
    """The loaded entities, keyed by id. Lots carry their positions and
    production orders their completions and interruptions, as the
    repositories load them."""

    lots: Mapping[int, ProductionLot] = field(default_factory=dict)
    production_orders: Mapping[int, ProductionOrder] = field(default_factory=dict)
    order_items: Mapping[int, OrderItem] = field(default_factory=dict)
    orders: Mapping[int, Order] = field(default_factory=dict)
    bought_demands: Mapping[int, BoughtItemDemandItem] = field(default_factory=dict)
    made_demands: Mapping[int, MadeItemDemandItem] = field(default_factory=dict)
    source_demands: Mapping[int, SourceItemDemandItem] = field(default_factory=dict)
    bought_allocations: tuple[BoughtItemDemandAllocation, ...] = ()
    made_allocations: tuple[MadeItemDemandAllocation, ...] = ()
    source_allocations: tuple[SourceItemDemandAllocation, ...] = ()
    quote_requests: Mapping[int, QuoteRequest] = field(default_factory=dict)

    def positions(self) -> dict[int, LotPosition]:
        """Every position of the snapshot's lots, keyed by id."""
        return {p.id: p for lot in self.lots.values() for p in lot.positions}


@dataclass(frozen=True)
class RuleRef:
    """The table row a derived value came from."""

    table: str
    number: int
    condition: str

    def __str__(self) -> str:
        return f"{self.table} row {self.number}: {self.condition}"


@dataclass(frozen=True)
class Derived[V: Enum, F]:
    """A derived value with the row that produced it and the facts it read."""

    value: V
    rule: RuleRef
    facts: F


@dataclass(frozen=True)
class DerivedPosition:
    """A lot position's derived kind, status and completed count. The count
    is the facts' total, not capped at the position quantity."""

    kind: Derived[LotPositionKind, LotPositionFacts]
    status: Derived[LotPositionStatus, LotPositionFacts]
    quantity_completed: float


@dataclass(frozen=True)
class DerivedLot:
    """A lot's derived status and completed count (its last position's)."""

    status: Derived[LotStatus, LotFacts]
    quantity_completed: float


@dataclass(frozen=True)
class SnapshotDerivation:
    """The derived values of every aggregate in a snapshot, keyed by id."""

    order_items: Mapping[int, Derived[OrderItemStatus, OrderItemFacts]]
    production_orders: Mapping[int, Derived[ProductionOrderStatus, ProductionOrderFacts]]
    positions: Mapping[int, DerivedPosition]
    lots: Mapping[int, DerivedLot]
    orders: Mapping[int, Derived[OrderStatus, OrderFacts]]
    bought_demands: Mapping[int, Derived[BoughtItemDemandStatus, DemandFacts]]
    made_demands: Mapping[int, Derived[MadeItemDemandStatus, DemandFacts]]
    source_demands: Mapping[int, Derived[SourceItemDemandStatus, DemandFacts]]
    quote_requests: Mapping[int, Derived[QuoteRequestStatus, QuoteRequestFacts]] = field(
        default_factory=dict
    )


def _derive[F, V: Enum](table: DerivationTable[F, V], facts: F) -> Derived[V, F]:
    derivation = table.derive(facts)
    row = table.rows[derivation.rule - 1]
    return Derived(
        value=derivation.value,
        rule=RuleRef(table=table.key, number=row.number, condition=row.condition),
        facts=facts,
    )


def order_item_facts(item: OrderItem) -> OrderItemFacts:
    return OrderItemFacts(
        quantity=item.quantity,
        delivered=item.quantity_delivered,
        lost=item.quantity_rejected_lost,
        requested_at=item.requested_at,
        ordered_date=item.ordered_date,
        canceled_at=item.canceled_at,
    )


def _open_interruption(
    interruptions: Iterable[ProductionOrderInterruption],
) -> InterruptionReason | None:
    """The reason of the interruption that has not been resumed, the latest
    one if several are open."""
    open_rows = [i for i in interruptions if i.resumed_at is None]
    if not open_rows:
        return None
    latest = max(open_rows, key=lambda i: (i.paused_at, i.id))
    return latest.reason


def accepted_pieces(order: ProductionOrder) -> float:
    """The pieces an order completed, from its completion rows: their
    accepted pieces, reversals netted out, never below zero and snapped to
    zero or the order quantity within the tolerance. The stored
    quantity_completed is this count capped at the order quantity."""
    return snapped_to(max(order.pieces_accepted, 0.0), 0.0, order.quantity)


def production_order_facts(order: ProductionOrder) -> ProductionOrderFacts:
    return ProductionOrderFacts(
        quantity=order.quantity,
        processed=order.pieces_processed,
        actual_start=order.actual_start,
        canceled_at=order.canceled_at,
        open_interruption=_open_interruption(order.interruptions),
    )


class _Derivation:
    """Derives one snapshot, aggregate after aggregate, keeping what each
    step produced for the steps that read it."""

    def __init__(self, snapshot: LifecycleSnapshot) -> None:
        self._snapshot = snapshot
        self._line_by_position: dict[int, OrderItem] = {}
        self._lines_by_order: defaultdict[int, list[OrderItem]] = defaultdict(list)
        for item in sorted(snapshot.order_items.values(), key=lambda i: (i.position, i.id)):
            self._lines_by_order[item.order_id].append(item)
        # A position's line is its newest live line, else its newest canceled
        # one. Earlier live lines beside it were closed short.
        self._closed_lines_by_position: defaultdict[int, list[OrderItem]] = defaultdict(list)
        for item in sorted(
            snapshot.order_items.values(), key=lambda i: (i.canceled_at is not None, -i.id)
        ):
            if item.lot_position_id is None:
                continue
            if item.lot_position_id not in self._line_by_position:
                self._line_by_position[item.lot_position_id] = item
            elif item.canceled_at is None:
                self._closed_lines_by_position[item.lot_position_id].append(item)
        self._orders_by_position: defaultdict[int, list[ProductionOrder]] = defaultdict(list)
        for order in sorted(snapshot.production_orders.values(), key=lambda o: o.id):
            self._orders_by_position[order.lot_position_id].append(order)

    def run(self) -> SnapshotDerivation:
        snapshot = self._snapshot
        order_items = {
            item.id: _derive(ORDER_ITEM_STATUS, order_item_facts(item))
            for item in snapshot.order_items.values()
        }
        production_orders = {
            order.id: _derive(PRODUCTION_ORDER_STATUS, production_order_facts(order))
            for order in snapshot.production_orders.values()
        }
        positions: dict[int, DerivedPosition] = {}
        lots: dict[int, DerivedLot] = {}
        for lot in snapshot.lots.values():
            for position in lot.positions:
                positions[position.id] = self._position(
                    lot, position, order_items, production_orders
                )
            lots[lot.id] = self._lot(lot, positions)
        orders = {order.id: self._order(order, order_items) for order in snapshot.orders.values()}
        return SnapshotDerivation(
            order_items=order_items,
            production_orders=production_orders,
            positions=positions,
            lots=lots,
            orders=orders,
            bought_demands=self._bought_demands(order_items),
            made_demands=self._made_demands(lots),
            source_demands=self._source_demands(order_items),
            quote_requests={
                request.id: _derive(QUOTE_REQUEST_STATUS, quote_request_facts(request))
                for request in snapshot.quote_requests.values()
            },
        )

    def _position(
        self,
        lot: ProductionLot,
        position: LotPosition,
        order_items: Mapping[int, Derived[OrderItemStatus, OrderItemFacts]],
        production_orders: Mapping[int, Derived[ProductionOrderStatus, ProductionOrderFacts]],
    ) -> DerivedPosition:
        item = self._line_by_position.get(position.id)
        line = (
            PositionLineFacts(
                status=order_items[item.id].value,
                quantity=item.quantity,
                delivered=item.quantity_delivered,
            )
            if item is not None
            else None
        )
        facts = LotPositionFacts(
            quantity=position.quantity,
            line=line,
            closed_lines=tuple(
                PositionLineFacts(
                    status=order_items[closed.id].value,
                    quantity=closed.quantity,
                    delivered=closed.quantity_delivered,
                )
                for closed in self._closed_lines_by_position.get(position.id, ())
            ),
            orders=tuple(
                PositionOrderFacts(
                    status=production_orders[order.id].value,
                    quantity=order.quantity,
                    quantity_completed=accepted_pieces(order),
                )
                for order in self._orders_by_position.get(position.id, ())
            ),
            lot_canceled=lot.canceled_at is not None,
        )
        return DerivedPosition(
            kind=_derive(POSITION_KIND, facts),
            status=_derive(POSITION_STATUS, facts),
            quantity_completed=derive_position_quantity_completed(facts),
        )

    @staticmethod
    def _lot(lot: ProductionLot, positions: Mapping[int, DerivedPosition]) -> DerivedLot:
        in_sequence = sorted(lot.positions, key=lambda p: p.sequence)
        facts = LotFacts(
            quantity=lot.quantity,
            position_statuses=tuple(positions[p.id].status.value for p in in_sequence),
            held_at=lot.held_at,
            canceled_at=lot.canceled_at,
            force_completed_at=lot.force_completed_at,
        )
        return DerivedLot(
            status=_derive(LOT_STATUS, facts),
            quantity_completed=derive_lot_quantity_completed(
                [positions[p.id].quantity_completed for p in in_sequence]
            ),
        )

    def _order(
        self, order: Order, order_items: Mapping[int, Derived[OrderItemStatus, OrderItemFacts]]
    ) -> Derived[OrderStatus, OrderFacts]:
        facts = OrderFacts(
            requested_at=order.requested_at,
            ordered_date=order.ordered_date,
            canceled_at=order.canceled_at,
            line_statuses=tuple(
                order_items[i.id].value for i in self._lines_by_order.get(order.id, ())
            ),
        )
        return _derive(ORDER_STATUS, facts)

    def _line_fill(self) -> dict[int, list[FillEntry]]:
        """The fill entries of every line, from the allocations of both
        families on it; the loader reads them all for a line it reads."""
        fill: defaultdict[int, list[FillEntry]] = defaultdict(list)
        for rank, allocations, stock in (
            (BOUGHT_FILL_RANK, self._snapshot.bought_allocations, AllocationSource.STOCK),
            (
                SOURCE_FILL_RANK,
                self._snapshot.source_allocations,
                SourceItemAllocationSource.STOCK,
            ),
        ):
            for a in allocations:
                if a.source != stock and a.order_item_id is not None:
                    fill[a.order_item_id].append((rank, a.demand_item_id, a.quantity))
        return fill

    def _line_allocation(
        self,
        allocation: BoughtItemDemandAllocation | SourceItemDemandAllocation,
        from_stock: bool,
        rank: int,
        fill: Mapping[int, list[FillEntry]],
        order_items: Mapping[int, Derived[OrderItemStatus, OrderItemFacts]],
    ) -> AllocationFacts:
        quantity = allocation.quantity
        if from_stock:
            return AllocationFacts.stock(quantity)
        order_item_id = allocation.order_item_id
        item = self._snapshot.order_items.get(order_item_id) if order_item_id else None
        if item is None:
            return AllocationFacts(quantity=quantity, from_stock=False, line=None, lot=None)
        return AllocationFacts.on_line(
            quantity,
            CoveringLineFacts(
                status=order_items[item.id].value,
                quantity=item.quantity,
                delivered=item.quantity_delivered,
                lost=item.quantity_rejected_lost,
            ),
            ahead=pieces_ahead(fill.get(item.id, ()), rank, allocation.demand_item_id),
        )

    def _bought_demands(
        self, order_items: Mapping[int, Derived[OrderItemStatus, OrderItemFacts]]
    ) -> dict[int, Derived[BoughtItemDemandStatus, DemandFacts]]:
        by_demand: defaultdict[int, list[AllocationFacts]] = defaultdict(list)
        fill = self._line_fill()
        for a in _in_order(self._snapshot.bought_allocations):
            by_demand[a.demand_item_id].append(
                self._line_allocation(
                    a, a.source == AllocationSource.STOCK, BOUGHT_FILL_RANK, fill, order_items
                )
            )
        return {
            d.id: _derive(BOUGHT_DEMAND_STATUS, _demand_facts(d, by_demand[d.id]))
            for d in self._snapshot.bought_demands.values()
        }

    def _source_demands(
        self, order_items: Mapping[int, Derived[OrderItemStatus, OrderItemFacts]]
    ) -> dict[int, Derived[SourceItemDemandStatus, DemandFacts]]:
        by_demand: defaultdict[int, list[AllocationFacts]] = defaultdict(list)
        fill = self._line_fill()
        for a in _in_order(self._snapshot.source_allocations):
            by_demand[a.demand_item_id].append(
                self._line_allocation(
                    a,
                    a.source == SourceItemAllocationSource.STOCK,
                    SOURCE_FILL_RANK,
                    fill,
                    order_items,
                )
            )
        return {
            d.id: _derive(SOURCE_DEMAND_STATUS, _demand_facts(d, by_demand[d.id]))
            for d in self._snapshot.source_demands.values()
        }

    def _made_demands(
        self, lots: Mapping[int, DerivedLot]
    ) -> dict[int, Derived[MadeItemDemandStatus, DemandFacts]]:
        by_demand: defaultdict[int, list[AllocationFacts]] = defaultdict(list)
        fill: defaultdict[int, list[FillEntry]] = defaultdict(list)
        for a in self._snapshot.made_allocations:
            if a.source != MadeItemAllocationSource.STOCK and a.lot_id is not None:
                fill[a.lot_id].append((MADE_FILL_RANK, a.demand_item_id, a.quantity))
        for a in sorted(
            self._snapshot.made_allocations, key=lambda a: (a.demand_item_id, a.lot_id or 0)
        ):
            by_demand[a.demand_item_id].append(self._lot_allocation(a, lots, fill))
        return {
            d.id: _derive(MADE_DEMAND_STATUS, _demand_facts(d, by_demand[d.id]))
            for d in self._snapshot.made_demands.values()
        }

    def _lot_allocation(
        self,
        allocation: MadeItemDemandAllocation,
        lots: Mapping[int, DerivedLot],
        fill: Mapping[int, list[FillEntry]],
    ) -> AllocationFacts:
        if allocation.source == MadeItemAllocationSource.STOCK:
            return AllocationFacts.stock(allocation.quantity)
        lot = self._snapshot.lots.get(allocation.lot_id) if allocation.lot_id else None
        if lot is None:
            return AllocationFacts(
                quantity=allocation.quantity, from_stock=False, line=None, lot=None
            )
        derived = lots[lot.id]
        return AllocationFacts.on_lot(
            allocation.quantity,
            CoveringLotFacts(
                status=derived.status.value,
                quantity=lot.quantity,
                quantity_completed=derived.quantity_completed,
            ),
            ahead=pieces_ahead(fill.get(lot.id, ()), MADE_FILL_RANK, allocation.demand_item_id),
        )


def _in_order[A: (BoughtItemDemandAllocation, SourceItemDemandAllocation)](
    allocations: Iterable[A],
) -> list[A]:
    return sorted(allocations, key=lambda a: (a.demand_item_id, a.order_item_id or 0))


class _DemandRow(Protocol):
    @property
    def quantity(self) -> float: ...

    @property
    def canceled_at(self) -> datetime | None: ...

    @property
    def fulfilled_manually_at(self) -> datetime | None: ...


def _demand_facts(demand: _DemandRow, allocations: Iterable[AllocationFacts]) -> DemandFacts:
    return DemandFacts(
        quantity=demand.quantity,
        allocations=tuple(allocations),
        canceled_at=demand.canceled_at,
        fulfilled_manually_at=demand.fulfilled_manually_at,
    )


def derive_snapshot(snapshot: LifecycleSnapshot) -> SnapshotDerivation:
    """Derives every aggregate the snapshot holds, see the module docstring."""
    return _Derivation(snapshot).run()
