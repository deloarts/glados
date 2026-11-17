"""
Auto-allocation notes what it allocated on the demand's changelog, and the
lifecycle reconciler adds the line naming the status the demand left and
the status it reached, for both demand families that auto-allocate.
In-memory fakes, no database.
"""

from src.modules.fulfillment.application.dto.allocation_dto import AutoAllocateCommand
from src.modules.fulfillment.application.dto.source_item_allocation_dto import (
    AutoAllocateSourceItemDemandCommand,
)
from src.modules.fulfillment.application.services.allocation_fill import LineFillRepos
from src.modules.fulfillment.application.use_cases.bought_item_demand.auto_allocate import (
    AutoAllocate,
)
from src.modules.fulfillment.application.use_cases.source_item_allocation.auto_allocate import (
    AutoAllocateSourceItemDemand,
)
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler
from tests.unit.production_lot.fakes import FakeBoughtItemAllocationRepository
from tests.unit.production_lot.fakes import FakeProjectRepository
from tests.unit.production_lot.fakes import FakeSourceItemAllocationRepository
from tests.unit.test_bought_item_allocation_use_cases import (
    FakeAllocationRepository as BoughtAllocations,
)
from tests.unit.test_bought_item_allocation_use_cases import FakeDemandRepository as BoughtDemands
from tests.unit.test_bought_item_allocation_use_cases import FakeOrderItemRepository as BoughtLines
from tests.unit.test_bought_item_allocation_use_cases import FakeUnitOfWork
from tests.unit.test_bought_item_allocation_use_cases import make_demand as make_bought_demand
from tests.unit.test_bought_item_allocation_use_cases import make_order_item as make_bought_line
from tests.unit.test_source_item_allocation_use_cases import (
    FakeAllocationRepository as SourceAllocations,
)
from tests.unit.test_source_item_allocation_use_cases import FakeDemandRepository as SourceDemands
from tests.unit.test_source_item_allocation_use_cases import FakeOrderItemRepository as SourceLines
from tests.unit.test_source_item_allocation_use_cases import make_demand as make_source_demand
from tests.unit.test_source_item_allocation_use_cases import make_order_item as make_source_line

ALLOCATOR = make_user(permissions=[Permission.WRITE_ALLOCATIONS])


async def test_bought_auto_allocate_logs_the_old_and_the_new_status():
    demands = BoughtDemands([make_bought_demand(id=1, quantity=10.0, item_id=1)])
    lines = BoughtLines([make_bought_line(id=1, quantity=6.0, bought_item_id=1)])

    allocations = BoughtAllocations()
    await AutoAllocate(
        demands,
        lines,
        allocations,
        uow=FakeUnitOfWork(),
        reconciler=demand_reconciler(
            bought_demands=demands, bought_allocations=allocations, order_items=lines
        ),
        project_repo=FakeProjectRepository(),
        fill_repos=LineFillRepos(bought=allocations, source=FakeSourceItemAllocationRepository()),
    ).execute(ALLOCATOR, AutoAllocateCommand(demand_item_id=1))

    demand = await demands.get_by_id(1)
    assert demand is not None
    assert demand.changes[-2].endswith("Auto-allocated 6.000 pcs across 1 order item(s).")
    assert demand.changes[-1].endswith("Status: open → allocated (allocation recalculated).")


async def test_source_auto_allocate_logs_the_old_and_the_new_status():
    demands = SourceDemands([make_source_demand(id=1, quantity=10.0, source_item_id=1)])
    lines = SourceLines([make_source_line(id=1, quantity=6.0, source_item_id=1)])

    allocations = SourceAllocations()
    await AutoAllocateSourceItemDemand(
        demands,
        lines,
        allocations,
        uow=FakeUnitOfWork(),
        reconciler=demand_reconciler(
            source_demands=demands, source_allocations=allocations, order_items=lines
        ),
        project_repo=FakeProjectRepository(),
        fill_repos=LineFillRepos(bought=FakeBoughtItemAllocationRepository(), source=allocations),
    ).execute(ALLOCATOR, AutoAllocateSourceItemDemandCommand(demand_item_id=1))

    demand = await demands.get_by_id(1)
    assert demand is not None
    assert demand.changes[-2].endswith("Auto-allocated 6.000 pcs across 1 order item(s).")
    assert demand.changes[-1].endswith("Status: open → allocated (allocation recalculated).")
