"""
A demand may draw on an order line of another unit, since nothing converts
between units yet; the allocation reads and the demand summary flag it, so
the clients can warn. Units compare without case and surrounding spaces.
"""

import pytest

from src.modules.fulfillment.application.use_cases.bought_item_demand.get_allocations import (
    GetAllocationsForDemand,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.get_allocations import (
    GetDemandSummary,
)
from src.modules.fulfillment.domain.entities.bought_item_allocation import (
    BoughtItemDemandAllocation,
)
from src.modules.fulfillment.domain.services.allocation_coverage import units_differ
from tests.unit.test_bought_item_allocation_use_cases import FakeAllocationRepository
from tests.unit.test_bought_item_allocation_use_cases import FakeCatalogueRepository
from tests.unit.test_bought_item_allocation_use_cases import FakeDemandRepository
from tests.unit.test_bought_item_allocation_use_cases import FakeOrderItemRepository
from tests.unit.test_bought_item_allocation_use_cases import FakeOrderRepository
from tests.unit.test_bought_item_allocation_use_cases import make_demand
from tests.unit.test_bought_item_allocation_use_cases import make_order_item


@pytest.mark.parametrize(
    ("demand_unit", "line_unit", "differ"),
    [("PCS", "pcs", False), (" M ", "M", False), ("PCS", "M", True), ("SET", "PCS", True)],
)
def test_units_differ(demand_unit: str, line_unit: str, differ: bool) -> None:
    assert units_differ(demand_unit, line_unit) is differ


def _repos(line_unit: str):
    demand = make_demand(id=1)
    line = make_order_item(id=1)
    line.unit = line_unit
    allocation = BoughtItemDemandAllocation(demand_item_id=1, order_item_id=1, quantity=4.0)
    return (
        FakeDemandRepository([demand]),
        FakeAllocationRepository([allocation]),
        FakeOrderItemRepository([line]),
    )


@pytest.mark.parametrize(("line_unit", "mismatch"), [("M", True), ("PCS", False)])
async def test_the_allocation_read_flags_a_line_of_another_unit(
    line_unit: str, mismatch: bool
) -> None:
    demands, allocations, lines = _repos(line_unit)

    [result] = await GetAllocationsForDemand(
        allocations, lines, FakeOrderRepository(), demand_repo=demands
    ).execute(1)

    assert (result.demand_unit, result.order_item_unit) == ("pcs", line_unit)
    assert result.unit_mismatch is mismatch


@pytest.mark.parametrize(("line_unit", "mismatch"), [("M", True), ("PCS", False)])
async def test_the_demand_summary_flags_a_line_of_another_unit(
    line_unit: str, mismatch: bool
) -> None:
    demands, allocations, lines = _repos(line_unit)

    summary = await GetDemandSummary(
        demands, allocations, lines, FakeOrderRepository(), FakeCatalogueRepository()
    ).execute(1)

    assert summary.unit_mismatch is mismatch
