"""
Tests for LotMaterialDemand (application/services/lot_material_demand.py):
settling a lot's raw material demand keeps what reached it, and resizing it
never goes below that and releases only unarrived pieces, newest lines first.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.fulfillment.application.services.lot_material_demand import LotMaterialDemand
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.source_item_allocation import (
    SourceItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from tests.factories import make_user
from tests.unit.production_lot._helpers import make_order_item
from tests.unit.production_lot._helpers import make_source_item_demand
from tests.unit.production_lot.fakes import FakeOrderItemRepository
from tests.unit.production_lot.fakes import FakeSourceItemAllocationRepository
from tests.unit.production_lot.fakes import FakeSourceItemDemandRepository
from tests.unit.production_lot.fakes import fake_line_release

NOW = datetime(2026, 11, 24, 12, 0, tzinfo=UTC)
ACTOR = make_user()


def _line(id: int, quantity: float, delivered: float) -> OrderItem:
    line = make_order_item(id=id, line_type=OrderLineType.SOURCE)
    line.status = OrderItemStatus.PARTIALLY_DELIVERED if delivered > 0 else OrderItemStatus.ORDERED
    line.quantity = quantity
    line.quantity_delivered = delivered
    return line


class _World:
    def __init__(
        self,
        demand: SourceItemDemandItem,
        lines: list[OrderItem],
        allocations: list[SourceItemDemandAllocation],
    ) -> None:
        self.demands = FakeSourceItemDemandRepository([demand])
        self.allocations = FakeSourceItemAllocationRepository(allocations)
        self.service = LotMaterialDemand(
            self.demands,  # type: ignore[arg-type]
            self.allocations,  # type: ignore[arg-type]
            fake_line_release(self.allocations, FakeOrderItemRepository(lines)),
        )

    def held(self, demand_id: int) -> dict[int | None, float]:
        return {
            a.order_item_id: a.quantity
            for a in self.allocations.allocations
            if a.demand_item_id == demand_id
        }


def _demand(status: SourceItemDemandStatus, quantity: float = 10.0) -> SourceItemDemandItem:
    demand = make_source_item_demand(id=50, status=status)
    demand.quantity = quantity
    return demand


class TestSettle:
    async def test_open_demand_is_canceled(self) -> None:
        demand = _demand(SourceItemDemandStatus.OPEN)
        world = _World(demand, [], [])

        arrived = await world.service.settle(ACTOR, demand, NOW, reason="first step external")

        assert arrived == 0.0
        assert demand.canceled_at == NOW
        assert "Demand canceled (first step external)." in demand.changes[-1]

    async def test_nothing_arrived_cancels_and_releases(self) -> None:
        demand = _demand(SourceItemDemandStatus.ORDERED)
        world = _World(
            demand,
            [_line(1, 10.0, 0.0)],
            [SourceItemDemandAllocation(demand_item_id=50, order_item_id=1, quantity=10.0)],
        )

        arrived = await world.service.settle(ACTOR, demand, NOW, reason="first step external")

        assert arrived == 0.0
        assert demand.canceled_at == NOW
        assert world.held(50) == {}

    async def test_arrived_pieces_stay_and_the_rest_is_released(self) -> None:
        demand = _demand(SourceItemDemandStatus.ORDERED)
        world = _World(
            demand,
            [_line(1, 10.0, 4.0)],
            [SourceItemDemandAllocation(demand_item_id=50, order_item_id=1, quantity=10.0)],
        )

        arrived = await world.service.settle(ACTOR, demand, NOW, reason="first step external")

        assert arrived == pytest.approx(4.0)
        assert demand.canceled_at is None
        assert demand.fulfilled_manually_at == NOW
        assert world.held(50) == {1: pytest.approx(4.0)}


class TestResize:
    async def test_grow_sets_the_quantity(self) -> None:
        demand = _demand(SourceItemDemandStatus.OPEN, quantity=6.0)
        world = _World(demand, [], [])

        quantity = await world.service.resize(ACTOR, demand, 10.0, NOW, reason="mixed")

        assert quantity == 10.0
        assert (await world.demands.get_by_id(50)).quantity == 10.0  # type: ignore[union-attr]
        assert "from 6 to 10 pcs (mixed)" in demand.changes[-1]

    async def test_shrink_without_allocations_only_sets_the_quantity(self) -> None:
        demand = _demand(SourceItemDemandStatus.OPEN)
        world = _World(demand, [], [])

        assert await world.service.resize(ACTOR, demand, 6.0, NOW, reason="mixed") == 6.0

    async def test_shrink_releases_unarrived_pieces_from_the_newest_line(self) -> None:
        demand = _demand(SourceItemDemandStatus.ORDERED)
        world = _World(
            demand,
            [_line(1, 5.0, 0.0), _line(2, 5.0, 0.0)],
            [
                SourceItemDemandAllocation(demand_item_id=50, order_item_id=1, quantity=5.0),
                SourceItemDemandAllocation(demand_item_id=50, order_item_id=2, quantity=5.0),
            ],
        )

        quantity = await world.service.resize(ACTOR, demand, 7.0, NOW, reason="mixed")

        assert quantity == 7.0
        assert world.held(50) == {1: 5.0, 2: pytest.approx(2.0)}
        assert "released 3.000 pcs that had not arrived" in demand.changes[-1]

    async def test_shrink_never_goes_below_what_arrived(self) -> None:
        demand = _demand(SourceItemDemandStatus.ORDERED)
        world = _World(
            demand,
            [_line(1, 10.0, 8.0)],
            [SourceItemDemandAllocation(demand_item_id=50, order_item_id=1, quantity=10.0)],
        )

        quantity = await world.service.resize(ACTOR, demand, 6.0, NOW, reason="mixed")

        assert quantity == pytest.approx(8.0)
        assert world.held(50) == {1: pytest.approx(8.0)}

    async def test_same_quantity_writes_nothing(self) -> None:
        demand = _demand(SourceItemDemandStatus.OPEN)
        world = _World(demand, [], [])

        await world.service.resize(ACTOR, demand, 10.0, NOW, reason="mixed")

        assert demand.changes == []
