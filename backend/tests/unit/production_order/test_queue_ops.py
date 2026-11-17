"""
Covers how production orders move through their machine queues: splitting a quantity off
an order, merging orders back together, reordering the queue, and reassigning an order to
a different machine or pool. Unit tests for TestSplitProductionOrder,
TestMergeProductionOrders, TestReorderProductionOrders and
TestReassignProductionOrderMachine. No database, no HTTP. All dependencies replaced with
in-memory fakes.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta

import pytest
from pydantic import ValidationError

from src.modules.catalogue.domain.errors import MachineCapabilityMismatchError
from src.modules.fulfillment.application.dto.production_order_dto import (
    MergeProductionOrdersCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    ReassignProductionOrderMachineCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    ReorderProductionOrdersCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import SplitProductionOrderCommand
from src.modules.fulfillment.application.use_cases.production_order.merge_production_orders import (
    MergeProductionOrders,
)
from src.modules.fulfillment.application.use_cases.production_order.reassign_production_order_machine import (
    ReassignProductionOrderMachine,
)
from src.modules.fulfillment.application.use_cases.production_order.reorder_production_orders import (
    ReorderProductionOrders,
)
from src.modules.fulfillment.application.use_cases.production_order.split_production_order import (
    SplitProductionOrder,
)
from src.modules.fulfillment.domain.errors import ProductionOrderCannotMergeError
from src.modules.fulfillment.domain.errors import ProductionOrderInvalidStatusTransitionError
from src.modules.fulfillment.domain.errors import ProductionOrderNotSplittableError
from src.modules.fulfillment.domain.errors import ProductionOrderReorderInvalidError
from src.modules.fulfillment.domain.errors import ProductionOrderSplitMismatchError
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderCanceled
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.production_order._helpers import make_lot
from tests.unit.production_order._helpers import make_machine
from tests.unit.production_order._helpers import make_order
from tests.unit.production_order._helpers import make_position
from tests.unit.production_order._helpers import make_step
from tests.unit.production_order.fakes import FakeAdminSettingsRepository
from tests.unit.production_order.fakes import FakeEventBus
from tests.unit.production_order.fakes import FakeLockPlan
from tests.unit.production_order.fakes import FakeProductionLotRepository
from tests.unit.production_order.fakes import FakeProductionMachineRepository
from tests.unit.production_order.fakes import FakeProductionOrderRepository
from tests.unit.production_order.fakes import FakeUnitOfWork
from tests.unit.production_order.fakes import production_order_reconciler


class TestSplitProductionOrder:
    def setup_method(self):
        self.order_repo = FakeProductionOrderRepository([make_order(id=1, quantity=10.0)])
        self.lot_repo = FakeProductionLotRepository(
            [make_lot(positions=[make_position(id=1, quantity=10.0)])]
        )
        self.settings_repo = FakeAdminSettingsRepository()
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.WRITE_PRODUCTION_ORDERS])
        self.use_case = SplitProductionOrder(
            self.order_repo,
            self.lot_repo,
            self.settings_repo,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=production_order_reconciler(self.order_repo, self.lot_repo, self.bus),
        )

    async def test_splits_quantities_conserved(self):
        cmd = SplitProductionOrderCommand(quantities=[6.0, 4.0])
        results = await self.use_case.execute(self.actor, production_order_id=1, cmd=cmd)
        assert sum(r.quantity for r in results) == 10.0
        assert len(results) == 2
        assert len(await self.order_repo.get_by_lot_position_id(1)) == 2

    async def test_rejects_non_queued_order(self):
        self.order_repo._orders[1].status = ProductionOrderStatus.IN_PROGRESS
        cmd = SplitProductionOrderCommand(quantities=[6.0, 4.0])
        with pytest.raises(ProductionOrderNotSplittableError):
            await self.use_case.execute(self.actor, production_order_id=1, cmd=cmd)

    async def test_rejects_mismatched_sum(self):
        cmd = SplitProductionOrderCommand(quantities=[6.0, 6.0])
        with pytest.raises(ProductionOrderSplitMismatchError):
            await self.use_case.execute(self.actor, production_order_id=1, cmd=cmd)

    async def test_rejects_zero_or_negative_part(self):
        # Same guard, exercised through the use case rather than the pure
        # function directly.
        cmd = SplitProductionOrderCommand(quantities=[0.0, 10.0])
        with pytest.raises(ProductionOrderSplitMismatchError, match="positive"):
            await self.use_case.execute(self.actor, production_order_id=1, cmd=cmd)

    async def test_records_a_lot_event(self):
        cmd = SplitProductionOrderCommand(quantities=[6.0, 4.0])
        results = await self.use_case.execute(self.actor, production_order_id=1, cmd=cmd)
        events = [
            e for e in await self.lot_repo.get_events(1) if e.event_type == LotEventType.ORDER_SPLIT
        ]
        assert len(events) == 1
        assert events[0].entity_id == 1
        assert events[0].payload["source_production_order_id"] == 1
        assert events[0].payload["quantities"] == [6.0, 4.0]
        # The new part's id is recorded (the keeper is the source, not a part).
        new_ids = [r.id for r in results if r.id != 1]
        assert events[0].payload["part_production_order_ids"] == new_ids


class TestMergeProductionOrders:
    def setup_method(self):
        self.order_repo = FakeProductionOrderRepository(
            [
                make_order(id=1, quantity=6.0, queue_sequence=1),
                make_order(id=2, quantity=4.0, queue_sequence=2),
            ]
        )
        self.lot_repo = FakeProductionLotRepository(
            [make_lot(positions=[make_position(id=1, quantity=10.0)])]
        )
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.WRITE_PRODUCTION_ORDERS])
        self.use_case = MergeProductionOrders(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=production_order_reconciler(self.order_repo, self.lot_repo, self.bus),
        )

    async def test_merges_into_keeper(self):
        cmd = MergeProductionOrdersCommand(production_order_ids=[1, 2])
        result = await self.use_case.execute(self.actor, cmd=cmd)
        assert result.id == 1
        assert result.quantity == 10.0
        assert (await self.order_repo.get_by_id(2)).status == ProductionOrderStatus.CANCELED.value
        assert (await self.order_repo.get_by_id(2)).quantity == 0.0

    async def test_merged_duration_is_recomputed_not_summed(self):
        """Each split part's estimated_duration_minutes already includes a
        full setup pass; summing them would double-count setup. The merged
        keeper's duration must be recomputed from the position's steps for
        the merged quantity instead."""
        self.order_repo._orders[1].estimated_duration_minutes = 30  # 10 setup + 6*(10/3)
        self.order_repo._orders[2].estimated_duration_minutes = 30  # 10 setup + 4*5
        cmd = MergeProductionOrdersCommand(production_order_ids=[1, 2])
        result = await self.use_case.execute(self.actor, cmd=cmd)
        # position steps default to make_step(setup=10, per_piece=2.0)
        # -> 10 + 10*2.0 = 30, NOT 30+30=60.
        assert result.estimated_duration_minutes == 30

    async def test_rejects_different_machines(self):
        self.order_repo._orders[2].machine_id = 2
        cmd = MergeProductionOrdersCommand(production_order_ids=[1, 2])
        with pytest.raises(ProductionOrderCannotMergeError):
            await self.use_case.execute(self.actor, cmd=cmd)

    async def test_rejects_non_queued(self):
        self.order_repo._orders[2].status = ProductionOrderStatus.IN_PROGRESS
        cmd = MergeProductionOrdersCommand(production_order_ids=[1, 2])
        with pytest.raises(ProductionOrderCannotMergeError):
            await self.use_case.execute(self.actor, cmd=cmd)

    async def test_publishes_production_order_canceled_for_merged_away_orders(self):
        cmd = MergeProductionOrdersCommand(production_order_ids=[1, 2])
        await self.use_case.execute(self.actor, cmd=cmd)
        events = [e for e in self.bus.published if isinstance(e, ProductionOrderCanceled)]
        # One per merged-away order, zero for the keeper (#1).
        assert len(events) == 1
        assert events[0].production_order_id == 2
        assert events[0].actor_id == self.actor.id

    async def test_records_a_lot_event(self):
        cmd = MergeProductionOrdersCommand(production_order_ids=[1, 2])
        await self.use_case.execute(self.actor, cmd=cmd)
        events = [
            e
            for e in await self.lot_repo.get_events(1)
            if e.event_type == LotEventType.ORDER_MERGED
        ]
        assert len(events) == 1
        assert events[0].payload["keeper_production_order_id"] == 1
        assert events[0].payload["merged_production_order_ids"] == [2]
        assert events[0].payload["quantity"] == 10.0


class TestReorderProductionOrders:
    def setup_method(self):
        self.order_repo = FakeProductionOrderRepository(
            [
                make_order(id=1, machine_id=1, queue_sequence=1),
                make_order(id=2, machine_id=1, queue_sequence=2),
            ]
        )
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.WRITE_PRODUCTION_ORDERS])
        self.use_case = ReorderProductionOrders(
            self.order_repo, event_bus=self.bus, uow=self.uow, lock_plan=FakeLockPlan()
        )

    async def test_reorders_sequence_only_never_status(self):
        cmd = ReorderProductionOrdersCommand(ordered_production_order_ids=[2, 1])
        await self.use_case.execute(self.actor, machine_id=1, cmd=cmd)
        assert (await self.order_repo.get_by_id(2)).queue_sequence == 1
        assert (await self.order_repo.get_by_id(1)).queue_sequence == 2
        assert (await self.order_repo.get_by_id(1)).status == ProductionOrderStatus.QUEUED.value
        assert (await self.order_repo.get_by_id(2)).status == ProductionOrderStatus.QUEUED.value

    async def test_rejects_reordering_pinned_order(self):
        self.order_repo._orders[1].pinned = True
        cmd = ReorderProductionOrdersCommand(ordered_production_order_ids=[2, 1])
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(self.actor, machine_id=1, cmd=cmd)

    async def test_rejects_reordering_in_progress_order(self):
        # An IN_PROGRESS order is a state conflict (422), not a
        # permission error (403).
        self.order_repo._orders[1].status = ProductionOrderStatus.IN_PROGRESS
        cmd = ReorderProductionOrdersCommand(ordered_production_order_ids=[2, 1])
        with pytest.raises(ProductionOrderInvalidStatusTransitionError):
            await self.use_case.execute(self.actor, machine_id=1, cmd=cmd)

    async def test_rejects_completed_order(self):
        self.order_repo._orders[1].status = ProductionOrderStatus.COMPLETED
        cmd = ReorderProductionOrdersCommand(ordered_production_order_ids=[2, 1])
        with pytest.raises(ProductionOrderInvalidStatusTransitionError):
            await self.use_case.execute(self.actor, machine_id=1, cmd=cmd)
        # No queue_sequence rewritten.
        assert (await self.order_repo.get_by_id(1)).queue_sequence == 1
        assert (await self.order_repo.get_by_id(2)).queue_sequence == 2

    async def test_rejects_canceled_order(self):
        self.order_repo._orders[1].status = ProductionOrderStatus.CANCELED
        cmd = ReorderProductionOrdersCommand(ordered_production_order_ids=[2, 1])
        with pytest.raises(ProductionOrderInvalidStatusTransitionError):
            await self.use_case.execute(self.actor, machine_id=1, cmd=cmd)
        assert (await self.order_repo.get_by_id(1)).queue_sequence == 1
        assert (await self.order_repo.get_by_id(2)).queue_sequence == 2

    async def test_rejects_duplicate_ids(self):
        cmd = ReorderProductionOrdersCommand(ordered_production_order_ids=[1, 2, 1])
        with pytest.raises(ProductionOrderReorderInvalidError):
            await self.use_case.execute(self.actor, machine_id=1, cmd=cmd)

    async def test_swapping_two_adjacent_orders_succeeds(self):
        """The queue_sequence backstop must not break a legitimate
        reorder: an adjacent swap rewrites both rows within one
        transaction and must succeed (it transiently duplicates a sequence
        mid-loop, which is exactly why a plain unique constraint was
        rejected in favour of the advisory lock)."""
        cmd = ReorderProductionOrdersCommand(ordered_production_order_ids=[2, 1])
        results = await self.use_case.execute(self.actor, machine_id=1, cmd=cmd)
        assert [r.id for r in results] == [2, 1]
        assert (await self.order_repo.get_by_id(2)).queue_sequence == 1
        assert (await self.order_repo.get_by_id(1)).queue_sequence == 2
        # No two orders share a sequence once the operation completes.
        sequences = [o.queue_sequence for o in await self.order_repo.get_by_machine_id(1)]
        assert len(set(sequences)) == len(sequences)

    async def test_a_moved_order_loses_its_planned_window_for_the_walk(self):
        start = datetime(2026, 7, 27, 8, tzinfo=UTC)
        for order in self.order_repo._orders.values():
            order.planned_start, order.planned_end = start, start + timedelta(hours=1)
        cmd = ReorderProductionOrdersCommand(ordered_production_order_ids=[2, 1])

        await self.use_case.execute(self.actor, machine_id=1, cmd=cmd)

        for order_id in (1, 2):
            order = await self.order_repo.get_by_id(order_id)
            assert (order.planned_start, order.planned_end) == (None, None)

    async def test_locks_the_queue_scope_before_reading_it(self):
        cmd = ReorderProductionOrdersCommand(ordered_production_order_ids=[2, 1])
        await self.use_case.execute(self.actor, machine_id=1, cmd=cmd)
        assert self.order_repo.queue_locks == [(1, None)]

    def test_empty_id_list_is_rejected_by_the_schema(self):
        """An "empty list is a no-op" case might seem worth testing, but
        ReorderProductionOrdersCommand.ordered_production_order_ids carries
        min_length=1 (production_order_dto.py), so an empty reorder can never
        reach the use case at all; it is rejected at command construction.
        Characterized here so the guarantee is pinned rather than assumed."""
        with pytest.raises(ValidationError):
            ReorderProductionOrdersCommand(ordered_production_order_ids=[])


class TestReassignProductionOrderMachine:
    def setup_method(self):
        self.step = make_step(position_id=1, fabrication_method_id=1)
        self.position = make_position(
            id=1, quantity=10.0, kind=LotPositionKind.INTERNAL, steps=[self.step]
        )
        self.lot = make_lot(positions=[self.position])
        self.lot_repo = FakeProductionLotRepository([self.lot])
        self.machine_repo = FakeProductionMachineRepository(
            [
                make_machine(id=1, fabrication_method_ids=[1]),
                make_machine(id=2, fabrication_method_ids=[1]),
                make_machine(id=3, fabrication_method_ids=[99]),
            ]
        )
        self.order_repo = FakeProductionOrderRepository(
            [make_order(id=1, machine_id=1, lot_position_id=1, queue_sequence=1)]
        )
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.WRITE_PRODUCTION_ORDERS])
        self.use_case = ReassignProductionOrderMachine(
            self.order_repo,
            self.lot_repo,
            self.machine_repo,
            event_bus=self.bus,
            uow=self.uow,
            lock_plan=FakeLockPlan(),
        )

    async def test_reassigns_to_another_machine(self):
        cmd = ReassignProductionOrderMachineCommand(machine_id=2)
        result = await self.use_case.execute(self.actor, production_order_id=1, cmd=cmd)
        assert result.machine_id == 2
        assert self.uow.committed is True

    async def test_a_reassigned_order_loses_its_planned_window_for_the_walk(self):
        start = datetime(2026, 7, 27, 8, tzinfo=UTC)
        order = self.order_repo._orders[1]
        order.planned_start, order.planned_end = start, start + timedelta(hours=1)
        cmd = ReassignProductionOrderMachineCommand(machine_id=2)

        result = await self.use_case.execute(self.actor, production_order_id=1, cmd=cmd)

        assert (result.planned_start, result.planned_end) == (None, None)

    async def test_reassigns_to_no_machine(self):
        cmd = ReassignProductionOrderMachineCommand(machine_id=None)
        result = await self.use_case.execute(self.actor, production_order_id=1, cmd=cmd)
        assert result.machine_id is None

    async def test_reassigns_from_no_machine_to_a_real_machine(self):
        self.order_repo._orders[1].machine_id = None
        cmd = ReassignProductionOrderMachineCommand(machine_id=2)
        result = await self.use_case.execute(self.actor, production_order_id=1, cmd=cmd)
        assert result.machine_id == 2

    async def test_a_paused_order_moves_and_its_changelog_names_both_machines(self):
        order = self.order_repo._orders[1]
        order.status = ProductionOrderStatus.PAUSED
        order.quantity_completed = 4.0

        result = await self.use_case.execute(
            self.actor,
            production_order_id=1,
            cmd=ReassignProductionOrderMachineCommand(machine_id=2),
        )

        assert result.machine_id == 2
        last_entry = (await self.order_repo.get_by_id(1)).changes[-1]
        assert last_entry.endswith(
            "Reassigned to machine #2 from machine #1. Paused after 4 completed piece(s)."
        )

    async def test_rejects_pinned_order(self):
        self.order_repo._orders[1].pinned = True
        cmd = ReassignProductionOrderMachineCommand(machine_id=2)
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(self.actor, production_order_id=1, cmd=cmd)

    async def test_rejects_in_progress_order(self):
        # An IN_PROGRESS order is a state conflict (422), not a
        # permission error (403).
        self.order_repo._orders[1].status = ProductionOrderStatus.IN_PROGRESS
        cmd = ReassignProductionOrderMachineCommand(machine_id=2)
        with pytest.raises(ProductionOrderInvalidStatusTransitionError):
            await self.use_case.execute(self.actor, production_order_id=1, cmd=cmd)

    async def test_rejects_machine_without_capability(self):
        cmd = ReassignProductionOrderMachineCommand(machine_id=3)
        with pytest.raises(MachineCapabilityMismatchError):
            await self.use_case.execute(self.actor, production_order_id=1, cmd=cmd)

    async def test_locks_the_target_queue_scope(self):
        cmd = ReassignProductionOrderMachineCommand(machine_id=2)
        await self.use_case.execute(self.actor, production_order_id=1, cmd=cmd)
        # Locked on the TARGET queue, where the new sequence is drawn from.
        assert self.order_repo.queue_locks == [(2, None)]

    async def test_rejects_completed_order(self):
        self.order_repo._orders[1].status = ProductionOrderStatus.COMPLETED
        cmd = ReassignProductionOrderMachineCommand(machine_id=2)
        with pytest.raises(ProductionOrderInvalidStatusTransitionError):
            await self.use_case.execute(self.actor, production_order_id=1, cmd=cmd)
        assert (await self.order_repo.get_by_id(1)).machine_id == 1
        assert (await self.order_repo.get_by_id(1)).queue_sequence == 1

    async def test_rejects_canceled_order(self):
        self.order_repo._orders[1].status = ProductionOrderStatus.CANCELED
        cmd = ReassignProductionOrderMachineCommand(machine_id=2)
        with pytest.raises(ProductionOrderInvalidStatusTransitionError):
            await self.use_case.execute(self.actor, production_order_id=1, cmd=cmd)
        assert (await self.order_repo.get_by_id(1)).machine_id == 1
        assert (await self.order_repo.get_by_id(1)).queue_sequence == 1
