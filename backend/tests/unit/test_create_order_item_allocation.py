"""
Creating an order item from bought item demands: each demand takes the share
of the line the request names, which must fit what the demand still needs,
its quantity minus what orders and stock already cover; a fulfilled,
canceled or unknown demand is refused, not skipped; and the status follows
from the allocations through the reconciler. Demands are locked in ascending
id. In-memory fakes, no database.
"""

import pytest

from src.modules.catalogue.domain.value_objects.bought_item_status import AllocationSource
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.fulfillment.application.dto.order_dto import CreateOrderItemCommand
from src.modules.fulfillment.application.dto.order_dto import OrderLineDemandAllocationInput
from src.modules.fulfillment.application.use_cases.order.create_order_item import CreateOrderItem
from src.modules.fulfillment.domain.entities.bought_item_allocation import (
    BoughtItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.errors import AllocationOverflowError
from src.modules.fulfillment.domain.errors import DemandItemAlreadyFulfilledError
from src.modules.fulfillment.domain.errors import DemandItemNotFoundError
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler
from tests.unit.lifecycle.fake_reconciler import give_order_item_facts
from tests.unit.order._helpers import ExistingSuppliers
from tests.unit.order._helpers import FakeCatalogueRepository
from tests.unit.order._helpers import FakeOrderItemRepository
from tests.unit.order._helpers import FakeOrderRepository
from tests.unit.order._helpers import FakeSourceItemRepository
from tests.unit.order._helpers import FakeUnitOfWork
from tests.unit.order._helpers import make_bought_item
from tests.unit.order._helpers import make_order
from tests.unit.production_lot.fakes import FakeProjectRepository
from tests.unit.test_bought_item_allocation_use_cases import FakeAllocationRepository
from tests.unit.test_bought_item_allocation_use_cases import FakeDemandRepository
from tests.unit.test_bought_item_allocation_use_cases import make_demand
from tests.unit.test_bought_item_allocation_use_cases import make_order_item

BUYER = make_user(permissions=[Permission.WRITE_ORDERS])

# The line that already exists on the order before the new one is added.
EXISTING_LINE_ID = 1


class World:
    def __init__(
        self,
        demands: list[BoughtItemDemandItem],
        allocations: list[BoughtItemDemandAllocation] | None = None,
        existing_line_status: OrderItemStatus = OrderItemStatus.ORDERED,
    ) -> None:
        self.demands = FakeDemandRepository(demands)
        self.allocations = FakeAllocationRepository(list(allocations or []))
        self.lines = FakeOrderItemRepository(
            [
                give_order_item_facts(
                    make_order_item(
                        id=EXISTING_LINE_ID,
                        order_id=1,
                        status=existing_line_status,
                        quantity=10.0,
                        bought_item_id=1,
                    )
                )
            ]
        )
        self.uow = FakeUnitOfWork()
        orders = FakeOrderRepository([make_order(id=1, status=OrderStatus.DRAFT)])
        self.use_case = CreateOrderItem(
            project_repo=FakeProjectRepository(),
            supplier_repo=ExistingSuppliers(),
            order_item_repo=self.lines,
            item_repo=FakeCatalogueRepository([make_bought_item(id=1)]),
            order_repo=orders,
            demand_repo=self.demands,
            allocation_repo=self.allocations,
            source_item_repo=FakeSourceItemRepository(),
            uow=self.uow,
            reconciler=demand_reconciler(
                orders=orders,
                order_items=self.lines,
                bought_demands=self.demands,
                bought_allocations=self.allocations,
            ),
        )

    async def add_line(self, quantity: float, shares: dict[int, float]) -> int:
        result = await self.use_case.execute(
            BUYER,
            CreateOrderItemCommand(
                order_id=1,
                supplier_id=1,
                project_id=1,
                bought_item_id=1,
                quantity=quantity,
                unit="pcs",
                bought_demand_allocations=[
                    OrderLineDemandAllocationInput(demand_item_id=d, quantity=q)
                    for d, q in shares.items()
                ],
            ),
        )
        return result.id

    async def on_line(self, line_id: int) -> dict[int, float]:
        return {
            a.demand_item_id: a.quantity
            for a in await self.allocations.get_by_order_item_id(line_id)
        }

    async def status(self, demand_id: int) -> str:
        demand = await self.demands.get_by_id(demand_id)
        assert demand is not None
        return demand.status


def _on_existing_line(demand_id: int, quantity: float) -> BoughtItemDemandAllocation:
    return BoughtItemDemandAllocation(
        demand_item_id=demand_id, order_item_id=EXISTING_LINE_ID, quantity=quantity
    )


class TestCreateOrderItemAllocatesTheNamedShares:
    async def test_a_short_line_goes_to_the_demand_it_is_named_for(self):
        """Two demands of one item, 5 and 3; a line of 3 meant for the second
        one covers the second one, not the older first one."""
        world = World([make_demand(id=1, quantity=5.0), make_demand(id=2, quantity=3.0)])

        new_line = await world.add_line(3.0, {2: 3.0})

        assert await world.on_line(new_line) == {2: 3.0}
        assert await world.allocations.get_allocated_quantity(1) == 0.0

    async def test_a_share_above_what_the_demand_still_needs_is_refused(self):
        world = World(
            [make_demand(id=1, quantity=10.0, status=BoughtItemDemandStatus.ALLOCATED)],
            [_on_existing_line(1, 6.0)],
            existing_line_status=OrderItemStatus.PENDING,
        )

        with pytest.raises(AllocationOverflowError):
            await world.add_line(10.0, {1: 5.0})

        assert world.uow.committed is False

    async def test_a_share_of_what_the_demand_still_needs_is_allocated(self):
        world = World(
            [make_demand(id=1, quantity=10.0, status=BoughtItemDemandStatus.ALLOCATED)],
            [_on_existing_line(1, 6.0)],
            existing_line_status=OrderItemStatus.PENDING,
        )

        new_line = await world.add_line(10.0, {1: 4.0})

        assert await world.on_line(new_line) == {1: 4.0}
        assert await world.allocations.get_allocated_quantity(1) == 10.0

    async def test_stock_counts_toward_what_a_demand_still_needs(self):
        world = World(
            [make_demand(id=1, quantity=10.0, status=BoughtItemDemandStatus.ALLOCATED)],
            [
                BoughtItemDemandAllocation(
                    demand_item_id=1,
                    order_item_id=None,
                    quantity=3.0,
                    source=AllocationSource.STOCK,
                )
            ],
        )

        with pytest.raises(AllocationOverflowError):
            await world.add_line(10.0, {1: 8.0})
        new_line = await world.add_line(10.0, {1: 7.0})

        assert await world.on_line(new_line) == {1: 7.0}

    async def test_a_line_larger_than_its_shares_keeps_the_rest_free(self):
        world = World([make_demand(id=1, quantity=3.0)])

        new_line = await world.add_line(10.0, {1: 3.0})

        assert await world.on_line(new_line) == {1: 3.0}

    async def test_demands_are_read_through_their_locks_in_ascending_id(self):
        world = World([make_demand(id=1, quantity=4.0), make_demand(id=2, quantity=5.0)])

        new_line = await world.add_line(6.0, {2: 2.0, 1: 4.0})

        assert await world.on_line(new_line) == {1: 4.0, 2: 2.0}
        assert world.demands.for_update_calls == [1, 2]

    async def test_a_fulfilled_demand_is_refused_not_skipped(self):
        world = World([make_demand(id=1, quantity=5.0, status=BoughtItemDemandStatus.FULFILLED)])

        with pytest.raises(DemandItemAlreadyFulfilledError):
            await world.add_line(10.0, {1: 5.0})

        assert world.uow.committed is False

    async def test_an_unknown_demand_is_refused(self):
        world = World([])

        with pytest.raises(DemandItemNotFoundError):
            await world.add_line(10.0, {99: 5.0})

        assert world.uow.committed is False


class TestCreateOrderItemResolvesTheStatus:
    async def test_an_open_demand_becomes_allocated(self):
        world = World([make_demand(id=1, quantity=5.0)])

        await world.add_line(5.0, {1: 5.0})

        demand = await world.demands.get_by_id(1)
        assert demand is not None
        assert demand.status == BoughtItemDemandStatus.ALLOCATED.value
        assert any("Status: open → allocated" in line for line in demand.changes)

    async def test_an_ordered_demand_with_a_share_on_the_new_pending_line_is_allocated(self):
        # ORDERED needs every covering line placed; the new line is pending,
        # so the 4 pieces on it leave the demand allocated until it is ordered.
        world = World(
            [make_demand(id=1, quantity=10.0, status=BoughtItemDemandStatus.ORDERED)],
            [_on_existing_line(1, 6.0)],
        )

        new_line = await world.add_line(10.0, {1: 4.0})

        assert await world.on_line(new_line) == {1: 4.0}
        assert await world.status(1) == BoughtItemDemandStatus.ALLOCATED.value
