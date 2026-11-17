"""
Unit tests for MarkOrderItemOrdered, MarkOrderItemRequested and
MarkAllOrderItemsOrdered: the line transitions, the order they must belong
to, the automatic submit once every line is ordered, and the demands and
lots that advance with an ordered line. No database, no HTTP; every
dependency is an in-memory fake.
"""

from datetime import date

import pytest

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.fulfillment.application.use_cases.order.mark_order_item_ordered import (
    MarkAllOrderItemsOrdered,
)
from src.modules.fulfillment.application.use_cases.order.mark_order_item_ordered import (
    MarkOrderItemOrdered,
)
from src.modules.fulfillment.application.use_cases.order.mark_order_item_ordered import (
    MarkOrderItemRequested,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.errors import OrderItemNotFoundError
from src.modules.fulfillment.domain.errors import OrderNotFoundError
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler
from tests.unit.lifecycle.fake_reconciler import order_reconciler
from tests.unit.order._helpers import FakeAllocationRepository
from tests.unit.order._helpers import FakeDemandRepository
from tests.unit.order._helpers import FakeOrderItemRepository
from tests.unit.order._helpers import FakeOrderRepository
from tests.unit.order._helpers import FakeProductionLotRepository
from tests.unit.order._helpers import FakeSourceItemAllocationRepository
from tests.unit.order._helpers import FakeSourceItemDemandRepository
from tests.unit.order._helpers import FakeUnitOfWork
from tests.unit.order._helpers import lot_aware_reconciler
from tests.unit.order._helpers import make_allocation
from tests.unit.order._helpers import make_demand
from tests.unit.order._helpers import make_order
from tests.unit.order._helpers import make_order_item
from tests.unit.order._helpers import make_source_item_allocation
from tests.unit.order._helpers import make_source_item_demand


class TestMarkOrderItemOrdered:
    def setup_method(self):
        self.actor = make_user(permissions=[Permission.WRITE_ORDERS])
        self.order = make_order(id=1, status=OrderStatus.DRAFT)
        self.order_item = make_order_item(id=1, order_id=1, status=OrderItemStatus.PENDING)
        self.order_repo = FakeOrderRepository([self.order])
        self.order_item_repo = FakeOrderItemRepository([self.order_item])
        self.allocation_repo = FakeAllocationRepository()
        self.demand_repo = FakeDemandRepository()
        self.use_case = MarkOrderItemOrdered(
            order_item_repo=self.order_item_repo,
            order_repo=self.order_repo,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                orders=self.order_repo,
                order_items=self.order_item_repo,
                bought_demands=self.demand_repo,
                bought_allocations=self.allocation_repo,
            ),
        )

    async def test_transitions_item_to_ordered(self):
        result = await self.use_case.execute(actor=self.actor, order_id=1, order_item_id=1)
        assert result.status == "ordered"

    async def test_order_not_found_raises(self):
        with pytest.raises(OrderNotFoundError):
            await self.use_case.execute(actor=self.actor, order_id=999, order_item_id=1)

    async def test_order_item_not_found_raises(self):
        with pytest.raises(OrderItemNotFoundError):
            await self.use_case.execute(actor=self.actor, order_id=1, order_item_id=999)

    async def test_rejects_item_belonging_to_another_order(self):
        """The item must belong to the order named in the path."""
        other_order = make_order(id=2, status=OrderStatus.DRAFT)
        await self.order_repo.save(other_order)
        foreign_item = make_order_item(id=2, order_id=2, status=OrderItemStatus.PENDING)
        await self.order_item_repo.save(foreign_item)

        with pytest.raises(OrderItemNotFoundError):
            await self.use_case.execute(actor=self.actor, order_id=1, order_item_id=2)
        assert (await self.order_item_repo.get_by_id(2)).status == "pending"

    async def test_rejects_item_from_a_manage_only_order_named_via_a_draft_order(self):
        """The concrete escalation bypass: the actor holds write:orders only.
        Order A (#1) is DRAFT, so assert_can_update passes against it; order B
        is past draft and would need manage:orders. Naming A in the path while
        targeting B's item must not mutate B's item."""
        order_b = make_order(id=2, status=OrderStatus.ORDERED)
        await self.order_repo.save(order_b)
        item_b = make_order_item(id=2, order_id=2, status=OrderItemStatus.PENDING)
        await self.order_item_repo.save(item_b)

        with pytest.raises(OrderItemNotFoundError):
            await self.use_case.execute(actor=self.actor, order_id=1, order_item_id=2)
        assert (await self.order_item_repo.get_by_id(2)).status == "pending"
        assert (await self.order_repo.get_by_id(2)).status == "ordered"

    async def test_single_item_order_auto_submits(self):
        await self.use_case.execute(actor=self.actor, order_id=1, order_item_id=1)
        order = await self.order_repo.get_by_id(1)
        assert order.status == "ordered"

    async def test_linked_demand_transitions_from_allocated_to_ordered(self):
        demand = make_demand(id=1, status=BoughtItemDemandStatus.ALLOCATED)
        allocation = make_allocation(demand_item_id=1, order_item_id=1)
        demand_repo = FakeDemandRepository([demand])
        allocation_repo = FakeAllocationRepository([allocation])
        use_case = MarkOrderItemOrdered(
            order_item_repo=self.order_item_repo,
            order_repo=self.order_repo,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                orders=self.order_repo,
                order_items=self.order_item_repo,
                bought_demands=demand_repo,
                bought_allocations=allocation_repo,
            ),
        )
        await use_case.execute(actor=self.actor, order_id=1, order_item_id=1)
        assert (await demand_repo.get_by_id(1)).status == "ordered"

    async def test_made_line_ordered_advances_lot_to_planned(self):
        made_order_item = make_order_item(id=2, order_id=1, status=OrderItemStatus.PENDING)
        made_order_item.line_type = OrderLineType.MADE
        made_order_item.lot_position_id = 1
        order_item_repo = FakeOrderItemRepository([made_order_item])

        lot = ProductionLot(
            id=1,
            created=date(2026, 1, 1),
            changed=None,
            changes=[],
            lot_number="LOT-1",
            quantity=5.0,
            status=LotStatus.DRAFT,
            priority=UrgencyClass.NORMAL,
            note=None,
            creator_id=1,
            made_item_id=1,
            project_id=1,
            input_demand_id=None,
        )
        position = LotPosition(
            id=1,
            created=date(2026, 1, 1),
            changed=None,
            changes=[],
            sequence=1,
            kind=LotPositionKind.EXTERNAL,
            status=LotPositionStatus.PENDING,
            quantity=5.0,
            quantity_completed=0.0,
            note=None,
            creator_id=1,
            lot_id=1,
        )
        lot_repo = FakeProductionLotRepository(lots=[lot], positions=[position])

        use_case = MarkOrderItemOrdered(
            order_item_repo=order_item_repo,
            order_repo=self.order_repo,
            uow=FakeUnitOfWork(),
            reconciler=lot_aware_reconciler(self.order_repo, order_item_repo, lot_repo),
        )
        await use_case.execute(actor=self.actor, order_id=1, order_item_id=2)

        assert (await lot_repo.get_position_by_id(1)).status == "ordered_or_queued"
        assert (await lot_repo.get_by_id(1)).status == "planned"

    async def test_unprivileged_cannot_mark(self):
        actor = make_user(permissions=[])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor=actor, order_id=1, order_item_id=1)

    async def test_linked_source_item_demand_transitions_from_allocated_to_ordered(self):
        demand = make_source_item_demand(id=1, status=SourceItemDemandStatus.ALLOCATED)
        allocation = make_source_item_allocation(demand_item_id=1, order_item_id=1)
        source_item_demand_repo = FakeSourceItemDemandRepository([demand])
        source_item_allocation_repo = FakeSourceItemAllocationRepository([allocation])
        use_case = MarkOrderItemOrdered(
            order_item_repo=self.order_item_repo,
            order_repo=self.order_repo,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                orders=self.order_repo,
                order_items=self.order_item_repo,
                bought_demands=self.demand_repo,
                bought_allocations=self.allocation_repo,
                source_demands=source_item_demand_repo,
                source_allocations=source_item_allocation_repo,
            ),
        )
        await use_case.execute(actor=self.actor, order_id=1, order_item_id=1)
        assert (await source_item_demand_repo.get_by_id(1)).status == "ordered"

    async def test_source_item_repos_optional_and_default_to_no_transition(self):
        """Source-item repos are optional (mirrors the MADE-line params): a
        caller that never passes them gets no source transition and no
        error."""
        result = await self.use_case.execute(actor=self.actor, order_id=1, order_item_id=1)
        assert result.status == "ordered"


class TestMarkOrderItemRequested:
    def setup_method(self):
        self.actor = make_user(permissions=[Permission.WRITE_ORDERS])
        self.order = make_order(id=1, status=OrderStatus.DRAFT)
        self.order_item = make_order_item(id=1, order_id=1, status=OrderItemStatus.PENDING)
        self.order_repo = FakeOrderRepository([self.order])
        self.order_item_repo = FakeOrderItemRepository([self.order_item])
        self.use_case = MarkOrderItemRequested(
            order_item_repo=self.order_item_repo,
            order_repo=self.order_repo,
            uow=FakeUnitOfWork(),
            reconciler=order_reconciler(self.order_repo, self.order_item_repo),
        )

    async def test_transitions_item_to_requested(self):
        result = await self.use_case.execute(actor=self.actor, order_id=1, order_item_id=1)
        assert result.status == "requested"

    async def test_rejects_item_belonging_to_another_order(self):
        other_order = make_order(id=2, status=OrderStatus.DRAFT)
        await self.order_repo.save(other_order)
        foreign_item = make_order_item(id=2, order_id=2, status=OrderItemStatus.PENDING)
        await self.order_item_repo.save(foreign_item)

        with pytest.raises(OrderItemNotFoundError):
            await self.use_case.execute(actor=self.actor, order_id=1, order_item_id=2)
        assert (await self.order_item_repo.get_by_id(2)).status == "pending"

    async def test_rejects_item_from_a_manage_only_order_named_via_a_draft_order(self):
        order_b = make_order(id=2, status=OrderStatus.ORDERED)
        await self.order_repo.save(order_b)
        item_b = make_order_item(id=2, order_id=2, status=OrderItemStatus.PENDING)
        await self.order_item_repo.save(item_b)

        with pytest.raises(OrderItemNotFoundError):
            await self.use_case.execute(actor=self.actor, order_id=1, order_item_id=2)
        assert (await self.order_item_repo.get_by_id(2)).status == "pending"


class TestMarkAllOrderItemsOrdered:
    def setup_method(self):
        self.actor = make_user(permissions=[Permission.WRITE_ORDERS])
        self.order = make_order(id=1, status=OrderStatus.DRAFT)
        items = [
            make_order_item(id=1, order_id=1, status=OrderItemStatus.PENDING),
            make_order_item(id=2, order_id=1, status=OrderItemStatus.PENDING),
        ]
        self.order_repo = FakeOrderRepository([self.order])
        self.order_item_repo = FakeOrderItemRepository(items)
        self.allocation_repo = FakeAllocationRepository()
        self.demand_repo = FakeDemandRepository()
        self.use_case = MarkAllOrderItemsOrdered(
            order_item_repo=self.order_item_repo,
            order_repo=self.order_repo,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                orders=self.order_repo,
                order_items=self.order_item_repo,
                bought_demands=self.demand_repo,
                bought_allocations=self.allocation_repo,
            ),
        )

    async def test_all_pending_items_become_ordered(self):
        results = await self.use_case.execute(actor=self.actor, order_id=1)
        assert len(results) == 2
        assert all(r.status == "ordered" for r in results)

    async def test_order_auto_submits_after_all_ordered(self):
        await self.use_case.execute(actor=self.actor, order_id=1)
        order = await self.order_repo.get_by_id(1)
        assert order.status == "ordered"

    async def test_already_ordered_items_are_skipped(self):
        self.order_item_repo._items[1].status = OrderItemStatus.ORDERED
        results = await self.use_case.execute(actor=self.actor, order_id=1)
        assert len(results) == 1
        assert results[0].id == 2

    async def test_order_not_found_raises(self):
        with pytest.raises(OrderNotFoundError):
            await self.use_case.execute(actor=self.actor, order_id=999)

    async def test_linked_source_item_demand_transitions_from_allocated_to_ordered(self):
        demand = make_source_item_demand(id=1, status=SourceItemDemandStatus.ALLOCATED)
        allocation = make_source_item_allocation(demand_item_id=1, order_item_id=1)
        source_item_demand_repo = FakeSourceItemDemandRepository([demand])
        source_item_allocation_repo = FakeSourceItemAllocationRepository([allocation])
        use_case = MarkAllOrderItemsOrdered(
            order_item_repo=self.order_item_repo,
            order_repo=self.order_repo,
            uow=FakeUnitOfWork(),
            reconciler=demand_reconciler(
                orders=self.order_repo,
                order_items=self.order_item_repo,
                bought_demands=self.demand_repo,
                bought_allocations=self.allocation_repo,
                source_demands=source_item_demand_repo,
                source_allocations=source_item_allocation_repo,
            ),
        )
        await use_case.execute(actor=self.actor, order_id=1)
        assert (await source_item_demand_repo.get_by_id(1)).status == "ordered"
