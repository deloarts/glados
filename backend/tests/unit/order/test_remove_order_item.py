"""
Unit tests for RemoveOrderItem: which lines may be removed, how the linked
lot position falls back to its earlier kind, the allocations that are
released, and the schedule recompute after the commit. No database, no
HTTP; every dependency is an in-memory fake.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

import pytest

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.fulfillment.application.use_cases.order.delete_order_item import RemoveOrderItem
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)
from src.modules.fulfillment.domain.errors import OrderItemCannotBeRemovedError
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler
from tests.unit.order._helpers import FailingRecomputeSchedule
from tests.unit.order._helpers import FakeAllocationRepository
from tests.unit.order._helpers import FakeDemandRepository
from tests.unit.order._helpers import FakeOrderItemRepository
from tests.unit.order._helpers import FakeOrderRepository
from tests.unit.order._helpers import FakeProductionLotRepository
from tests.unit.order._helpers import FakeRecomputeSchedule
from tests.unit.order._helpers import FakeSourceItemAllocationRepository
from tests.unit.order._helpers import FakeSourceItemDemandRepository
from tests.unit.order._helpers import FakeUnitOfWork
from tests.unit.order._helpers import lot_aware_reconciler
from tests.unit.order._helpers import make_allocation
from tests.unit.order._helpers import make_demand
from tests.unit.order._helpers import make_order
from tests.unit.order._helpers import make_order_item
from tests.unit.order._helpers import make_production_order
from tests.unit.order._helpers import make_source_item_allocation
from tests.unit.order._helpers import make_source_item_demand
from tests.unit.production_order._helpers import give_status_facts


class TestRemoveOrderItem:
    def setup_method(self):
        self.actor = make_user(permissions=[Permission.WRITE_ORDERS])
        self.order = make_order(id=1, status=OrderStatus.DRAFT)
        self.order_repo = FakeOrderRepository([self.order])
        self.allocation_repo = FakeAllocationRepository()
        self.demand_repo = FakeDemandRepository()
        self.uow = FakeUnitOfWork()

    def _use_case(self, order_item_repo, lot_repo=None, recompute_schedule=None) -> RemoveOrderItem:
        lots = lot_repo or FakeProductionLotRepository()
        return RemoveOrderItem(
            order_repo=self.order_repo,
            order_item_repo=order_item_repo,
            allocation_repo=self.allocation_repo,
            recompute_schedule=recompute_schedule,
            uow=self.uow,
            reconciler=lot_aware_reconciler(self.order_repo, order_item_repo, lots),
        )

    def _made_lot_and_position(
        self,
        lot_status: LotStatus = LotStatus.DRAFT,
        position_status: LotPositionStatus = LotPositionStatus.ORDERED_OR_QUEUED,
        kind: LotPositionKind = LotPositionKind.EXTERNAL,
    ):
        lot = ProductionLot(
            id=1,
            created=date(2026, 1, 1),
            changed=None,
            changes=[],
            lot_number="LOT-1",
            quantity=5.0,
            status=lot_status,
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
            kind=kind,
            status=position_status,
            quantity=5.0,
            quantity_completed=0.0,
            note=None,
            creator_id=1,
            lot_id=1,
        )
        return lot, position

    async def test_removes_a_bought_line_item(self):
        item = make_order_item(id=1, order_id=1, status=OrderItemStatus.PENDING)
        order_item_repo = FakeOrderItemRepository([item])
        use_case = self._use_case(order_item_repo)

        await use_case.execute(actor=self.actor, order_id=1, order_item_id=1)

        assert await order_item_repo.get_by_id(1) is None
        assert self.uow.committed is True

    async def test_the_order_keeps_a_line_of_what_was_removed(self):
        item = make_order_item(id=1, order_id=1, status=OrderItemStatus.PENDING)
        order_item_repo = FakeOrderItemRepository([item])

        await self._use_case(order_item_repo).execute(actor=self.actor, order_id=1, order_item_id=1)

        changes = (await self.order_repo.get_by_id(1)).changes
        assert any(f"(order item #1, {item.quantity:g} {item.unit}) removed." in c for c in changes)

    async def test_blocked_for_delivered_item(self):
        item = make_order_item(id=1, order_id=1, status=OrderItemStatus.DELIVERED)
        order_item_repo = FakeOrderItemRepository([item])
        use_case = self._use_case(order_item_repo)

        with pytest.raises(OrderItemCannotBeRemovedError):
            await use_case.execute(actor=self.actor, order_id=1, order_item_id=1)

    async def test_reverts_the_linked_lot_position_to_unassigned(self):
        item = make_order_item(id=1, order_id=1, status=OrderItemStatus.PENDING)
        item.line_type = OrderLineType.MADE
        item.lot_position_id = 1
        order_item_repo = FakeOrderItemRepository([item])
        lot, position = self._made_lot_and_position(position_status=LotPositionStatus.PENDING)
        lot_repo = FakeProductionLotRepository(lots=[lot], positions=[position])
        use_case = self._use_case(order_item_repo, lot_repo=lot_repo)

        await use_case.execute(actor=self.actor, order_id=1, order_item_id=1)

        reverted = await lot_repo.get_position_by_id(1)
        assert reverted.kind == "unassigned"
        assert await order_item_repo.get_by_id(1) is None

    async def test_reverts_a_mixed_position_to_internal_not_unassigned(self):
        # Manage Orders assigned an already-internal position, making it
        # MIXED. Removing the order line from the order side must leave the
        # in-house side intact, mirroring UnassignExternalPosition. Falling
        # back to UNASSIGNED here would let lot_rules.assert_positions_unassigned
        # wave through a regroup of a position with a live ProductionOrder.
        item = make_order_item(id=1, order_id=1, status=OrderItemStatus.PENDING)
        item.line_type = OrderLineType.MADE
        item.lot_position_id = 1
        order_item_repo = FakeOrderItemRepository([item])
        lot, position = self._made_lot_and_position(
            position_status=LotPositionStatus.IN_PROGRESS, kind=LotPositionKind.MIXED
        )
        position.quantity_completed = 2.0
        in_house = give_status_facts(
            make_production_order(id=1, lot_position_id=1, status=ProductionOrderStatus.IN_PROGRESS)
        )
        # The in-house side's progress is its completion row of 2 pieces.
        in_house.quantity_completed = 2.0
        in_house.completions = [
            ProductionOrderCompletion(
                id=1,
                production_order_id=1,
                quantity=2.0,
                quantity_accepted=2.0,
                quantity_rejected=0.0,
                completion_date=date(2026, 1, 2),
                note=None,
                operator_id=1,
                recorded_by_id=1,
                created=datetime(2026, 1, 2, tzinfo=UTC),
            )
        ]
        position.production_orders = [in_house]
        lot_repo = FakeProductionLotRepository(lots=[lot], positions=[position])
        use_case = self._use_case(order_item_repo, lot_repo=lot_repo)

        await use_case.execute(actor=self.actor, order_id=1, order_item_id=1)

        reverted = await lot_repo.get_position_by_id(1)
        assert reverted.kind == "internal"
        assert reverted.status == "partially_completed"
        assert reverted.quantity_completed == 2.0
        assert await order_item_repo.get_by_id(1) is None

    async def test_reverts_to_unassigned_when_every_production_order_is_canceled(self):
        item = make_order_item(id=1, order_id=1, status=OrderItemStatus.PENDING)
        item.line_type = OrderLineType.MADE
        item.lot_position_id = 1
        order_item_repo = FakeOrderItemRepository([item])
        lot, position = self._made_lot_and_position(
            position_status=LotPositionStatus.PENDING, kind=LotPositionKind.MIXED
        )
        position.production_orders = [
            give_status_facts(
                make_production_order(
                    id=1, lot_position_id=1, status=ProductionOrderStatus.CANCELED
                )
            )
        ]
        lot_repo = FakeProductionLotRepository(lots=[lot], positions=[position])
        use_case = self._use_case(order_item_repo, lot_repo=lot_repo)

        await use_case.execute(actor=self.actor, order_id=1, order_item_id=1)

        assert (await lot_repo.get_position_by_id(1)).kind == "unassigned"

    async def test_blocked_for_made_line_past_requested(self):
        item = make_order_item(id=1, order_id=1, status=OrderItemStatus.ORDERED)
        item.line_type = OrderLineType.MADE
        item.lot_position_id = 1
        order_item_repo = FakeOrderItemRepository([item])
        lot, position = self._made_lot_and_position()
        lot_repo = FakeProductionLotRepository(lots=[lot], positions=[position])
        use_case = self._use_case(order_item_repo, lot_repo=lot_repo)

        with pytest.raises(OrderItemCannotBeRemovedError):
            await use_case.execute(actor=self.actor, order_id=1, order_item_id=1)

        # Nothing was touched, the item and position are both still there.
        assert await order_item_repo.get_by_id(1) is not None
        assert (await lot_repo.get_position_by_id(1)).kind == "external"

    async def test_allows_made_line_removal_while_requested(self):
        item = make_order_item(id=1, order_id=1, status=OrderItemStatus.REQUESTED)
        item.line_type = OrderLineType.MADE
        item.lot_position_id = 1
        order_item_repo = FakeOrderItemRepository([item])
        lot, position = self._made_lot_and_position(position_status=LotPositionStatus.PENDING)
        lot_repo = FakeProductionLotRepository(lots=[lot], positions=[position])
        use_case = self._use_case(order_item_repo, lot_repo=lot_repo)

        await use_case.execute(actor=self.actor, order_id=1, order_item_id=1)

        assert (await lot_repo.get_position_by_id(1)).kind == "unassigned"

    async def test_deallocates_bought_item_allocations(self):
        item = make_order_item(id=1, order_id=1, status=OrderItemStatus.PENDING)
        order_item_repo = FakeOrderItemRepository([item])
        demand = make_demand(id=1, status=BoughtItemDemandStatus.ALLOCATED)
        allocation = make_allocation(demand_item_id=1, order_item_id=1)
        demand_repo = FakeDemandRepository([demand])
        allocation_repo = FakeAllocationRepository([allocation])
        use_case = RemoveOrderItem(
            order_repo=self.order_repo,
            order_item_repo=order_item_repo,
            allocation_repo=allocation_repo,
            uow=self.uow,
            reconciler=demand_reconciler(
                orders=self.order_repo,
                order_items=order_item_repo,
                bought_demands=demand_repo,
                bought_allocations=allocation_repo,
            ),
        )

        await use_case.execute(actor=self.actor, order_id=1, order_item_id=1)

        assert await allocation_repo.get_by_order_item_id(1) == []

    async def test_deallocates_source_item_demand_allocations(self):
        item = make_order_item(id=1, order_id=1, status=OrderItemStatus.PENDING)
        order_item_repo = FakeOrderItemRepository([item])
        base_demand = make_source_item_demand(id=1, status=SourceItemDemandStatus.ALLOCATED)
        base_allocation = make_source_item_allocation(demand_item_id=1, order_item_id=1)
        source_item_demand_repo = FakeSourceItemDemandRepository([base_demand])
        source_item_allocation_repo = FakeSourceItemAllocationRepository([base_allocation])
        use_case = RemoveOrderItem(
            order_repo=self.order_repo,
            order_item_repo=order_item_repo,
            allocation_repo=self.allocation_repo,
            uow=self.uow,
            source_item_allocation_repo=source_item_allocation_repo,
            reconciler=demand_reconciler(
                orders=self.order_repo,
                order_items=order_item_repo,
                bought_demands=self.demand_repo,
                bought_allocations=self.allocation_repo,
                source_demands=source_item_demand_repo,
                source_allocations=source_item_allocation_repo,
            ),
        )

        await use_case.execute(actor=self.actor, order_id=1, order_item_id=1)

        assert await source_item_allocation_repo.get_by_order_item_id(1) == []
        assert (await source_item_demand_repo.get_by_id(1)).status == "open"

    async def test_recompute_is_called_exactly_once_on_success(self):
        item = make_order_item(id=1, order_id=1, status=OrderItemStatus.PENDING)
        order_item_repo = FakeOrderItemRepository([item])
        recompute = FakeRecomputeSchedule()
        use_case = self._use_case(order_item_repo, recompute_schedule=recompute)

        await use_case.execute(actor=self.actor, order_id=1, order_item_id=1)

        assert recompute.execute_all_calls == 1

    async def test_recompute_failure_does_not_roll_back_the_commit(self):
        item = make_order_item(id=1, order_id=1, status=OrderItemStatus.PENDING)
        order_item_repo = FakeOrderItemRepository([item])
        recompute = FailingRecomputeSchedule()
        use_case = self._use_case(order_item_repo, recompute_schedule=recompute)

        await use_case.execute(actor=self.actor, order_id=1, order_item_id=1)

        assert recompute.attempts == 1
        assert self.uow.committed is True
        assert await order_item_repo.get_by_id(1) is None
