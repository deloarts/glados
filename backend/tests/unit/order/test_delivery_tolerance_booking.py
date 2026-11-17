"""
Deliveries under a tolerance, over the real delivery, allocation and
correction use cases with the lifecycle reconciler and in-memory fakes. A
delivery within the over-delivery tolerance is booked and its surplus is
free capacity on the line, one beyond it is refused, and the booking that
brings a line within its under-delivery tolerance closes it short with its
allocations fitted into what arrived, unless pieces are coming back for
redelivery. A correction that takes back surplus fits the allocations into
what is left.
"""

from typing import Any

import pytest

from src.modules.fulfillment.application.dto.allocation_dto import CreateAllocationCommand
from src.modules.fulfillment.application.services.allocation_fill import LineFillRepos
from src.modules.fulfillment.application.use_cases.bought_item_demand.create_allocation import (
    CreateAllocation,
)
from src.modules.fulfillment.application.use_cases.order.correct_order_item_delivery import (
    CorrectOrderItemDelivery,
)
from src.modules.fulfillment.application.use_cases.order.process_order_item_delivery import (
    ProcessOrderItemDelivery,
)
from src.modules.fulfillment.domain.entities.bought_item_allocation import (
    BoughtItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.errors import InvalidDeliveryQuantityError
from src.modules.fulfillment.domain.services.allocation_coverage import order_item_capacity_left
from src.modules.fulfillment.domain.services.delivery_tolerance import DeliveryTolerance
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler_harness
from tests.unit.lifecycle.fake_reconciler import give_order_facts
from tests.unit.lifecycle.fake_reconciler import give_order_item_facts
from tests.unit.order._helpers import FakeEventBus
from tests.unit.order._helpers import FakeOrderRepository
from tests.unit.order._helpers import FakeUnitOfWork
from tests.unit.order._helpers import make_order
from tests.unit.production_lot._helpers import NoLotCreation
from tests.unit.production_lot.fakes import FakeMadeItemAllocationRepository
from tests.unit.production_lot.fakes import FakeMadeItemDemandRepository
from tests.unit.production_lot.fakes import FakeSourceItemAllocationRepository
from tests.unit.production_lot.fakes import delivery_collaborators
from tests.unit.test_bought_item_allocation_use_cases import FakeAllocationRepository
from tests.unit.test_bought_item_allocation_use_cases import FakeDemandRepository
from tests.unit.test_bought_item_allocation_use_cases import FakeOrderItemRepository
from tests.unit.test_bought_item_allocation_use_cases import make_demand
from tests.unit.test_bought_item_allocation_use_cases import make_order_item
from tests.unit.test_bought_item_delivery import FakeDeliveryRepository

_ACTOR = make_user(
    id=7,
    permissions=[
        Permission.WRITE_ORDERS,
        Permission.MANAGE_ORDERS,
        Permission.RECEIVE_DELIVERIES,
        Permission.WRITE_ALLOCATIONS,
    ],
)


class _Tolerances:
    def __init__(self, tolerance: DeliveryTolerance) -> None:
        self._tolerance = tolerance

    async def for_line(self, line: OrderItem) -> DeliveryTolerance:
        return self._tolerance


class _Floor:
    """A line of 10 pieces with demand 1 allocated on all of it and demand 2
    open for 5."""

    def __init__(self, tolerance: DeliveryTolerance) -> None:
        self.tolerance = tolerance
        self.demands = FakeDemandRepository([make_demand(id=1), make_demand(id=2, quantity=5.0)])
        self.allocations = FakeAllocationRepository(
            [BoughtItemDemandAllocation(demand_item_id=1, order_item_id=1, quantity=10.0)]
        )
        self.lines = FakeOrderItemRepository([give_order_item_facts(make_order_item(id=1))])
        self.orders = FakeOrderRepository(
            [give_order_facts(make_order(id=1, status=OrderStatus.ORDERED))]
        )
        self.deliveries = FakeDeliveryRepository()

    def line(self) -> OrderItem:
        return self.lines._items[1]

    def held(self) -> dict[int, float]:
        return {a.demand_item_id: a.quantity for a in self.allocations._allocations}

    def _reconciler(self) -> Any:
        return demand_reconciler_harness(
            bought_demands=self.demands,
            bought_allocations=self.allocations,
            order_items=self.lines,
            orders=self.orders,
        ).reconciler

    async def deliver(self, quantity: float, **rejection: Any) -> None:
        await ProcessOrderItemDelivery(
            self.lines,
            self.orders,
            self.deliveries,
            event_bus=FakeEventBus(),
            uow=FakeUnitOfWork(),
            reconciler=self._reconciler(),
            delivery_tolerances=_Tolerances(self.tolerance),
            made_item_demand_repo=FakeMadeItemDemandRepository(),
            made_item_allocation_repo=FakeMadeItemAllocationRepository(),
            create_lot=NoLotCreation(),
            **delivery_collaborators(bought_item_allocation_repo=self.allocations),
        ).execute(_ACTOR, 1, quantity=quantity, **rejection)

    async def allocate(self, demand_id: int, quantity: float) -> None:
        await CreateAllocation(
            self.allocations,
            self.demands,
            self.lines,
            uow=FakeUnitOfWork(),
            reconciler=self._reconciler(),
            fill_repos=LineFillRepos(
                bought=self.allocations, source=FakeSourceItemAllocationRepository()
            ),
        ).execute(
            _ACTOR,
            CreateAllocationCommand(demand_item_id=demand_id, order_item_id=1, quantity=quantity),
        )

    async def correct(self, quantity: float) -> None:
        await CorrectOrderItemDelivery(
            self.orders,
            self.lines,
            self.deliveries,
            self.allocations,
            self.demands,
            uow=FakeUnitOfWork(),
            reconciler=self._reconciler(),
        ).execute(_ACTOR, 1, 1, self.deliveries.deliveries[0].id, quantity, "Counted twice")


class TestOverDelivery:
    async def test_a_delivery_within_the_tolerance_is_booked_and_its_surplus_is_free(self):
        floor = _Floor(DeliveryTolerance(over_percent=10.0))

        await floor.deliver(11.0)

        line = floor.line()
        assert (line.status, line.quantity, line.quantity_delivered) == ("delivered", 10.0, 11.0)
        assert floor.demands._demands[1].status == "fulfilled"
        assert order_item_capacity_left(line, 10.0) == 1.0
        await floor.allocate(demand_id=2, quantity=1.0)
        assert floor.held() == {1: 10.0, 2: 1.0}

    async def test_a_delivery_beyond_the_tolerance_is_refused(self):
        floor = _Floor(DeliveryTolerance(over_percent=10.0))

        with pytest.raises(InvalidDeliveryQuantityError, match=r"allows 1\.000 more"):
            await floor.deliver(12.0)

    async def test_no_tolerance_takes_exactly_the_quantity(self):
        floor = _Floor(DeliveryTolerance())

        with pytest.raises(InvalidDeliveryQuantityError, match=r"10\.000 pcs remaining;"):
            await floor.deliver(11.0)

    async def test_a_correction_of_the_surplus_fits_the_allocations_into_what_is_left(self):
        floor = _Floor(DeliveryTolerance(over_percent=10.0))
        await floor.deliver(11.0)
        await floor.allocate(demand_id=2, quantity=1.0)

        await floor.correct(1.0)

        assert floor.line().quantity_delivered == 10.0
        assert floor.held() == {1: 10.0}


class TestUnderDelivery:
    async def test_the_booking_within_the_tolerance_closes_the_line_short(self):
        floor = _Floor(DeliveryTolerance(under_percent=10.0))

        await floor.deliver(9.0)

        line = floor.line()
        assert (line.status, line.quantity, line.closed_short_from) == ("delivered", 9.0, 10.0)
        assert line.closed_short_at is not None
        assert "under-delivery tolerance of 10%" in line.changes[-2]
        assert floor.held() == {1: 9.0}
        # The shortage stays on the demand, which waits for the missing piece.
        assert floor.demands._demands[1].status != "fulfilled"

    async def test_a_line_further_short_stays_open(self):
        floor = _Floor(DeliveryTolerance(under_percent=10.0))

        await floor.deliver(8.0)

        line = floor.line()
        assert (line.status, line.quantity, line.closed_short_at) == (
            "partially_delivered",
            10.0,
            None,
        )

    async def test_pieces_coming_back_for_redelivery_keep_the_line_open(self):
        floor = _Floor(DeliveryTolerance(under_percent=10.0))

        await floor.deliver(
            9.0,
            quantity_rejected=1.0,
            rejection_reason="damaged",
            rejection_outcome="redeliver",
        )

        assert floor.line().closed_short_at is None
        assert floor.line().status == "partially_delivered"
