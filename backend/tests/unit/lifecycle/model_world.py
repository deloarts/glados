"""
One shop over in-memory fakes in which every lifecycle aggregate lives
together: a lot created by the real CreateLot with its positions, the made
demands it covers and its raw material demand, the production orders on its
positions, one supplier order with bought lines, an optional SOURCE line for
the raw material and the MADE lines of external positions, a second, empty
order that lines may be moved to, bought demands allocated to those lines or
taken from stock, optionally a second lot that the first made demand
shares with a lower-id neighbour, and the quote requests an award places
onto the supplier order. Every use case
of a request is built over the same fakes and one lifecycle reconciler with
every aggregate enabled, as the app wires them, so a request on one
aggregate reaches every other through the reconciler's closure.

The cross-aggregate model (test_lifecycle_model.py) and the scenario suite
(test_lifecycle_scenarios.py) drive it. `request` runs one request: a domain
refusal restores every fake as the request's rollback would, a success
returns what the reconciler published. `status_table` reads the stored
status of every aggregate, and `snapshot` the whole world as the lifecycle
loader would read it, for an independent derivation.
"""

import asyncio
import copy
import sys
from collections.abc import Awaitable
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from datetime import UTC
from datetime import date
from datetime import datetime
from types import SimpleNamespace
from typing import Any

from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.application.dto.allocation_dto import CreateAllocationCommand
from src.modules.fulfillment.application.dto.allocation_dto import FulfillFromStockCommand
from src.modules.fulfillment.application.dto.allocation_dto import UpdateAllocationCommand
from src.modules.fulfillment.application.dto.order_dto import DeliveryRejectionInput
from src.modules.fulfillment.application.dto.order_dto import UpdateOrderItemCommand
from src.modules.fulfillment.application.dto.production_lot_dto import AssignExternalPositionCommand
from src.modules.fulfillment.application.dto.production_lot_dto import CancelLotCommand
from src.modules.fulfillment.application.dto.production_lot_dto import CompleteLotCommand
from src.modules.fulfillment.application.dto.production_lot_dto import CreateLotCommand
from src.modules.fulfillment.application.dto.production_lot_dto import HoldLotCommand
from src.modules.fulfillment.application.dto.production_lot_dto import LotDemandAllocationInput
from src.modules.fulfillment.application.dto.production_lot_dto import (
    RecordLotPositionProvisionCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    AssignInternalPositionCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    AssignInternalPositionOrderInput,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    CancelProductionOrderCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    MergeProductionOrdersCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import PauseProductionOrderCommand
from src.modules.fulfillment.application.dto.production_order_dto import (
    RecordProductionOrderCompletionCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    ScrapProductionPiecesCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import SplitProductionOrderCommand
from src.modules.fulfillment.application.dto.production_order_dto import StartProductionOrderCommand
from src.modules.fulfillment.application.dto.quote_request_dto import AwardLineInput
from src.modules.fulfillment.application.dto.quote_request_dto import AwardQuoteRequestCommand
from src.modules.fulfillment.application.dto.quote_request_dto import AwardSupplierInput
from src.modules.fulfillment.application.dto.source_item_allocation_dto import (
    CreateSourceItemAllocationCommand,
)
from src.modules.fulfillment.application.dto.source_item_allocation_dto import (
    FulfillSourceItemDemandFromStockCommand,
)
from src.modules.fulfillment.application.services.allocation_fill import LineFillRepos
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases.bought_item_demand.cancel_demand_item import (
    CancelDemandItem,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.create_allocation import (
    CreateAllocation,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.create_allocation import (
    DeleteAllocation,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.create_allocation import (
    UpdateAllocation,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.fulfill_from_stock import (
    FulfillDemandFromStock,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.update_demand_item_status import (
    UpdateDemandItemStatus,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.cancel_demand import (
    CancelImpactCollector,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.cancel_demand import (
    CancelMadeItemDemand,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.update_demand_item_status import (
    UpdateDemandItemStatus as UpdateMadeItemDemandStatus,
)
from src.modules.fulfillment.application.use_cases.order.cancel_order_item import CancelOrderItem
from src.modules.fulfillment.application.use_cases.order.close_order_item_short import (
    CloseOrderItemShort,
)
from src.modules.fulfillment.application.use_cases.order.correct_order_item_delivery import (
    CorrectOrderItemDelivery,
)
from src.modules.fulfillment.application.use_cases.order.create_order import CreateOrder
from src.modules.fulfillment.application.use_cases.order.create_order_item import CreateOrderItem
from src.modules.fulfillment.application.use_cases.order.mark_order_item_ordered import (
    MarkOrderItemOrdered,
)
from src.modules.fulfillment.application.use_cases.order.mark_order_item_ordered import (
    MarkOrderItemRequested,
)
from src.modules.fulfillment.application.use_cases.order.move_order_item import MoveOrderItem
from src.modules.fulfillment.application.use_cases.order.process_order_item_delivery import (
    DeliverAllOrderItems,
)
from src.modules.fulfillment.application.use_cases.order.process_order_item_delivery import (
    ProcessOrderItemDelivery,
)
from src.modules.fulfillment.application.use_cases.order.reopen_order_item import ReopenOrderItem
from src.modules.fulfillment.application.use_cases.order.update_order import CancelOrder
from src.modules.fulfillment.application.use_cases.order.update_order import RequestOrder
from src.modules.fulfillment.application.use_cases.order.update_order import SubmitOrder
from src.modules.fulfillment.application.use_cases.order.update_order_item import UpdateOrderItem
from src.modules.fulfillment.application.use_cases.production_lot.assign_external_position import (
    AssignExternalPosition,
)
from src.modules.fulfillment.application.use_cases.production_lot.assign_external_position import (
    UnassignExternalPosition,
)
from src.modules.fulfillment.application.use_cases.production_lot.create_lot import CreateLot
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import CancelLot
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import CompleteLot
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import HoldLot
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import ResumeLot
from src.modules.fulfillment.application.use_cases.production_lot.record_lot_position_provision import (
    RecordLotPositionProvision,
)
from src.modules.fulfillment.application.use_cases.production_order.assign_internal_position import (
    AssignInternalPosition,
)
from src.modules.fulfillment.application.use_cases.production_order.merge_production_orders import (
    MergeProductionOrders,
)
from src.modules.fulfillment.application.use_cases.production_order.production_order_lifecycle import (
    CancelProductionOrder,
)
from src.modules.fulfillment.application.use_cases.production_order.production_order_lifecycle import (
    PauseProductionOrder,
)
from src.modules.fulfillment.application.use_cases.production_order.production_order_lifecycle import (
    StartProductionOrder,
)
from src.modules.fulfillment.application.use_cases.production_order.record_production_order_completion import (
    RecordProductionOrderCompletion,
)
from src.modules.fulfillment.application.use_cases.production_order.reverse_production_order_completion import (
    ReverseProductionOrderCompletion,
)
from src.modules.fulfillment.application.use_cases.production_order.scrap_production_pieces import (
    ScrapProductionPieces,
)
from src.modules.fulfillment.application.use_cases.production_order.split_production_order import (
    SplitProductionOrder,
)
from src.modules.fulfillment.application.use_cases.quote_request.award_quote_request import (
    AwardQuoteRequest,
)
from src.modules.fulfillment.application.use_cases.quote_request.award_quote_request import (
    AwardRepositories,
)
from src.modules.fulfillment.application.use_cases.source_item_allocation.create_allocation import (
    CreateSourceItemAllocation,
)
from src.modules.fulfillment.application.use_cases.source_item_allocation.fulfill_from_stock import (
    FulfillSourceItemDemandFromStock,
)
from src.modules.fulfillment.application.use_cases.source_item_demand.cancel_source_item_demand import (
    CancelSourceItemDemand,
)
from src.modules.fulfillment.application.use_cases.source_item_demand.update_source_item_demand_status import (
    UpdateSourceItemDemandStatus,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.quote_request import Quote
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequest
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequestLine
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequestLineDemand
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequestSupplier
from src.modules.fulfillment.domain.services.lifecycle.snapshot import LifecycleSnapshot
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.quote_request_status import (
    QuoteRequestDemandFamily,
)
from src.modules.fulfillment.domain.value_objects.quote_request_status import QuoteRequestStatus
from src.modules.fulfillment.domain.value_objects.rejection_after_receipt import (
    RejectionAfterReceipt,
)
from src.modules.fulfillment.domain.value_objects.rejection_outcome import RejectionOutcome
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import DomainError
from src.modules.platform.domain.value_objects.permission import Permission
from src.shared_kernel.domain.services.clock import now_utc
from tests.factories import make_user
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler_harness
from tests.unit.lifecycle.fake_reconciler import give_order_facts
from tests.unit.production_lot._floor import Floor
from tests.unit.production_lot._helpers import make_demand
from tests.unit.production_lot._helpers import make_machine
from tests.unit.production_lot._helpers import make_order as make_supplier_order
from tests.unit.production_lot._helpers import make_source_item
from tests.unit.production_lot._helpers import make_source_item_demand
from tests.unit.production_lot.fakes import FakeAdminSettingsRepository
from tests.unit.production_lot.fakes import FakeOrderItemRepository
from tests.unit.production_lot.fakes import FakeOrderRepository
from tests.unit.production_lot.fakes import FakeProductionLotRepository
from tests.unit.production_lot.fakes import FakeProductionMachineRepository
from tests.unit.production_lot.fakes import FakeProjectRepository
from tests.unit.production_lot.fakes import FakeSourceItemAllocationRepository
from tests.unit.production_lot.fakes import FakeSourceItemRepository
from tests.unit.production_lot.fakes import FakeUnitOfWork
from tests.unit.production_order.fakes import FakeProductionOrderInterruptionRepository
from tests.unit.test_bought_item_allocation_use_cases import FakeAllocationRepository
from tests.unit.test_bought_item_allocation_use_cases import FakeCatalogueRepository
from tests.unit.test_bought_item_allocation_use_cases import FakeDemandRepository
from tests.unit.test_bought_item_allocation_use_cases import make_bought_item
from tests.unit.test_bought_item_allocation_use_cases import make_demand as make_bought_demand
from tests.unit.test_bought_item_allocation_use_cases import make_order_item as make_bought_line
from tests.unit.test_bought_item_delivery import FakeDeliveryRepository

ORDER_ID = 1
# A second supplier order, empty and draft, that lines may be moved to.
OTHER_ORDER_ID = 2
ACTOR = make_user(
    id=7,
    permissions=[
        Permission.WRITE_LOTS,
        Permission.MANAGE_LOTS,
        Permission.WRITE_PRODUCTION_ORDERS,
        Permission.MANAGE_PRODUCTION_ORDERS,
        Permission.WRITE_INSPECTIONS,
        Permission.WRITE_ORDERS,
        Permission.MANAGE_ORDERS,
        Permission.RECEIVE_DELIVERIES,
        Permission.WRITE_ALLOCATIONS,
        Permission.WRITE_DEMAND_ITEMS,
        Permission.MANAGE_DEMAND_ITEMS,
    ],
)

type Call = Callable[[LifecycleReconciler], Awaitable[object]]


class WorldOrderItems(FakeOrderItemRepository):
    """The lot tests' order line fake with the reads the order and
    allocation use cases add. Every read stamps a MADE line with the lot of
    its position, as the repository's read does."""

    def __init__(self, lots: FakeProductionLotRepository) -> None:
        super().__init__()
        self._lots = lots
        # The quote request of each request line, by line id, for the
        # request a line's award came from.
        self.quote_request_of_line: dict[int, int] = {}

    def _stamped[T](self, found: T) -> T:
        positions = self._lots._positions
        for item in self._items.values():
            position = positions.get(item.lot_position_id) if item.lot_position_id else None
            item.lot_id = position.lot_id if position is not None else None
            item.quote_request_id = (
                self.quote_request_of_line.get(item.quote_request_line_id)
                if item.quote_request_line_id is not None
                else None
            )
        return found

    async def get_by_id(self, id: int) -> OrderItem | None:
        return self._stamped(await super().get_by_id(id))

    async def get_by_id_for_update(self, id: int) -> OrderItem | None:
        return self._stamped(await super().get_by_id_for_update(id))

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[OrderItem]:
        return self._stamped(await super().get_by_ids(ids))

    async def get_by_order_id(self, order_id: int) -> list[OrderItem]:
        return self._stamped(await super().get_by_order_id(order_id))

    async def get_by_order_ids(self, order_ids: list[int]) -> list[OrderItem]:
        return self._stamped(await super().get_by_order_ids(order_ids))

    async def get_by_lot_position_id(self, lot_position_id: int) -> OrderItem | None:
        return self._stamped(await super().get_by_lot_position_id(lot_position_id))

    async def get_by_lot_position_ids(
        self, lot_position_ids: list[int], *, refresh: bool = False
    ) -> list[OrderItem]:
        return self._stamped(await super().get_by_lot_position_ids(lot_position_ids))

    async def get_by_bought_item_id(self, bought_item_id: int) -> list[OrderItem]:
        return self._stamped(
            [i for i in self._items.values() if i.bought_item_id == bought_item_id]
        )

    async def get_by_source_item_id(self, source_item_id: int) -> list[OrderItem]:
        return self._stamped(
            [i for i in self._items.values() if i.source_item_id == source_item_id]
        )

    async def save(self, item: OrderItem) -> OrderItem:
        """Saves as the base fake does, and never hands out the id of a line
        seeded with an explicit one."""
        saved = await super().save(item)
        self._next_id = max(self._next_id, saved.id + 1)
        return saved


class WorldQuoteRequests:
    """The quote requests of the world. A read carries on each line the
    order line its award created and whether one is still live, from the
    world's order lines, as the SQL mapper reads them. `order_lines` reads
    the world's current lines, so a restored world is read as restored."""

    def __init__(self, order_lines: Callable[[], list[OrderItem]]) -> None:
        self._order_lines = order_lines
        self.requests: dict[int, QuoteRequest] = {}

    def view(self, request: QuoteRequest) -> QuoteRequest:
        view = copy.deepcopy(request)
        lines = self._order_lines()
        for line in view.lines:
            awarded = [i for i in lines if i.quote_request_line_id == line.id]
            newest = max(awarded, key=lambda i: i.id, default=None)
            line.order_item_id = newest.id if newest is not None else None
            line.order_id = newest.order_id if newest is not None else None
            line.award_live = any(i.canceled_at is None for i in awarded)
        return view

    async def get_by_id(self, id: int) -> QuoteRequest | None:
        request = self.requests.get(id)
        return self.view(request) if request is not None else None

    async def get_by_id_for_update(self, id: int) -> QuoteRequest | None:
        return await self.get_by_id(id)

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[QuoteRequest]:
        return [self.view(self.requests[i]) for i in ids if i in self.requests]

    async def lock_for_update(self, ids: list[int]) -> None:
        return None

    async def save(self, request: QuoteRequest) -> QuoteRequest:
        """Writes the request's own fields; its lines stay as stored."""
        stored = copy.deepcopy(request)
        stored.lines = self.requests[request.id].lines
        self.requests[request.id] = stored
        return self.view(stored)

    async def save_line(self, line: QuoteRequestLine) -> QuoteRequestLine:
        stored = self.requests[line.quote_request_id]
        stored.lines = [copy.deepcopy(line) if row.id == line.id else row for row in stored.lines]
        return copy.deepcopy(line)


class WorldSourceAllocations(FakeSourceItemAllocationRepository):
    """The lot tests' source allocation fake with the totals the source
    allocation use cases read."""

    async def get_allocated_quantity(self, demand_item_id: int) -> float:
        return sum(a.quantity for a in self.allocations if a.demand_item_id == demand_item_id)

    async def get_allocated_quantities_for_order_items(
        self, order_item_ids: list[int]
    ) -> dict[int, float]:
        return {i: await self.get_allocated_quantity_for_order_item(i) for i in order_item_ids}

    async def get_allocated_quantity_for_order_item(self, order_item_id: int) -> float:
        return sum(a.quantity for a in self.allocations if a.order_item_id == order_item_id)


class WorldLots(FakeProductionLotRepository):
    """The lot tests' lot fake, reading a step without a fabrication method
    (an inspection) as needing no machine, as the repository's join does."""

    def _hydrate(self, lot: ProductionLot) -> ProductionLot:
        for step in self._steps.values():
            if step.fabrication_method_id is None:
                step.fabrication_method_requires_machine = False
        return super()._hydrate(lot)


# The bought and raw material lines and demands are in metres, so their
# fractional quantities are allowed; lots always count whole pieces.
MEASURED_UNIT = "M"


@dataclass(frozen=True)
class Spec:
    """The shape of a world: the lot's steps, its quantity, the made demands
    it covers (each fully allocated to it), the bought lines of the supplier
    order and the bought demands of their item, and an optional SOURCE line
    for the lot's raw material."""

    steps: int = 2
    inspection_last: bool = False
    lot_quantity: float = 6.0
    made_demands: tuple[float, ...] = ()
    bought_lines: tuple[float, ...] = (4.0,)
    bought_demands: tuple[float, ...] = (2.0,)
    # A SOURCE line of the lot's raw material on the supplier order, of this
    # quantity, which the raw material demand may be allocated to.
    source_line: float | None = None
    # A second lot of this quantity, which the first made demand shares with
    # the lot one piece at a time and on which a made demand of a lower id,
    # its neighbour, has one piece: a writer on the first lot moves what
    # reaches the neighbour. Needs a made demand.
    neighbour_lot: float | None = None


@dataclass
class Outcome:
    """What one request did: refused, or the events it published."""

    refused: DomainError | None
    published: list[object] = field(default_factory=list)


class World:
    def __init__(self, spec: Spec) -> None:
        self.spec = spec
        # The World method the model called for the last request, the
        # trigger of the status changes it made.
        self.last_request = ""
        self.floor = Floor(positions=spec.steps, inspection_last=spec.inspection_last)
        self.floor.lots = WorldLots()
        self.floor.lots.production_orders = self.floor.orders._orders
        self.floor.planner = ACTOR
        self.floor.operator = ACTOR
        self.floor.order_items = WorldOrderItems(self.floor.lots)
        self.floor.source_allocations = WorldSourceAllocations()
        self.floor.parent_orders = FakeOrderRepository(
            [
                give_order_facts(make_supplier_order(id=ORDER_ID)),
                give_order_facts(make_supplier_order(id=OTHER_ORDER_ID)),
            ]
        )
        self.lines: WorldOrderItems = self.floor.order_items
        self.orders: FakeOrderRepository = self.floor.parent_orders
        self.deliveries = FakeDeliveryRepository()
        self.bought_demands = FakeDemandRepository()
        self.bought_allocations = FakeAllocationRepository()
        self.catalogue = FakeCatalogueRepository([make_bought_item()])
        self.machines = FakeProductionMachineRepository([_machine()])
        self.quote_requests = WorldQuoteRequests(lambda: list(self.lines._items.values()))
        self.lot_id = 0
        asyncio.run(self._seed())

    async def _seed(self) -> None:
        spec = self.spec
        demands = [
            (100 + i, quantity, MadeItemDemandStatus.OPEN)
            for i, quantity in enumerate(spec.made_demands, start=1)
        ]
        lot = await self.floor.lot(spec.lot_quantity, demands=demands)
        self.lot_id = lot.id
        input_demand = make_source_item_demand(id=lot.input_demand_id or 0, lot_id=lot.id)
        input_demand.quantity = spec.lot_quantity
        input_demand.unit = MEASURED_UNIT
        await self.floor.source_demands.save(input_demand)
        for i, quantity in enumerate(spec.bought_lines, start=1):
            line = make_bought_line(
                id=i,
                order_id=ORDER_ID,
                status=OrderItemStatus.PENDING,
                quantity=quantity,
            )
            line.unit = MEASURED_UNIT
            line.position = i
            await self.lines.save(line)
        if spec.source_line is not None:
            line = make_bought_line(
                id=len(spec.bought_lines) + 1,
                order_id=ORDER_ID,
                status=OrderItemStatus.PENDING,
                quantity=spec.source_line,
            )
            line.unit = MEASURED_UNIT
            line.line_type = OrderLineType.SOURCE
            line.bought_item_id = None
            line.source_item_id = input_demand.source_item_id
            line.position = line.id
            await self.lines.save(line)
        for i, quantity in enumerate(spec.bought_demands, start=1):
            demand = make_bought_demand(id=i, quantity=quantity)
            demand.unit = MEASURED_UNIT
            await self.bought_demands.save(demand)
        if spec.neighbour_lot is not None and spec.made_demands:
            await self._seed_neighbour_lot(spec.neighbour_lot)
        reconciler = self.reconciler()
        self.touch_everything(reconciler)
        await reconciler.run(ACTOR, datetime.now(UTC))

    async def _seed_neighbour_lot(self, quantity: float) -> None:
        """The second lot of Spec.neighbour_lot: its own made demand #99 of
        one piece, and one more piece of the first made demand #101."""
        floor = self.floor
        lot = await floor.lot(quantity, demands=[(99, 1.0, MadeItemDemandStatus.OPEN)])
        input_demand = make_source_item_demand(id=lot.input_demand_id or 0, lot_id=lot.id)
        input_demand.quantity = quantity
        input_demand.unit = MEASURED_UNIT
        await floor.source_demands.save(input_demand)
        shared = floor.made_demands._demands[101]
        shared.quantity += 1.0
        await floor.made_allocations.save(
            MadeItemDemandAllocation(demand_item_id=101, lot_id=lot.id, quantity=1.0)
        )

    # ── Reads ────────────────────────────────────────────────────────

    def lots(self) -> list[ProductionLot]:
        lots = self.floor.lots
        return [lots._hydrate(lots._lots[i]) for i in sorted(lots._lots)]

    @property
    def lot(self) -> ProductionLot:
        return self.floor.lots._hydrate(self.floor.lots._lots[self.lot_id])

    def positions(self) -> list[LotPosition]:
        return [p for lot in self.lots() for p in lot.positions]

    def production_orders(self) -> list[ProductionOrder]:
        return sorted(self.floor.orders._orders.values(), key=lambda o: o.id)

    def order_lines(self) -> list[OrderItem]:
        return sorted(self.lines._items.values(), key=lambda i: i.id)

    def made_lines(self) -> list[OrderItem]:
        return [i for i in self.order_lines() if i.line_type == OrderLineType.MADE.value]

    def snapshot(self) -> LifecycleSnapshot:
        """The whole world, copied, as the lifecycle loader would read it."""
        floor = self.floor
        return copy.deepcopy(
            LifecycleSnapshot(
                lots={lot.id: lot for lot in self.lots()},
                production_orders=dict(floor.orders._orders),
                order_items=dict(self.lines._items),
                orders=dict(self.orders._orders),
                bought_demands=dict(self.bought_demands._demands),
                made_demands=dict(floor.made_demands._demands),
                source_demands=dict(floor.source_demands._demands),
                bought_allocations=tuple(self.bought_allocations._allocations),
                made_allocations=tuple(floor.made_allocations._allocations),
                source_allocations=tuple(floor.source_allocations.allocations),
                quote_requests={
                    i: self.quote_requests.view(r) for i, r in self.quote_requests.requests.items()
                },
            )
        )

    def status_table(self) -> dict[str, str]:
        """The stored status of every aggregate, keyed `kind#id`; a position
        reads `status/kind`. Each status is its plain value."""
        table: dict[str, str] = {}
        for lot in self.lots():
            table[f"lot#{lot.id}"] = str(lot.status.value)
            for p in lot.positions:
                table[f"position#{p.id}"] = f"{p.status.value}/{p.kind.value}"
        for o in self.production_orders():
            table[f"production_order#{o.id}"] = str(o.status.value)
        for order in self.orders._orders.values():
            table[f"order#{order.id}"] = str(order.status.value)
        for line in self.order_lines():
            table[f"line#{line.id}"] = str(line.status.value)
        for d in self.bought_demands._demands.values():
            table[f"bought_demand#{d.id}"] = str(d.status.value)
        for d in self.floor.made_demands._demands.values():
            table[f"made_demand#{d.id}"] = str(d.status.value)
        for d in self.floor.source_demands._demands.values():
            table[f"source_demand#{d.id}"] = str(d.status.value)
        for r in self.quote_requests.requests.values():
            table[f"quote_request#{r.id}"] = str(r.status.value)
        return table

    # ── Requests ─────────────────────────────────────────────────────

    def repos(self) -> tuple[Any, ...]:
        """Every fake a request may write, copied and restored together so
        the references between them survive."""
        floor = self.floor
        return (
            floor.lots,
            floor.orders,
            floor.made_demands,
            floor.made_allocations,
            floor.source_demands,
            floor.source_allocations,
            self.lines,
            self.orders,
            self.deliveries,
            self.bought_demands,
            self.bought_allocations,
            self.quote_requests,
        )

    def reconciler(self) -> LifecycleReconciler:
        """A reconciler of every aggregate over the world's fakes, publishing
        on the world's bus."""
        floor = self.floor
        return demand_reconciler_harness(
            bought_demands=self.bought_demands,
            bought_allocations=self.bought_allocations,
            made_demands=floor.made_demands,
            made_allocations=floor.made_allocations,
            source_demands=floor.source_demands,
            source_allocations=floor.source_allocations,
            order_items=self.lines,
            orders=self.orders,
            lots=floor.lots,
            production_orders=floor.orders,
            quote_requests=self.quote_requests,
            bus=floor.bus,
        ).reconciler

    def touch_everything(self, reconciler: LifecycleReconciler) -> None:
        from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import (
            LifecycleAggregate,
        )

        reconciler.touch_lots([lot.id for lot in self.lots()])
        reconciler.touch_production_orders([o.id for o in self.production_orders()])
        reconciler.touch_orders(list(self.orders._orders))
        reconciler.touch_order_items([i.id for i in self.order_lines()])
        reconciler.touch_demands(
            LifecycleAggregate.BOUGHT_DEMANDS, list(self.bought_demands._demands)
        )
        reconciler.touch_demands(
            LifecycleAggregate.MADE_DEMANDS, list(self.floor.made_demands._demands)
        )
        reconciler.touch_demands(
            LifecycleAggregate.SOURCE_DEMANDS, list(self.floor.source_demands._demands)
        )
        reconciler.touch_quote_requests(list(self.quote_requests.requests))

    def request(self, call: Call) -> Outcome:
        """Runs one request with a reconciler of its own. A domain refusal
        restores every fake as the request's rollback would."""
        self.last_request = self._calling_method()
        saved = copy.deepcopy(tuple(repo.__dict__ for repo in self.repos()))
        self.floor.bus.published.clear()
        try:
            asyncio.run(call(self.reconciler()))
        except DomainError as refused:
            for repo, state in zip(self.repos(), saved, strict=True):
                repo.__dict__.clear()
                repo.__dict__.update(state)
            self.floor.bus.published.clear()
            return Outcome(refused=refused)
        published = list(self.floor.bus.published)
        self.floor.bus.published.clear()
        return Outcome(refused=None, published=published)

    def _calling_method(self) -> str:
        """The outermost method of this world on the stack, the one the
        model called."""
        frame = sys._getframe(1)
        name = ""
        while frame is not None:
            if frame.f_locals.get("self") is self:
                name = frame.f_code.co_name
            frame = frame.f_back
        return name

    def settle(self) -> list[object]:
        """Runs the reconciler over everything and returns what it changed."""
        reconciler = self.reconciler()
        self.touch_everything(reconciler)
        self.floor.bus.published.clear()
        result = asyncio.run(reconciler.run(ACTOR, datetime.now(UTC)))
        self.floor.bus.published.clear()
        return list(result.changes)

    # ── Collaborators ────────────────────────────────────────────────

    def interruptions(self) -> FakeProductionOrderInterruptionRepository:
        return FakeProductionOrderInterruptionRepository(self.floor.orders._orders)

    def fill(self) -> LineFillRepos:
        """Both families' allocations, which an allocation writer reads a
        line's whole fill from."""
        return LineFillRepos(bought=self.bought_allocations, source=self.floor.source_allocations)

    def create_lot(self, reconciler: LifecycleReconciler) -> CreateLot:
        floor = self.floor
        return CreateLot(
            lot_repo=floor.lots,
            made_item_repo=floor.made_items,
            demand_repo=floor.made_demands,
            allocation_repo=floor.made_allocations,
            settings_repo=FakeAdminSettingsRepository(require_qa=False),
            source_item_demand_repo=floor.source_demands,
            order_repo=floor.orders,
            inspection_method_repo=floor.inspection_methods,
            machine_repo=FakeProductionMachineRepository(),
            uow=FakeUnitOfWork(),
            event_bus=floor.bus,
            reconciler=reconciler,
        )

    def delivery(self, reconciler: LifecycleReconciler) -> ProcessOrderItemDelivery:
        floor = self.floor
        return ProcessOrderItemDelivery(
            self.lines,
            self.orders,
            self.deliveries,
            event_bus=floor.bus,
            uow=FakeUnitOfWork(),
            lot_repo=floor.lots,
            made_item_demand_repo=floor.made_demands,
            made_item_allocation_repo=floor.made_allocations,
            source_item_demand_repo=floor.source_demands,
            source_item_allocation_repo=floor.source_allocations,
            bought_item_allocation_repo=self.bought_allocations,
            production_order_repo=floor.orders,
            create_lot=self.create_lot(reconciler),
            reconciler=reconciler,
            interruption_repo=self.interruptions(),
        )

    def cancel_lot(self, reconciler: LifecycleReconciler) -> CancelLot:
        floor = self.floor
        return CancelLot(
            floor.lots,
            floor.orders,
            self.lines,
            self.bought_allocations,
            floor.made_allocations,
            floor.source_demands,
            floor.source_allocations,
            event_bus=floor.bus,
            uow=FakeUnitOfWork(),
            parent_order_repo=self.orders,
            reconciler=reconciler,
            interruption_repo=self.interruptions(),
        )

    def cancel_bought_demand(self, reconciler: LifecycleReconciler) -> CancelDemandItem:
        return CancelDemandItem(
            self.bought_demands,
            self.bought_allocations,
            uow=FakeUnitOfWork(),
            reconciler=reconciler,
        )

    def cancel_made_demand(self, reconciler: LifecycleReconciler) -> CancelMadeItemDemand:
        floor = self.floor
        collector = CancelImpactCollector(
            floor.made_demands,
            floor.made_allocations,
            floor.lots,
            floor.orders,
            self.orders,
            self.lines,
            floor.source_demands,
            floor.source_allocations,
        )
        return CancelMadeItemDemand(
            floor.made_demands,
            floor.made_allocations,
            floor.lots,
            collector,
            self.cancel_lot(reconciler),
            event_bus=floor.bus,
            uow=FakeUnitOfWork(),
            reconciler=reconciler,
        )

    # ── Lot and production order intents ─────────────────────────────

    def assign_internal(self, position_id: int, quantity: float) -> Outcome:
        floor = self.floor
        command = AssignInternalPositionCommand(
            orders=[AssignInternalPositionOrderInput(machine_id=1, quantity=quantity)]
        )
        return self.request(
            lambda r: AssignInternalPosition(
                floor.lots,
                self.machines,
                floor.orders,
                FakeAdminSettingsRepository(),
                event_bus=floor.bus,
                uow=FakeUnitOfWork(),
                reconciler=r,
            ).execute(ACTOR, self._lot_of(position_id), position_id, command)
        )

    def assign_external(self, position_id: int, quantity: float | None = None) -> Outcome:
        floor = self.floor
        command = AssignExternalPositionCommand(order_id=ORDER_ID, unit="pcs", quantity=quantity)
        return self.request(
            lambda r: AssignExternalPosition(
                floor.lots,
                floor.made_items,
                self.orders,
                self.lines,
                event_bus=floor.bus,
                uow=FakeUnitOfWork(),
                reconciler=r,
                project_repo=FakeProjectRepository(),
            ).execute(ACTOR, self._lot_of(position_id), position_id, command)
        )

    def record_provision(self, position_id: int, quantity: float) -> Outcome:
        return self.request(
            lambda _r: RecordLotPositionProvision(self.floor.lots, uow=FakeUnitOfWork()).execute(
                ACTOR,
                self._lot_of(position_id),
                position_id,
                RecordLotPositionProvisionCommand(
                    quantity=quantity, provision_date=date(2026, 3, 2)
                ),
            )
        )

    def unassign_external(self, position_id: int) -> Outcome:
        return self.request(
            lambda r: UnassignExternalPosition(
                self.floor.lots, self.lines, uow=FakeUnitOfWork(), reconciler=r
            ).execute(ACTOR, self._lot_of(position_id), position_id)
        )

    def start(self, order_id: int) -> Outcome:
        floor = self.floor
        return self.request(
            lambda r: StartProductionOrder(
                floor.orders,
                floor.lots,
                event_bus=floor.bus,
                uow=FakeUnitOfWork(),
                reconciler=r,
                interruption_repo=self.interruptions(),
            ).execute(ACTOR, order_id, StartProductionOrderCommand())
        )

    def pause(self, order_id: int) -> Outcome:
        floor = self.floor
        return self.request(
            lambda r: PauseProductionOrder(
                floor.orders,
                floor.lots,
                event_bus=floor.bus,
                uow=FakeUnitOfWork(),
                reconciler=r,
                interruption_repo=self.interruptions(),
            ).execute(ACTOR, order_id, PauseProductionOrderCommand())
        )

    def cancel_production_order(self, order_id: int) -> Outcome:
        floor = self.floor
        return self.request(
            lambda r: CancelProductionOrder(
                floor.orders,
                floor.lots,
                event_bus=floor.bus,
                uow=FakeUnitOfWork(),
                reconciler=r,
                interruption_repo=self.interruptions(),
            ).execute(ACTOR, order_id, CancelProductionOrderCommand())
        )

    def complete(
        self,
        order_id: int,
        quantity: float,
        *,
        rejected: float = 0.0,
        rework: float = 0.0,
        scrap: float = 0.0,
    ) -> Outcome:
        """Records `quantity` processed pieces, `rejected` of them rejected
        and disposed as `rework` and `scrap`."""
        floor = self.floor
        command = RecordProductionOrderCompletionCommand(
            quantity=quantity,
            quantity_accepted=quantity - rejected,
            quantity_rejected=rejected,
            quantity_rework=rework,
            quantity_scrap=scrap,
            scrap_reason="tool_breakage" if scrap else None,
            # The day the request runs, which the order was started on.
            completion_date=now_utc().date(),
        )
        return self.request(
            lambda r: RecordProductionOrderCompletion(
                floor.orders,
                floor.lots,
                None,
                event_bus=floor.bus,
                uow=FakeUnitOfWork(),
                reconciler=r,
                made_item_demand_repo=floor.made_demands,
                made_item_allocation_repo=floor.made_allocations,
                create_lot=self.create_lot(r),
                order_item_repo=self.lines,
                parent_order_repo=self.orders,
                interruption_repo=self.interruptions(),
                source_item_demand_repo=floor.source_demands,
                source_item_allocation_repo=floor.source_allocations,
                bought_allocation_repo=self.bought_allocations,
                settings_repo=_TenantSettings(require_qa=False),
            ).execute(ACTOR, order_id, command)
        )

    def scrap(self, order_id: int, quantity: float, *, replace: bool = False) -> Outcome:
        floor = self.floor
        command = ScrapProductionPiecesCommand(
            production_order_id=order_id,
            quantity=quantity,
            reason="tool_breakage",
            create_replacement=replace,
        )
        return self.request(
            lambda r: ScrapProductionPieces(
                floor.orders,
                floor.lots,
                event_bus=floor.bus,
                uow=FakeUnitOfWork(),
                made_item_demand_repo=floor.made_demands,
                made_item_allocation_repo=floor.made_allocations,
                create_lot=self.create_lot(r),
                reconciler=r,
                interruption_repo=self.interruptions(),
                order_item_repo=self.lines,
                parent_order_repo=self.orders,
                source_item_demand_repo=floor.source_demands,
                source_item_allocation_repo=floor.source_allocations,
                bought_allocation_repo=self.bought_allocations,
                settings_repo=_TenantSettings(require_qa=False),
            ).execute(ACTOR, command)
        )

    def reverse_completion(self, order_id: int, completion_id: int) -> Outcome:
        floor = self.floor
        return self.request(
            lambda r: ReverseProductionOrderCompletion(
                floor.orders,
                floor.lots,
                self.lines,
                _TenantSettings(require_qa=False),
                uow=FakeUnitOfWork(),
                event_bus=floor.bus,
                reconciler=r,
            ).execute(ACTOR, order_id, completion_id, "Miscounted")
        )

    def split(self, order_id: int, quantities: list[float]) -> Outcome:
        floor = self.floor
        return self.request(
            lambda r: SplitProductionOrder(
                floor.orders,
                floor.lots,
                _TenantSettings(require_qa=False),
                event_bus=floor.bus,
                uow=FakeUnitOfWork(),
                reconciler=r,
            ).execute(ACTOR, order_id, SplitProductionOrderCommand(quantities=quantities))
        )

    def merge(self, order_ids: list[int]) -> Outcome:
        floor = self.floor
        return self.request(
            lambda r: MergeProductionOrders(
                floor.orders,
                floor.lots,
                event_bus=floor.bus,
                uow=FakeUnitOfWork(),
                reconciler=r,
            ).execute(ACTOR, MergeProductionOrdersCommand(production_order_ids=order_ids))
        )

    def hold(self, lot_id: int) -> Outcome:
        floor = self.floor
        return self.request(
            lambda r: HoldLot(
                floor.lots,
                floor.orders,
                event_bus=floor.bus,
                uow=FakeUnitOfWork(),
                reconciler=r,
                interruption_repo=self.interruptions(),
            ).execute(ACTOR, lot_id, HoldLotCommand(reason="Material check"))
        )

    def resume_lot(self, lot_id: int) -> Outcome:
        floor = self.floor
        return self.request(
            lambda r: ResumeLot(
                floor.lots,
                floor.orders,
                event_bus=floor.bus,
                uow=FakeUnitOfWork(),
                reconciler=r,
                interruption_repo=self.interruptions(),
            ).execute(ACTOR, lot_id)
        )

    def cancel_lot_request(self, lot_id: int) -> Outcome:
        return self.request(
            lambda r: self.cancel_lot(r).execute(
                ACTOR, lot_id, CancelLotCommand(reason="Customer dropped it")
            )
        )

    def force_complete(self, lot_id: int) -> Outcome:
        floor = self.floor
        return self.request(
            lambda r: CompleteLot(
                floor.lots,
                floor.orders,
                self.lines,
                event_bus=floor.bus,
                uow=FakeUnitOfWork(),
                parent_order_repo=self.orders,
                made_item_demand_repo=floor.made_demands,
                made_item_allocation_repo=floor.made_allocations,
                source_item_demand_repo=floor.source_demands,
                source_item_allocation_repo=floor.source_allocations,
                bought_allocation_repo=self.bought_allocations,
                reconciler=r,
                interruption_repo=self.interruptions(),
            ).execute(ACTOR, lot_id, CompleteLotCommand())
        )

    # ── Order intents ────────────────────────────────────────────────

    def request_order(self) -> Outcome:
        return self.request(
            lambda r: RequestOrder(
                self.orders,
                event_bus=self.floor.bus,
                uow=FakeUnitOfWork(),
                reconciler=r,
                order_item_repo=self.lines,
            ).execute(ACTOR, ORDER_ID)
        )

    def submit_order(self) -> Outcome:
        return self.request(
            lambda r: SubmitOrder(
                self.orders,
                event_bus=self.floor.bus,
                uow=FakeUnitOfWork(),
                reconciler=r,
                order_item_repo=self.lines,
            ).execute(ACTOR, ORDER_ID)
        )

    def cancel_order(self) -> Outcome:
        return self.request(
            lambda r: CancelOrder(
                self.orders,
                self.lines,
                self.bought_allocations,
                event_bus=self.floor.bus,
                uow=FakeUnitOfWork(),
                reconciler=r,
                source_item_allocation_repo=self.floor.source_allocations,
            ).execute(ACTOR, ORDER_ID)
        )

    def deliver_all(self, losing: int | None = None) -> Outcome:
        """Delivers every line of the order in full, `losing` one piece of
        the line named so at receipt."""
        rejections = (
            [
                DeliveryRejectionInput(
                    order_item_id=losing,
                    quantity_rejected=1.0,
                    rejection_reason="supplier_damage",
                    rejection_outcome="lost",
                    create_replacement=False,
                )
            ]
            if losing is not None
            else None
        )
        return self.request(
            lambda r: DeliverAllOrderItems(
                self.orders,
                self.lines,
                self.delivery(r),
                event_bus=self.floor.bus,
                uow=FakeUnitOfWork(),
                reconciler=r,
            ).execute(ACTOR, ORDER_ID, rejections=rejections)
        )

    def mark_requested(self, line_id: int) -> Outcome:
        return self.request(
            lambda r: MarkOrderItemRequested(
                self.lines, self.orders, uow=FakeUnitOfWork(), reconciler=r
            ).execute(ACTOR, self.order_of(line_id), line_id)
        )

    def mark_ordered(self, line_id: int) -> Outcome:
        return self.request(
            lambda r: MarkOrderItemOrdered(
                self.lines, self.orders, uow=FakeUnitOfWork(), reconciler=r
            ).execute(ACTOR, self.order_of(line_id), line_id)
        )

    def deliver(
        self,
        line_id: int,
        accepted: float | None,
        *,
        rejected: float = 0.0,
        outcome: str | None = None,
    ) -> Outcome:
        """Delivers `accepted` pieces (None: what the line awaits) and
        rejects `rejected` with `outcome` (lost or redeliver)."""
        return self.request(
            lambda r: self.delivery(r).execute(
                ACTOR,
                line_id,
                quantity=accepted,
                quantity_rejected=rejected,
                rejection_reason="supplier_damage" if rejected else None,
                rejection_outcome=outcome if rejected else None,
                create_replacement=False,
            )
        )

    def cancel_line(self, line_id: int) -> Outcome:
        return self.request(
            lambda r: CancelOrderItem(
                self.orders,
                self.lines,
                self.bought_allocations,
                uow=FakeUnitOfWork(),
                reconciler=r,
                source_item_allocation_repo=self.floor.source_allocations,
            ).execute(ACTOR, self.order_of(line_id), line_id)
        )

    def close_short(self, line_id: int) -> Outcome:
        return self.request(
            lambda r: CloseOrderItemShort(
                self.orders,
                self.lines,
                self.bought_allocations,
                uow=FakeUnitOfWork(),
                reconciler=r,
                source_item_allocation_repo=self.floor.source_allocations,
            ).execute(ACTOR, self.order_of(line_id), line_id)
        )

    def reopen(self, line_id: int) -> Outcome:
        """Reopens a line closed short, with its quantity before the close."""
        return self.request(
            lambda r: ReopenOrderItem(
                self.orders,
                self.lines,
                project_repo=FakeProjectRepository(),
                uow=FakeUnitOfWork(),
                reconciler=r,
            ).execute(ACTOR, self.order_of(line_id), line_id)
        )

    def add_made_demand(self, demand_id: int, quantity: float) -> None:
        """An open made demand of the lot's item that no lot covers yet."""
        asyncio.run(
            self.floor.made_demands.save(
                make_demand(id=demand_id, quantity=quantity, status=MadeItemDemandStatus.OPEN)
            )
        )

    def create_lot_for_demand(self, demand_id: int, quantity: float) -> Outcome:
        """A new lot of the made item that covers `quantity` of the demand."""
        return self.request(
            lambda r: self.create_lot(r).execute(
                ACTOR,
                CreateLotCommand(
                    made_item_id=1,
                    project_id=1,
                    quantity=quantity,
                    demand_allocations=[
                        LotDemandAllocationInput(demand_item_id=demand_id, quantity=quantity)
                    ],
                ),
            )
        )

    def move(self, line_id: int, target_order_id: int) -> Outcome:
        source = self.lines._items[line_id].order_id
        return self.request(
            lambda r: MoveOrderItem(
                self.orders, self.lines, uow=FakeUnitOfWork(), reconciler=r
            ).execute(ACTOR, source, line_id, target_order_id)
        )

    def correct(
        self, line_id: int, row_id: int, quantity: float, *, rejected_as: str | None = None
    ) -> Outcome:
        """Takes back `quantity` accepted pieces of the row as a miscount, or
        with `rejected_as` (lost or redeliver) as pieces rejected after
        receipt."""
        rejection = (
            RejectionAfterReceipt(reason="transport_damage", outcome=RejectionOutcome(rejected_as))
            if rejected_as is not None
            else None
        )
        return self.request(
            lambda r: CorrectOrderItemDelivery(
                self.orders,
                self.lines,
                self.deliveries,
                self.bought_allocations,
                self.bought_demands,
                uow=FakeUnitOfWork(),
                reconciler=r,
                source_item_allocation_repo=self.floor.source_allocations,
                source_item_demand_repo=self.floor.source_demands,
                event_bus=self.floor.bus,
            ).execute(
                ACTOR,
                self.order_of(line_id),
                line_id,
                row_id,
                quantity,
                None if rejection is not None else "Counted twice",
                rejection=rejection,
            )
        )

    # ── Demand intents ───────────────────────────────────────────────

    def allocate(self, demand_id: int, line_id: int, quantity: float) -> Outcome:
        command = CreateAllocationCommand(
            demand_item_id=demand_id, order_item_id=line_id, quantity=quantity
        )
        return self.request(
            lambda r: CreateAllocation(
                self.bought_allocations,
                self.bought_demands,
                self.lines,
                uow=FakeUnitOfWork(),
                reconciler=r,
                fill_repos=self.fill(),
            ).execute(ACTOR, command)
        )

    def release(self, demand_id: int, line_id: int) -> Outcome:
        return self.request(
            lambda r: DeleteAllocation(
                self.bought_allocations,
                self.bought_demands,
                self.lines,
                uow=FakeUnitOfWork(),
                reconciler=r,
                fill_repos=self.fill(),
            ).execute(ACTOR, demand_id, line_id)
        )

    def take_from_stock(self, demand_id: int, quantity: float) -> Outcome:
        command = FulfillFromStockCommand(demand_item_id=demand_id, quantity=quantity)
        return self.request(
            lambda r: FulfillDemandFromStock(
                self.bought_demands,
                self.bought_allocations,
                self.lines,
                uow=FakeUnitOfWork(),
                reconciler=r,
            ).execute(ACTOR, command)
        )

    def cancel_bought_demand_request(self, demand_id: int) -> Outcome:
        return self.request(lambda r: self.cancel_bought_demand(r).execute(ACTOR, demand_id))

    def fulfil_bought_demand(self, demand_id: int) -> Outcome:
        return self.request(
            lambda r: UpdateDemandItemStatus(
                self.bought_demands,
                self.cancel_bought_demand(r),
                uow=FakeUnitOfWork(),
                reconciler=r,
                allocation_repo=self.bought_allocations,
                source_allocation_repo=self.floor.source_allocations,
                order_item_repo=self.lines,
            ).execute(ACTOR, demand_id, "fulfilled")
        )

    def cancel_made_demand_request(self, demand_id: int) -> Outcome:
        return self.request(lambda r: self.cancel_made_demand(r).execute(ACTOR, demand_id))

    def fulfil_made_demand(self, demand_id: int) -> Outcome:
        return self.request(
            lambda r: UpdateMadeItemDemandStatus(
                self.floor.made_demands,
                self.cancel_made_demand(r),
                uow=FakeUnitOfWork(),
                reconciler=r,
            ).execute(ACTOR, demand_id, "fulfilled")
        )

    def update_allocation(self, demand_id: int, line_id: int, quantity: float) -> Outcome:
        return self.request(
            lambda r: UpdateAllocation(
                self.bought_allocations,
                self.bought_demands,
                self.lines,
                uow=FakeUnitOfWork(),
                reconciler=r,
                fill_repos=self.fill(),
            ).execute(ACTOR, demand_id, line_id, UpdateAllocationCommand(quantity=quantity))
        )

    def edit_line_quantity(self, line_id: int, quantity: float) -> Outcome:
        line = self.lines._items[line_id]
        command = UpdateOrderItemCommand(quantity=quantity, unit=line.unit)
        return self.request(
            lambda r: UpdateOrderItem(
                order_item_repo=self.lines,
                order_repo=self.orders,
                catalogue_repo=self.catalogue,
                allocation_repo=self.bought_allocations,
                demand_repo=self.bought_demands,
                lot_repo=self.floor.lots,
                production_order_repo=self.floor.orders,
                uow=FakeUnitOfWork(),
                reconciler=r,
                source_allocation_repo=self.floor.source_allocations,
                project_repo=FakeProjectRepository(),
            ).execute(ACTOR, self.order_of(line_id), line_id, command)
        )

    def allocate_source(self, demand_id: int, line_id: int, quantity: float) -> Outcome:
        floor = self.floor
        command = CreateSourceItemAllocationCommand(
            demand_item_id=demand_id, order_item_id=line_id, quantity=quantity
        )
        return self.request(
            lambda r: CreateSourceItemAllocation(
                floor.source_allocations,
                floor.source_demands,
                self.lines,
                uow=FakeUnitOfWork(),
                reconciler=r,
                fill_repos=self.fill(),
            ).execute(ACTOR, command)
        )

    def source_from_stock(self, demand_id: int, quantity: float) -> Outcome:
        floor = self.floor
        command = FulfillSourceItemDemandFromStockCommand(
            demand_item_id=demand_id, quantity=quantity
        )
        return self.request(
            lambda r: FulfillSourceItemDemandFromStock(
                floor.source_demands,
                floor.source_allocations,
                self.lines,
                uow=FakeUnitOfWork(),
                reconciler=r,
            ).execute(ACTOR, command)
        )

    def cancel_source_demand(self, reconciler: LifecycleReconciler) -> CancelSourceItemDemand:
        floor = self.floor
        return CancelSourceItemDemand(
            floor.source_demands,
            floor.lots,
            floor.source_allocations,
            uow=FakeUnitOfWork(),
            reconciler=reconciler,
            cancel_lot=self.cancel_lot(reconciler),
        )

    def cancel_source_demand_request(self, demand_id: int, *, cancel_lot: bool = False) -> Outcome:
        """`cancel_lot` is the choice the cancel takes for a lot the demand
        still feeds: cancel it too, or leave it waiting on raw material."""
        return self.request(
            lambda r: self.cancel_source_demand(r).execute(ACTOR, demand_id, cancel_lot=cancel_lot)
        )

    def fulfil_source_demand(self, demand_id: int) -> Outcome:
        return self.request(
            lambda r: UpdateSourceItemDemandStatus(
                self.floor.source_demands,
                self.cancel_source_demand(r),
                uow=FakeUnitOfWork(),
                reconciler=r,
                allocation_repo=self.floor.source_allocations,
                bought_allocation_repo=self.bought_allocations,
                order_item_repo=self.lines,
            ).execute(ACTOR, demand_id, "fulfilled")
        )

    # ── Quote requests ───────────────────────────────────────────────

    def quote_request(self, *, source_share: float, position_id: int) -> QuoteRequest:
        """A sent request to the supplier of the supplier order with a SOURCE
        line for the lot's raw material, sharing `source_share` of its
        demand, and a MADE line for the position, both quoted."""
        lot = self.lot
        position = self.floor.lots._positions[position_id]
        request_id = len(self.quote_requests.requests) + 1
        source_line_id, made_line_id = request_id * 10 + 1, request_id * 10 + 2
        input_demand = self.floor.source_demands._demands[lot.input_demand_id or 0]
        now = datetime(2026, 3, 1, tzinfo=UTC)
        lines = [
            QuoteRequestLine(
                id=source_line_id,
                quote_request_id=request_id,
                position=1,
                line_type=OrderLineType.SOURCE,
                quantity=source_share,
                unit=MEASURED_UNIT,
                created=now,
                project_id=lot.project_id,
                source_item_id=input_demand.source_item_id,
                demands=[
                    QuoteRequestLineDemand(
                        id=1,
                        line_id=source_line_id,
                        family=QuoteRequestDemandFamily.SOURCE,
                        demand_item_id=input_demand.id,
                        quantity=source_share,
                    )
                ],
            ),
            QuoteRequestLine(
                id=made_line_id,
                quote_request_id=request_id,
                position=2,
                line_type=OrderLineType.MADE,
                quantity=position.quantity,
                unit="pcs",
                created=now,
                project_id=lot.project_id,
                lot_position_id=position.id,
                lot_id=lot.id,
            ),
        ]
        supplier_id = self.orders._orders[ORDER_ID].supplier_id
        request = QuoteRequest(
            id=request_id,
            request_number=f"RFQ-{request_id}",
            created=now,
            changed=None,
            changes=[],
            status=QuoteRequestStatus.SENT,
            creator_id=ACTOR.id,
            lines=lines,
            suppliers=[
                QuoteRequestSupplier(
                    id=request_id,
                    quote_request_id=request_id,
                    supplier_id=supplier_id,
                    position=1,
                    sent_at=now,
                    quotes=[
                        Quote(id=i, supplier_row_id=request_id, line_id=line.id, unit_price=100)
                        for i, line in enumerate(lines, start=1)
                    ],
                )
            ],
        )
        self.quote_requests.requests[request.id] = request
        for line in lines:
            self.lines.quote_request_of_line[line.id] = request.id
        return copy.deepcopy(request)

    def award(self, request_id: int) -> Outcome:
        """Awards every line of the request to its supplier, onto the
        supplier order."""
        floor = self.floor
        request = self.quote_requests.requests[request_id]
        row = request.suppliers[0]
        command = AwardQuoteRequestCommand(
            awards=[
                AwardLineInput(line_id=line.id, supplier_row_id=row.id) for line in request.lines
            ],
            suppliers=[AwardSupplierInput(supplier_row_id=row.id, target_order_id=ORDER_ID)],
            expected_edit_version=request.edit_version,
        )

        def award(r: LifecycleReconciler) -> Awaitable[object]:
            return AwardQuoteRequest(
                AwardRepositories(
                    requests=self.quote_requests,
                    orders=self.orders,
                    order_items=self.lines,
                    lots=floor.lots,
                    projects=FakeProjectRepository(),
                    bought_demands=self.bought_demands,
                    bought_allocations=self.bought_allocations,
                    source_demands=floor.source_demands,
                    source_allocations=floor.source_allocations,
                ),
                create_order=CreateOrder(
                    self.orders,
                    event_bus=floor.bus,
                    admin_settings_repo=FakeAdminSettingsRepository(),
                    uow=FakeUnitOfWork(),
                ),
                create_order_item=CreateOrderItem(
                    self.lines,
                    self.catalogue,
                    self.orders,
                    self.bought_demands,
                    self.bought_allocations,
                    FakeSourceItemRepository([make_source_item()]),
                    project_repo=FakeProjectRepository(),
                    supplier_repo=SimpleNamespace(),
                    uow=FakeUnitOfWork(),
                    reconciler=r,
                    source_demand_repo=floor.source_demands,
                    source_allocation_repo=floor.source_allocations,
                ),
                assign_external=AssignExternalPosition(
                    floor.lots,
                    floor.made_items,
                    self.orders,
                    self.lines,
                    event_bus=floor.bus,
                    uow=FakeUnitOfWork(),
                    reconciler=r,
                    project_repo=FakeProjectRepository(),
                ),
                event_bus=floor.bus,
                uow=FakeUnitOfWork(),
                reconciler=r,
            ).execute(ACTOR, request_id, command)

        return self.request(award)

    # ── Helpers ──────────────────────────────────────────────────────

    def order_of(self, line_id: int) -> int:
        """The order a line is on, the first order for an unknown line."""
        line = self.lines._items.get(line_id)
        return line.order_id if line is not None else ORDER_ID

    def _lot_of(self, position_id: int) -> int:
        position = self.floor.lots._positions[position_id]
        return position.lot_id

    def remaining_of_line(self, line_id: int) -> float:
        line = self.lines._items[line_id]
        return round(line.quantity - line.quantity_delivered - line.quantity_rejected_lost, 6)

    def open_rows(self, line_id: int) -> list[tuple[int, float]]:
        """(row, accepted pieces no correction took back yet) for every
        delivery row of the line a correction may still take from."""
        rows = [r for r in self.deliveries._deliveries if r.order_item_id == line_id]
        found = []
        for row in rows:
            if row.corrects_delivery_id is not None:
                continue
            taken = -sum(r.quantity for r in rows if r.corrects_delivery_id == row.id)
            if row.quantity - taken > 1e-6:
                found.append((row.id, round(row.quantity - taken, 6)))
        return found


class _TenantSettings(FakeAdminSettingsRepository):
    """The admin settings with the general ones a reversal reads, the
    tenant's timezone."""

    async def get_general(self) -> Any:
        return SimpleNamespace(default_timezone="UTC")


def _machine() -> Any:
    machine = make_machine(1)
    machine.fabrication_method_ids = [1]
    return machine


def user() -> User:
    """The actor every request of the world runs as."""
    return ACTOR
