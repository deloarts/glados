"""
Verifies that a production order use case's domain events still reach the transactional
outbox even when its post-commit recompute work (the scheduler's execute_all) raises. Unit
tests for TestPublishSurvivesFailingPostCommitWork. No database, no HTTP. All dependencies
replaced with in-memory fakes.
"""

from datetime import date
from datetime import datetime

import pytest

from src.modules.fulfillment.application.dto.production_order_dto import (
    AssignInternalPositionCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    AssignInternalPositionOrderInput,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    CancelProductionOrderCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import PauseProductionOrderCommand
from src.modules.fulfillment.application.dto.production_order_dto import (
    ReassignProductionOrderMachineCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    RecordProductionOrderCompletionCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import SplitProductionOrderCommand
from src.modules.fulfillment.application.dto.production_order_dto import StartProductionOrderCommand
from src.modules.fulfillment.application.use_cases.production_order.assign_internal_position import (
    AssignInternalPosition,
)
from src.modules.fulfillment.application.use_cases.production_order.production_order_lifecycle import (
    CancelProductionOrder,
)
from src.modules.fulfillment.application.use_cases.production_order.production_order_lifecycle import (
    PauseProductionOrder,
)
from src.modules.fulfillment.application.use_cases.production_order.production_order_lifecycle import (
    StartProductionOrder,
)
from src.modules.fulfillment.application.use_cases.production_order.reassign_production_order_machine import (
    ReassignProductionOrderMachine,
)
from src.modules.fulfillment.application.use_cases.production_order.record_production_order_completion import (
    RecordProductionOrderCompletion,
)
from src.modules.fulfillment.application.use_cases.production_order.split_production_order import (
    SplitProductionOrder,
)
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderCanceled
from src.modules.fulfillment.domain.events.production_order_events import (
    ProductionOrderCompletionRecorded,
)
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderCreated
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderStarted
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.domain.entities.project import Project
from tests.factories import make_user
from tests.unit.production_lot._helpers import NoLotCreation
from tests.unit.production_lot.fakes import FakeMadeItemAllocationRepository
from tests.unit.production_lot.fakes import FakeMadeItemDemandRepository
from tests.unit.production_lot.fakes import FakeProjectRepository
from tests.unit.production_lot.fakes import completion_collaborators
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
from tests.unit.production_order.fakes import FakeProductionOrderFileRepository
from tests.unit.production_order.fakes import FakeProductionOrderRepository
from tests.unit.production_order.fakes import FakeUnitOfWork
from tests.unit.production_order.fakes import lifecycle_collaborators
from tests.unit.production_order.fakes import production_order_reconciler


class FailingRecomputeSchedule:
    """A schedule recompute that always blows up.

    Post-commit work must not swallow the domain events of an
    already-committed operation. These fakes pin the order: publish
    first, then the fallible recompute behind a try/except.
    """

    def __init__(self) -> None:
        self.attempts: int = 0

    async def execute_all(self, response_time_days=None, settings=None):
        self.attempts += 1
        raise RuntimeError("scheduling service is down")


class TestPublishSurvivesFailingPostCommitWork:
    def setup_method(self):
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.recompute = FailingRecomputeSchedule()
        self.actor = make_user(permissions=[Permission.WRITE_PRODUCTION_ORDERS])

    async def test_assign_internal_publishes_even_when_the_recompute_fails(self):
        step = make_step(position_id=1, fabrication_method_id=1)
        position = make_position(id=1, quantity=10.0, steps=[step])
        lot_repo = FakeProductionLotRepository([make_lot(positions=[position])])
        order_repo = FakeProductionOrderRepository()
        use_case = AssignInternalPosition(
            lot_repo,
            FakeProductionMachineRepository([make_machine(id=1, fabrication_method_ids=[1])]),
            order_repo,
            FakeAdminSettingsRepository(),
            self.recompute,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=production_order_reconciler(order_repo, lot_repo, FakeEventBus()),
        )

        await use_case.execute(
            self.actor,
            lot_id=1,
            position_id=1,
            cmd=AssignInternalPositionCommand(
                orders=[AssignInternalPositionOrderInput(machine_id=1, quantity=10.0)]
            ),
        )

        assert self.recompute.attempts  # the failing work really ran
        assert self.uow.committed is True
        assert any(isinstance(e, ProductionOrderCreated) for e in self.bus.published)

    async def test_reassign_publishes_even_when_the_recompute_fails(self):
        step = make_step(position_id=1, fabrication_method_id=1)
        position = make_position(id=1, quantity=10.0, kind=LotPositionKind.INTERNAL, steps=[step])
        lot_repo = FakeProductionLotRepository([make_lot(positions=[position])])
        order_repo = FakeProductionOrderRepository(
            [make_order(id=1, machine_id=1, lot_position_id=1, queue_sequence=1)]
        )
        use_case = ReassignProductionOrderMachine(
            order_repo,
            lot_repo,
            FakeProductionMachineRepository(
                [
                    make_machine(id=1, fabrication_method_ids=[1]),
                    make_machine(id=2, fabrication_method_ids=[1]),
                ]
            ),
            event_bus=self.bus,
            uow=self.uow,
            recompute_schedule=self.recompute,
            lock_plan=FakeLockPlan(),
        )

        result = await use_case.execute(
            self.actor,
            production_order_id=1,
            cmd=ReassignProductionOrderMachineCommand(machine_id=2),
        )

        # A plain queue move produces no lot-level bus event (only a lot
        # status change the lifecycle reconciler writes does),
        # so what this pins for this site is the other half of that ordering:
        # a recompute failure must not escape past an already-committed
        # reassignment and fail the request after the write has landed.
        # Exactly one execute_all() attempt covers both the old and new scope.
        assert result.machine_id == 2
        assert self.recompute.attempts == 1
        assert self.uow.committed is True

    async def test_split_publishes_even_when_the_recompute_fails(self):
        order_repo = FakeProductionOrderRepository([make_order(id=1, quantity=10.0)])
        lot_repo = FakeProductionLotRepository(
            [make_lot(positions=[make_position(id=1, quantity=10.0)])]
        )
        use_case = SplitProductionOrder(
            order_repo,
            lot_repo,
            FakeAdminSettingsRepository(),
            self.recompute,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=production_order_reconciler(order_repo, lot_repo, self.bus),
        )

        cmd = SplitProductionOrderCommand(quantities=[6.0, 4.0])
        results = await use_case.execute(self.actor, production_order_id=1, cmd=cmd)

        assert len(results) == 2
        assert self.recompute.attempts
        assert self.uow.committed is True
        created = [e for e in self.bus.published if isinstance(e, ProductionOrderCreated)]
        assert len(created) == 1  # one new part (the keeper is the source order)

    async def test_completion_publishes_even_when_the_recompute_fails(self):
        position = make_position(id=1, quantity=10.0, kind=LotPositionKind.INTERNAL)
        lot = make_lot(positions=[position])
        lot.source_made_item_id = 99  # rework lot, exempt from raw-material gating
        lot_repo = FakeProductionLotRepository([lot])
        order_repo = FakeProductionOrderRepository(
            [
                make_order(
                    id=1,
                    lot_position_id=1,
                    quantity=10.0,
                    status=ProductionOrderStatus.IN_PROGRESS,
                )
            ]
        )
        use_case = RecordProductionOrderCompletion(
            order_repo,
            lot_repo,
            FakeProductionOrderFileRepository(),
            event_bus=self.bus,
            uow=self.uow,
            recompute_schedule=self.recompute,
            reconciler=production_order_reconciler(order_repo, lot_repo, self.bus),
            made_item_demand_repo=FakeMadeItemDemandRepository(),
            made_item_allocation_repo=FakeMadeItemAllocationRepository(),
            create_lot=NoLotCreation(),
            **completion_collaborators(order_repo),
        )

        await use_case.execute(
            self.actor,
            production_order_id=1,
            cmd=RecordProductionOrderCompletionCommand(
                quantity=3.0, completion_date=date(2026, 1, 2)
            ),
        )

        assert self.recompute.attempts
        assert self.uow.committed is True
        assert any(isinstance(e, ProductionOrderCompletionRecorded) for e in self.bus.published)

    @pytest.mark.parametrize(
        ("use_case_cls", "kwargs", "event_type"),
        [
            (StartProductionOrder, {"cmd": StartProductionOrderCommand()}, ProductionOrderStarted),
            (PauseProductionOrder, {"cmd": PauseProductionOrderCommand()}, None),
            (
                CancelProductionOrder,
                {"cmd": CancelProductionOrderCommand()},
                ProductionOrderCanceled,
            ),
        ],
        ids=["start", "pause", "cancel"],
    )
    async def test_start_pause_cancel_publish_even_when_time_budget_recompute_fails(
        self, monkeypatch, use_case_cls, kwargs, event_type
    ):
        """The trailing work here is recompute_project_time_budgets, which
        the use case only runs when the position's kind crossed the
        time-budget eligibility boundary. That boundary is reachable only on
        cancel, so the gate is forced open for all three: the assertion is
        about the ordering of commit / publish / recompute, not about when
        the recompute is warranted."""
        import src.modules.fulfillment.application.use_cases.production_order.production_order_lifecycle as module

        original = module._ProductionOrderLifecycleBase._after_run

        async def always_ask_for_a_project_recompute(self, *args, **kw):
            await original(self, *args, **kw)
            return 1

        async def boom(*args, **kw):
            raise RuntimeError("project time-budget recompute is down")

        monkeypatch.setattr(
            module._ProductionOrderLifecycleBase,
            "_after_run",
            always_ask_for_a_project_recompute,
        )
        monkeypatch.setattr(module, "recompute_project_time_budgets", boom)

        position = make_position(id=1, quantity=10.0, kind=LotPositionKind.INTERNAL)
        lot = make_lot(positions=[position])
        lot.source_made_item_id = 99  # rework lot, exempt from raw-material gating
        lot_repo = FakeProductionLotRepository([lot])
        status = (
            ProductionOrderStatus.IN_PROGRESS
            if use_case_cls is PauseProductionOrder
            else ProductionOrderStatus.QUEUED
        )
        order_repo = FakeProductionOrderRepository(
            [make_order(id=1, lot_position_id=1, status=status)]
        )
        project = Project(
            id=1, created=datetime(2026, 1, 1), project_number="P1", production_time_budget=100
        )
        use_case = use_case_cls(
            order_repo,
            lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            project_repo=FakeProjectRepository([project]),
            **lifecycle_collaborators(order_repo, lot_repo, self.bus),
        )

        await use_case.execute(self.actor, production_order_id=1, **kwargs)

        assert self.uow.committed is True
        if event_type is not None:
            assert any(isinstance(e, event_type) for e in self.bus.published)
