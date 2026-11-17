"""
One in-memory world of lifecycle aggregates behind fakes of the repository
ports that the lifecycle loader, lock plan, reconciler and drift report use.
Every fake reads from and writes to the same store, so the views agree: a
lot read through the lot fake carries the positions the store holds, a
production order its completions and interruptions, an order line the lot
of its position. Reads return copies and saves write the copy back, as the
SQL repositories do, so a test sees exactly what was saved. Locks, saves
and timeline rows are logged in order.

The builders create rows with neutral values; a test passes what it is
about. `on_first_lock` lets a test change the store while the reconciler
holds its first locks, as a concurrent transaction would.
"""

import copy
import dataclasses
import itertools
from collections.abc import Callable
from collections.abc import Iterable
from datetime import UTC
from datetime import datetime
from typing import Any

from src.modules.catalogue.domain.value_objects.bought_item_status import AllocationSource
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemAllocationSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.application.services.lifecycle_loader import LifecycleRepositories
from src.modules.fulfillment.domain.entities.bought_item_allocation import (
    BoughtItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.entities.lot_event import LotEvent
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)
from src.modules.fulfillment.domain.entities.production_order_interruption import (
    ProductionOrderInterruption,
)
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequest
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequestLine
from src.modules.fulfillment.domain.entities.source_item_allocation import (
    SourceItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.services.lifecycle.snapshot import LifecycleSnapshot
from src.modules.fulfillment.domain.value_objects.interruption_reason import InterruptionReason
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.domain.value_objects.quote_request_status import QuoteRequestStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemAllocationSource,
)
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.start_page import StartPage
from src.modules.platform.domain.value_objects.theme import ThemePreset
from src.modules.platform.domain.value_objects.theme import ThemePrimary
from src.modules.platform.domain.value_objects.theme import ThemeSurface
from tests.unit._entity_enums import enum_fields

NOW = datetime(2026, 10, 12, 9, 0, tzinfo=UTC)

_A = LifecycleAggregate


def actor(user_id: int = 1, full_name: str = "Pat Planner") -> User:
    """The user a test runs the reconciler as."""
    return User(
        id=user_id,
        username=f"user{user_id}",
        full_name=full_name,
        email=f"user{user_id}@example.com",
        created=NOW,
        hashed_password="x",
        is_active=True,
        is_systemuser=False,
        permissions=[],
        language=Language.enGB,
        date_format=DateFormat.ISO,
        start_page=StartPage.DASHBOARD,
        theme_preset=ThemePreset.Aura,
        theme_surface=ThemeSurface.glados,
        theme_primary=ThemePrimary.glados,
        theme_dark_mode=False,
        button_flat_style=False,
        table_gridlines=False,
        table_striped_rows=False,
    )


def make[T](cls: type[T], **values: Any) -> T:
    """Builds an entity, filling every required field the caller did not
    pass with a neutral value for its annotated type, None for an optional
    one and the first member for an enum."""
    enums = enum_fields(cls)
    for f in dataclasses.fields(cls):  # type: ignore[arg-type]
        if f.name in values or f.init is False:
            continue
        if f.default is not dataclasses.MISSING or f.default_factory is not dataclasses.MISSING:
            continue
        enum_type = enums.get(f.name)
        values[f.name] = next(iter(enum_type)) if enum_type else _neutral(str(f.type))
    return cls(**values)


def _neutral(type_name: str) -> object:
    if "None" in type_name:
        return None
    for marker, value in (
        ("list", list),
        ("datetime", lambda: NOW),
        ("date", lambda: NOW.date()),
        ("float", lambda: 0.0),
        ("bool", lambda: False),
        ("int", lambda: 0),
        ("str", lambda: "x"),
    ):
        if marker in type_name:
            return value()
    raise KeyError(type_name)


class FakeWorld:
    """The store, its builders and its logs."""

    def __init__(self) -> None:
        self.lots: dict[int, ProductionLot] = {}
        self.positions: dict[int, LotPosition] = {}
        self.production_orders: dict[int, ProductionOrder] = {}
        self.orders: dict[int, Order] = {}
        self.order_items: dict[int, OrderItem] = {}
        self.bought_demands: dict[int, BoughtItemDemandItem] = {}
        self.made_demands: dict[int, MadeItemDemandItem] = {}
        self.source_demands: dict[int, SourceItemDemandItem] = {}
        self.bought_allocations: list[BoughtItemDemandAllocation] = []
        self.made_allocations: list[MadeItemDemandAllocation] = []
        self.source_allocations: list[SourceItemDemandAllocation] = []
        self.quote_requests: dict[int, QuoteRequest] = {}
        self.lot_events: list[LotEvent] = []
        self.lock_log: list[tuple[LifecycleAggregate, tuple[int, ...]]] = []
        self.queue_locks: list[tuple[int | None, int | None]] = []
        self.saves: list[tuple[LifecycleAggregate, int]] = []
        self.reads = 0
        self.on_first_lock: Callable[[], None] | None = None
        self._ids = itertools.count(1)
        self.repositories = LifecycleRepositories(
            lots=FakeLots(self),
            production_orders=FakeProductionOrders(self),
            orders=FakeOrders(self),
            order_items=FakeOrderItems(self),
            bought_demands=FakeDemands(self, self.bought_demands, _A.BOUGHT_DEMANDS),
            bought_allocations=FakeLineAllocations(self, self.bought_allocations),
            made_demands=FakeDemands(self, self.made_demands, _A.MADE_DEMANDS),
            made_allocations=FakeLotAllocations(self),
            source_demands=FakeDemands(self, self.source_demands, _A.SOURCE_DEMANDS),
            source_allocations=FakeLineAllocations(self, self.source_allocations),
            quote_requests=FakeQuoteRequests(self),
        )

    def next_id(self) -> int:
        return next(self._ids)

    def locked(self, aggregate: LifecycleAggregate) -> set[int]:
        """Every id of the aggregate the reconciler locked."""
        return {i for a, ids in self.lock_log if a is aggregate for i in ids}

    def log_lock(self, aggregate: LifecycleAggregate, ids: Iterable[int]) -> None:
        self.lock_log.append((aggregate, tuple(ids)))
        hook, self.on_first_lock = self.on_first_lock, None
        if hook is not None:
            hook()

    # ── Builders ─────────────────────────────────────────────────────

    def lot(
        self, *, quantity: float = 10.0, status: LotStatus = LotStatus.DRAFT, **values: Any
    ) -> ProductionLot:
        lot = make(
            ProductionLot,
            id=self.next_id(),
            lot_number=f"LOT-{len(self.lots) + 1}",
            quantity=quantity,
            status=status,
            priority=UrgencyClass.NORMAL,
            creator_id=7,
            made_item_id=3,
            project_id=5,
            input_demand_id=values.pop("input_demand_id", None),
            **values,
        )
        self.lots[lot.id] = lot
        return lot

    def position(
        self,
        lot: ProductionLot,
        *,
        kind: LotPositionKind = LotPositionKind.UNASSIGNED,
        status: LotPositionStatus = LotPositionStatus.PENDING,
        quantity: float | None = None,
        **values: Any,
    ) -> LotPosition:
        sequence = 1 + sum(1 for p in self.positions.values() if p.lot_id == lot.id)
        position = make(
            LotPosition,
            id=self.next_id(),
            sequence=values.pop("sequence", sequence),
            kind=kind,
            status=status,
            quantity=lot.quantity if quantity is None else quantity,
            quantity_completed=values.pop("quantity_completed", 0.0),
            creator_id=7,
            lot_id=lot.id,
            **values,
        )
        self.positions[position.id] = position
        return position

    def production_order(
        self,
        position: LotPosition,
        *,
        status: ProductionOrderStatus = ProductionOrderStatus.QUEUED,
        quantity: float | None = None,
        processed: float = 0.0,
        open_interruption: InterruptionReason | None = None,
        **values: Any,
    ) -> ProductionOrder:
        """A production order; `processed` becomes one completion row whose
        accepted pieces are `quantity_completed` (default: all of them). The
        stored count is those pieces capped at the order quantity, as the
        database constraint holds it."""
        order_id = self.next_id()
        accepted = values.pop("quantity_completed", processed)
        order_quantity = position.quantity if quantity is None else quantity
        completions = (
            [
                make(
                    ProductionOrderCompletion,
                    id=self.next_id(),
                    production_order_id=order_id,
                    quantity=processed,
                    quantity_accepted=accepted,
                    quantity_rejected=processed - accepted,
                    operator_id=7,
                    recorded_by_id=7,
                )
            ]
            if processed
            else []
        )
        interruptions = (
            [
                make(
                    ProductionOrderInterruption,
                    id=self.next_id(),
                    production_order_id=order_id,
                    paused_at=NOW,
                    resumed_at=None,
                    paused_by_id=7,
                    resumed_by_id=None,
                    reason=open_interruption,
                )
            ]
            if open_interruption is not None
            else []
        )
        order = make(
            ProductionOrder,
            id=order_id,
            production_order_number=f"PO-{order_id}",
            status=status,
            priority=UrgencyClass.NORMAL,
            pinned=False,
            queue_sequence=order_id,
            quantity=order_quantity,
            quantity_completed=min(accepted, order_quantity),
            estimated_duration_minutes=60,
            creator_id=8,
            machine_id=values.pop("machine_id", 4),
            lot_position_id=position.id,
            completions=completions,
            interruptions=interruptions,
            **values,
        )
        self.production_orders[order.id] = order
        return order

    def order(self, *, status: OrderStatus = OrderStatus.DRAFT, **values: Any) -> Order:
        order_id = self.next_id()
        order = make(
            Order,
            id=order_id,
            order_number=f"ORD-{order_id}",
            status=status,
            creator_id=7,
            supplier_id=2,
            **values,
        )
        self.orders[order.id] = order
        return order

    def line(
        self,
        order: Order,
        *,
        status: OrderItemStatus = OrderItemStatus.PENDING,
        quantity: float = 10.0,
        delivered: float = 0.0,
        lost: float = 0.0,
        position: LotPosition | None = None,
        **values: Any,
    ) -> OrderItem:
        item = make(
            OrderItem,
            id=self.next_id(),
            status=status,
            quantity=quantity,
            quantity_delivered=delivered,
            quantity_rejected_lost=lost,
            unit="pcs",
            items_per_unit=1.0,
            position=1 + sum(1 for i in self.order_items.values() if i.order_id == order.id),
            creator_id=7,
            order_id=order.id,
            supplier_id=order.supplier_id,
            line_type=OrderLineType.MADE if position is not None else OrderLineType.BOUGHT,
            lot_position_id=position.id if position is not None else None,
            **values,
        )
        self.order_items[item.id] = item
        return item

    def quote_request(
        self, *, status: QuoteRequestStatus = QuoteRequestStatus.SENT, lines: int = 1, **values: Any
    ) -> QuoteRequest:
        """A request with `lines` open lines, numbered from 1."""
        request_id = self.next_id()
        request = make(
            QuoteRequest,
            id=request_id,
            request_number=f"RFQ-{request_id}",
            status=status,
            creator_id=7,
            **values,
        )
        request.lines = [
            make(
                QuoteRequestLine,
                id=self.next_id(),
                quote_request_id=request_id,
                position=position,
                line_type=OrderLineType.BOUGHT,
                quantity=10.0,
                unit="pcs",
            )
            for position in range(1, lines + 1)
        ]
        self.quote_requests[request.id] = request
        return request

    def _demand_values(
        self,
        quantity: float,
        status: BoughtItemDemandStatus | MadeItemDemandStatus | SourceItemDemandStatus,
    ) -> dict[str, Any]:
        return {
            "id": self.next_id(),
            "status": status,
            "quantity": quantity,
            "unit": "pcs",
            "items_per_unit": 1.0,
            "creator_id": 9,
            "project_id": 5,
            "notify_on_delivery": True,
        }

    def bought_demand(
        self,
        *,
        quantity: float = 10.0,
        status: BoughtItemDemandStatus = BoughtItemDemandStatus.OPEN,
        **values: Any,
    ) -> BoughtItemDemandItem:
        demand = make(
            BoughtItemDemandItem,
            **self._demand_values(quantity, status),
            item_id=11,
            item_article_name="Bolt",
            **values,
        )
        self.bought_demands[demand.id] = demand
        return demand

    def made_demand(
        self,
        *,
        quantity: float = 10.0,
        status: MadeItemDemandStatus = MadeItemDemandStatus.OPEN,
        **values: Any,
    ) -> MadeItemDemandItem:
        demand = make(
            MadeItemDemandItem,
            **self._demand_values(quantity, status),
            made_item_id=3,
            item_article_name="Bracket",
            **values,
        )
        self.made_demands[demand.id] = demand
        return demand

    def source_demand(
        self,
        *,
        quantity: float = 10.0,
        status: SourceItemDemandStatus = SourceItemDemandStatus.OPEN,
        **values: Any,
    ) -> SourceItemDemandItem:
        demand = make(
            SourceItemDemandItem,
            **self._demand_values(quantity, status),
            lot_id=values.pop("lot_id", 0),
            **values,
        )
        self.source_demands[demand.id] = demand
        return demand

    def allocate_bought(
        self, demand: BoughtItemDemandItem, line: OrderItem | None, quantity: float
    ) -> None:
        """An allocation on the line, or from stock without one."""
        self.bought_allocations.append(
            BoughtItemDemandAllocation(
                demand_item_id=demand.id,
                order_item_id=line.id if line is not None else None,
                quantity=quantity,
                source=AllocationSource.ORDER if line is not None else AllocationSource.STOCK,
            )
        )

    def allocate_source(
        self, demand: SourceItemDemandItem, line: OrderItem | None, quantity: float
    ) -> None:
        self.source_allocations.append(
            SourceItemDemandAllocation(
                demand_item_id=demand.id,
                order_item_id=line.id if line is not None else None,
                quantity=quantity,
                source=(
                    SourceItemAllocationSource.ORDER
                    if line is not None
                    else SourceItemAllocationSource.STOCK
                ),
            )
        )

    def allocate_made(
        self, demand: MadeItemDemandItem, lot: ProductionLot | None, quantity: float
    ) -> None:
        self.made_allocations.append(
            MadeItemDemandAllocation(
                demand_item_id=demand.id,
                lot_id=lot.id if lot is not None else None,
                quantity=quantity,
                source=MadeItemAllocationSource.LOT
                if lot is not None
                else MadeItemAllocationSource.STOCK,
            )
        )

    # ── Views ────────────────────────────────────────────────────────

    def snapshot(self) -> LifecycleSnapshot:
        """Everything the store holds, as the repositories would read it."""
        return LifecycleSnapshot(
            lots={i: self.hydrated_lot(i) for i in self.lots},
            production_orders={
                i: self.production_order_view(o) for i, o in self.production_orders.items()
            },
            order_items={i: self.order_item_view(o) for i, o in self.order_items.items()},
            orders=copy.deepcopy(self.orders),
            bought_demands=copy.deepcopy(self.bought_demands),
            made_demands=copy.deepcopy(self.made_demands),
            source_demands=copy.deepcopy(self.source_demands),
            bought_allocations=tuple(copy.deepcopy(self.bought_allocations)),
            made_allocations=tuple(copy.deepcopy(self.made_allocations)),
            source_allocations=tuple(copy.deepcopy(self.source_allocations)),
            quote_requests={i: self.quote_request_view(r) for i, r in self.quote_requests.items()},
        )

    def hydrated_lot(self, lot_id: int) -> ProductionLot:
        lot = copy.deepcopy(self.lots[lot_id])
        lot.positions = sorted(
            (copy.deepcopy(p) for p in self.positions.values() if p.lot_id == lot_id),
            key=lambda p: p.sequence,
        )
        return lot

    def order_item_view(self, item: OrderItem) -> OrderItem:
        view = copy.deepcopy(item)
        position = self.positions.get(item.lot_position_id) if item.lot_position_id else None
        view.lot_id = position.lot_id if position is not None else None
        view.quote_request_id = next(
            (
                request.id
                for request in self.quote_requests.values()
                for line in request.lines
                if line.id == item.quote_request_line_id
            ),
            None,
        )
        return view

    def quote_request_view(self, request: QuoteRequest) -> QuoteRequest:
        """The request with each line's award liveness and newest order line
        read from the order lines pointing back at it, as the SQL mapper
        reads them."""
        view = copy.deepcopy(request)
        for line in view.lines:
            awarded = [i for i in self.order_items.values() if i.quote_request_line_id == line.id]
            newest = max(awarded, key=lambda i: i.id, default=None)
            order = self.orders.get(newest.order_id) if newest is not None else None
            line.order_item_id = newest.id if newest is not None else None
            line.order_id = newest.order_id if newest is not None else None
            line.order_number = order.order_number if order is not None else ""
            line.award_live = any(item.canceled_at is None for item in awarded)
        return view

    def production_order_view(self, order: ProductionOrder) -> ProductionOrder:
        view = copy.deepcopy(order)
        position = self.positions.get(order.lot_position_id)
        view.lot_id = position.lot_id if position is not None else 0
        return view


def _ids_after(ids: Iterable[int], after_id: int, limit: int) -> list[int]:
    return sorted(i for i in ids if i > after_id)[:limit]


class FakeLots:
    def __init__(self, world: FakeWorld) -> None:
        self._world = world

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[ProductionLot]:
        self._world.reads += 1
        return [self._world.hydrated_lot(i) for i in ids if i in self._world.lots]

    async def get_positions_by_ids(self, position_ids: list[int]) -> list[LotPosition]:
        self._world.reads += 1
        positions = self._world.positions
        return [copy.deepcopy(positions[i]) for i in position_ids if i in positions]

    async def save(self, lot: ProductionLot) -> ProductionLot:
        stored = copy.deepcopy(lot)
        stored.positions = []
        self._world.lots[lot.id] = stored
        self._world.saves.append((_A.LOTS, lot.id))
        return self._world.hydrated_lot(lot.id)

    async def save_position(self, position: LotPosition) -> LotPosition:
        self._world.positions[position.id] = copy.deepcopy(position)
        self._world.saves.append((_A.LOT_POSITIONS, position.id))
        return copy.deepcopy(position)

    async def record_event(self, event: LotEvent) -> LotEvent:
        self._world.lot_events.append(event)
        return event

    async def lock_for_update(self, ids: list[int]) -> None:
        self._world.log_lock(_A.LOTS, ids)

    async def get_ids_after(self, after_id: int, limit: int) -> list[int]:
        return _ids_after(self._world.lots, after_id, limit)


class FakeProductionOrders:
    def __init__(self, world: FakeWorld) -> None:
        self._world = world

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[ProductionOrder]:
        self._world.reads += 1
        orders = self._world.production_orders
        return [self._world.production_order_view(orders[i]) for i in ids if i in orders]

    async def get_by_lot_position_ids(
        self, lot_position_ids: list[int], *, refresh: bool = False
    ) -> list[ProductionOrder]:
        self._world.reads += 1
        wanted = set(lot_position_ids)
        return [
            self._world.production_order_view(o)
            for o in sorted(self._world.production_orders.values(), key=lambda o: o.id)
            if o.lot_position_id in wanted
        ]

    async def save(self, order: ProductionOrder) -> ProductionOrder:
        self._world.production_orders[order.id] = copy.deepcopy(order)
        self._world.saves.append((_A.PRODUCTION_ORDERS, order.id))
        return self._world.production_order_view(order)

    async def lock_for_update(self, ids: list[int]) -> None:
        self._world.log_lock(_A.PRODUCTION_ORDERS, ids)

    async def lock_queue_scope(
        self, machine_id: int | None, machine_pool_id: int | None = None
    ) -> None:
        self._world.queue_locks.append((machine_id, machine_pool_id))

    async def next_queue_sequence(
        self, machine_id: int | None, machine_pool_id: int | None = None
    ) -> int:
        """One past the highest place of the queue, over the same scopes as
        the repository: the machine, else the pool without a machine, else
        neither."""
        places = [
            o.queue_sequence
            for o in self._world.production_orders.values()
            if _in_queue(o, machine_id, machine_pool_id)
        ]
        return max(places, default=0) + 1


def _in_queue(order: ProductionOrder, machine_id: int | None, machine_pool_id: int | None) -> bool:
    if machine_id is not None:
        return order.machine_id == machine_id
    return order.machine_id is None and order.machine_pool_id == machine_pool_id


class FakeOrders:
    def __init__(self, world: FakeWorld) -> None:
        self._world = world

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[Order]:
        self._world.reads += 1
        return [copy.deepcopy(self._world.orders[i]) for i in ids if i in self._world.orders]

    async def save(self, order: Order) -> Order:
        self._world.orders[order.id] = copy.deepcopy(order)
        self._world.saves.append((_A.ORDERS, order.id))
        return copy.deepcopy(order)

    async def lock_for_update(self, ids: list[int]) -> None:
        self._world.log_lock(_A.ORDERS, ids)

    async def get_ids_after(self, after_id: int, limit: int) -> list[int]:
        return _ids_after(self._world.orders, after_id, limit)


class FakeOrderItems:
    def __init__(self, world: FakeWorld) -> None:
        self._world = world

    def _where(self, keep: Callable[[OrderItem], bool]) -> list[OrderItem]:
        self._world.reads += 1
        return [
            self._world.order_item_view(i)
            for i in sorted(self._world.order_items.values(), key=lambda i: i.id)
            if keep(i)
        ]

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[OrderItem]:
        wanted = set(ids)
        return self._where(lambda i: i.id in wanted)

    async def get_by_order_ids(
        self, order_ids: list[int], *, refresh: bool = False
    ) -> list[OrderItem]:
        wanted = set(order_ids)
        return self._where(lambda i: i.order_id in wanted)

    async def get_by_lot_position_ids(
        self, lot_position_ids: list[int], *, refresh: bool = False
    ) -> list[OrderItem]:
        wanted = set(lot_position_ids)
        return self._where(lambda i: i.lot_position_id in wanted)

    async def save(self, item: OrderItem) -> OrderItem:
        self._world.order_items[item.id] = copy.deepcopy(item)
        self._world.saves.append((_A.ORDER_ITEMS, item.id))
        return self._world.order_item_view(item)

    async def lock_for_update(self, ids: list[int]) -> None:
        self._world.log_lock(_A.ORDER_ITEMS, ids)


class FakeQuoteRequests:
    def __init__(self, world: FakeWorld) -> None:
        self._world = world

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[QuoteRequest]:
        self._world.reads += 1
        store = self._world.quote_requests
        return [self._world.quote_request_view(store[i]) for i in ids if i in store]

    async def save(self, request: QuoteRequest) -> QuoteRequest:
        self._world.quote_requests[request.id] = copy.deepcopy(request)
        self._world.saves.append((_A.QUOTE_REQUESTS, request.id))
        return self._world.quote_request_view(request)

    async def lock_for_update(self, ids: list[int]) -> None:
        self._world.log_lock(_A.QUOTE_REQUESTS, ids)

    async def get_ids_after(self, after_id: int, limit: int) -> list[int]:
        return _ids_after(self._world.quote_requests, after_id, limit)


class FakeDemands[D: (BoughtItemDemandItem, MadeItemDemandItem, SourceItemDemandItem)]:
    def __init__(
        self, world: FakeWorld, store: dict[int, D], aggregate: LifecycleAggregate
    ) -> None:
        self._world = world
        self._store = store
        self._aggregate = aggregate

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[D]:
        self._world.reads += 1
        return [copy.deepcopy(self._store[i]) for i in ids if i in self._store]

    async def save(self, demand: D) -> D:
        self._store[demand.id] = copy.deepcopy(demand)
        self._world.saves.append((self._aggregate, demand.id))
        return copy.deepcopy(demand)

    async def lock_for_update(self, ids: list[int]) -> None:
        self._world.log_lock(self._aggregate, ids)

    async def get_ids_after(self, after_id: int, limit: int) -> list[int]:
        return _ids_after(self._store, after_id, limit)


class FakeLineAllocations[L: (BoughtItemDemandAllocation, SourceItemDemandAllocation)]:
    def __init__(self, world: FakeWorld, rows: list[L]) -> None:
        self._world = world
        self._rows = rows

    async def get_by_demand_item_ids(
        self, demand_item_ids: list[int], *, refresh: bool = False
    ) -> list[L]:
        self._world.reads += 1
        wanted = set(demand_item_ids)
        return [copy.deepcopy(a) for a in self._rows if a.demand_item_id in wanted]

    async def get_by_order_item_ids(
        self, order_item_ids: list[int], *, refresh: bool = False
    ) -> list[L]:
        self._world.reads += 1
        wanted = set(order_item_ids)
        return [copy.deepcopy(a) for a in self._rows if a.order_item_id in wanted]

    async def save(self, allocation: L) -> L:
        """Replaces the demand's row on the same line, as the repositories do."""
        await self.delete(allocation)
        self._rows.append(copy.deepcopy(allocation))
        return copy.deepcopy(allocation)

    async def delete(self, allocation: L) -> None:
        """Deletes the demand's row on the same line, as the repositories do."""
        _delete_first(
            self._rows,
            lambda a: (
                (a.demand_item_id, a.order_item_id)
                == (allocation.demand_item_id, allocation.order_item_id)
            ),
        )


class FakeLotAllocations:
    def __init__(self, world: FakeWorld) -> None:
        self._world = world

    async def get_by_demand_item_ids(
        self, demand_item_ids: list[int], *, refresh: bool = False
    ) -> list[MadeItemDemandAllocation]:
        self._world.reads += 1
        wanted = set(demand_item_ids)
        return [
            copy.deepcopy(a) for a in self._world.made_allocations if a.demand_item_id in wanted
        ]

    async def get_by_lot_ids(
        self, lot_ids: list[int], *, refresh: bool = False
    ) -> list[MadeItemDemandAllocation]:
        self._world.reads += 1
        wanted = set(lot_ids)
        return [copy.deepcopy(a) for a in self._world.made_allocations if a.lot_id in wanted]

    async def delete(self, allocation: MadeItemDemandAllocation) -> None:
        """Deletes the demand's row on the same lot, as the repository does."""
        _delete_first(
            self._world.made_allocations,
            lambda a: (
                (a.demand_item_id, a.lot_id) == (allocation.demand_item_id, allocation.lot_id)
            ),
        )


def _delete_first[T](rows: list[T], matches: Callable[[T], bool]) -> None:
    index = next((i for i, row in enumerate(rows) if matches(row)), None)
    if index is not None:
        del rows[index]
