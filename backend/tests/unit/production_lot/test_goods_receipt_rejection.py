"""
Unit tests for rejecting pieces while booking a supplier delivery
(ProcessOrderItemDelivery.execute's quantity_rejected/rejection_reason/
rejection_outcome/create_replacement parameters): both outcomes on a MADE
line (the lot-closing disposition against the line's external position)
and on a bought line (demand coverage via the delivered_ratio fix), the
OrderRules validation, and expected_delivery_date clearing on redeliver.
No database, no HTTP. All dependencies replaced with in-memory fakes,
mirroring test_delivery_propagation.py's and test_scrap_production_pieces.
py's own style.
"""

from datetime import date

import pytest

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemAllocationSource
from src.modules.fulfillment.application.use_cases.order.process_order_item_delivery import (
    ProcessOrderItemDelivery,
)
from src.modules.fulfillment.application.use_cases.production_lot.create_lot import CreateLot
from src.modules.fulfillment.domain.entities.bought_item_allocation import (
    BoughtItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.errors import DeliveryRejectionInvalidError
from src.modules.fulfillment.domain.errors import InvalidDeliveryQuantityError
from src.modules.fulfillment.domain.events.order_events import DeliveryPiecesRejected
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler
from tests.unit.production_lot._helpers import NoLotCreation
from tests.unit.production_lot._helpers import make_demand
from tests.unit.production_lot._helpers import make_made_item
from tests.unit.production_lot._helpers import make_order
from tests.unit.production_lot._helpers import make_process
from tests.unit.production_lot.fakes import FakeAdminSettingsRepository
from tests.unit.production_lot.fakes import FakeBoughtItemAllocationRepository
from tests.unit.production_lot.fakes import FakeBoughtItemDemandRepository
from tests.unit.production_lot.fakes import FakeEventBus
from tests.unit.production_lot.fakes import FakeInspectionMethodRepository
from tests.unit.production_lot.fakes import FakeMadeItemAllocationRepository
from tests.unit.production_lot.fakes import FakeMadeItemDemandRepository
from tests.unit.production_lot.fakes import FakeMadeItemRepository
from tests.unit.production_lot.fakes import FakeOrderItemDeliveryRepository
from tests.unit.production_lot.fakes import FakeOrderItemRepository
from tests.unit.production_lot.fakes import FakeOrderRepository
from tests.unit.production_lot.fakes import FakeProductionLotRepository
from tests.unit.production_lot.fakes import FakeProductionMachineRepository
from tests.unit.production_lot.fakes import FakeProductionOrderRepository
from tests.unit.production_lot.fakes import FakeSourceItemAllocationRepository
from tests.unit.production_lot.fakes import FakeSourceItemDemandRepository
from tests.unit.production_lot.fakes import FakeUnitOfWork
from tests.unit.production_lot.fakes import delivery_collaborators
from tests.unit.production_lot.fakes import lot_reconciler
from tests.unit.production_order.fakes import FakeProductionOrderInterruptionRepository


def _made_order_item(
    *, quantity: float = 2.0, lot_position_id: int = 1, expected_delivery_date: date | None = None
) -> OrderItem:
    return OrderItem(
        id=1,
        created=date(2026, 1, 1),
        changed=None,
        changes=[],
        status=OrderItemStatus.ORDERED,
        quantity=quantity,
        quantity_delivered=0.0,
        unit="pcs",
        items_per_unit=1.0,
        price=None,
        note=None,
        ordered_date=date(2026, 1, 1),
        expected_delivery_date=expected_delivery_date,
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
        lot_position_id=lot_position_id,
        source_item_id=None,
        virtual_name=None,
    )


class TestMadeLineGoodsReceiptRejection:
    def setup_method(self):
        self.lot_repo = FakeProductionLotRepository()
        self.made_item_repo = FakeMadeItemRepository(
            [make_made_item(processes=[make_process(id=1, position=0, fabrication_method_id=1)])]
        )
        self.demand_repo = FakeMadeItemDemandRepository([make_demand(id=1, quantity=2.0)])
        self.allocation_repo = FakeMadeItemAllocationRepository(
            [
                MadeItemDemandAllocation(
                    demand_item_id=1, lot_id=1, quantity=2.0, source=MadeItemAllocationSource.LOT
                )
            ]
        )
        self.settings_repo = FakeAdminSettingsRepository(require_qa=False)
        self.source_item_demand_repo = FakeSourceItemDemandRepository()
        self.production_order_repo = FakeProductionOrderRepository()
        self.inspection_method_repo = FakeInspectionMethodRepository()
        self.machine_repo = FakeProductionMachineRepository()
        self.uow = FakeUnitOfWork()
        self.bus = FakeEventBus()
        self.order_item_repo = FakeOrderItemRepository([_made_order_item()])
        self.order_repo = FakeOrderRepository([make_order(id=1, supplier_id=7)])
        # One reconciler per request, shared by the delivery and the CreateLot
        # its disposition spawns a replacement lot through.
        self.reconciler = lot_reconciler(
            self.lot_repo,
            self.production_order_repo,
            orders=self.order_repo,
            order_items=self.order_item_repo,
        )
        self.create_lot = CreateLot(
            lot_repo=self.lot_repo,
            made_item_repo=self.made_item_repo,
            demand_repo=self.demand_repo,
            allocation_repo=self.allocation_repo,
            settings_repo=self.settings_repo,
            source_item_demand_repo=self.source_item_demand_repo,
            order_repo=self.production_order_repo,
            inspection_method_repo=self.inspection_method_repo,
            machine_repo=self.machine_repo,
            uow=self.uow,
            event_bus=FakeEventBus(),
            reconciler=self.reconciler,
        )

        lot = ProductionLot(
            id=1,
            created=date(2026, 1, 1),
            changed=None,
            changes=[],
            lot_number="LOT-1",
            quantity=2.0,
            status=LotStatus.PLANNED,
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
            status=LotPositionStatus.ORDERED_OR_QUEUED,
            quantity=2.0,
            quantity_completed=0.0,
            note=None,
            creator_id=1,
            lot_id=1,
        )
        self.lot_repo._positions[1] = position
        self.lot_repo._next_position_id = 2

        self.delivery_repo = FakeOrderItemDeliveryRepository()
        self.actor = make_user(id=1, permissions=[Permission.RECEIVE_DELIVERIES])

    def _use_case(self) -> ProcessOrderItemDelivery:
        return ProcessOrderItemDelivery(
            order_item_repo=self.order_item_repo,
            order_repo=self.order_repo,
            delivery_repo=self.delivery_repo,
            event_bus=self.bus,
            uow=self.uow,
            lot_repo=self.lot_repo,
            made_item_demand_repo=self.demand_repo,
            made_item_allocation_repo=self.allocation_repo,
            production_order_repo=self.production_order_repo,
            create_lot=self.create_lot,
            reconciler=self.reconciler,
            interruption_repo=FakeProductionOrderInterruptionRepository(
                self.production_order_repo._orders
            ),
            source_item_demand_repo=self.source_item_demand_repo,
            source_item_allocation_repo=FakeSourceItemAllocationRepository(),
            bought_item_allocation_repo=FakeBoughtItemAllocationRepository(),
        )

    async def test_lost_outcome_closes_lot_short_and_creates_replacement(self):
        await self._use_case().execute(
            actor=self.actor,
            order_item_id=1,
            quantity=1.0,
            quantity_rejected=1.0,
            rejection_reason="supplier_damage",
            rejection_note="dented on arrival",
            rejection_outcome="lost",
            create_replacement=True,
        )

        origin = await self.lot_repo.get_by_id(1)
        assert origin.quantity == 1.0
        assert origin.quantity_scrapped == 1.0
        assert origin.status == "completed"

        events = await self.lot_repo.get_events(1)
        assert any(e.event_type == LotEventType.PIECES_LOST_AT_RECEIPT for e in events)
        replacement_events = [
            e for e in events if e.event_type == LotEventType.REPLACEMENT_LOT_CREATED
        ]
        assert len(replacement_events) == 1
        replacement_id = replacement_events[0].payload["lot_id"]
        replacement = await self.lot_repo.get_by_id(replacement_id)
        assert replacement.quantity == 1.0
        assert replacement.origin_lot_id == 1
        assert replacement.origin_disposition == "replacement"

        # Demand coverage moved onto the replacement lot.
        assert (await self.allocation_repo.get_by_lot_id(1))[0].quantity == 1.0
        assert (await self.allocation_repo.get_by_lot_id(replacement.id))[0].quantity == 1.0

        published_types = [type(e).__name__ for e in self.bus.published]
        assert "DeliveryPiecesRejected" in published_types
        rejected_event = next(
            e for e in self.bus.published if isinstance(e, DeliveryPiecesRejected)
        )
        assert rejected_event.quantity == 1.0
        assert rejected_event.reason == "supplier_damage"
        assert rejected_event.outcome == "lost"
        assert rejected_event.supplier_id == 7

    async def test_lost_outcome_full_quantity_sets_lot_scrapped(self):
        await self._use_case().execute(
            actor=self.actor,
            order_item_id=1,
            quantity=0.0,
            quantity_rejected=2.0,
            rejection_reason="transport_damage",
            rejection_outcome="lost",
            create_replacement=True,
        )

        origin = await self.lot_repo.get_by_id(1)
        assert origin.quantity == 0.0
        assert origin.quantity_scrapped == 2.0
        assert origin.status == "scrapped"

    async def test_lost_outcome_opt_out_skips_replacement_lot(self):
        await self._use_case().execute(
            actor=self.actor,
            order_item_id=1,
            quantity=1.0,
            quantity_rejected=1.0,
            rejection_reason="supplier_damage",
            rejection_outcome="lost",
            create_replacement=False,
        )

        origin = await self.lot_repo.get_by_id(1)
        assert origin.quantity == 1.0
        assert origin.quantity_scrapped == 1.0

        events = await self.lot_repo.get_events(1)
        assert any(e.event_type == LotEventType.REPLACEMENT_SKIPPED for e in events)
        assert not any(e.event_type == LotEventType.REPLACEMENT_LOT_CREATED for e in events)

        # No follow-up lot: the origin's own allocation is shrunk, no
        # compensating allocation exists to receive the difference.
        assert (await self.allocation_repo.get_by_lot_id(1))[0].quantity == 1.0

    async def test_redeliver_outcome_leaves_lot_untouched_and_clears_expected_date(self):
        self.order_item_repo = FakeOrderItemRepository(
            [_made_order_item(expected_delivery_date=date(2026, 10, 1))]
        )

        result = await self._use_case().execute(
            actor=self.actor,
            order_item_id=1,
            quantity=1.0,
            quantity_rejected=1.0,
            rejection_reason="wrong_spec",
            rejection_outcome="redeliver",
        )

        assert result.expected_delivery_date is None
        assert result.quantity_delivered == 1.0
        assert result.quantity_rejected == 1.0
        assert result.quantity_rejected_lost == 0.0

        origin = await self.lot_repo.get_by_id(1)
        # Only the accepted piece propagated; nothing was closed short.
        assert origin.quantity == 2.0
        assert origin.quantity_scrapped == 0.0
        events = await self.lot_repo.get_events(1)
        assert not any(e.event_type == LotEventType.PIECES_LOST_AT_RECEIPT for e in events)


class TestBoughtLineGoodsReceiptRejection:
    """A bought line has no lot: "lost" pieces simply count as covered for
    demand-fulfillment purposes (allocation_coverage.OrderItemCoverageSource),
    no disposition, no replacement lot option."""

    def setup_method(self):
        self.order_item = OrderItem(
            id=1,
            created=date(2026, 1, 1),
            changed=None,
            changes=[],
            status=OrderItemStatus.ORDERED,
            quantity=2.0,
            quantity_delivered=0.0,
            unit="pcs",
            items_per_unit=1.0,
            price=None,
            note=None,
            ordered_date=date(2026, 1, 1),
            expected_delivery_date=date(2026, 10, 1),
            delivery_date=None,
            storage_place=None,
            expected_pickup_date=None,
            ready_for_pickup_date=None,
            position=1,
            creator_id=1,
            orderer_id=None,
            receiver_id=None,
            bought_item_id=1,
            order_id=1,
            supplier_id=7,
            project_id=1,
            line_type=OrderLineType.BOUGHT,
            lot_position_id=None,
            source_item_id=None,
            virtual_name=None,
        )
        self.order_item_repo = FakeOrderItemRepository([self.order_item])
        self.order_repo = FakeOrderRepository([make_order(id=1, supplier_id=7)])
        self.delivery_repo = FakeOrderItemDeliveryRepository()
        self.demand = BoughtItemDemandItem(
            id=1,
            created=date(2026, 1, 1),
            changed=None,
            changes=[],
            status=BoughtItemDemandStatus.ALLOCATED,
            quantity=2.0,
            unit="pcs",
            items_per_unit=1.0,
            high_priority=False,
            notify_on_delivery=False,
            note=None,
            desired_delivery_date=None,
            creator_id=1,
            item_id=1,
            project_id=1,
        )
        self.demand_repo = FakeBoughtItemDemandRepository([self.demand])
        self.allocation_repo = FakeBoughtItemAllocationRepository(
            [BoughtItemDemandAllocation(demand_item_id=1, order_item_id=1, quantity=2.0)]
        )
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(id=1, permissions=[Permission.RECEIVE_DELIVERIES])

    def _use_case(self) -> ProcessOrderItemDelivery:
        return ProcessOrderItemDelivery(
            order_item_repo=self.order_item_repo,
            order_repo=self.order_repo,
            delivery_repo=self.delivery_repo,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=demand_reconciler(
                orders=self.order_repo,
                order_items=self.order_item_repo,
                bought_demands=self.demand_repo,
                bought_allocations=self.allocation_repo,
            ),
            made_item_demand_repo=FakeMadeItemDemandRepository(),
            made_item_allocation_repo=FakeMadeItemAllocationRepository(),
            create_lot=NoLotCreation(),
            **delivery_collaborators(bought_item_allocation_repo=self.allocation_repo),
        )

    async def test_lost_pieces_reopen_the_demands_rest(self):
        # The line is settled, 1 accepted and 1 lost, but the lost piece
        # never arrived: the allocation is fitted to the 1 that can, and
        # the demand of 2 is allocated with its other piece open again.
        await self._use_case().execute(
            actor=self.actor,
            order_item_id=1,
            quantity=1.0,
            quantity_rejected=1.0,
            rejection_reason="transport_damage",
            rejection_outcome="lost",
        )

        item = await self.order_item_repo.get_by_id(1)
        assert item.quantity_delivered == 1.0
        assert item.quantity_rejected_lost == 1.0
        assert item.status == "delivered"
        assert await self.allocation_repo.get_allocated_quantity(1) == 1.0
        assert (await self.demand_repo.get_by_id(1)).status == "allocated"

    async def test_redeliver_outcome_leaves_demand_open_and_clears_expected_date(self):
        await self._use_case().execute(
            actor=self.actor,
            order_item_id=1,
            quantity=1.0,
            quantity_rejected=1.0,
            rejection_reason="transport_damage",
            rejection_outcome="redeliver",
        )

        item = await self.order_item_repo.get_by_id(1)
        assert item.quantity_delivered == 1.0
        assert item.quantity_rejected_lost == 0.0
        assert item.status == "partially_delivered"
        assert item.expected_delivery_date is None
        assert (await self.demand_repo.get_by_id(1)).status != "fulfilled"

    async def test_missing_reason_or_outcome_raises(self):
        with pytest.raises(DeliveryRejectionInvalidError):
            await self._use_case().execute(
                actor=self.actor,
                order_item_id=1,
                quantity=1.0,
                quantity_rejected=1.0,
            )

    async def test_over_capacity_rejection_raises(self):
        with pytest.raises(InvalidDeliveryQuantityError):
            await self._use_case().execute(
                actor=self.actor,
                order_item_id=1,
                quantity=1.0,
                quantity_rejected=5.0,
                rejection_reason="transport_damage",
                rejection_outcome="lost",
            )

    async def test_redelivered_pieces_can_be_redelivered_in_a_later_call(self):
        """A "redeliver" outcome doesn't permanently consume capacity:
        the supplier's resend still fits within the line's remaining
        quantity on a later call."""
        use_case = self._use_case()
        await use_case.execute(
            actor=self.actor,
            order_item_id=1,
            quantity=1.0,
            quantity_rejected=1.0,
            rejection_reason="transport_damage",
            rejection_outcome="redeliver",
        )
        await use_case.execute(actor=self.actor, order_item_id=1, quantity=1.0)

        item = await self.order_item_repo.get_by_id(1)
        assert item.quantity_delivered == 2.0
        assert item.status == "delivered"
