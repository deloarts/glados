"""
Unit tests for TestCancelMadeItemDemandCascade. No database, no HTTP. All
dependencies replaced with in-memory fakes.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

import pytest

from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemAllocationSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemDemandStatus
from src.modules.fulfillment.application.use_cases.made_item_demand.cancel_demand import (
    CancelImpactCollector,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.cancel_demand import (
    CancelMadeItemDemand,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.cancel_demand import (
    PreviewCancelMadeItemDemand,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.update_demand_item_status import (
    UpdateDemandItemStatus as UpdateMadeItemDemandStatus,
)
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import CancelLot
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.source_item_allocation import (
    SourceItemDemandAllocation,
)
from src.modules.fulfillment.domain.errors import DemandItemAlreadyCanceledError
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.domain.entities.project import Project
from tests.factories import make_user
from tests.unit.production_lot._helpers import make_demand
from tests.unit.production_lot._helpers import make_order
from tests.unit.production_lot._helpers import make_production_order
from tests.unit.production_lot._helpers import make_source_item_demand
from tests.unit.production_lot.fakes import FakeBoughtItemAllocationRepository
from tests.unit.production_lot.fakes import FakeEventBus
from tests.unit.production_lot.fakes import FakeMadeItemAllocationRepository
from tests.unit.production_lot.fakes import FakeMadeItemDemandRepository
from tests.unit.production_lot.fakes import FakeOrderItemRepository
from tests.unit.production_lot.fakes import FakeOrderRepository
from tests.unit.production_lot.fakes import FakeProductionLotRepository
from tests.unit.production_lot.fakes import FakeProductionOrderRepository
from tests.unit.production_lot.fakes import FakeProjectRepository
from tests.unit.production_lot.fakes import FakeRecomputeMachineSchedule
from tests.unit.production_lot.fakes import FakeSourceItemAllocationRepository
from tests.unit.production_lot.fakes import FakeSourceItemDemandRepository
from tests.unit.production_lot.fakes import FakeUnitOfWork
from tests.unit.production_order.fakes import FakeProductionOrderInterruptionRepository
from tests.unit.production_order.fakes import lifecycle_collaborators


class TestCancelMadeItemDemandCascade:
    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.lot_repo = FakeProductionLotRepository()
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        # Canceling a made demand needs the demand permissions, and canceling
        # the lots built for it manage:lots besides.
        self.actor = make_user(
            permissions=[
                Permission.WRITE_LOTS,
                Permission.MANAGE_LOTS,
                Permission.WRITE_DEMAND_ITEMS,
                Permission.MANAGE_DEMAND_ITEMS,
            ]
        )

        self.lot = await self.lot_repo.save(
            ProductionLot(
                id=0,
                created=date(2026, 1, 1),
                changed=None,
                changes=[],
                lot_number="LOT-CASCADE",
                quantity=10.0,
                status=LotStatus.IN_PROGRESS,
                priority=UrgencyClass.NORMAL,
                note=None,
                creator_id=1,
                made_item_id=1,
                project_id=1,
                input_demand_id=None,
            )
        )
        self.internal_position = await self.lot_repo.save_position(
            LotPosition(
                id=0,
                created=date(2026, 1, 1),
                changed=None,
                changes=[],
                sequence=1,
                kind=LotPositionKind.INTERNAL,
                status=LotPositionStatus.IN_PROGRESS,
                quantity=10.0,
                quantity_completed=0.0,
                note=None,
                creator_id=1,
                lot_id=self.lot.id,
            )
        )
        self.external_position = await self.lot_repo.save_position(
            LotPosition(
                id=0,
                created=date(2026, 1, 1),
                changed=None,
                changes=[],
                sequence=2,
                kind=LotPositionKind.EXTERNAL,
                status=LotPositionStatus.ORDERED_OR_QUEUED,
                quantity=10.0,
                quantity_completed=0.0,
                note=None,
                creator_id=1,
                lot_id=self.lot.id,
            )
        )

        self.production_order = make_production_order(1, self.internal_position.id)
        self.production_order_repo = FakeProductionOrderRepository([self.production_order])

        self.order_item = OrderItem(
            id=1,
            created=date(2026, 1, 1),
            changed=date(2026, 1, 1),
            changes=[],
            status=OrderItemStatus.ORDERED,
            quantity=10.0,
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
            position=3,
            creator_id=1,
            orderer_id=None,
            receiver_id=None,
            bought_item_id=None,
            order_id=1,
            supplier_id=7,
            project_id=1,
            line_type=OrderLineType.MADE,
            lot_position_id=self.external_position.id,
            source_item_id=None,
            virtual_name="Bracket coating",
        )
        self.order_item_repo = FakeOrderItemRepository([self.order_item])
        self.order_repo = FakeOrderRepository([make_order(id=1, supplier_id=7)])

        # The lot's raw material demand.
        self.source_item_demand = make_source_item_demand(
            id=50, lot_id=self.lot.id, status=SourceItemDemandStatus.ORDERED
        )
        self.source_item_demand_repo = FakeSourceItemDemandRepository([self.source_item_demand])
        self.lot.input_demand_id = self.source_item_demand.id
        await self.lot_repo.save(self.lot)
        self.source_item_allocation_repo = FakeSourceItemAllocationRepository(
            [SourceItemDemandAllocation(demand_item_id=50, order_item_id=1, quantity=10.0)]
        )

        self.demand = make_demand(
            id=9,
            quantity=10.0,
            status=MadeItemDemandStatus.ORDERED,
            item_article_name="Bracket",
            item_part_number="PN-CASCADE",
            item_revision="B",
        )
        self.demand_repo = FakeMadeItemDemandRepository([self.demand])
        self.made_item_allocation_repo = FakeMadeItemAllocationRepository(
            [MadeItemDemandAllocation(demand_item_id=9, lot_id=self.lot.id, quantity=10.0)]
        )

        self.collector = CancelImpactCollector(
            demand_repo=self.demand_repo,
            allocation_repo=self.made_item_allocation_repo,
            lot_repo=self.lot_repo,
            production_order_repo=self.production_order_repo,
            order_repo=self.order_repo,
            order_item_repo=self.order_item_repo,
            source_item_demand_repo=self.source_item_demand_repo,
            source_item_allocation_repo=self.source_item_allocation_repo,
        )
        # The cancel and the lot cancel it drives share one reconciler, as
        # they share the request's in the app.
        lifecycle = lifecycle_collaborators(
            self.production_order_repo,
            self.lot_repo,
            self.bus,
            orders=self.order_repo,
            order_items=self.order_item_repo,
            made_demands=self.demand_repo,
            made_allocations=self.made_item_allocation_repo,
            source_demands=self.source_item_demand_repo,
            source_allocations=self.source_item_allocation_repo,
        )
        self.reconciler = lifecycle["reconciler"]
        self.cancel_lot = CancelLot(
            self.lot_repo,
            self.production_order_repo,
            self.order_item_repo,
            FakeBoughtItemAllocationRepository(),
            self.made_item_allocation_repo,
            self.source_item_demand_repo,
            self.source_item_allocation_repo,
            event_bus=self.bus,
            uow=self.uow,
            parent_order_repo=self.order_repo,
            **lifecycle,
        )
        self.use_case = CancelMadeItemDemand(
            demand_repo=self.demand_repo,
            allocation_repo=self.made_item_allocation_repo,
            lot_repo=self.lot_repo,
            collector=self.collector,
            cancel_lot=self.cancel_lot,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=self.reconciler,
        )

    # ── Preview ──────────────────────────────────────────────────────

    async def test_preview_lists_every_affected_entity(self):
        impact = await PreviewCancelMadeItemDemand(self.demand_repo, self.collector).execute(
            self.actor, self.demand.id
        )

        # item_revision is denormalized alongside item_part_number.
        assert impact.item_part_number == "PN-CASCADE"
        assert impact.item_revision == "B"

        assert len(impact.lots) == 1
        lot_impact = impact.lots[0]
        assert lot_impact.lot_number == "LOT-CASCADE"
        assert lot_impact.will_cancel is True
        assert lot_impact.allocated_quantity == 10.0

        assert [o.production_order_number for o in lot_impact.production_orders] == ["PO-0001"]
        assert lot_impact.production_orders[0].will_cancel is True

        assert [(i.order_number, i.position) for i in lot_impact.order_items] == [("ORD-1", 3)]
        assert lot_impact.order_items[0].will_cancel is True
        assert lot_impact.order_items[0].supplier_name == self.order_item.supplier_name

        assert lot_impact.source_item_demand is not None
        assert lot_impact.source_item_demand.demand_id == 50
        assert lot_impact.source_item_demand.will_cancel is True
        # The raw material already on order is reported but never canceled.
        assert [i.order_number for i in lot_impact.source_item_demand.order_items] == ["ORD-1"]
        assert lot_impact.source_item_demand.order_items[0].will_cancel is False

    async def test_preview_changes_nothing(self):
        await PreviewCancelMadeItemDemand(self.demand_repo, self.collector).execute(
            self.actor, self.demand.id
        )
        assert (await self.demand_repo.get_by_id(9)).status == "ordered"
        assert (await self.lot_repo.get_by_id(self.lot.id)).status == "in_progress"
        assert self.uow.committed is False

    async def test_preview_flags_missing_manage_lots_permission(self):
        actor = make_user(permissions=[Permission.WRITE_LOTS])
        impact = await PreviewCancelMadeItemDemand(self.demand_repo, self.collector).execute(
            actor, self.demand.id
        )
        assert impact.can_cancel_lots is False

    async def test_preview_keeps_a_delivered_order_item(self):
        self.order_item.status = OrderItemStatus.DELIVERED
        self.order_item.quantity_delivered = 10.0
        impact = await PreviewCancelMadeItemDemand(self.demand_repo, self.collector).execute(
            self.actor, self.demand.id
        )
        order_item_impact = impact.lots[0].order_items[0]
        assert order_item_impact.will_cancel is False
        assert order_item_impact.keep_reason == "already delivered"

    # ── Cancel ───────────────────────────────────────────────────────

    async def test_cancel_cascades_through_lot_orders_and_source_item_demand(self):
        result = await self.use_case.execute(self.actor, self.demand.id)

        assert result.status == "canceled"
        assert (await self.lot_repo.get_by_id(self.lot.id)).status == "canceled"
        assert self.production_order_repo.orders[1].status == ProductionOrderStatus.CANCELED.value
        # The supplier was ordered, so its line stays open for purchasing,
        # and the ordered raw material is fulfilled short instead of
        # canceled behind the supplier's back.
        assert (await self.order_item_repo.get_by_id(1)).status == "ordered"
        input_demand = await self.source_item_demand_repo.get_by_id(50)
        assert input_demand is not None
        assert (input_demand.status, input_demand.canceled_at) == ("fulfilled", None)
        assert (
            await self.lot_repo.get_position_by_id(self.internal_position.id)
        ).status == "canceled"
        assert (
            await self.lot_repo.get_position_by_id(self.external_position.id)
        ).status == "canceled"
        assert await self.made_item_allocation_repo.get_by_demand_item_id(9) == []
        assert self.uow.committed is True

    async def test_cancel_reads_the_lot_with_a_row_lock(self):
        """This loop feeds the same lot cancel cascade over the live work as
        CancelLot.execute, so it needs the same lock, see
        IProductionLotRepository.get_by_id_for_update."""
        await self.use_case.execute(self.actor, self.demand.id)
        assert self.lot_repo.for_update_calls == [self.lot.id]

    async def test_cancel_publishes_lot_and_demand_events(self):
        # The lifecycle reconciler publishes the status events of the
        # force-canceled child order (this lot has one live internal order),
        # both positions, the lot, the line's order, the canceled demand and
        # the lot's raw material demand, fulfilled short, in its write order,
        # before the use case publishes its own lot event. The ordered line
        # stays open, which the lot cancel names to purchasing first.
        await self.use_case.execute(self.actor, self.demand.id)
        published = [type(e).__name__ for e in self.bus.published]
        assert published == [
            "LotSupplierLinesToSettle",
            "ProductionOrderStatusChanged",
            "ProductionOrderCanceled",
            "LotPositionStatusChanged",
            "LotPositionStatusChanged",
            "LotStatusChanged",
            "OrderStatusChanged",
            "MadeItemDemandItemStatusChanged",
            "SourceItemDemandStatusChanged",
            "LotCanceled",
        ]

    async def test_publishes_exactly_one_canceled_event_per_order(self):
        """Double-publication guard for the cancel_no_commit reuse path:
        exactly one ProductionOrderCanceled per force-canceled child order,
        never duplicated by both cancel_no_commit and the outer owner."""
        await self.use_case.execute(self.actor, self.demand.id)
        order_events = [
            e for e in self.bus.published if type(e).__name__ == "ProductionOrderCanceled"
        ]
        assert len(order_events) == 1
        assert order_events[0].production_order_id == 1

    async def test_cancel_requires_manage_lots_when_a_lot_would_be_canceled(self):
        actor = make_user(
            permissions=[
                Permission.WRITE_LOTS,
                Permission.WRITE_DEMAND_ITEMS,
                Permission.MANAGE_DEMAND_ITEMS,
            ]
        )
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor, self.demand.id)
        assert (await self.demand_repo.get_by_id(9)).status == "ordered"

    async def test_cancel_keeps_a_lot_shared_with_another_open_demand(self):
        await self.demand_repo.save(
            make_demand(id=10, quantity=4.0, status=MadeItemDemandStatus.ALLOCATED)
        )
        await self.made_item_allocation_repo.save(
            MadeItemDemandAllocation(demand_item_id=10, lot_id=self.lot.id, quantity=4.0)
        )

        result = await self.use_case.execute(self.actor, self.demand.id)

        assert result.status == "canceled"
        assert (await self.lot_repo.get_by_id(self.lot.id)).status == "in_progress"
        assert (
            self.production_order_repo.orders[1].status == ProductionOrderStatus.IN_PROGRESS.value
        )
        assert (await self.source_item_demand_repo.get_by_id(50)).status == "ordered"
        # Only this demand's own claim on the lot is released.
        assert await self.made_item_allocation_repo.get_by_demand_item_id(9) == []
        assert len(await self.made_item_allocation_repo.get_by_demand_item_id(10)) == 1

    async def test_cancel_ignores_a_lot_whose_only_other_demand_is_canceled(self):
        canceled = make_demand(id=10, quantity=4.0, status=MadeItemDemandStatus.CANCELED)
        canceled.canceled_at = datetime(2026, 1, 1, tzinfo=UTC)
        await self.demand_repo.save(canceled)
        await self.made_item_allocation_repo.save(
            MadeItemDemandAllocation(demand_item_id=10, lot_id=self.lot.id, quantity=4.0)
        )

        await self.use_case.execute(self.actor, self.demand.id)

        assert (await self.lot_repo.get_by_id(self.lot.id)).status == "canceled"

    async def test_cancel_leaves_a_fulfilled_source_item_demand_alone(self):
        self.source_item_demand.status = SourceItemDemandStatus.FULFILLED
        self.source_item_demand.fulfilled_manually_at = datetime(2026, 1, 1, tzinfo=UTC)
        await self.use_case.execute(self.actor, self.demand.id)

        assert (await self.lot_repo.get_by_id(self.lot.id)).status == "canceled"
        assert (await self.source_item_demand_repo.get_by_id(50)).status == "fulfilled"
        assert (await self.source_item_demand_repo.get_by_id(50)).canceled_at is None

    async def test_a_second_cancel_is_refused(self):
        """A second cancel is refused like in the bought family and leaves
        the demand's lot as it is."""
        self.demand.status = MadeItemDemandStatus.CANCELED
        with pytest.raises(DemandItemAlreadyCanceledError):
            await self.use_case.execute(self.actor, self.demand.id)
        assert (await self.lot_repo.get_by_id(self.lot.id)).status == "in_progress"

    async def test_cancel_without_any_lot_just_cancels_the_demand(self):
        lone_demand = make_demand(id=11, quantity=2.0, status=MadeItemDemandStatus.OPEN)
        await self.demand_repo.save(lone_demand)

        result = await self.use_case.execute(self.actor, 11)

        assert result.status == "canceled"
        assert (await self.lot_repo.get_by_id(self.lot.id)).status == "in_progress"

    async def test_cancel_releases_the_stock_allocations_of_the_demand(self):
        """A cancel frees the pieces the demand holds from stock as well as
        its lot shares, so the stock is free for other demands again."""
        stocked = make_demand(id=12, quantity=4.0, status=MadeItemDemandStatus.OPEN)
        await self.demand_repo.save(stocked)
        await self.made_item_allocation_repo.save(
            MadeItemDemandAllocation(
                demand_item_id=12, lot_id=None, quantity=3.0, source=MadeItemAllocationSource.STOCK
            )
        )

        result = await self.use_case.execute(self.actor, 12)

        assert result.status == "canceled"
        assert await self.made_item_allocation_repo.get_by_demand_item_id(12) == []
        demand = await self.demand_repo.get_by_id(12)
        assert demand is not None and demand.canceled_at is not None

    async def test_cancel_of_the_lot_frees_the_open_line_of_its_ordered_input_demand(self):
        """The lot's raw material was ordered, so its demand is fulfilled at
        what arrived, nothing here, and gives up the share of the order line
        that has not arrived, which the changelog notes; the line is free
        capacity for purchasing to settle with the supplier."""
        await self.use_case.execute(self.actor, self.demand.id)

        input_demand = await self.source_item_demand_repo.get_by_id(50)
        assert input_demand is not None
        assert input_demand.fulfilled_manually_at is not None
        assert await self.source_item_allocation_repo.get_by_demand_item_id(50) == []
        assert any(
            "Fulfilled short at 0.000 of" in entry and "order line(s) #1" in entry
            for entry in input_demand.changes
        )

    async def test_status_use_case_delegates_cancel_to_the_cascade(self):
        status_use_case = UpdateMadeItemDemandStatus(
            demand_repo=self.demand_repo,
            cancel_use_case=self.use_case,
            uow=FakeUnitOfWork(),
            reconciler=self.reconciler,
        )
        # This test exercises the delegation wiring, not permissions. There
        # is a demand-side gate on UpdateDemandItemStatus (write:demand_items,
        # escalating to manage:demand_items for a terminal target such as
        # CANCELED), so the actor needs those on top of its lot permissions to
        # reach the cascade at all. Granted locally so the class-level actor,
        # which other tests here use for lot-permission assertions, is unchanged.
        actor = make_user(
            permissions=[
                Permission.WRITE_LOTS,
                Permission.MANAGE_LOTS,
                Permission.WRITE_DEMAND_ITEMS,
                Permission.MANAGE_DEMAND_ITEMS,
            ]
        )
        result = await status_use_case.execute(actor, self.demand.id, "canceled")

        assert result.status == "canceled"
        assert (await self.lot_repo.get_by_id(self.lot.id)).status == "canceled"

    # ── Schedule recompute (Gap: this use case bypasses CancelLot.execute, ──
    # ── so it must drive the recompute itself, only when a lot was ──────────
    # ── actually canceled; releasing a still-shared lot doesn't touch any ───
    # ── machine's queue) ──────────────────────────────────────────────────

    async def test_recompute_is_called_exactly_once_when_a_lot_is_canceled(self):
        recompute = FakeRecomputeMachineSchedule()
        use_case = CancelMadeItemDemand(
            demand_repo=self.demand_repo,
            allocation_repo=self.made_item_allocation_repo,
            lot_repo=self.lot_repo,
            collector=self.collector,
            cancel_lot=self.cancel_lot,
            recompute_schedule=recompute,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=self.reconciler,
        )
        await use_case.execute(self.actor, self.demand.id)
        assert recompute.calls == 1

    async def test_recompute_is_not_called_when_no_lot_is_involved(self):
        lone_demand = make_demand(id=11, quantity=2.0, status=MadeItemDemandStatus.OPEN)
        await self.demand_repo.save(lone_demand)
        recompute = FakeRecomputeMachineSchedule()
        use_case = CancelMadeItemDemand(
            demand_repo=self.demand_repo,
            allocation_repo=self.made_item_allocation_repo,
            lot_repo=self.lot_repo,
            collector=self.collector,
            cancel_lot=self.cancel_lot,
            recompute_schedule=recompute,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=self.reconciler,
        )
        await use_case.execute(self.actor, 11)
        assert recompute.calls == 0

    async def test_recompute_is_not_called_when_a_shared_lot_is_only_released(self):
        """The lot survives (still allocated to demand #10), so nothing on
        its machines' queues changed; the recompute would be wasted work."""
        await self.demand_repo.save(
            make_demand(id=10, quantity=4.0, status=MadeItemDemandStatus.ALLOCATED)
        )
        await self.made_item_allocation_repo.save(
            MadeItemDemandAllocation(demand_item_id=10, lot_id=self.lot.id, quantity=4.0)
        )
        recompute = FakeRecomputeMachineSchedule()
        use_case = CancelMadeItemDemand(
            demand_repo=self.demand_repo,
            allocation_repo=self.made_item_allocation_repo,
            lot_repo=self.lot_repo,
            collector=self.collector,
            cancel_lot=self.cancel_lot,
            recompute_schedule=recompute,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=self.reconciler,
        )
        await use_case.execute(self.actor, self.demand.id)
        assert recompute.calls == 0

    async def test_recompute_failure_does_not_undo_the_committed_cancellation(self):
        class FailingRecomputeSchedule:
            def __init__(self) -> None:
                self.attempts: int = 0

            async def execute_all(self, response_time_days=None, settings=None):
                self.attempts += 1
                raise RuntimeError("scheduling service is down")

        recompute = FailingRecomputeSchedule()
        use_case = CancelMadeItemDemand(
            demand_repo=self.demand_repo,
            allocation_repo=self.made_item_allocation_repo,
            lot_repo=self.lot_repo,
            collector=self.collector,
            cancel_lot=self.cancel_lot,
            recompute_schedule=recompute,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=self.reconciler,
        )
        result = await use_case.execute(self.actor, self.demand.id)

        assert recompute.attempts == 1
        assert self.uow.committed is True
        assert result.status == "canceled"
        assert (await self.lot_repo.get_by_id(self.lot.id)).status == "canceled"

    async def test_the_canceled_lot_leaves_the_time_budget_of_its_project(self):
        """The lot's budgeted step stops sharing the project's time budget,
        so the queued order of another lot of the project is snapshotted
        with the larger share in the same transaction, under its lock."""
        await self.lot_repo.save_step(_budgeted_step(self.lot.id, self.internal_position.id))
        other_lot = await self.lot_repo.save(
            ProductionLot(
                id=0,
                created=date(2026, 1, 1),
                changed=None,
                changes=[],
                lot_number="LOT-OTHER",
                quantity=10.0,
                status=LotStatus.PLANNED,
                priority=UrgencyClass.NORMAL,
                note=None,
                creator_id=1,
                made_item_id=1,
                project_id=1,
                input_demand_id=None,
            )
        )
        other_position = await self.lot_repo.save_position(
            LotPosition(
                id=0,
                created=date(2026, 1, 1),
                changed=None,
                changes=[],
                sequence=1,
                kind=LotPositionKind.INTERNAL,
                status=LotPositionStatus.ORDERED_OR_QUEUED,
                quantity=10.0,
                quantity_completed=0.0,
                note=None,
                creator_id=1,
                lot_id=other_lot.id,
            )
        )
        await self.lot_repo.save_step(_budgeted_step(other_lot.id, other_position.id))
        queued = make_production_order(
            2,
            other_position.id,
            status=ProductionOrderStatus.QUEUED,
            machine_id=8,
            quantity=2.0,
        )
        queued.estimated_duration_minutes = 2 * 50
        await self.production_order_repo.save(queued)
        cancel_lot = CancelLot(
            self.lot_repo,
            self.production_order_repo,
            self.order_item_repo,
            FakeBoughtItemAllocationRepository(),
            self.made_item_allocation_repo,
            self.source_item_demand_repo,
            self.source_item_allocation_repo,
            event_bus=self.bus,
            uow=self.uow,
            parent_order_repo=self.order_repo,
            reconciler=self.reconciler,
            interruption_repo=FakeProductionOrderInterruptionRepository(
                self.production_order_repo.orders
            ),
            project_repo=FakeProjectRepository([_project_with_budget(1000)]),
        )
        use_case = CancelMadeItemDemand(
            demand_repo=self.demand_repo,
            allocation_repo=self.made_item_allocation_repo,
            lot_repo=self.lot_repo,
            collector=self.collector,
            cancel_lot=cancel_lot,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=self.reconciler,
        )

        await use_case.execute(self.actor, self.demand.id)

        # 1000 minutes over the other lot's 10 pieces instead of over 20.
        assert self.production_order_repo.orders[2].estimated_duration_minutes == 2 * 100
        assert any(2 in ids for ids in self.production_order_repo.lock_calls)
        assert self.uow.committed is True


def _budgeted_step(lot_id: int, position_id: int) -> LotStep:
    """A fabrication step without a measured estimate, which draws from the
    project's time budget; two lots of 10 pieces share 1000 minutes."""
    return LotStep(
        id=0,
        created=date(2026, 1, 1),
        note=None,
        estimated_setup_minutes=0,
        estimated_minutes_per_piece=None,
        sequence=1,
        creator_id=1,
        fabrication_method_id=1,
        lot_id=lot_id,
        position_id=position_id,
        source_process_id=None,
        time_budget_per_piece=50.0,
    )


def _project_with_budget(budget: int) -> Project:
    return Project(
        id=1,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        project_number="P-0001",
        production_time_budget=budget,
    )
