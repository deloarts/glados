"""
Unit tests for TestHoldAndResumeLot and TestForceCancelAndCompleteLot.
No database, no HTTP. All dependencies replaced with in-memory fakes.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

import pytest

from src.modules.catalogue.domain.value_objects.bought_item_status import AllocationSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemAllocationSource
from src.modules.fulfillment.application.dto.production_lot_dto import CancelLotCommand
from src.modules.fulfillment.application.dto.production_lot_dto import CompleteLotCommand
from src.modules.fulfillment.application.dto.production_lot_dto import HoldLotCommand
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import CancelLot
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import CompleteLot
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import HoldLot
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import ResumeLot
from src.modules.fulfillment.domain.entities.bought_item_allocation import (
    BoughtItemDemandAllocation,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)
from src.modules.fulfillment.domain.errors import LotInvalidStatusTransitionError
from src.modules.fulfillment.domain.events.lot_events import LotCompleted
from src.modules.fulfillment.domain.events.lot_events import LotOnHold
from src.modules.fulfillment.domain.events.lot_events import LotResumed
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderCanceled
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderCompleted
from src.modules.fulfillment.domain.value_objects.interruption_reason import InterruptionReason
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.production_lot._helpers import make_demand
from tests.unit.production_lot._helpers import make_order
from tests.unit.production_lot._helpers import make_production_order
from tests.unit.production_lot.fakes import FakeBoughtItemAllocationRepository
from tests.unit.production_lot.fakes import FakeBoughtItemDemandRepository
from tests.unit.production_lot.fakes import FakeEventBus
from tests.unit.production_lot.fakes import FakeMadeItemAllocationRepository
from tests.unit.production_lot.fakes import FakeMadeItemDemandRepository
from tests.unit.production_lot.fakes import FakeOrderItemRepository
from tests.unit.production_lot.fakes import FakeOrderRepository
from tests.unit.production_lot.fakes import FakeProductionLotRepository
from tests.unit.production_lot.fakes import FakeProductionOrderRepository
from tests.unit.production_lot.fakes import FakeSourceItemAllocationRepository
from tests.unit.production_lot.fakes import FakeSourceItemDemandRepository
from tests.unit.production_lot.fakes import FakeUnitOfWork
from tests.unit.production_order.fakes import lifecycle_collaborators


class TestHoldAndResumeLot:
    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.lot_repo = FakeProductionLotRepository()
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.WRITE_LOTS])

        lot = await self.lot_repo.save(
            ProductionLot(
                id=0,
                created=date(2026, 1, 1),
                changed=None,
                changes=[],
                lot_number="LOT-HOLD",
                quantity=5.0,
                status=LotStatus.IN_PROGRESS,
                priority=UrgencyClass.NORMAL,
                note=None,
                creator_id=1,
                made_item_id=1,
                project_id=1,
                input_demand_id=None,
            )
        )
        self.lot = lot
        self.position = await self.lot_repo.save_position(
            LotPosition(
                id=0,
                created=date(2026, 1, 1),
                changed=None,
                changes=[],
                sequence=1,
                kind=LotPositionKind.INTERNAL,
                status=LotPositionStatus.IN_PROGRESS,
                quantity=5.0,
                quantity_completed=0.0,
                note=None,
                creator_id=1,
                lot_id=lot.id,
            )
        )

    async def test_hold_pauses_in_progress_orders_and_sets_lot_on_hold(self):
        order_repo = FakeProductionOrderRepository(
            [make_production_order(1, self.position.id, status=ProductionOrderStatus.IN_PROGRESS)]
        )
        use_case = HoldLot(
            self.lot_repo,
            order_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(order_repo, self.lot_repo, self.bus),
        )
        result = await use_case.execute(
            self.actor, self.lot.id, HoldLotCommand(reason="urgent job")
        )
        assert result.status == "on_hold"
        assert order_repo.orders[1].status == ProductionOrderStatus.PAUSED.value
        assert self.uow.committed is True

    def test_hold_requires_reason(self):
        with pytest.raises(Exception):  # noqa: B017, pydantic ValidationError, min_length=1
            HoldLotCommand(reason="")

    async def test_hold_rejects_invalid_source_status(self):
        # The other Hold/Resume tests start from "in_progress" (the happy
        # path); the lot intent table does not hold a DRAFT lot, so this
        # test exercises the guard itself.
        self.lot.status = LotStatus.DRAFT
        await self.lot_repo.save(self.lot)
        order_repo = FakeProductionOrderRepository()
        use_case = HoldLot(
            self.lot_repo,
            order_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(order_repo, self.lot_repo, self.bus),
        )
        with pytest.raises(LotInvalidStatusTransitionError):
            await use_case.execute(self.actor, self.lot.id, HoldLotCommand(reason="urgent job"))

    async def test_resume_rejects_a_lot_that_is_not_on_hold(self):
        # self.lot is "in_progress" (setup_method); the recomputed resume
        # target for an unchanged in-progress position is "in_progress"
        # itself, and IN_PROGRESS -> IN_PROGRESS is not a legal transition.
        order_repo = FakeProductionOrderRepository()
        use_case = ResumeLot(
            self.lot_repo,
            order_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(order_repo, self.lot_repo, self.bus),
        )
        with pytest.raises(LotInvalidStatusTransitionError):
            await use_case.execute(self.actor, self.lot.id)

    async def test_resume_recomputes_target_status_and_resumes_paused_orders(self):
        order_repo = FakeProductionOrderRepository(
            [
                make_production_order(
                    1,
                    self.position.id,
                    status=ProductionOrderStatus.PAUSED,
                    interruption_reason=InterruptionReason.LOT_HOLD,
                )
            ]
        )
        self.lot.status = LotStatus.ON_HOLD
        await self.lot_repo.save(self.lot)
        use_case = ResumeLot(
            self.lot_repo,
            order_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(order_repo, self.lot_repo, self.bus),
        )
        result = await use_case.execute(self.actor, self.lot.id)
        assert result.status == "in_progress"  # position status != PENDING -> IN_PROGRESS
        assert order_repo.orders[1].status == ProductionOrderStatus.IN_PROGRESS.value

    async def test_resume_targets_draft_when_all_positions_pending(self):
        self.position.status = LotPositionStatus.PENDING
        await self.lot_repo.save_position(self.position)
        self.lot.status = LotStatus.ON_HOLD
        await self.lot_repo.save(self.lot)
        order_repo = FakeProductionOrderRepository()
        use_case = ResumeLot(
            self.lot_repo,
            order_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(order_repo, self.lot_repo, self.bus),
        )
        result = await use_case.execute(self.actor, self.lot.id)
        assert result.status == "draft"

    # ── Publish-after-commit ordering ─────────────────────────────────
    #
    # The hold/resume events are published immediately after the commit,
    # with the schedule recompute behind a try/except, so a recompute
    # failure neither 500s an already-committed hold nor loses its event.

    @pytest.mark.parametrize("action", ["hold", "resume"])
    async def test_hold_and_resume_publish_even_when_the_recompute_fails(self, action):
        class FailingRecomputeSchedule:
            def __init__(self) -> None:
                self.attempts: int = 0

            async def execute_all(self, response_time_days=None, settings=None):
                self.attempts += 1
                raise RuntimeError("scheduling service is down")

        recompute = FailingRecomputeSchedule()
        if action == "hold":
            order_repo = FakeProductionOrderRepository(
                [
                    make_production_order(
                        1, self.position.id, status=ProductionOrderStatus.IN_PROGRESS
                    )
                ]
            )
            use_case = HoldLot(
                self.lot_repo,
                order_repo,
                recompute,
                event_bus=self.bus,
                uow=self.uow,
                **lifecycle_collaborators(order_repo, self.lot_repo, self.bus),
            )
            await use_case.execute(self.actor, self.lot.id, HoldLotCommand(reason="urgent job"))
            expected = LotOnHold
        else:
            order_repo = FakeProductionOrderRepository(
                [
                    make_production_order(
                        1,
                        self.position.id,
                        status=ProductionOrderStatus.PAUSED,
                        interruption_reason=InterruptionReason.LOT_HOLD,
                    )
                ]
            )
            self.lot.status = LotStatus.ON_HOLD
            await self.lot_repo.save(self.lot)
            use_case = ResumeLot(
                self.lot_repo,
                order_repo,
                recompute,
                event_bus=self.bus,
                uow=self.uow,
                **lifecycle_collaborators(order_repo, self.lot_repo, self.bus),
            )
            await use_case.execute(self.actor, self.lot.id)
            expected = LotResumed

        assert recompute.attempts  # the failing work really ran
        assert self.uow.committed is True
        assert any(isinstance(e, expected) for e in self.bus.published)


class TestForceCancelAndCompleteLot:
    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.lot_repo = FakeProductionLotRepository()
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.source_item_demand_repo = FakeSourceItemDemandRepository()
        self.source_item_allocation_repo = FakeSourceItemAllocationRepository()
        self.actor = make_user(permissions=[Permission.WRITE_LOTS, Permission.MANAGE_LOTS])

        self.lot = await self.lot_repo.save(
            ProductionLot(
                id=0,
                created=date(2026, 1, 1),
                changed=None,
                changes=[],
                lot_number="LOT-FORCE",
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
                quantity=6.0,
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
                quantity=4.0,
                quantity_completed=0.0,
                note=None,
                creator_id=1,
                lot_id=self.lot.id,
            )
        )
        self.order_item = OrderItem(
            id=1,
            created=date(2026, 1, 1),
            changed=date(2026, 1, 1),
            changes=[],
            status=OrderItemStatus.ORDERED,
            quantity=4.0,
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
            lot_position_id=self.external_position.id,
            source_item_id=None,
            virtual_name="Bracket",
        )
        self.external_position.order_item_id = self.order_item.id
        self.external_position.order_item_quantity = 4.0
        self.external_position.order_item_quantity_delivered = 0.0
        await self.lot_repo.save_position(self.external_position)

        self.internal_order = make_production_order(
            1, self.internal_position.id, status=ProductionOrderStatus.IN_PROGRESS
        )
        self.internal_order.quantity = 6.0
        self.internal_position.production_orders = [self.internal_order]
        await self.lot_repo.save_position(self.internal_position)

        self.order_item_repo = FakeOrderItemRepository([self.order_item])
        self.production_order_repo = FakeProductionOrderRepository([self.internal_order])
        self.allocation = BoughtItemDemandAllocation(
            demand_item_id=1, order_item_id=1, quantity=4.0, source=AllocationSource.ORDER
        )
        self.allocation_repo = FakeBoughtItemAllocationRepository([self.allocation])
        self.demand_repo = FakeBoughtItemDemandRepository([make_demand(id=1, quantity=4.0)])
        self.parent_order_repo = FakeOrderRepository([make_order(id=1, supplier_id=7)])
        self.made_item_demand_repo = FakeMadeItemDemandRepository()
        self.made_item_allocation_repo = FakeMadeItemAllocationRepository()

    async def _give_progress(self) -> None:
        """Three of the six pieces made in house and two of the four bought
        ones delivered, so the lot has produced two pieces, its last
        position's count."""
        self.internal_order.quantity_completed = 3.0
        await self.production_order_repo.save_completion(
            ProductionOrderCompletion(
                id=0,
                production_order_id=self.internal_order.id,
                quantity=3.0,
                quantity_accepted=3.0,
                quantity_rejected=0.0,
                completion_date=date(2026, 1, 2),
                note=None,
                operator_id=1,
                recorded_by_id=1,
                created=datetime(2026, 1, 2, tzinfo=UTC),
            )
        )
        self.internal_position.quantity_completed = 3.0
        self.internal_position.status = LotPositionStatus.PARTIALLY_COMPLETED
        await self.lot_repo.save_position(self.internal_position)
        self.order_item.quantity_delivered = 2.0
        self.order_item.status = OrderItemStatus.PARTIALLY_DELIVERED
        self.external_position.quantity_completed = 2.0
        self.external_position.status = LotPositionStatus.PARTIALLY_COMPLETED
        await self.lot_repo.save_position(self.external_position)

    async def test_complete_closes_the_lot_short_at_what_it_produced(self):
        await self._give_progress()

        result = await self._complete_use_case().execute(
            self.actor, self.lot.id, CompleteLotCommand()
        )

        assert result.status == "completed"
        assert result.quantity == 2.0
        lot = await self.lot_repo.get_by_id(self.lot.id)
        assert lot.force_completed_at is not None
        assert lot.completed_at is not None

        internal = await self.lot_repo.get_position_by_id(self.internal_position.id)
        assert (internal.quantity, internal.quantity_completed, internal.status) == (
            3.0,
            3.0,
            "completed",
        )
        order = self.production_order_repo._orders[1]
        assert (order.quantity, order.quantity_completed, order.status) == (
            3.0,
            3.0,
            ProductionOrderStatus.COMPLETED.value,
        )

        external = await self.lot_repo.get_position_by_id(self.external_position.id)
        assert (external.quantity, external.quantity_completed, external.status) == (
            2.0,
            2.0,
            "completed",
        )
        line = await self.order_item_repo.get_by_id(1)
        assert (line.quantity, line.quantity_delivered, line.status) == (2.0, 2.0, "delivered")

        assert self.uow.committed is True

    async def test_complete_cancels_live_work_that_did_nothing(self):
        await self._give_progress()
        queued = make_production_order(
            2, self.internal_position.id, status=ProductionOrderStatus.QUEUED, quantity=3.0
        )
        await self.production_order_repo.save(queued)

        await self._complete_use_case().execute(self.actor, self.lot.id, CompleteLotCommand())

        assert self.production_order_repo.orders[2].status == ProductionOrderStatus.CANCELED.value
        assert self.production_order_repo.orders[2].canceled_at is not None

    async def test_complete_books_no_piece_nobody_made_or_received(self):
        await self._give_progress()

        await self._complete_use_case().execute(self.actor, self.lot.id, CompleteLotCommand())

        completions = await self.production_order_repo.get_completions(self.internal_order.id)
        assert [c.quantity for c in completions] == [3.0]
        assert (await self.order_item_repo.get_by_id(1)).quantity_delivered == 2.0

    async def test_complete_records_its_own_row_and_lot_completed_once(self):
        await self._give_progress()

        await self._complete_use_case().execute(
            self.actor, self.lot.id, CompleteLotCommand(reason="customer took what is done")
        )

        completed = [
            e
            for e in await self.lot_repo.get_events(self.lot.id)
            if e.event_type == LotEventType.LOT_COMPLETED
        ]
        assert [e.summary for e in completed] == [
            "Lot force-completed at 2.000 of 10.000 piece(s). Reason: customer took what is done"
        ]
        assert [e.lot_id for e in self.bus.published if isinstance(e, LotCompleted)] == [
            self.lot.id
        ]

    async def test_complete_refuses_a_lot_that_produced_nothing(self):
        with pytest.raises(LotInvalidStatusTransitionError):
            await self._complete_use_case().execute(self.actor, self.lot.id, CompleteLotCommand())

    async def test_complete_reads_the_lot_with_a_row_lock(self):
        """The cascade writes every position under this lot, so it
        must not interleave with a concurrent quantity-mutating use case on
        the same lot, see IProductionLotRepository.get_by_id_for_update."""
        await self._give_progress()
        await self._complete_use_case().execute(self.actor, self.lot.id, CompleteLotCommand())
        assert self.lot_repo.for_update_calls == [self.lot.id]

    async def test_complete_requires_manage_lots_permission(self):
        actor = make_user(permissions=[Permission.WRITE_LOTS])
        with pytest.raises(InsufficientPermissionsError):
            await self._complete_use_case().execute(actor, self.lot.id, CompleteLotCommand())

    @pytest.mark.parametrize("terminal_status", [LotStatus.COMPLETED, LotStatus.CANCELED])
    async def test_complete_rejects_an_already_terminal_lot(self, terminal_status):
        # The lot intent table refuses a force-complete of a lot already
        # COMPLETED or CANCELED, as it refuses CancelLot's.
        self.lot.status = terminal_status
        await self.lot_repo.save(self.lot)
        with pytest.raises(LotInvalidStatusTransitionError):
            await self._complete_use_case().execute(self.actor, self.lot.id, CompleteLotCommand())

    async def test_complete_force_finishes_a_held_lot(self):
        # Force-finishing a lot on hold, beside the in-progress lot of the
        # tests above. The hold is settled first, so the lot derives ON_HOLD
        # from its facts before the force-complete. A lot that produced
        # something never derives DRAFT, so that case has no seed.
        await self._give_progress()
        self.lot.held_at = datetime(2026, 1, 3, tzinfo=UTC)
        await self.lot_repo.save(self.lot)
        settle = lifecycle_collaborators(
            self.production_order_repo,
            self.lot_repo,
            self.bus,
            orders=self.parent_order_repo,
            order_items=self.order_item_repo,
        )["reconciler"]
        settle.touch_lots([self.lot.id])
        await settle.run(self.actor, datetime(2026, 1, 3, tzinfo=UTC))
        assert (await self.lot_repo.get_by_id(self.lot.id)).status == "on_hold"

        result = await self._complete_use_case().execute(
            self.actor, self.lot.id, CompleteLotCommand()
        )
        assert result.status == "completed"
        lot = await self.lot_repo.get_by_id(self.lot.id)
        assert lot.held_at is None
        internal = await self.lot_repo.get_position_by_id(self.internal_position.id)
        assert internal.status == "completed"
        assert internal.quantity_completed == 3.0

    async def test_cancel_forces_children_and_deallocates_order_item(self):
        use_case = CancelLot(
            self.lot_repo,
            self.production_order_repo,
            self.order_item_repo,
            self.allocation_repo,
            self.made_item_allocation_repo,
            self.source_item_demand_repo,
            self.source_item_allocation_repo,
            event_bus=self.bus,
            uow=self.uow,
            parent_order_repo=self.parent_order_repo,
            **lifecycle_collaborators(
                self.production_order_repo,
                self.lot_repo,
                self.bus,
                orders=self.parent_order_repo,
                order_items=self.order_item_repo,
            ),
        )
        result = await use_case.execute(
            self.actor, self.lot.id, CancelLotCommand(reason="scrapped")
        )
        assert result.status == "canceled"

        internal = await self.lot_repo.get_position_by_id(self.internal_position.id)
        assert internal.status == "canceled"
        assert self.production_order_repo.orders[1].status == ProductionOrderStatus.CANCELED.value

        external = await self.lot_repo.get_position_by_id(self.external_position.id)
        assert external.status == "canceled"
        # The supplier line was ordered and received nothing, so it stays
        # open for purchasing to settle with the supplier.
        assert (await self.order_item_repo.get_by_id(1)).status == "ordered"

        assert self.uow.committed is True

    def _cancel_use_case(self) -> CancelLot:
        return CancelLot(
            self.lot_repo,
            self.production_order_repo,
            self.order_item_repo,
            self.allocation_repo,
            self.made_item_allocation_repo,
            self.source_item_demand_repo,
            self.source_item_allocation_repo,
            event_bus=self.bus,
            uow=self.uow,
            parent_order_repo=self.parent_order_repo,
            **lifecycle_collaborators(
                self.production_order_repo,
                self.lot_repo,
                self.bus,
                orders=self.parent_order_repo,
                order_items=self.order_item_repo,
            ),
        )

    def _complete_use_case(self) -> CompleteLot:
        return CompleteLot(
            self.lot_repo,
            self.production_order_repo,
            self.order_item_repo,
            event_bus=self.bus,
            uow=self.uow,
            parent_order_repo=self.parent_order_repo,
            made_item_demand_repo=self.made_item_demand_repo,
            made_item_allocation_repo=self.made_item_allocation_repo,
            **lifecycle_collaborators(
                self.production_order_repo,
                self.lot_repo,
                self.bus,
                orders=self.parent_order_repo,
                order_items=self.order_item_repo,
            ),
            source_item_demand_repo=FakeSourceItemDemandRepository(),
            source_item_allocation_repo=FakeSourceItemAllocationRepository(),
            bought_allocation_repo=FakeBoughtItemAllocationRepository(),
        )

    async def test_cancel_publishes_production_order_canceled_per_child(self):
        await self._cancel_use_case().execute(
            self.actor, self.lot.id, CancelLotCommand(reason="scrap")
        )
        events = [e for e in self.bus.published if isinstance(e, ProductionOrderCanceled)]
        assert len(events) == 1
        assert events[0].production_order_id == self.internal_order.id
        assert events[0].creator_id == self.internal_order.creator_id
        assert events[0].actor_id == self.actor.id

    async def test_cancel_records_a_lot_event_per_canceled_order(self):
        await self._cancel_use_case().execute(
            self.actor, self.lot.id, CancelLotCommand(reason="scrap")
        )
        events = await self.lot_repo.get_events(self.lot.id)
        order_canceled = [e for e in events if e.event_type == LotEventType.ORDER_CANCELED]
        lot_canceled = [e for e in events if e.event_type == LotEventType.LOT_CANCELED]
        assert len(order_canceled) == 1
        assert order_canceled[0].entity_id == self.internal_order.id
        assert len(lot_canceled) == 1

    async def test_cancel_of_a_lot_with_good_pieces_is_refused(self):
        # The position made pieces, which force-complete keeps and a cancel
        # would throw away, so the lot and its position stay as they are.
        await self._give_progress()

        with pytest.raises(LotInvalidStatusTransitionError, match="force-complete"):
            await self._cancel_use_case().execute(
                self.actor, self.lot.id, CancelLotCommand(reason="scrap")
            )

        position = await self.lot_repo.get_position_by_id(self.internal_position.id)
        assert position.kind == "internal"
        assert (await self.lot_repo.get_by_id(self.lot.id)).canceled_at is None

    async def test_complete_publishes_production_order_completed_per_child(self):
        await self._give_progress()
        await self._complete_use_case().execute(self.actor, self.lot.id, CompleteLotCommand())
        events = [e for e in self.bus.published if isinstance(e, ProductionOrderCompleted)]
        assert len(events) == 1
        assert events[0].production_order_id == self.internal_order.id

    async def test_cancel_reads_the_lot_with_a_row_lock(self):
        """Same rationale as test_complete_reads_the_lot_with_a_row_lock."""
        use_case = CancelLot(
            self.lot_repo,
            self.production_order_repo,
            self.order_item_repo,
            self.allocation_repo,
            self.made_item_allocation_repo,
            self.source_item_demand_repo,
            self.source_item_allocation_repo,
            event_bus=self.bus,
            uow=self.uow,
            parent_order_repo=self.parent_order_repo,
            **lifecycle_collaborators(
                self.production_order_repo,
                self.lot_repo,
                self.bus,
                orders=self.parent_order_repo,
                order_items=self.order_item_repo,
            ),
        )
        await use_case.execute(self.actor, self.lot.id, CancelLotCommand(reason="scrapped"))
        assert self.lot_repo.for_update_calls == [self.lot.id]

    async def test_cancel_requires_manage_lots_permission(self):
        actor = make_user(permissions=[Permission.WRITE_LOTS])
        use_case = CancelLot(
            self.lot_repo,
            self.production_order_repo,
            self.order_item_repo,
            self.allocation_repo,
            self.made_item_allocation_repo,
            self.source_item_demand_repo,
            self.source_item_allocation_repo,
            event_bus=self.bus,
            uow=self.uow,
            parent_order_repo=self.parent_order_repo,
            **lifecycle_collaborators(
                self.production_order_repo,
                self.lot_repo,
                self.bus,
                orders=self.parent_order_repo,
                order_items=self.order_item_repo,
            ),
        )
        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(actor, self.lot.id, CancelLotCommand())

    async def test_cancel_rejects_already_terminal_lot(self):
        self.lot.status = LotStatus.CANCELED
        await self.lot_repo.save(self.lot)
        use_case = CancelLot(
            self.lot_repo,
            self.production_order_repo,
            self.order_item_repo,
            self.allocation_repo,
            self.made_item_allocation_repo,
            self.source_item_demand_repo,
            self.source_item_allocation_repo,
            event_bus=self.bus,
            uow=self.uow,
            parent_order_repo=self.parent_order_repo,
            **lifecycle_collaborators(
                self.production_order_repo,
                self.lot_repo,
                self.bus,
                orders=self.parent_order_repo,
                order_items=self.order_item_repo,
            ),
        )
        with pytest.raises(LotInvalidStatusTransitionError):
            await use_case.execute(self.actor, self.lot.id, CancelLotCommand())

    async def test_cancel_deallocates_made_item_demand_this_lot_was_built_for(self):
        self.made_item_demand_repo = FakeMadeItemDemandRepository([make_demand(id=9, quantity=6.0)])
        self.made_item_allocation_repo = FakeMadeItemAllocationRepository(
            [
                MadeItemDemandAllocation(
                    demand_item_id=9,
                    lot_id=self.lot.id,
                    quantity=6.0,
                    source=MadeItemAllocationSource.LOT,
                )
            ]
        )
        use_case = CancelLot(
            self.lot_repo,
            self.production_order_repo,
            self.order_item_repo,
            self.allocation_repo,
            self.made_item_allocation_repo,
            self.source_item_demand_repo,
            self.source_item_allocation_repo,
            event_bus=self.bus,
            uow=self.uow,
            parent_order_repo=self.parent_order_repo,
            **lifecycle_collaborators(
                self.production_order_repo,
                self.lot_repo,
                self.bus,
                orders=self.parent_order_repo,
                order_items=self.order_item_repo,
            ),
        )
        await use_case.execute(self.actor, self.lot.id, CancelLotCommand(reason="scrapped"))

        assert await self.made_item_allocation_repo.get_by_demand_item_id(9) == []
        assert (await self.made_item_demand_repo.get_by_id(9)).status == "open"
