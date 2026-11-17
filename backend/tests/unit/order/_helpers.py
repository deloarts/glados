"""
Builders and in-memory fakes for the order and order-line use case tests.
The repository fakes keep their rows in dicts and implement only what the
order use cases and the lifecycle reconciler reach. Tests elsewhere in the
unit suite that drive order lines (demand intents, lifecycle and guard
tests) import them from here too.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from types import SimpleNamespace

from src.modules.catalogue.domain.entities.admin_settings.orders import AdminOrderSettings
from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.entities.source_item import SourceItem
from src.modules.catalogue.domain.entities.supplier import Supplier
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.source_item_status import SourceItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.supplier_level import SupplierLevel
from src.modules.catalogue.ports.outbound.catalogue_queries import SupplierFilterDto
from src.modules.fulfillment.domain.entities.bought_item_allocation import (
    BoughtItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.source_item_allocation import (
    SourceItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    DemandItemFilterDto,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import OrderFilterDto
from src.modules.platform.domain.value_objects.localized_text import LocalizedText
from tests.unit.production_order.fakes import FakeProductionOrderRepository
from tests.unit.production_order.fakes import production_order_reconciler


def make_order(
    id: int = 1,
    status: OrderStatus = OrderStatus.DRAFT,
    supplier_id: int = 1,
    creator_id: int = 1,
) -> Order:
    return Order(
        id=id,
        order_number=f"ORD-2026-{id:04d}",
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        status=status,
        note=None,
        ordered_date=None,
        expected_delivery_date=None,
        delivery_date=None,
        storage_place=None,
        creator_id=creator_id,
        supplier_id=supplier_id,
    )


def make_order_item(
    id: int = 1,
    order_id: int = 1,
    status: OrderItemStatus = OrderItemStatus.PENDING,
    bought_item_id: int | None = 1,
    source_item_id: int | None = None,
) -> OrderItem:
    return OrderItem(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        status=status,
        quantity=10.0,
        quantity_delivered=0.0,
        unit="pcs",
        items_per_unit=1.0,
        price=None,
        note=None,
        ordered_date=None,
        expected_delivery_date=None,
        delivery_date=None,
        storage_place=None,
        expected_pickup_date=None,
        ready_for_pickup_date=None,
        position=1,
        creator_id=1,
        orderer_id=None,
        receiver_id=None,
        bought_item_id=None if source_item_id is not None else bought_item_id,
        order_id=order_id,
        supplier_id=1,
        project_id=1,
        line_type=OrderLineType.SOURCE if source_item_id is not None else OrderLineType.BOUGHT,
        lot_position_id=None,
        source_item_id=source_item_id,
    )


def make_demand(
    id: int = 1,
    status: BoughtItemDemandStatus = BoughtItemDemandStatus.ALLOCATED,
    creator_id: int = 1,
) -> BoughtItemDemandItem:
    return BoughtItemDemandItem(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        status=status,
        quantity=10.0,
        unit="pcs",
        items_per_unit=1.0,
        high_priority=False,
        notify_on_delivery=False,
        note=None,
        desired_delivery_date=None,
        creator_id=creator_id,
        item_id=1,
        project_id=1,
    )


def make_allocation(
    demand_item_id: int = 1,
    order_item_id: int = 1,
    quantity: float = 10.0,
) -> BoughtItemDemandAllocation:
    return BoughtItemDemandAllocation(
        demand_item_id=demand_item_id,
        order_item_id=order_item_id,
        quantity=quantity,
    )


def make_production_order(
    id: int,
    lot_position_id: int,
    status: ProductionOrderStatus = ProductionOrderStatus.IN_PROGRESS,
) -> ProductionOrder:
    """The in-house side of a MIXED LotPosition, only status matters to
    the order-side use cases under test here."""
    return ProductionOrder(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        production_order_number=f"PO-{id:04d}",
        status=status,
        priority=UrgencyClass.NORMAL,
        pinned=False,
        queue_sequence=1,
        quantity=5.0,
        quantity_completed=0.0,
        estimated_duration_minutes=30,
        note=None,
        planned_start=None,
        planned_end=None,
        not_before=None,
        actual_start=None,
        actual_end=None,
        creator_id=1,
        machine_id=1,
        lot_position_id=lot_position_id,
    )


def make_supplier(id: int = 1, name: str = "Acme") -> Supplier:
    return Supplier(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=False,
        name=name,
        legal_name=None,
        vat_id=None,
        level=SupplierLevel.B,
        capability_ids=[],
        article_group_ids=[],
        street=None,
        city=None,
        country=None,
        postal_code=None,
        email=None,
        phone=None,
        weblink=None,
        order_email=None,
        order_language=None,
        order_template=None,
        request_email=None,
        request_language=None,
        request_template=None,
        creator_id=1,
    )


class FakeOrderRepository:
    def __init__(self, orders: list[Order] | None = None):
        self._orders: dict[int, Order] = {}
        self._next_id = 1
        self._order_counter = 0
        for o in orders or []:
            self._orders[o.id] = o
            self._next_id = max(self._next_id, o.id + 1)

    async def get_by_id(self, id: int) -> Order | None:
        return self._orders.get(id)

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list[Order]:
        return [self._orders[i] for i in ids if i in self._orders]

    async def next_order_number(self, template: str) -> str:
        self._order_counter += 1
        return f"ORD-2026-{self._order_counter:04d}"

    async def save(self, order: Order) -> Order:
        if order.id == 0:
            order.id = self._next_id
            self._next_id += 1
        self._orders[order.id] = order
        return order

    async def get_by_order_number(self, order_number: str) -> Order | None:
        raise NotImplementedError

    async def get_multi(self, filters: OrderFilterDto) -> tuple[int, list[Order]]:
        raise NotImplementedError

    async def delete(self, order: Order) -> None:
        raise NotImplementedError


class FakeOrderItemRepository:
    def __init__(self, items: list[OrderItem] | None = None):
        self._items: dict[int, OrderItem] = {}
        self._next_id = 1
        for i in items or []:
            self._items[i.id] = i
            self._next_id = max(self._next_id, i.id + 1)

    async def get_by_ids(self, ids: list[int], *, refresh: bool = False) -> list:
        found = [await self.get_by_id(i) for i in ids]
        return [item for item in found if item is not None]

    async def get_by_id(self, id: int) -> OrderItem | None:
        return self._items.get(id)

    async def get_by_id_for_update(self, id: int) -> OrderItem | None:
        return self._items.get(id)

    async def get_by_order_id(self, order_id: int) -> list[OrderItem]:
        return [i for i in self._items.values() if i.order_id == order_id]

    async def next_position(self, order_id: int) -> int:
        items = await self.get_by_order_id(order_id)
        return max((i.position for i in items), default=0) + 1

    async def save(self, item: OrderItem) -> OrderItem:
        if item.id == 0:
            item.id = self._next_id
            self._next_id += 1
        self._items[item.id] = item
        return item

    async def get_by_order_ids(
        self, order_ids: list[int], *, refresh: bool = False
    ) -> list[OrderItem]:
        raise NotImplementedError

    async def get_by_bought_item_id(self, bought_item_id: int) -> list[OrderItem]:
        raise NotImplementedError

    async def get_by_lot_position_id(self, lot_position_id: int) -> OrderItem | None:
        """The live line, else the newest canceled one."""
        lines = sorted(
            (i for i in self._items.values() if i.lot_position_id == lot_position_id),
            key=lambda i: (i.canceled_at is not None, -i.id),
        )
        return lines[0] if lines else None

    async def delete(self, item: OrderItem) -> None:
        self._items.pop(item.id, None)


class FakeAllocationRepository:
    def __init__(self, allocations: list[BoughtItemDemandAllocation] | None = None):
        self._allocations: list[BoughtItemDemandAllocation] = list(allocations or [])

    @property
    def allocations(self) -> list[BoughtItemDemandAllocation]:
        """The stored allocations, for assertions."""
        return self._allocations

    async def get_by_order_item_id(self, order_item_id: int) -> list[BoughtItemDemandAllocation]:
        return [a for a in self._allocations if a.order_item_id == order_item_id]

    async def get_by_order_item_ids(
        self, order_item_ids: list[int], *, refresh: bool = False
    ) -> list[BoughtItemDemandAllocation]:
        return [a for a in self._allocations if a.order_item_id in order_item_ids]

    async def get_by_demand_item_id(self, demand_item_id: int) -> list[BoughtItemDemandAllocation]:
        return [a for a in self._allocations if a.demand_item_id == demand_item_id]

    async def get_by_demand_item_ids(self, demand_item_ids: list[int]) -> list:
        return [a for d in demand_item_ids for a in await self.get_by_demand_item_id(d)]

    async def delete(self, allocation: BoughtItemDemandAllocation) -> None:
        self._allocations = [
            a
            for a in self._allocations
            if not (
                a.demand_item_id == allocation.demand_item_id
                and a.order_item_id == allocation.order_item_id
            )
        ]

    async def save(self, allocation: BoughtItemDemandAllocation) -> BoughtItemDemandAllocation:
        self._allocations.append(allocation)
        return allocation

    async def get_allocated_quantity(self, demand_item_id: int) -> float:
        raise NotImplementedError


class FakeDemandRepository:
    def __init__(self, demands: list[BoughtItemDemandItem] | None = None):
        self._demands: dict[int, BoughtItemDemandItem] = {d.id: d for d in (demands or [])}

    async def get_by_id(self, id: int) -> BoughtItemDemandItem | None:
        return self._demands.get(id)

    async def get_by_id_for_update(self, id: int) -> BoughtItemDemandItem | None:
        return self._demands.get(id)

    async def save(self, demand: BoughtItemDemandItem) -> BoughtItemDemandItem:
        self._demands[demand.id] = demand
        return demand

    async def get_by_ids(
        self, ids: list[int], *, refresh: bool = False
    ) -> list[BoughtItemDemandItem]:
        return [self._demands[i] for i in ids if i in self._demands]

    async def get_by_project_id(self, project_id: int) -> list[BoughtItemDemandItem]:
        raise NotImplementedError

    async def get_multi(
        self, filters: DemandItemFilterDto
    ) -> tuple[int, list[BoughtItemDemandItem]]:
        raise NotImplementedError

    async def delete(self, demand: BoughtItemDemandItem) -> None:
        raise NotImplementedError


def make_source_item(
    id: int = 1,
    dimension: str | None = "20x20x1000",
    material: str = "Aluminium",
    order_code_1: str | None = "SRC-OC-1",
    type_name: str = "Bar",
) -> SourceItem:
    return SourceItem(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=False,
        type_id=1,
        dimension=dimension,
        material=material,
        mass=None,
        note=None,
        order_code_1=order_code_1,
        order_code_2=None,
        status=SourceItemCatalogueStatus.ACTIVE,
        creator_id=1,
        approver_id=None,
        manufacturer_id=None,
        successor_item_id=None,
        type_name=LocalizedText({"enGB": type_name}),
    )


def make_source_item_demand(
    id: int = 1,
    status: SourceItemDemandStatus = SourceItemDemandStatus.ALLOCATED,
    source_item_id: int | None = 1,
    source_item: SourceItem | None = None,
) -> SourceItemDemandItem:
    return SourceItemDemandItem(
        id=id,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        status=status,
        quantity=10.0,
        unit="pcs",
        items_per_unit=1.0,
        high_priority=False,
        notify_on_delivery=False,
        note=None,
        desired_delivery_date=None,
        creator_id=1,
        bought_item_id=None,
        source_item_id=source_item_id,
        source_item=source_item,
        lot_id=1,
        project_id=1,
    )


def make_source_item_allocation(
    demand_item_id: int = 1,
    order_item_id: int = 1,
    quantity: float = 10.0,
    substitute_source_item_id: int | None = None,
    substitute_reason: str | None = None,
) -> SourceItemDemandAllocation:
    return SourceItemDemandAllocation(
        demand_item_id=demand_item_id,
        order_item_id=order_item_id,
        quantity=quantity,
        substitute_source_item_id=substitute_source_item_id,
        substitute_reason=substitute_reason,
    )


class FakeSourceItemAllocationRepository:
    def __init__(self, allocations: list[SourceItemDemandAllocation] | None = None):
        self._allocations: list[SourceItemDemandAllocation] = list(allocations or [])

    @property
    def allocations(self) -> list[SourceItemDemandAllocation]:
        """The stored allocations, for assertions."""
        return self._allocations

    async def get_by_order_item_id(self, order_item_id: int) -> list[SourceItemDemandAllocation]:
        return [a for a in self._allocations if a.order_item_id == order_item_id]

    async def get_by_order_item_ids(
        self, order_item_ids: list[int], *, refresh: bool = False
    ) -> list[SourceItemDemandAllocation]:
        return [a for a in self._allocations if a.order_item_id in order_item_ids]

    async def get_by_demand_item_id(self, demand_item_id: int) -> list[SourceItemDemandAllocation]:
        return [a for a in self._allocations if a.demand_item_id == demand_item_id]

    async def save(self, allocation: SourceItemDemandAllocation) -> SourceItemDemandAllocation:
        await self.delete(allocation)
        self._allocations.append(allocation)
        return allocation

    async def delete(self, allocation: SourceItemDemandAllocation) -> None:
        self._allocations = [
            a
            for a in self._allocations
            if not (
                a.demand_item_id == allocation.demand_item_id
                and a.order_item_id == allocation.order_item_id
            )
        ]


class FakeSourceItemDemandRepository:
    def __init__(self, demands: list[SourceItemDemandItem] | None = None):
        self._demands: dict[int, SourceItemDemandItem] = {d.id: d for d in (demands or [])}

    async def get_by_id(self, id: int) -> SourceItemDemandItem | None:
        return self._demands.get(id)

    async def get_by_ids(
        self, ids: list[int], *, refresh: bool = False
    ) -> list[SourceItemDemandItem]:
        return [self._demands[i] for i in ids if i in self._demands]

    async def get_by_id_for_update(self, id: int) -> SourceItemDemandItem | None:
        return self._demands.get(id)

    async def save(self, demand: SourceItemDemandItem) -> SourceItemDemandItem:
        self._demands[demand.id] = demand
        return demand


class FakeOrderItemDeliveryRepository:
    """Stands in for IOrderItemDeliveryRepository. Only get_by_order_item_ids
    is reachable from GetOrders."""

    async def get_by_order_item_ids(self, order_item_ids: list[int]) -> list:
        return []


class FakeSupplierRepository:
    def __init__(self, suppliers: list[Supplier] | None = None):
        self._suppliers: dict[int, Supplier] = {s.id: s for s in (suppliers or [])}

    async def get_by_id(self, id: int) -> Supplier | None:
        return self._suppliers.get(id)

    async def get_by_vat_id(self, vat_id: str) -> Supplier | None:
        raise NotImplementedError

    async def get_multi(self, filters: SupplierFilterDto) -> tuple[int, list[Supplier]]:
        raise NotImplementedError

    async def save(self, supplier: Supplier) -> Supplier:
        raise NotImplementedError

    async def delete(self, supplier: Supplier) -> None:
        raise NotImplementedError


class FakeEventBus:
    def __init__(self):
        self.published = []

    async def publish(self, event):
        self.published.append(event)


class FakeUnitOfWork:
    def __init__(self):
        self.committed = False
        self.rolled_back = False

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True


class FakeRecomputeSchedule:
    """Fake of RecomputeMachineSchedule, see
    tests/unit/production_order/fakes.py's identical class."""

    def __init__(self) -> None:
        self.execute_all_calls: int = 0

    async def execute_all(self, response_time_days=None, settings=None):
        self.execute_all_calls += 1
        return []


class FailingRecomputeSchedule:
    def __init__(self) -> None:
        self.attempts: int = 0

    async def execute_all(self, response_time_days=None, settings=None):
        self.attempts += 1
        raise RuntimeError("scheduling service is down")


class FakeProductionLotRepository:
    """Minimal enough for the lifecycle reconciler to derive a MADE line's
    lot and position from, unused (no methods ever called) in tests whose
    order items all have lot_position_id=None."""

    def __init__(self, lots=None, positions=None):
        self._lots = {lot.id: lot for lot in (lots or [])}
        self._positions = {p.id: p for p in (positions or [])}

    def _hydrate(self, lot):
        if lot is not None:
            lot.positions = sorted(
                (p for p in self._positions.values() if p.lot_id == lot.id),
                key=lambda p: p.sequence,
            )
        return lot

    async def get_by_id(self, id):
        return self._hydrate(self._lots.get(id))

    async def get_by_id_for_update(self, id):
        return self._hydrate(self._lots.get(id))

    async def get_by_ids(self, ids, *, refresh=False):
        return [self._hydrate(self._lots[i]) for i in ids if i in self._lots]

    async def lock_for_update(self, ids):
        return None

    async def record_event(self, event):
        return event

    async def get_position_by_id(self, position_id):
        return self._positions.get(position_id)

    async def get_positions_by_ids(self, position_ids: list[int]) -> list:
        positions = [await self.get_position_by_id(i) for i in position_ids]
        return [p for p in positions if p is not None]

    async def get_positions(self, lot_id):
        return [p for p in self._positions.values() if p.lot_id == lot_id]

    async def save_position(self, position):
        self._positions[position.id] = position
        return position

    async def save(self, lot):
        self._lots[lot.id] = lot
        return lot


def lot_aware_reconciler(order_repo, order_item_repo, lot_repo):
    """A lifecycle reconciler of order lines, orders, lot positions and lots
    over the test's fakes, with the production orders the seeded positions
    carry."""
    production_orders = FakeProductionOrderRepository(
        [o for position in lot_repo._positions.values() for o in position.production_orders]
    )
    return production_order_reconciler(
        production_orders,
        lot_repo,
        FakeEventBus(),
        orders=order_repo,
        order_items=order_item_repo,
    )


class FakeAdminSettingsRepository:
    def __init__(self, order_number_format: str = "ORD-{year}-{seq:04d}"):
        self._orders = AdminOrderSettings(
            id=1,
            order_number_format=order_number_format,
            part_number_format="PN-{year}-{seq:04d}",
            part_number_auto=False,
            part_number_editable=True,
            web_creation_allowed=True,
            pdm_part_number_pattern="",
        )

    async def get_orders(self) -> AdminOrderSettings:
        return self._orders

    async def save_orders(self, settings: AdminOrderSettings) -> AdminOrderSettings:
        self._orders = settings
        return settings


class FakeCatalogueRepository:
    """Only get_by_id is reachable from the use cases exercised below."""

    def __init__(self, items: list[BoughtItem] | None = None):
        self._items: dict[int, BoughtItem] = {i.id: i for i in (items or [])}
        self.lookups: list[int] = []

    async def get_by_id(self, id: int) -> BoughtItem | None:
        self.lookups.append(id)
        return self._items.get(id)


class FakeSourceItemRepository:
    async def get_by_id(self, id: int):
        raise NotImplementedError


def make_bought_item(id: int = 1, article_name: str = "Hex bolt M8") -> BoughtItem:
    return BoughtItem(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=False,
        article_name=article_name,
        order_code_1=f"OC-{id}",
        order_code_2=None,
        gtin=None,
        ean=None,
        tariff_number=None,
        status=BoughtItemCatalogueStatus.ACTIVE,
        data_source=DataSource.WEB,
        part_number=None,
        mass=None,
        note=None,
        weblink=None,
        files=[],
        creator_id=1,
        approver_id=None,
        manufacturer_id=1,
        article_group_ids=[],
        successor_item_id=None,
    )


class ExistingSuppliers:
    """A supplier repository in which every supplier exists, for a use case
    that only checks the supplier it is given."""

    async def get_by_id(self, id: int) -> SimpleNamespace:
        return SimpleNamespace(id=id, name=f"Supplier {id}")
