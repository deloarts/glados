"""
The two intents a user sets on a demand, cancel and fulfil, and the delete,
over the use cases with the lifecycle reconciler deriving every status. A
cancel records canceled_at and releases every allocation of the demand, on
order lines and from stock, so the capacity it held is free again; a
fulfilled demand cannot be canceled, and marking one fulfilled keeps its stock
and its arrived pieces and releases the rest of its line allocations. A delete is
refused while the demand holds allocations, since deleting it would leave
them behind. The status route narrows to the two intents in
tests/unit/test_demand_status_permissions.py, the made cancel and the lot
cascade are covered in production_lot/test_cancel_made_item_demand_cascade.py.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.catalogue.domain.events.bought_item_events import DemandItemStatusChanged
from src.modules.catalogue.domain.value_objects.bought_item_status import AllocationSource
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemAllocationSource
from src.modules.fulfillment.application.use_cases.bought_item_demand.cancel_demand_item import (
    CancelDemandItem,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.delete_demand_item import (
    DeleteDemandItem,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.update_demand_item_status import (
    UpdateDemandItemStatus,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.delete_demand_item import (
    DeleteDemandItem as DeleteMadeItemDemandItem,
)
from src.modules.fulfillment.application.use_cases.source_item_demand.cancel_source_item_demand import (
    CancelSourceItemDemand,
)
from src.modules.fulfillment.domain.entities.bought_item_allocation import (
    BoughtItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.entities.source_item_allocation import (
    SourceItemDemandAllocation,
)
from src.modules.fulfillment.domain.errors import DemandItemAlreadyFulfilledError
from src.modules.fulfillment.domain.errors import DemandItemHasAllocationsError
from src.modules.fulfillment.domain.events.source_item_demand_events import (
    SourceItemDemandStatusChanged,
)
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler_harness
from tests.unit.order._helpers import FakeAllocationRepository
from tests.unit.order._helpers import FakeDemandRepository
from tests.unit.order._helpers import FakeOrderItemRepository
from tests.unit.order._helpers import FakeOrderRepository
from tests.unit.order._helpers import FakeUnitOfWork
from tests.unit.order._helpers import make_demand
from tests.unit.order._helpers import make_order
from tests.unit.order._helpers import make_order_item
from tests.unit.production_lot._helpers import make_demand as make_made_demand
from tests.unit.production_lot._helpers import make_source_item_demand
from tests.unit.production_lot.fakes import FakeMadeItemAllocationRepository
from tests.unit.production_lot.fakes import FakeMadeItemDemandRepository
from tests.unit.production_lot.fakes import FakeSourceItemAllocationRepository
from tests.unit.production_lot.fakes import FakeSourceItemDemandRepository
from tests.unit.test_source_item_demand_use_cases import FakeProductionLotRepository as SourceLots
from tests.unit.test_source_item_demand_use_cases import RecordingLotCancel
from tests.unit.test_source_item_demand_use_cases import make_lot

MANAGER = make_user(
    id=3,
    username="manager",
    permissions=[
        Permission.WRITE_DEMAND_ITEMS,
        Permission.MANAGE_DEMAND_ITEMS,
        Permission.WRITE_LOTS,
    ],
)
OWNER = make_user(id=1, username="owner", permissions=[Permission.WRITE_DEMAND_ITEMS])


def _line_allocation(quantity: float) -> BoughtItemDemandAllocation:
    return BoughtItemDemandAllocation(demand_item_id=1, order_item_id=1, quantity=quantity)


def _stock_allocation(quantity: float) -> BoughtItemDemandAllocation:
    return BoughtItemDemandAllocation(
        demand_item_id=1,
        order_item_id=None,
        quantity=quantity,
        source=AllocationSource.STOCK,
    )


class _BoughtWorld:
    """A bought demand of ten with six pieces on an ordered line and four
    from stock, which the reconciler derives as ORDERED."""

    def __init__(self) -> None:
        self.demands = FakeDemandRepository(
            [make_demand(id=1, status=BoughtItemDemandStatus.ORDERED)]
        )
        self.allocations = FakeAllocationRepository([_line_allocation(6.0), _stock_allocation(4.0)])
        self.lines = FakeOrderItemRepository(
            [make_order_item(id=1, status=OrderItemStatus.ORDERED)]
        )
        self.orders = FakeOrderRepository([make_order(id=1, status=OrderStatus.ORDERED)])
        self.uow = FakeUnitOfWork()
        self.harness = demand_reconciler_harness(
            bought_demands=self.demands,
            bought_allocations=self.allocations,
            order_items=self.lines,
            orders=self.orders,
        )

    def cancel(self) -> CancelDemandItem:
        return CancelDemandItem(
            self.demands, self.allocations, uow=self.uow, reconciler=self.harness.reconciler
        )

    def status(self) -> UpdateDemandItemStatus:
        return UpdateDemandItemStatus(
            self.demands,
            self.cancel(),
            uow=self.uow,
            reconciler=self.harness.reconciler,
            allocation_repo=self.allocations,
            source_allocation_repo=FakeSourceItemAllocationRepository(),
            order_item_repo=self.lines,
        )


class TestBoughtCancel:
    async def test_cancel_releases_the_line_and_stock_allocations(self) -> None:
        world = _BoughtWorld()

        result = await world.cancel().execute(MANAGER, 1)

        assert result.status == "canceled"
        assert await world.allocations.get_by_demand_item_id(1) == []
        demand = await world.demands.get_by_id(1)
        assert demand is not None and demand.canceled_at is not None
        assert demand.changes[-1].endswith("Status: ordered → canceled (demand canceled).")
        assert world.uow.committed is True

    async def test_the_reconciler_publishes_the_status_event(self) -> None:
        world = _BoughtWorld()

        await world.cancel().execute(MANAGER, 1)

        [event] = [e for e in world.harness.bus.published if isinstance(e, DemandItemStatusChanged)]
        assert (event.demand_id, event.old_status, event.new_status) == (1, "ordered", "canceled")

    async def test_the_status_route_cancels_the_same_way(self) -> None:
        world = _BoughtWorld()

        result = await world.status().execute(MANAGER, 1, "canceled")

        assert result.status == "canceled"
        assert await world.allocations.get_by_demand_item_id(1) == []

    async def test_a_fulfilled_demand_is_not_canceled_and_keeps_its_allocations(self) -> None:
        world = _BoughtWorld()
        demand = await world.demands.get_by_id(1)
        assert demand is not None
        demand.status = BoughtItemDemandStatus.FULFILLED
        demand.fulfilled_manually_at = datetime(2026, 1, 2, tzinfo=UTC)

        with pytest.raises(DemandItemAlreadyFulfilledError):
            await world.cancel().execute(MANAGER, 1)

        assert len(await world.allocations.get_by_demand_item_id(1)) == 2
        assert world.uow.committed is False

    async def test_marking_fulfilled_records_the_intent_and_releases_the_unarrived_pieces(
        self,
    ) -> None:
        world = _BoughtWorld()

        result = await world.status().execute(MANAGER, 1, "fulfilled")

        assert result.status == "fulfilled"
        demand = await world.demands.get_by_id(1)
        assert demand is not None and demand.fulfilled_manually_at is not None
        assert "released 6.000 pcs" in demand.changes[-2]
        [kept] = await world.allocations.get_by_demand_item_id(1)
        assert (kept.order_item_id, kept.quantity) == (None, 4.0)


class TestDeleteWithAllocations:
    async def test_a_bought_demand_holding_allocations_is_not_deleted(self) -> None:
        demands = FakeDemandRepository([make_demand(id=1, status=BoughtItemDemandStatus.ALLOCATED)])
        allocations = FakeAllocationRepository([_line_allocation(4.0)])

        with pytest.raises(DemandItemHasAllocationsError):
            await DeleteDemandItem(demands, allocations, uow=FakeUnitOfWork()).execute(OWNER, 1)

        assert await demands.get_by_id(1) is not None

    async def test_a_made_demand_holding_allocations_is_not_deleted(self) -> None:
        demands = FakeMadeItemDemandRepository([make_made_demand(id=1, quantity=4.0)])
        allocations = FakeMadeItemAllocationRepository(
            [
                MadeItemDemandAllocation(
                    demand_item_id=1,
                    lot_id=None,
                    quantity=2.0,
                    source=MadeItemAllocationSource.STOCK,
                )
            ]
        )
        uow = FakeUnitOfWork()

        with pytest.raises(DemandItemHasAllocationsError):
            await DeleteMadeItemDemandItem(demands, allocations, uow=uow).execute(OWNER, 1)

        assert await demands.get_by_id(1) is not None
        assert uow.committed is False


class TestSourceCancel:
    async def test_cancel_releases_the_allocations_unlinks_the_lot_and_sets_the_flag(
        self,
    ) -> None:
        lots = SourceLots([make_lot(id=1, input_demand_id=7)])
        demands = FakeSourceItemDemandRepository(
            [make_source_item_demand(id=7, lot_id=1, status=SourceItemDemandStatus.OPEN)]
        )
        allocations = FakeSourceItemAllocationRepository()
        await allocations.save(
            SourceItemDemandAllocation(demand_item_id=7, order_item_id=None, quantity=2.0)
        )
        harness = demand_reconciler_harness(source_demands=demands, source_allocations=allocations)
        uow = FakeUnitOfWork()

        result = await CancelSourceItemDemand(
            demands,
            lots,
            allocations,
            uow=uow,
            reconciler=harness.reconciler,
            cancel_lot=RecordingLotCancel(lots),
        ).execute(MANAGER, 7, cancel_lot=False)

        assert result.status == "canceled"
        demand = await demands.get_by_id(7)
        assert demand is not None
        assert demand.canceled_at is not None
        assert await allocations.get_by_demand_item_id(7) == []
        lot = await lots.get_by_id(1)
        assert lot is not None and lot.input_demand_id is None
        [event] = [e for e in harness.bus.published if isinstance(e, SourceItemDemandStatusChanged)]
        assert (event.demand_id, event.lot_id, event.new_status) == (7, 1, "canceled")
