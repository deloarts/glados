"""
Quantity edits of bought and made demands: refused below what allocations
and stock already cover, refused on a fulfilled or canceled demand for
every actor, and followed by a status recompute. No database, no HTTP,
in-memory fakes only.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

import pytest

from src.modules.catalogue.domain.value_objects.bought_item_status import AllocationSource
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemAllocationSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.application.dto.bought_item_demand_dto import UpdateDemandItemCommand
from src.modules.fulfillment.application.dto.made_item_demand_dto import UpdateMadeItemDemandCommand
from src.modules.fulfillment.application.use_cases.bought_item_demand.update_demand_item import (
    UpdateDemandItem as UpdateBoughtDemandItem,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.update_demand_item import (
    UpdateDemandItem as UpdateMadeDemandItem,
)
from src.modules.fulfillment.domain.entities.bought_item_allocation import (
    BoughtItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.errors import AllocationOverflowError
from src.modules.fulfillment.domain.errors import DemandItemAlreadyCanceledError
from src.modules.fulfillment.domain.errors import DemandItemAlreadyFulfilledError
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.domain.value_objects.start_page import StartPage
from src.modules.platform.domain.value_objects.theme import ThemePreset
from src.modules.platform.domain.value_objects.theme import ThemePrimary
from src.modules.platform.domain.value_objects.theme import ThemeSurface
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler
from tests.unit.production_order._helpers import make_order as make_production_order
from tests.unit.production_order.fakes import FakeProductionLotRepository as ProductionLots
from tests.unit.production_order.fakes import FakeProductionOrderRepository as ProductionOrders

# ── Builders ──────────────────────────────────────────────────────────


def make_manager() -> User:
    return User(
        id=3,
        username="mgr",
        full_name="Demand Manager",
        email="mgr@example.com",
        created=datetime(2026, 1, 1, tzinfo=UTC),
        hashed_password="x",
        is_active=True,
        is_systemuser=False,
        permissions=[Permission.WRITE_DEMAND_ITEMS, Permission.MANAGE_DEMAND_ITEMS],
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


def make_bought_demand(
    quantity: float = 10.0, status: BoughtItemDemandStatus = BoughtItemDemandStatus.ORDERED
) -> BoughtItemDemandItem:
    return BoughtItemDemandItem(
        id=1,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        status=status,
        quantity=quantity,
        unit="pcs",
        items_per_unit=1.0,
        high_priority=False,
        notify_on_delivery=False,
        note=None,
        desired_delivery_date=None,
        creator_id=1,
        item_id=1,
        project_id=1,
    )


def make_made_demand(
    quantity: float = 10.0, status: MadeItemDemandStatus = MadeItemDemandStatus.ORDERED
) -> MadeItemDemandItem:
    return MadeItemDemandItem(
        id=1,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        status=status,
        quantity=quantity,
        unit="pcs",
        items_per_unit=1.0,
        high_priority=False,
        notify_on_delivery=False,
        note=None,
        desired_delivery_date=None,
        creator_id=1,
        made_item_id=1,
        project_id=1,
    )


def make_line(quantity: float, delivered: float, status: OrderItemStatus) -> OrderItem:
    return OrderItem(
        id=1,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=None,
        changes=[],
        status=status,
        quantity=quantity,
        quantity_delivered=delivered,
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
        bought_item_id=1,
        order_id=1,
        supplier_id=1,
        project_id=1,
        line_type=OrderLineType.BOUGHT,
        lot_position_id=None,
        source_item_id=None,
    )


def make_completed_lot(quantity: float) -> ProductionLot:
    lot = ProductionLot(
        id=7,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=None,
        changes=[],
        lot_number="LOT-7",
        quantity=quantity,
        status=LotStatus.COMPLETED,
        priority=UrgencyClass.NORMAL,
        note=None,
        creator_id=1,
        made_item_id=1,
        project_id=1,
        input_demand_id=None,
    )
    lot.positions = [
        LotPosition(
            id=1,
            created=datetime(2026, 1, 1, tzinfo=UTC),
            changed=None,
            changes=[],
            sequence=1,
            kind=LotPositionKind.INTERNAL,
            status=LotPositionStatus.COMPLETED,
            quantity=quantity,
            quantity_completed=quantity,
            note=None,
            creator_id=1,
            lot_id=7,
        )
    ]
    return lot


# ── Fakes ─────────────────────────────────────────────────────────────


class FakeDemandRepository:
    """Serves either demand family by id and records the locked reads."""

    def __init__(self, demand) -> None:
        self._demands = {demand.id: demand}
        self.locked: list[int] = []

    async def get_by_id(self, id: int):
        return self._demands.get(id)

    async def get_by_id_for_update(self, id: int):
        self.locked.append(id)
        return self._demands.get(id)

    async def save(self, demand):
        self._demands[demand.id] = demand
        return demand


class FakeAllocationRepository:
    """Serves either allocation family by demand."""

    def __init__(self, allocations: list) -> None:
        self._allocations = list(allocations)

    async def get_by_demand_item_id(self, demand_item_id: int) -> list:
        return [a for a in self._allocations if a.demand_item_id == demand_item_id]

    async def get_allocated_quantity(self, demand_item_id: int) -> float:
        return sum(a.quantity for a in await self.get_by_demand_item_id(demand_item_id))


class FakeOrderItemRepository:
    def __init__(self, lines: list[OrderItem]) -> None:
        self._lines = {line.id: line for line in lines}

    async def get_by_id(self, id: int) -> OrderItem | None:
        return self._lines.get(id)


class FakeMadeItemRepository:
    async def get_by_id(self, id: int) -> None:
        return None


# ── Bought demands ────────────────────────────────────────────────────


class TestBoughtDemandQuantityEdit:
    def _use_case(
        self,
        demand: BoughtItemDemandItem,
        allocations: list[BoughtItemDemandAllocation] | None = None,
        lines: list[OrderItem] | None = None,
    ) -> UpdateBoughtDemandItem:
        self.demands = FakeDemandRepository(demand)
        self.uow = FakeUnitOfWork()
        allocation_repo = FakeAllocationRepository(allocations or [])
        return UpdateBoughtDemandItem(
            self.demands,
            uow=self.uow,
            reconciler=demand_reconciler(
                bought_demands=self.demands,
                bought_allocations=allocation_repo,
                order_items=FakeOrderItemRepository(lines or []),
            ),
            allocation_repo=allocation_repo,
        )

    async def _edit(
        self, use_case: UpdateBoughtDemandItem, quantity: float, note: str | None = None
    ):
        return await use_case.execute(
            actor=make_manager(),
            demand_id=1,
            cmd=UpdateDemandItemCommand(quantity=quantity, unit="pcs", note=note),
        )

    async def test_a_cut_below_allocations_and_stock_is_refused(self):
        demand = make_bought_demand(quantity=10.0)
        use_case = self._use_case(
            demand,
            allocations=[
                BoughtItemDemandAllocation(demand_item_id=1, order_item_id=1, quantity=6.0),
                BoughtItemDemandAllocation(
                    demand_item_id=1,
                    order_item_id=None,
                    quantity=2.0,
                    source=AllocationSource.STOCK,
                ),
            ],
        )

        with pytest.raises(AllocationOverflowError, match=r"8\.000 pcs allocated"):
            await self._edit(use_case, 7.0)

        assert demand.quantity == 10.0
        assert not self.uow.committed

    async def test_a_cut_to_what_deliveries_and_stock_cover_fulfils_the_demand(self):
        # 6 delivered on the line plus 2 from stock hold 8 pieces.
        demand = make_bought_demand(quantity=10.0, status=BoughtItemDemandStatus.ORDERED)
        use_case = self._use_case(
            demand,
            allocations=[
                BoughtItemDemandAllocation(demand_item_id=1, order_item_id=1, quantity=6.0),
                BoughtItemDemandAllocation(
                    demand_item_id=1,
                    order_item_id=None,
                    quantity=2.0,
                    source=AllocationSource.STOCK,
                ),
            ],
            lines=[make_line(quantity=6.0, delivered=6.0, status=OrderItemStatus.DELIVERED)],
        )

        result = await self._edit(use_case, 8.0)

        assert result.quantity == 8.0
        assert result.status == "fulfilled"
        assert demand.changes[-1].endswith("Status: ordered → fulfilled (quantity changed).")
        assert self.uow.committed

    async def test_a_raise_keeps_the_status(self):
        demand = make_bought_demand(quantity=10.0, status=BoughtItemDemandStatus.ALLOCATED)
        use_case = self._use_case(
            demand,
            allocations=[
                BoughtItemDemandAllocation(demand_item_id=1, order_item_id=1, quantity=4.0)
            ],
            lines=[make_line(quantity=10.0, delivered=0.0, status=OrderItemStatus.PENDING)],
        )

        result = await self._edit(use_case, 12.0)

        assert result.quantity == 12.0
        assert result.status == "allocated"

    async def test_a_manager_cannot_edit_a_fulfilled_demand_at_all(self):
        demand = make_bought_demand(quantity=10.0, status=BoughtItemDemandStatus.FULFILLED)
        use_case = self._use_case(demand)

        with pytest.raises(DemandItemAlreadyFulfilledError):
            await self._edit(use_case, 10.0, note="Late note")

        assert demand.note is None
        assert not self.uow.committed

    async def test_a_manager_cannot_edit_a_canceled_demand_at_all(self):
        demand = make_bought_demand(quantity=10.0, status=BoughtItemDemandStatus.CANCELED)
        use_case = self._use_case(demand)

        with pytest.raises(DemandItemAlreadyCanceledError):
            await self._edit(use_case, 12.0)

        assert demand.quantity == 10.0

    async def test_the_demand_is_read_with_the_lock(self):
        use_case = self._use_case(make_bought_demand(status=BoughtItemDemandStatus.OPEN))

        await self._edit(use_case, 12.0)

        assert self.demands.locked == [1]


# ── Made demands ──────────────────────────────────────────────────────


class TestMadeDemandQuantityEdit:
    def _use_case(
        self,
        demand: MadeItemDemandItem,
        allocations: list[MadeItemDemandAllocation] | None = None,
        lots: list[ProductionLot] | None = None,
    ) -> UpdateMadeDemandItem:
        self.demands = FakeDemandRepository(demand)
        self.uow = FakeUnitOfWork()
        allocation_repo = FakeAllocationRepository(allocations or [])
        # A lot's completed count derives from its production orders, so
        # each completed lot gets one completed order on its position.
        orders = [
            make_production_order(
                id=lot.id,
                lot_position_id=lot.positions[0].id,
                status=ProductionOrderStatus.COMPLETED,
                quantity=lot.quantity,
                quantity_completed=lot.quantity,
            )
            for lot in lots or []
        ]
        return UpdateMadeDemandItem(
            self.demands,
            FakeMadeItemRepository(),
            uow=self.uow,
            reconciler=demand_reconciler(
                made_demands=self.demands,
                made_allocations=allocation_repo,
                lots=ProductionLots(lots or []),
                production_orders=ProductionOrders(orders),
            ),
            allocation_repo=allocation_repo,
        )

    async def _edit(self, use_case: UpdateMadeDemandItem, quantity: float):
        return await use_case.execute(
            actor=make_manager(),
            demand_id=1,
            cmd=UpdateMadeItemDemandCommand(quantity=quantity, unit="pcs"),
        )

    async def test_a_cut_below_the_lot_allocation_is_refused(self):
        demand = make_made_demand(quantity=10.0)
        use_case = self._use_case(
            demand,
            allocations=[MadeItemDemandAllocation(demand_item_id=1, lot_id=7, quantity=10.0)],
            lots=[make_completed_lot(10.0)],
        )

        with pytest.raises(AllocationOverflowError, match=r"10\.000 pcs allocated"):
            await self._edit(use_case, 8.0)

        assert demand.quantity == 10.0
        assert not self.uow.committed

    async def test_a_cut_to_what_the_lot_and_stock_cover_fulfils_the_demand(self):
        # A completed lot of 6 plus 2 from stock hold 8 pieces.
        demand = make_made_demand(quantity=10.0, status=MadeItemDemandStatus.ORDERED)
        use_case = self._use_case(
            demand,
            allocations=[
                MadeItemDemandAllocation(demand_item_id=1, lot_id=7, quantity=6.0),
                MadeItemDemandAllocation(
                    demand_item_id=1,
                    lot_id=None,
                    quantity=2.0,
                    source=MadeItemAllocationSource.STOCK,
                ),
            ],
            lots=[make_completed_lot(6.0)],
        )

        result = await self._edit(use_case, 8.0)

        assert result.quantity == 8.0
        assert result.status == "fulfilled"
        assert self.uow.committed

    async def test_a_manager_cannot_edit_a_canceled_demand_at_all(self):
        demand = make_made_demand(quantity=10.0, status=MadeItemDemandStatus.CANCELED)
        use_case = self._use_case(demand)

        with pytest.raises(DemandItemAlreadyCanceledError):
            await self._edit(use_case, 12.0)

        assert demand.quantity == 10.0
        assert not self.uow.committed

    async def test_the_demand_is_read_with_the_lock(self):
        use_case = self._use_case(make_made_demand(status=MadeItemDemandStatus.OPEN))

        await self._edit(use_case, 12.0)

        assert self.demands.locked == [1]
