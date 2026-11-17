"""
Unit tests for the machine-pool variants of the queue use cases:
TestReassignProductionOrderMachineWithPool,
TestReorderProductionOrdersWithPool, TestAssignInternalPositionWithPool
and TestStartProductionOrderPoolResolution. No database, no HTTP. All
dependencies replaced with in-memory fakes.
"""

import pytest

from src.modules.catalogue.domain.errors import MachineCapabilityMismatchError
from src.modules.fulfillment.application.dto.production_order_dto import (
    AssignInternalPositionCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    AssignInternalPositionOrderInput,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    ReassignProductionOrderMachineCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    ReorderProductionOrdersCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import StartProductionOrderCommand
from src.modules.fulfillment.application.use_cases.production_order.assign_internal_position import (
    AssignInternalPosition,
)
from src.modules.fulfillment.application.use_cases.production_order.production_order_lifecycle import (
    StartProductionOrder,
)
from src.modules.fulfillment.application.use_cases.production_order.reassign_production_order_machine import (
    ReassignProductionOrderMachine,
)
from src.modules.fulfillment.application.use_cases.production_order.reorder_production_orders import (
    ReorderProductionOrders,
)
from src.modules.fulfillment.domain.errors import MachinePoolNotFoundError
from src.modules.fulfillment.domain.errors import ProductionOrderInvalidStatusTransitionError
from src.modules.fulfillment.domain.errors import ProductionOrderNoMachineAssignedError
from src.modules.fulfillment.domain.errors import ProductionOrderNotFoundError
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.production_order._helpers import make_lot
from tests.unit.production_order._helpers import make_machine
from tests.unit.production_order._helpers import make_order
from tests.unit.production_order._helpers import make_pool
from tests.unit.production_order._helpers import make_position
from tests.unit.production_order._helpers import make_step
from tests.unit.production_order.fakes import FakeAdminSettingsRepository
from tests.unit.production_order.fakes import FakeEventBus
from tests.unit.production_order.fakes import FakeLockPlan
from tests.unit.production_order.fakes import FakeMachinePoolRepository
from tests.unit.production_order.fakes import FakeProductionLotRepository
from tests.unit.production_order.fakes import FakeProductionMachineRepository
from tests.unit.production_order.fakes import FakeProductionOrderRepository
from tests.unit.production_order.fakes import FakeRecomputeSchedule
from tests.unit.production_order.fakes import FakeUnitOfWork
from tests.unit.production_order.fakes import lifecycle_collaborators
from tests.unit.production_order.fakes import production_order_reconciler


class TestReassignProductionOrderMachineWithPool:
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
            ]
        )
        self.pool_repo = FakeMachinePoolRepository(
            [
                make_pool(
                    id=10,
                    machine_ids=[1, 2],
                    machines=[make_machine(id=1, fabrication_method_ids=[1])],
                ),
                make_pool(
                    id=11,
                    machine_ids=[1],
                    machines=[make_machine(id=1, fabrication_method_ids=[99])],
                ),
            ]
        )
        self.order_repo = FakeProductionOrderRepository(
            [make_order(id=1, machine_id=1, lot_position_id=1, queue_sequence=1)]
        )
        self.recompute = FakeRecomputeSchedule()
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.WRITE_PRODUCTION_ORDERS])
        self.use_case = ReassignProductionOrderMachine(
            self.order_repo,
            self.lot_repo,
            self.machine_repo,
            event_bus=self.bus,
            uow=self.uow,
            recompute_schedule=self.recompute,
            pool_repo=self.pool_repo,
            lock_plan=FakeLockPlan(),
        )

    async def test_reassigns_to_pool_clears_machine_and_sets_pool(self):
        cmd = ReassignProductionOrderMachineCommand(machine_pool_id=10)
        result = await self.use_case.execute(self.actor, production_order_id=1, cmd=cmd)
        assert result.machine_id is None
        assert (await self.order_repo.get_by_id(1)).machine_pool_id == 10

    async def test_rejects_unknown_pool(self):
        cmd = ReassignProductionOrderMachineCommand(machine_pool_id=99)
        with pytest.raises(MachinePoolNotFoundError):
            await self.use_case.execute(self.actor, production_order_id=1, cmd=cmd)

    async def test_rejects_pool_that_does_not_cover_the_step(self):
        cmd = ReassignProductionOrderMachineCommand(machine_pool_id=11)
        with pytest.raises(MachineCapabilityMismatchError):
            await self.use_case.execute(self.actor, production_order_id=1, cmd=cmd)

    async def test_reassign_to_machine_keeps_existing_pool_provenance(self):
        """Mirrors the Start dialog's resolution: resolving a
        pool-assigned order to a concrete machine keeps machine_pool_id as
        provenance rather than clearing it."""
        self.order_repo._orders[1].machine_id = None
        self.order_repo._orders[1].machine_pool_id = 10
        cmd = ReassignProductionOrderMachineCommand(machine_id=2)
        result = await self.use_case.execute(self.actor, production_order_id=1, cmd=cmd)
        assert result.machine_id == 2
        assert (await self.order_repo.get_by_id(1)).machine_pool_id == 10

    async def test_unassign_reverts_a_resolved_order_back_to_pool_assigned(self):
        """Neither machine_id nor machine_pool_id given (the "unassign"
        request) clears machine_id but deliberately leaves
        machine_pool_id untouched: an already-resolved order (both set)
        reverts to pool-assigned-unresolved rather than losing the pool
        link too."""
        self.order_repo._orders[1].machine_id = 2
        self.order_repo._orders[1].machine_pool_id = 10
        cmd = ReassignProductionOrderMachineCommand()
        result = await self.use_case.execute(self.actor, production_order_id=1, cmd=cmd)
        assert result.machine_id is None
        assert (await self.order_repo.get_by_id(1)).machine_pool_id == 10

    async def test_reassign_to_pool_assigns_queue_sequence_in_pool_scope(self):
        """The pool's own queue is a distinct sequence space, not
        shared with another pool's queue or the unassigned one."""
        self.order_repo._orders[2] = make_order(
            id=2, machine_id=None, machine_pool_id=10, lot_position_id=1, queue_sequence=1
        )
        self.order_repo._orders[3] = make_order(
            id=3, machine_id=None, machine_pool_id=10, lot_position_id=1, queue_sequence=2
        )
        self.order_repo._orders[4] = make_order(
            id=4, machine_id=None, machine_pool_id=None, lot_position_id=1, queue_sequence=1
        )
        cmd = ReassignProductionOrderMachineCommand(machine_pool_id=10)
        result = await self.use_case.execute(self.actor, production_order_id=1, cmd=cmd)
        assert result.queue_sequence == 3

    async def test_reassign_triggers_recompute_for_old_and_new_scope(self):
        cmd = ReassignProductionOrderMachineCommand(machine_pool_id=10)
        await self.use_case.execute(self.actor, production_order_id=1, cmd=cmd)
        # A single global execute_all() covers both the old machine's queue
        # and the new pool's queue in the same pass, since scheduling runs
        # as one unified plan; there is no per-scope call to inspect.
        assert self.recompute.execute_all_calls == 1


class TestReorderProductionOrdersWithPool:
    def setup_method(self):
        self.order_repo = FakeProductionOrderRepository(
            [
                make_order(id=1, machine_id=None, machine_pool_id=10, queue_sequence=1),
                make_order(id=2, machine_id=None, machine_pool_id=10, queue_sequence=2),
                make_order(id=3, machine_id=None, machine_pool_id=None, queue_sequence=1),
            ]
        )
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.WRITE_PRODUCTION_ORDERS])
        self.use_case = ReorderProductionOrders(
            self.order_repo, event_bus=self.bus, uow=self.uow, lock_plan=FakeLockPlan()
        )

    async def test_reorders_within_pool_scope_only(self):
        cmd = ReorderProductionOrdersCommand(ordered_production_order_ids=[2, 1])
        await self.use_case.execute(self.actor, machine_id=None, cmd=cmd, machine_pool_id=10)
        assert (await self.order_repo.get_by_id(2)).queue_sequence == 1
        assert (await self.order_repo.get_by_id(1)).queue_sequence == 2
        # The no-machine-no-pool order is a different scope,
        # untouched by the pool-scoped reorder.
        assert (await self.order_repo.get_by_id(3)).queue_sequence == 1

    async def test_reorder_pool_rejects_an_order_outside_the_pool(self):
        cmd = ReorderProductionOrdersCommand(ordered_production_order_ids=[3])
        with pytest.raises(ProductionOrderNotFoundError):
            await self.use_case.execute(self.actor, machine_id=None, cmd=cmd, machine_pool_id=10)


class TestAssignInternalPositionWithPool:
    def setup_method(self):
        self.step = make_step(position_id=1, fabrication_method_id=1)
        self.position = make_position(id=1, quantity=10.0, steps=[self.step])
        self.lot = make_lot(positions=[self.position])
        self.lot_repo = FakeProductionLotRepository([self.lot])
        self.machine_repo = FakeProductionMachineRepository(
            [make_machine(id=1, fabrication_method_ids=[1])]
        )
        self.pool_repo = FakeMachinePoolRepository(
            [make_pool(id=1, machines=[make_machine(id=1, fabrication_method_ids=[1])])]
        )
        self.order_repo = FakeProductionOrderRepository()
        self.settings_repo = FakeAdminSettingsRepository()
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.WRITE_PRODUCTION_ORDERS])
        self.use_case = AssignInternalPosition(
            self.lot_repo,
            self.machine_repo,
            self.order_repo,
            self.settings_repo,
            pool_repo=self.pool_repo,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=production_order_reconciler(self.order_repo, self.lot_repo, FakeEventBus()),
        )

    async def test_assigns_to_pool_leaving_machine_id_unresolved(self):
        cmd = AssignInternalPositionCommand(
            orders=[AssignInternalPositionOrderInput(machine_pool_id=1, quantity=10.0)]
        )
        await self.use_case.execute(self.actor, lot_id=1, position_id=1, cmd=cmd)
        order = (await self.order_repo.get_by_lot_position_id(1))[0]
        assert order.machine_pool_id == 1
        assert order.machine_id is None

    async def test_rejects_unknown_pool(self):
        cmd = AssignInternalPositionCommand(
            orders=[AssignInternalPositionOrderInput(machine_pool_id=99, quantity=10.0)]
        )
        with pytest.raises(MachinePoolNotFoundError):
            await self.use_case.execute(self.actor, lot_id=1, position_id=1, cmd=cmd)

    async def test_rejects_pool_that_does_not_cover_the_step(self):
        self.pool_repo._pools[1] = make_pool(
            id=1, machines=[make_machine(id=1, fabrication_method_ids=[2])]
        )
        cmd = AssignInternalPositionCommand(
            orders=[AssignInternalPositionOrderInput(machine_pool_id=1, quantity=10.0)]
        )
        with pytest.raises(MachineCapabilityMismatchError):
            await self.use_case.execute(self.actor, lot_id=1, position_id=1, cmd=cmd)


class TestStartProductionOrderPoolResolution:
    def setup_method(self):
        self.position = make_position(id=1, quantity=10.0, kind=LotPositionKind.INTERNAL)
        self.lot = make_lot(positions=[self.position])
        self.lot.source_made_item_id = 99  # exempt from raw-material gating
        self.lot_repo = FakeProductionLotRepository([self.lot])
        self.order_repo = FakeProductionOrderRepository(
            [make_order(id=1, lot_position_id=1, machine_id=None)]
        )
        self.order_repo._orders[1].machine_pool_id = 1
        self.machine_repo = FakeProductionMachineRepository(
            [make_machine(id=1, fabrication_method_ids=[1]), make_machine(id=2)]
        )
        self.pool_repo = FakeMachinePoolRepository(
            [make_pool(id=1, machine_ids=[1], machines=[make_machine(id=1)])]
        )
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.WRITE_PRODUCTION_ORDERS])
        self.use_case = StartProductionOrder(
            self.order_repo,
            self.lot_repo,
            machine_repo=self.machine_repo,
            pool_repo=self.pool_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus),
        )

    async def test_resolves_machine_from_pool_and_starts(self):
        result = await self.use_case.execute(
            self.actor,
            production_order_id=1,
            cmd=StartProductionOrderCommand(machine_id=1),
        )
        assert result.status == ProductionOrderStatus.IN_PROGRESS.value
        assert (await self.order_repo.get_by_id(1)).machine_id == 1
        assert (await self.order_repo.get_by_id(1)).machine_pool_id == 1  # still remembers origin

    async def test_rejects_when_no_machine_id_given(self):
        with pytest.raises(ProductionOrderNoMachineAssignedError):
            await self.use_case.execute(
                self.actor, production_order_id=1, cmd=StartProductionOrderCommand()
            )

    async def test_rejects_machine_not_a_member_of_the_pool(self):
        with pytest.raises(MachineCapabilityMismatchError):
            await self.use_case.execute(
                self.actor,
                production_order_id=1,
                cmd=StartProductionOrderCommand(machine_id=2),
            )

    async def test_rejects_machine_id_when_already_resolved(self):
        self.order_repo._orders[1].machine_id = 1
        with pytest.raises(ProductionOrderInvalidStatusTransitionError):
            await self.use_case.execute(
                self.actor,
                production_order_id=1,
                cmd=StartProductionOrderCommand(machine_id=1),
            )

    async def test_resolving_onto_a_machine_with_an_existing_order_draws_a_fresh_queue_sequence(
        self,
    ):
        """Order #1 keeps the queue_sequence (1, make_order's
        default) it held in its pool scope. If the target machine already
        has a live order at that same number, resolving onto it without
        re-sequencing would hand two orders on the same machine identical
        queue_sequence values (uq_production_order_queue_sequence_machine).
        Resolving must draw a fresh number from the machine's own queue,
        exactly like ReassignProductionOrderMachine does."""
        await self.order_repo.save(
            make_order(
                id=2, machine_id=1, machine_pool_id=None, lot_position_id=1, queue_sequence=1
            )
        )
        result = await self.use_case.execute(
            self.actor,
            production_order_id=1,
            cmd=StartProductionOrderCommand(machine_id=1),
        )
        assert result.status == ProductionOrderStatus.IN_PROGRESS.value
        assert result.machine_id == 1
        assert result.queue_sequence == 2
        assert (await self.order_repo.get_by_id(1)).queue_sequence == 2
        # The pre-existing order on the machine keeps its own number.
        assert (await self.order_repo.get_by_id(2)).queue_sequence == 1
        # The machine's queue was locked before drawing the new number.
        assert (1, 1) in self.order_repo.queue_locks
