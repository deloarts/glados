"""
Unit tests for TestDeliveryPropagationToLot and
TestDeliveryPropagationRawMaterialGating. No database, no HTTP. All
dependencies replaced with in-memory fakes.
"""

from datetime import date

import pytest

from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemAllocationSource
from src.modules.fulfillment.application.use_cases.order.process_order_item_delivery import (
    ProcessOrderItemDelivery,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.errors import LotPositionOverflowError
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.production_lot._helpers import NoLotCreation
from tests.unit.production_lot._helpers import make_demand
from tests.unit.production_lot._helpers import make_order
from tests.unit.production_lot.fakes import FakeEventBus
from tests.unit.production_lot.fakes import FakeMadeItemAllocationRepository
from tests.unit.production_lot.fakes import FakeMadeItemDemandRepository
from tests.unit.production_lot.fakes import FakeOrderItemDeliveryRepository
from tests.unit.production_lot.fakes import FakeOrderItemRepository
from tests.unit.production_lot.fakes import FakeOrderRepository
from tests.unit.production_lot.fakes import FakeProductionLotRepository
from tests.unit.production_lot.fakes import FakeUnitOfWork
from tests.unit.production_lot.fakes import delivery_collaborators
from tests.unit.production_lot.fakes import lot_reconciler


class TestDeliveryPropagationToLot:
    def setup_method(self):
        self.lot_repo = FakeProductionLotRepository()
        self.order_repo = FakeOrderRepository([make_order(id=1, supplier_id=7)])
        self.demand_repo = FakeMadeItemDemandRepository([make_demand(id=1, quantity=5.0)])
        self.allocation_repo = FakeMadeItemAllocationRepository(
            [
                MadeItemDemandAllocation(
                    demand_item_id=1, lot_id=1, quantity=5.0, source=MadeItemAllocationSource.LOT
                )
            ]
        )
        self.delivery_repo = FakeOrderItemDeliveryRepository()
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(
            permissions=[
                Permission.WRITE_LOTS,
                Permission.WRITE_ORDERS,
                Permission.RECEIVE_DELIVERIES,
            ]
        )

        lot = ProductionLot(
            id=1,
            created=date(2026, 1, 1),
            changed=None,
            changes=[],
            lot_number="LOT-1",
            quantity=5.0,
            status=LotStatus.PARTIALLY_PLANNED,
            priority=UrgencyClass.NORMAL,
            note=None,
            creator_id=1,
            made_item_id=1,
            project_id=1,
            input_demand_id=None,
        )
        self.lot_repo._lots[1] = lot
        self.lot_repo._next_lot_id = 2
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
        self.lot_repo._positions[1] = position
        self.lot_repo._next_position_id = 2

        self.order_item = OrderItem(
            id=1,
            created=date(2026, 1, 1),
            changed=date(2026, 1, 1),
            changes=[],
            status=OrderItemStatus.ORDERED,
            quantity=5.0,
            quantity_delivered=0.0,
            unit="pcs",
            items_per_unit=1.0,
            price=None,
            note=None,
            ordered_date=date(2026, 1, 1),
            expected_delivery_date=None,
            delivery_date=None,
            storage_place=None,
            expected_pickup_date=None,
            ready_for_pickup_date=None,
            position=1,
            creator_id=1,
            orderer_id=None,
            receiver_id=None,
            bought_item_id=None,
            order_id=1,
            supplier_id=7,
            project_id=1,
            line_type=OrderLineType.MADE,
            lot_position_id=1,
            source_item_id=None,
            virtual_name="Bracket",
        )
        self.order_item_repo = FakeOrderItemRepository([self.order_item])

        self.use_case = ProcessOrderItemDelivery(
            order_item_repo=self.order_item_repo,
            order_repo=self.order_repo,
            delivery_repo=self.delivery_repo,
            event_bus=self.bus,
            uow=self.uow,
            made_item_demand_repo=self.demand_repo,
            made_item_allocation_repo=self.allocation_repo,
            reconciler=lot_reconciler(
                self.lot_repo,
                orders=self.order_repo,
                order_items=self.order_item_repo,
                made_demands=self.demand_repo,
                made_allocations=self.allocation_repo,
            ),
            create_lot=NoLotCreation(),
            **delivery_collaborators(lot_repo=self.lot_repo),
        )

    async def test_partial_delivery_propagates_to_position_and_demand(self):
        await self.use_case.execute(actor=self.actor, order_item_id=1, quantity=3.0)
        position = await self.lot_repo.get_position_by_id(1)
        assert position.quantity_completed == 3.0
        assert position.status == "partially_completed"
        # RELEASED -> IN_PROGRESS once any position leaves PENDING.
        assert (await self.lot_repo.get_by_id(1)).status == "in_progress"

    async def test_full_delivery_completes_lot_and_fulfills_demand(self):
        await self.use_case.execute(actor=self.actor, order_item_id=1, quantity=5.0)
        position = await self.lot_repo.get_position_by_id(1)
        assert position.quantity_completed == 5.0
        assert position.status == "completed"
        assert (await self.lot_repo.get_by_id(1)).status == "completed"
        assert (await self.demand_repo.get_by_id(1)).status == "fulfilled"

    async def test_overdelivery_beyond_lot_quantity_raises(self):
        with pytest.raises(  # noqa: B017
            Exception
        ):  # InvalidDeliveryQuantityError (order-item-level cap fires first)
            await self.use_case.execute(actor=self.actor, order_item_id=1, quantity=6.0)


class TestDeliveryPropagationRawMaterialGating:
    """A MIXED position 1 still has an in-house share drawing from our own
    raw material, unlike pure EXTERNAL (the supplier sources their own
    input, exempt by design, see TestDeliveryPropagationToLot's kind
    "external" setup), so its MADE-line delivery must respect the same
    raw-material-as-virtual-predecessor cap as the internal machine path."""

    def setup_method(self):
        self.demand_repo = FakeMadeItemDemandRepository()
        self.allocation_repo = FakeMadeItemAllocationRepository()
        self.delivery_repo = FakeOrderItemDeliveryRepository()
        self.order_repo = FakeOrderRepository([make_order(id=1, supplier_id=7)])
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(
            permissions=[
                Permission.WRITE_LOTS,
                Permission.WRITE_ORDERS,
                Permission.RECEIVE_DELIVERIES,
            ]
        )

        lot = ProductionLot(
            id=1,
            created=date(2026, 1, 1),
            changed=None,
            changes=[],
            lot_number="LOT-1",
            quantity=5.0,
            status=LotStatus.PARTIALLY_PLANNED,
            priority=UrgencyClass.NORMAL,
            note=None,
            creator_id=1,
            made_item_id=1,
            project_id=1,
            input_demand_id=42,
        )
        position = LotPosition(
            id=1,
            created=date(2026, 1, 1),
            changed=None,
            changes=[],
            sequence=1,
            kind=LotPositionKind.MIXED,
            status=LotPositionStatus.PENDING,
            quantity=5.0,
            quantity_completed=0.0,
            note=None,
            creator_id=1,
            lot_id=1,
        )
        order_item = OrderItem(
            id=1,
            created=date(2026, 1, 1),
            changed=date(2026, 1, 1),
            changes=[],
            status=OrderItemStatus.ORDERED,
            quantity=5.0,
            quantity_delivered=0.0,
            unit="pcs",
            items_per_unit=1.0,
            price=None,
            note=None,
            ordered_date=date(2026, 1, 1),
            expected_delivery_date=None,
            delivery_date=None,
            storage_place=None,
            expected_pickup_date=None,
            ready_for_pickup_date=None,
            position=1,
            creator_id=1,
            orderer_id=None,
            receiver_id=None,
            bought_item_id=None,
            order_id=1,
            supplier_id=7,
            project_id=1,
            line_type=OrderLineType.MADE,
            lot_position_id=1,
            source_item_id=None,
            virtual_name="Bracket",
        )
        self.order_item_repo = FakeOrderItemRepository([order_item])

        self.lot_repo = FakeProductionLotRepository(raw_material_arrived_by_demand={42: 3.0})
        self.lot_repo._lots[1] = lot
        self.lot_repo._next_lot_id = 2
        self.lot_repo._positions[1] = position
        self.lot_repo._next_position_id = 2

        self.use_case = ProcessOrderItemDelivery(
            order_item_repo=self.order_item_repo,
            order_repo=self.order_repo,
            delivery_repo=self.delivery_repo,
            event_bus=self.bus,
            uow=self.uow,
            made_item_demand_repo=self.demand_repo,
            made_item_allocation_repo=self.allocation_repo,
            reconciler=lot_reconciler(
                self.lot_repo,
                orders=self.order_repo,
                order_items=self.order_item_repo,
                made_demands=self.demand_repo,
                made_allocations=self.allocation_repo,
            ),
            create_lot=NoLotCreation(),
            **delivery_collaborators(lot_repo=self.lot_repo),
        )

    async def test_delivery_within_arrived_raw_material_succeeds(self):
        await self.use_case.execute(actor=self.actor, order_item_id=1, quantity=3.0)
        assert (await self.lot_repo.get_position_by_id(1)).quantity_completed == 3.0

    async def test_delivery_beyond_arrived_raw_material_blocked(self):
        with pytest.raises(LotPositionOverflowError):
            await self.use_case.execute(actor=self.actor, order_item_id=1, quantity=4.0)
