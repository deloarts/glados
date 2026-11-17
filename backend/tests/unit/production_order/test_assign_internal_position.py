"""
Unit tests for TestAssignInternalPosition. No database, no HTTP. All
dependencies replaced with in-memory fakes.
"""

from datetime import datetime

import pytest

from src.modules.catalogue.domain.errors import MachineCapabilityMismatchError
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.application.dto.production_order_dto import (
    AssignInternalPositionCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    AssignInternalPositionOrderInput,
)
from src.modules.fulfillment.application.use_cases.production_order.assign_internal_position import (
    AssignInternalPosition,
)
from src.modules.fulfillment.domain.errors import LotInvalidStatusTransitionError
from src.modules.fulfillment.domain.errors import LotPositionNotFoundError
from src.modules.fulfillment.domain.errors import ProductionOrderNoMachineAssignedError
from src.modules.fulfillment.domain.errors import ProductionOrderQuantityOverflowError
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderCreated
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.domain.entities.project import Project
from tests.factories import make_user
from tests.unit.lifecycle.fake_reconciler import give_order_item_facts
from tests.unit.production_lot._helpers import make_order as make_supplier_order
from tests.unit.production_lot._helpers import make_order_item
from tests.unit.production_lot.fakes import FakeOrderItemRepository
from tests.unit.production_lot.fakes import FakeOrderRepository
from tests.unit.production_lot.fakes import FakeProjectRepository
from tests.unit.production_order._helpers import make_lot
from tests.unit.production_order._helpers import make_machine
from tests.unit.production_order._helpers import make_position
from tests.unit.production_order._helpers import make_step
from tests.unit.production_order.fakes import FakeAdminSettingsRepository
from tests.unit.production_order.fakes import FakeEventBus
from tests.unit.production_order.fakes import FakeProductionLotRepository
from tests.unit.production_order.fakes import FakeProductionMachineRepository
from tests.unit.production_order.fakes import FakeProductionOrderRepository
from tests.unit.production_order.fakes import FakeUnitOfWork
from tests.unit.production_order.fakes import production_order_reconciler


class TestAssignInternalPosition:
    def setup_method(self):
        self.step = make_step(position_id=1, fabrication_method_id=1)
        self.position = make_position(id=1, quantity=10.0, steps=[self.step])
        self.lot = make_lot(positions=[self.position])
        self.lot_repo = FakeProductionLotRepository([self.lot])
        self.machine_repo = FakeProductionMachineRepository(
            [
                make_machine(id=1, fabrication_method_ids=[1]),
                make_machine(id=2, fabrication_method_ids=[1]),
            ]
        )
        self.order_repo = FakeProductionOrderRepository()
        self.lot_repo.production_orders = self.order_repo
        self.settings_repo = FakeAdminSettingsRepository()
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.WRITE_PRODUCTION_ORDERS])
        self.use_case = AssignInternalPosition(
            self.lot_repo,
            self.machine_repo,
            self.order_repo,
            self.settings_repo,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=production_order_reconciler(self.order_repo, self.lot_repo, FakeEventBus()),
        )

    async def test_assigns_single_machine_full_quantity(self):
        cmd = AssignInternalPositionCommand(
            orders=[AssignInternalPositionOrderInput(machine_id=1, quantity=10.0)]
        )
        result = await self.use_case.execute(self.actor, lot_id=1, position_id=1, cmd=cmd)
        assert result.kind == LotPositionKind.INTERNAL.value
        assert len(await self.order_repo.get_by_lot_position_id(1)) == 1
        assert (await self.order_repo.get_by_id(1)).quantity == 10.0
        assert self.uow.committed is True

    async def test_splits_across_two_machines(self):
        cmd = AssignInternalPositionCommand(
            orders=[
                AssignInternalPositionOrderInput(machine_id=1, quantity=6.0),
                AssignInternalPositionOrderInput(machine_id=2, quantity=4.0),
            ]
        )
        await self.use_case.execute(self.actor, lot_id=1, position_id=1, cmd=cmd)
        orders = await self.order_repo.get_by_lot_position_id(1)
        assert len(orders) == 2
        assert sum(o.quantity for o in orders) == 10.0
        assert {o.machine_id for o in orders} == {1, 2}

    async def test_assign_last_position_advances_draft_lot_to_planned(self):
        self.lot.status = LotStatus.DRAFT
        await self.lot_repo.save(self.lot)
        cmd = AssignInternalPositionCommand(
            orders=[AssignInternalPositionOrderInput(machine_id=1, quantity=10.0)]
        )
        await self.use_case.execute(self.actor, lot_id=1, position_id=1, cmd=cmd)
        assert (await self.lot_repo.get_by_id(1)).status == LotStatus.PLANNED.value

    async def test_assign_one_of_two_positions_advances_draft_lot_to_partially_planned(self):
        other_step = make_step(id=2, position_id=2, fabrication_method_id=1)
        other_position = make_position(id=2, sequence=2, quantity=5.0, steps=[other_step])
        self.lot.status = LotStatus.DRAFT
        self.lot.positions = [self.position, other_position]
        await self.lot_repo.save(self.lot)
        await self.lot_repo.save_position(other_position)

        cmd = AssignInternalPositionCommand(
            orders=[AssignInternalPositionOrderInput(machine_id=1, quantity=10.0)]
        )
        await self.use_case.execute(self.actor, lot_id=1, position_id=1, cmd=cmd)
        assert (await self.lot_repo.get_by_id(1)).status == LotStatus.PARTIALLY_PLANNED.value

    async def test_assign_makes_position_eligible_and_recomputes_project_time_budget(self):
        """The mirror image of
        test_cancel_last_order_recomputes_project_time_budget_across_lots:
        assigning an UNASSIGNED position to a machine makes it INTERNAL,
        newly eligible for the project's shared time-budget pool, so a
        sibling lot in the same project must have its apportioned share
        recalculated too, even though this action never touches it
        directly."""
        self.step.estimated_minutes_per_piece = None
        await self.lot_repo.save_step(self.step)

        other_step = make_step(id=2, position_id=2, estimated_minutes_per_piece=None)
        other_position = make_position(
            id=2, sequence=2, quantity=5.0, kind=LotPositionKind.INTERNAL, steps=[other_step]
        )
        other_lot = make_lot(id=2, quantity=5.0, positions=[other_position])
        self.lot_repo._lots[2] = other_lot
        self.lot_repo._positions[2] = other_position

        project = Project(
            id=1,
            created=datetime(2026, 1, 1),
            project_number="P1",
            production_time_budget=100,
        )
        project_repo = FakeProjectRepository([project])
        use_case = AssignInternalPosition(
            self.lot_repo,
            self.machine_repo,
            self.order_repo,
            self.settings_repo,
            project_repo=project_repo,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=production_order_reconciler(self.order_repo, self.lot_repo, FakeEventBus()),
        )

        cmd = AssignInternalPositionCommand(
            orders=[AssignInternalPositionOrderInput(machine_id=1, quantity=10.0)]
        )
        await use_case.execute(self.actor, lot_id=1, position_id=1, cmd=cmd)

        # Position 1 (qty 10) is now INTERNAL too, sharing the pool with
        # lot 2 (qty 5): denominator = 15, per-piece = 100 / 15.
        expected = 100 / 15
        assert (await self.lot_repo.get_step_by_id(1)).time_budget_per_piece == pytest.approx(
            expected
        )
        assert (await self.lot_repo.get_step_by_id(2)).time_budget_per_piece == pytest.approx(
            expected
        )

    async def test_rejects_machine_requiring_position_with_neither_machine_nor_pool(self):
        """A position with a machine-requiring step cannot be queued
        "assign the machine later"; see assert_machine_or_pool_assigned."""
        cmd = AssignInternalPositionCommand(
            orders=[AssignInternalPositionOrderInput(machine_id=None, quantity=10.0)]
        )
        with pytest.raises(ProductionOrderNoMachineAssignedError):
            await self.use_case.execute(self.actor, lot_id=1, position_id=1, cmd=cmd)

    async def test_assigns_manual_position_with_no_machine_queues_unassigned_and_advances_lot(self):
        """The mandatory-assignment rule exempts pure-manual
        positions: "assign now, no machine ever needed" stays legal."""
        manual_step = make_step(
            position_id=1, fabrication_method_id=2, fabrication_method_requires_machine=False
        )
        self.position.steps = [manual_step]
        await self.lot_repo.save_position(self.position)
        self.lot.status = LotStatus.DRAFT
        await self.lot_repo.save(self.lot)
        cmd = AssignInternalPositionCommand(
            orders=[AssignInternalPositionOrderInput(machine_id=None, quantity=10.0)]
        )
        result = await self.use_case.execute(self.actor, lot_id=1, position_id=1, cmd=cmd)
        assert result.kind == LotPositionKind.INTERNAL.value
        orders = await self.order_repo.get_by_lot_position_id(1)
        assert len(orders) == 1
        assert orders[0].machine_id is None
        assert orders[0].status == ProductionOrderStatus.QUEUED.value
        assert (await self.lot_repo.get_by_id(1)).status == LotStatus.PLANNED.value

    async def test_assigns_inspection_position_with_no_machine(self):
        """The mandatory-assignment rule exempts inspection/QA
        positions too. QA work is matched by is_qa_machine, never by this
        fabrication-method machinery, and stays legally machine-less here."""
        inspection_step = make_step(
            position_id=1,
            fabrication_method_id=None,
            fabrication_method_requires_machine=False,
            role=StepRole.INSPECTION,
            inspection_method_id=1,
            inspection_method_name="Measurement",
        )
        self.position.steps = [inspection_step]
        await self.lot_repo.save_position(self.position)
        cmd = AssignInternalPositionCommand(
            orders=[AssignInternalPositionOrderInput(machine_id=None, quantity=10.0)]
        )
        result = await self.use_case.execute(self.actor, lot_id=1, position_id=1, cmd=cmd)
        assert result.kind == LotPositionKind.INTERNAL.value
        orders = await self.order_repo.get_by_lot_position_id(1)
        assert len(orders) == 1
        assert orders[0].machine_id is None

    async def test_rejects_when_sum_exceeds_position_quantity(self):
        cmd = AssignInternalPositionCommand(
            orders=[
                AssignInternalPositionOrderInput(machine_id=1, quantity=6.0),
                AssignInternalPositionOrderInput(machine_id=2, quantity=6.0),
            ]
        )
        with pytest.raises(ProductionOrderQuantityOverflowError):
            await self.use_case.execute(self.actor, lot_id=1, position_id=1, cmd=cmd)

    async def test_rejects_machine_without_capability(self):
        cmd = AssignInternalPositionCommand(
            orders=[AssignInternalPositionOrderInput(machine_id=1, quantity=10.0)]
        )
        machine_repo = FakeProductionMachineRepository(
            [make_machine(id=1, fabrication_method_ids=[99])]
        )
        use_case = AssignInternalPosition(
            self.lot_repo,
            machine_repo,
            self.order_repo,
            self.settings_repo,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=production_order_reconciler(self.order_repo, self.lot_repo, FakeEventBus()),
        )
        with pytest.raises(MachineCapabilityMismatchError):
            await use_case.execute(self.actor, lot_id=1, position_id=1, cmd=cmd)

    async def test_assigns_machine_ignoring_manual_step_requirement(self):
        """A position mixing a manual step (e.g. cutting to length, no machine will
        ever cover it) with a machine step must still be assignable to a
        machine that covers only the machine step, the manual step is not
        counted against capability. See _machine_requiring_method_ids."""
        manual_step = make_step(
            id=2, position_id=1, fabrication_method_id=2, fabrication_method_requires_machine=False
        )
        self.position.steps = [self.step, manual_step]
        await self.lot_repo.save_position(self.position)

        cmd = AssignInternalPositionCommand(
            orders=[AssignInternalPositionOrderInput(machine_id=1, quantity=10.0)]
        )
        result = await self.use_case.execute(self.actor, lot_id=1, position_id=1, cmd=cmd)
        assert result.kind == LotPositionKind.INTERNAL.value

    async def test_rejects_without_permission(self):
        actor = make_user(permissions=[])
        cmd = AssignInternalPositionCommand(
            orders=[AssignInternalPositionOrderInput(machine_id=1, quantity=10.0)]
        )
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(actor, lot_id=1, position_id=1, cmd=cmd)

    async def test_assigning_internal_onto_external_position_becomes_mixed(self):
        self.position.kind = LotPositionKind.EXTERNAL
        self.position.order_item_id = 99
        self.position.order_item_quantity = 4.0
        await self.lot_repo.save_position(self.position)
        # The supplier line the external side stands for.
        line = make_order_item(id=99, lot_position_id=1)
        line.quantity = 4.0
        orders = FakeOrderRepository([make_supplier_order(id=1)])
        use_case = AssignInternalPosition(
            self.lot_repo,
            self.machine_repo,
            self.order_repo,
            self.settings_repo,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=production_order_reconciler(
                self.order_repo,
                self.lot_repo,
                FakeEventBus(),
                orders=orders,
                order_items=FakeOrderItemRepository([give_order_item_facts(line)]),
            ),
        )

        cmd = AssignInternalPositionCommand(
            orders=[AssignInternalPositionOrderInput(machine_id=1, quantity=6.0)]
        )
        result = await use_case.execute(self.actor, lot_id=1, position_id=1, cmd=cmd)
        assert result.kind == LotPositionKind.MIXED.value
        assert result.quantity_remaining == 0.0

    async def test_rejects_when_sum_exceeds_remaining_on_mixed_position(self):
        self.position.kind = LotPositionKind.EXTERNAL
        self.position.order_item_id = 99
        self.position.order_item_quantity = 4.0
        await self.lot_repo.save_position(self.position)

        cmd = AssignInternalPositionCommand(
            orders=[AssignInternalPositionOrderInput(machine_id=1, quantity=7.0)]
        )
        with pytest.raises(ProductionOrderQuantityOverflowError):
            await self.use_case.execute(self.actor, lot_id=1, position_id=1, cmd=cmd)

    async def test_tops_up_a_position_with_live_orders_within_its_remaining_quantity(self):
        cmd = AssignInternalPositionCommand(
            orders=[AssignInternalPositionOrderInput(machine_id=1, quantity=6.0)]
        )
        await self.use_case.execute(self.actor, lot_id=1, position_id=1, cmd=cmd)

        top_up = AssignInternalPositionCommand(
            orders=[AssignInternalPositionOrderInput(machine_id=2, quantity=4.0)]
        )
        result = await self.use_case.execute(self.actor, lot_id=1, position_id=1, cmd=top_up)
        assert result.quantity_remaining == 0.0
        assert sorted(o.quantity for o in await self.order_repo.get_by_lot_position_id(1)) == [
            4.0,
            6.0,
        ]

        beyond = AssignInternalPositionCommand(
            orders=[AssignInternalPositionOrderInput(machine_id=2, quantity=1.0)]
        )
        with pytest.raises(ProductionOrderQuantityOverflowError):
            await self.use_case.execute(self.actor, lot_id=1, position_id=1, cmd=beyond)

    async def test_rejects_assignment_on_canceled_lot(self):
        self.lot.status = LotStatus.CANCELED
        await self.lot_repo.save(self.lot)
        cmd = AssignInternalPositionCommand(
            orders=[AssignInternalPositionOrderInput(machine_id=1, quantity=10.0)]
        )
        with pytest.raises(LotInvalidStatusTransitionError):
            await self.use_case.execute(self.actor, lot_id=1, position_id=1, cmd=cmd)
        assert await self.order_repo.get_by_lot_position_id(1) == []

    async def test_rejects_assignment_on_completed_lot(self):
        self.lot.status = LotStatus.COMPLETED
        await self.lot_repo.save(self.lot)
        cmd = AssignInternalPositionCommand(
            orders=[AssignInternalPositionOrderInput(machine_id=1, quantity=10.0)]
        )
        with pytest.raises(LotInvalidStatusTransitionError):
            await self.use_case.execute(self.actor, lot_id=1, position_id=1, cmd=cmd)
        assert await self.order_repo.get_by_lot_position_id(1) == []

    async def test_an_unknown_position_on_a_finished_lot_is_not_found(self):
        """The position is looked up before the lot's state is judged, so a
        finished lot with an unknown position answers 404, not 422."""
        self.lot.status = LotStatus.COMPLETED
        await self.lot_repo.save(self.lot)
        cmd = AssignInternalPositionCommand(
            orders=[AssignInternalPositionOrderInput(machine_id=1, quantity=1.0)]
        )
        with pytest.raises(LotPositionNotFoundError):
            await self.use_case.execute(self.actor, lot_id=1, position_id=99, cmd=cmd)

    async def test_a_position_with_nothing_left_is_refused_by_the_intent_rule(self):
        """The assign internal rule refuses a fully covered position before
        the requested quantity is checked; its own message names it."""
        full = AssignInternalPositionCommand(
            orders=[AssignInternalPositionOrderInput(machine_id=1, quantity=10.0)]
        )
        await self.use_case.execute(self.actor, lot_id=1, position_id=1, cmd=full)

        more = AssignInternalPositionCommand(
            orders=[AssignInternalPositionOrderInput(machine_id=2, quantity=1.0)]
        )
        with pytest.raises(ProductionOrderQuantityOverflowError, match="nothing left to assign"):
            await self.use_case.execute(self.actor, lot_id=1, position_id=1, cmd=more)
        assert len(await self.order_repo.get_by_lot_position_id(1)) == 1

    async def test_allows_assignment_on_on_hold_lot(self):
        # ON_HOLD is NOT terminal, so this guards against an over-broad fix.
        self.lot.status = LotStatus.ON_HOLD
        await self.lot_repo.save(self.lot)
        cmd = AssignInternalPositionCommand(
            orders=[AssignInternalPositionOrderInput(machine_id=1, quantity=10.0)]
        )
        result = await self.use_case.execute(self.actor, lot_id=1, position_id=1, cmd=cmd)
        assert result.kind == LotPositionKind.INTERNAL.value
        assert len(await self.order_repo.get_by_lot_position_id(1)) == 1

    async def test_locks_every_target_queue_scope_in_a_deterministic_order(self):
        """Each queue this assignment appends to is locked, sorted, so two
        concurrent multi-machine assignments can't deadlock by taking the
        same pair in opposite orders."""
        cmd = AssignInternalPositionCommand(
            orders=[
                AssignInternalPositionOrderInput(machine_id=2, quantity=4.0),
                AssignInternalPositionOrderInput(machine_id=1, quantity=6.0),
            ]
        )
        await self.use_case.execute(self.actor, lot_id=1, position_id=1, cmd=cmd)
        assert self.order_repo.queue_locks == [(1, None), (2, None)]

    async def test_locks_the_lot_before_reading_remaining(self):
        cmd = AssignInternalPositionCommand(
            orders=[AssignInternalPositionOrderInput(machine_id=1, quantity=10.0)]
        )
        await self.use_case.execute(self.actor, lot_id=1, position_id=1, cmd=cmd)
        assert self.lot_repo.for_update_calls == [1]

    async def test_commits_exactly_once(self):
        cmd = AssignInternalPositionCommand(
            orders=[AssignInternalPositionOrderInput(machine_id=1, quantity=10.0)]
        )
        await self.use_case.execute(self.actor, lot_id=1, position_id=1, cmd=cmd)
        assert self.uow.commits == 1

    async def test_commits_exactly_once_on_project_path(self):
        project = Project(
            id=1,
            created=datetime(2026, 1, 1),
            project_number="P1",
            production_time_budget=100,
        )
        project_repo = FakeProjectRepository([project])
        use_case = AssignInternalPosition(
            self.lot_repo,
            self.machine_repo,
            self.order_repo,
            self.settings_repo,
            project_repo=project_repo,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=production_order_reconciler(self.order_repo, self.lot_repo, FakeEventBus()),
        )
        cmd = AssignInternalPositionCommand(
            orders=[AssignInternalPositionOrderInput(machine_id=1, quantity=10.0)]
        )
        await use_case.execute(self.actor, lot_id=1, position_id=1, cmd=cmd)
        assert self.uow.commits == 1

    async def test_publishes_events_even_when_schedule_recompute_raises(self):
        class RaisingRecompute:
            async def execute_all(self, response_time_days=None, settings=None):
                raise RuntimeError("boom")

        use_case = AssignInternalPosition(
            self.lot_repo,
            self.machine_repo,
            self.order_repo,
            self.settings_repo,
            recompute_schedule=RaisingRecompute(),
            event_bus=self.bus,
            uow=self.uow,
            reconciler=production_order_reconciler(self.order_repo, self.lot_repo, FakeEventBus()),
        )
        cmd = AssignInternalPositionCommand(
            orders=[
                AssignInternalPositionOrderInput(machine_id=1, quantity=6.0),
                AssignInternalPositionOrderInput(machine_id=2, quantity=4.0),
            ]
        )
        result = await use_case.execute(self.actor, lot_id=1, position_id=1, cmd=cmd)
        assert result.kind == LotPositionKind.INTERNAL.value
        created = [e for e in self.bus.published if isinstance(e, ProductionOrderCreated)]
        assert len(created) == 2
