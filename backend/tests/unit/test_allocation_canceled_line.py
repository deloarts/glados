"""
A canceled order line takes no new allocation, for bought and source item
demands alike. The line keeps its quantity, so its free capacity alone
would not refuse one; the writers check the line under their lock and answer
with AllocationOrderItemCanceledError (409), after the permission check and
without writing anything. No database, no HTTP.
"""

from datetime import UTC
from datetime import datetime

import pytest

from src.modules.fulfillment.application.dto.allocation_dto import CreateAllocationCommand
from src.modules.fulfillment.application.dto.source_item_allocation_dto import (
    CreateSourceItemAllocationCommand,
)
from src.modules.fulfillment.application.services.allocation_fill import LineFillRepos
from src.modules.fulfillment.application.use_cases.bought_item_demand.create_allocation import (
    CreateAllocation,
)
from src.modules.fulfillment.application.use_cases.source_item_allocation.create_allocation import (
    CreateSourceItemAllocation,
)
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.errors import AllocationOrderItemCanceledError
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.unit import test_bought_item_allocation_use_cases as bought
from tests.unit import test_source_item_allocation_use_cases as source
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler
from tests.unit.production_lot.fakes import FakeBoughtItemAllocationRepository
from tests.unit.production_lot.fakes import FakeSourceItemAllocationRepository

CANCELED_AT = datetime(2026, 1, 3, tzinfo=UTC)


def _canceled(line: OrderItem) -> OrderItem:
    line.status = OrderItemStatus.CANCELED
    line.canceled_at = CANCELED_AT
    return line


class TestBoughtDemand:
    def setup_method(self) -> None:
        self.demands = bought.FakeDemandRepository([bought.make_demand(id=1, quantity=10.0)])
        self.lines = bought.FakeOrderItemRepository([_canceled(bought.make_order_item(id=1))])
        self.allocations = bought.FakeAllocationRepository()
        self.use_case = CreateAllocation(
            self.allocations,
            self.demands,
            self.lines,
            uow=bought.FakeUnitOfWork(),
            reconciler=demand_reconciler(
                bought_demands=self.demands,
                bought_allocations=self.allocations,
                order_items=self.lines,
            ),
            fill_repos=LineFillRepos(
                bought=self.allocations, source=FakeSourceItemAllocationRepository()
            ),
        )
        self.command = CreateAllocationCommand(demand_item_id=1, order_item_id=1, quantity=2.0)

    async def test_an_allocation_onto_a_canceled_line_is_refused(self) -> None:
        actor = bought.make_user(permissions=[Permission.WRITE_ALLOCATIONS])

        with pytest.raises(AllocationOrderItemCanceledError):
            await self.use_case.execute(actor, self.command)

        assert self.allocations.allocations == []

    async def test_the_permission_is_checked_before_the_line(self) -> None:
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(bought.make_user(permissions=[]), self.command)


class TestSourceDemand:
    def setup_method(self) -> None:
        self.demands = source.FakeDemandRepository(
            [source.make_demand(id=1, quantity=10.0, source_item_id=1)]
        )
        self.lines = source.FakeOrderItemRepository(
            [_canceled(source.make_order_item(id=1, quantity=10.0, source_item_id=1))]
        )
        self.allocations = source.FakeAllocationRepository()
        self.use_case = CreateSourceItemAllocation(
            self.allocations,
            self.demands,
            self.lines,
            uow=source.FakeUnitOfWork(),
            reconciler=demand_reconciler(
                source_allocations=self.allocations,
                source_demands=self.demands,
                order_items=self.lines,
            ),
            fill_repos=LineFillRepos(
                bought=FakeBoughtItemAllocationRepository(), source=self.allocations
            ),
        )
        self.command = CreateSourceItemAllocationCommand(
            demand_item_id=1, order_item_id=1, quantity=2.0
        )

    async def test_an_allocation_onto_a_canceled_line_is_refused(self) -> None:
        actor = source.make_user(permissions=[Permission.WRITE_ALLOCATIONS])

        with pytest.raises(AllocationOrderItemCanceledError):
            await self.use_case.execute(actor, self.command)

        assert await self.allocations.get_by_demand_item_id(1) == []

    async def test_the_permission_is_checked_before_the_line(self) -> None:
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(source.make_user(permissions=[]), self.command)
