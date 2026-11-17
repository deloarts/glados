"""
How a canceled or force-completed lot settles its raw material demand
(lot_cascades.settle_input_demand): a demand nothing of which is placed or
arrived is canceled and gives up its allocations; any other is fulfilled by
hand at what arrived, and its allocations on supplier lines that still wait
for pieces are cut to what reached them, so the rest of those lines is free
capacity. A settled demand is left alone.
"""

from datetime import UTC
from datetime import datetime
from types import SimpleNamespace

from src.modules.fulfillment.application.services.lot_cascades import settle_input_demand
from src.modules.fulfillment.domain.entities.source_item_allocation import (
    SourceItemDemandAllocation,
)
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from tests.factories import make_user
from tests.unit.production_lot._helpers import make_order_item
from tests.unit.production_lot._helpers import make_source_item_demand
from tests.unit.production_lot.fakes import FakeBoughtItemAllocationRepository
from tests.unit.production_lot.fakes import FakeOrderItemRepository
from tests.unit.production_lot.fakes import FakeSourceItemAllocationRepository
from tests.unit.production_lot.fakes import FakeSourceItemDemandRepository

NOW = datetime(2026, 10, 25, 9, 0, tzinfo=UTC)
ACTOR = make_user()


class _Touches:
    """Records the demands the cascade registers."""

    def __init__(self) -> None:
        self.demands: list[tuple[object, list[int]]] = []

    def touch_demands(self, aggregate: object, ids) -> None:
        self.demands.append((aggregate, list(ids)))


def _line(id: int, status: OrderItemStatus, delivered: float = 0.0, quantity: float = 10.0):
    line = make_order_item(id=id, line_type=OrderLineType.SOURCE)
    line.status = status
    line.quantity = quantity
    line.quantity_delivered = delivered
    return line


class _Case:
    def __init__(
        self,
        lines,
        allocations,
        demand_status: SourceItemDemandStatus = SourceItemDemandStatus.ORDERED,
    ) -> None:
        self.demand = make_source_item_demand(id=50, lot_id=1, status=demand_status)
        self.demand.quantity = 10.0
        self.demands = FakeSourceItemDemandRepository([self.demand])
        self.allocations = FakeSourceItemAllocationRepository(allocations)
        self.lines = FakeOrderItemRepository(lines)
        self.touches = _Touches()
        self.lot = SimpleNamespace(id=1, lot_number="LOT-1", input_demand_id=50)

    async def settle(self):
        return await settle_input_demand(
            self.lot,  # type: ignore[arg-type]
            ACTOR,
            NOW,
            reason="lot 'LOT-1' was canceled",
            source_item_demands=self.demands,
            source_allocations=self.allocations,
            bought_allocations=FakeBoughtItemAllocationRepository(),
            order_item_repo=self.lines,
            reconciler=self.touches,  # type: ignore[arg-type]
        )

    async def stored(self):
        return await self.demands.get_by_id(50)


def _on(line_id: int, quantity: float) -> SourceItemDemandAllocation:
    return SourceItemDemandAllocation(demand_item_id=50, order_item_id=line_id, quantity=quantity)


async def test_a_demand_nothing_of_which_is_placed_is_canceled() -> None:
    case = _Case([_line(1, OrderItemStatus.PENDING)], [_on(1, 10.0)])

    released = (await case.settle()).open_lines

    demand = await case.stored()
    assert demand is not None and demand.canceled_at == NOW
    assert case.allocations.allocations == []
    assert released == []


async def test_a_placed_demand_is_fulfilled_at_what_arrived_and_frees_the_open_rest() -> None:
    case = _Case([_line(1, OrderItemStatus.PARTIALLY_DELIVERED, delivered=4.0)], [_on(1, 10.0)])

    released = (await case.settle()).open_lines

    demand = await case.stored()
    assert demand is not None
    assert (demand.fulfilled_manually_at, demand.canceled_at) == (NOW, None)
    assert "Fulfilled short at 4.000 of 10.000" in demand.changes[-1]
    assert "order line(s) #1" in demand.changes[-1]
    assert [(a.order_item_id, a.quantity) for a in case.allocations.allocations] == [(1, 4.0)]
    assert [line.id for line in released] == [1]


async def test_a_delivered_line_keeps_its_allocation() -> None:
    case = _Case(
        [
            _line(1, OrderItemStatus.DELIVERED, delivered=6.0, quantity=6.0),
            _line(2, OrderItemStatus.ORDERED),
        ],
        [_on(1, 6.0), _on(2, 4.0)],
    )

    released = (await case.settle()).open_lines

    assert [(a.order_item_id, a.quantity) for a in case.allocations.allocations] == [(1, 6.0)]
    assert [line.id for line in released] == [2]
    demand = await case.stored()
    assert demand is not None and "Fulfilled short at 6.000 of 10.000" in demand.changes[-1]


async def test_stock_alone_fulfils_the_demand() -> None:
    stock = SourceItemDemandAllocation(demand_item_id=50, order_item_id=None, quantity=3.0)
    case = _Case([], [stock], demand_status=SourceItemDemandStatus.ALLOCATED)

    released = (await case.settle()).open_lines

    demand = await case.stored()
    assert demand is not None and demand.fulfilled_manually_at == NOW
    assert case.allocations.allocations == [stock]
    assert released == []


async def test_a_settled_demand_is_left_alone() -> None:
    case = _Case(
        [_line(1, OrderItemStatus.DELIVERED, delivered=10.0)],
        [_on(1, 10.0)],
        SourceItemDemandStatus.FULFILLED,
    )

    released = (await case.settle()).open_lines

    demand = await case.stored()
    assert demand is not None
    assert (demand.fulfilled_manually_at, demand.canceled_at) == (None, None)
    assert released == [] and case.touches.demands == []
