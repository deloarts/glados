"""
Unit tests for TestProductionOrderLifecycle and
TestStartProductionOrderUpstreamGating. No database, no HTTP. All
dependencies replaced with in-memory fakes.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

import pytest

from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.application.dto.production_order_dto import (
    CancelProductionOrderCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import PauseProductionOrderCommand
from src.modules.fulfillment.application.dto.production_order_dto import StartProductionOrderCommand
from src.modules.fulfillment.application.use_cases.production_order.production_order_lifecycle import (
    CancelProductionOrder,
)
from src.modules.fulfillment.application.use_cases.production_order.production_order_lifecycle import (
    PauseProductionOrder,
)
from src.modules.fulfillment.application.use_cases.production_order.production_order_lifecycle import (
    StartProductionOrder,
)
from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)
from src.modules.fulfillment.domain.errors import LotPositionOverflowError
from src.modules.fulfillment.domain.errors import OperatorNotAssignedError
from src.modules.fulfillment.domain.errors import OperatorSelectionRequiredError
from src.modules.fulfillment.domain.errors import ProductionOrderInvalidStatusTransitionError
from src.modules.fulfillment.domain.errors import ProductionOrderNoMachineAssignedError
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.domain.entities.project import Project
from tests.factories import make_user
from tests.unit.production_lot.fakes import FakeProjectRepository
from tests.unit.production_order._helpers import give_status_facts
from tests.unit.production_order._helpers import make_lot
from tests.unit.production_order._helpers import make_order
from tests.unit.production_order._helpers import make_position
from tests.unit.production_order._helpers import make_step
from tests.unit.production_order.fakes import FakeEventBus
from tests.unit.production_order.fakes import FakeProductionLotRepository
from tests.unit.production_order.fakes import FakeProductionOrderRepository
from tests.unit.production_order.fakes import FakeUnitOfWork
from tests.unit.production_order.fakes import lifecycle_collaborators


class TestProductionOrderLifecycle:
    def setup_method(self):
        self.position = make_position(id=1, quantity=10.0, kind=LotPositionKind.INTERNAL)
        self.lot = make_lot(positions=[self.position])
        # Rework lot, exempt from sequence-1 raw-material gating (unrelated
        # to what these tests exercise: machine assignment/hold/operator).
        self.lot.source_made_item_id = 99
        self.lot_repo = FakeProductionLotRepository([self.lot])
        self.order_repo = FakeProductionOrderRepository([make_order(id=1, lot_position_id=1)])
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.WRITE_PRODUCTION_ORDERS])

    async def test_start_transitions_and_cascades_position_status(self):
        use_case = StartProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus),
        )
        result = await use_case.execute(
            self.actor, production_order_id=1, cmd=StartProductionOrderCommand()
        )
        assert result.status == ProductionOrderStatus.IN_PROGRESS.value
        assert result.actual_start is not None
        assert (
            await self.lot_repo.get_position_by_id(1)
        ).status == LotPositionStatus.IN_PROGRESS.value
        assert (await self.lot_repo.get_by_id(1)).status == LotStatus.IN_PROGRESS.value

    async def test_start_rejects_when_no_machine_assigned(self):
        self.order_repo._orders[1].machine_id = None
        use_case = StartProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus),
        )
        with pytest.raises(ProductionOrderNoMachineAssignedError):
            await use_case.execute(
                self.actor, production_order_id=1, cmd=StartProductionOrderCommand()
            )

    async def test_start_allows_machineless_order_on_pure_manual_position(self):
        # A position whose every step is pure manual labor never gets a
        # machine, starting its order without one must succeed.
        self.position.steps = [make_step(id=1, fabrication_method_requires_machine=False)]
        await self.lot_repo.save(self.lot)
        self.order_repo._orders[1].machine_id = None
        use_case = StartProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus),
        )
        result = await use_case.execute(
            self.actor, production_order_id=1, cmd=StartProductionOrderCommand()
        )
        assert result.status == ProductionOrderStatus.IN_PROGRESS.value
        assert result.machine_id is None

    async def _make_inspection_position(self):
        """Turns this class's position into an inspection one, machine-less,
        so the no-machine guard can't mask the permission guard."""
        self.position.steps = [
            make_step(
                id=1,
                position_id=1,
                fabrication_method_id=None,
                role=StepRole.INSPECTION,
                inspection_method_id=1,
                inspection_method_name="Visual Inspection",
                inspection_method_requires_evidence=False,
                fabrication_method_requires_machine=False,
            )
        ]
        await self.lot_repo.save(self.lot)
        self.order_repo._orders[1].machine_id = None

    async def test_start_on_inspection_position_requires_write_inspections(self):
        """Running a QA station is inspection work, not just machine work;
        write:production_orders alone must not open it."""
        await self._make_inspection_position()
        use_case = StartProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus),
        )
        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(
                self.actor, production_order_id=1, cmd=StartProductionOrderCommand()
            )

    async def test_start_on_inspection_position_succeeds_with_write_inspections(self):
        await self._make_inspection_position()
        actor = make_user(
            permissions=[Permission.WRITE_PRODUCTION_ORDERS, Permission.WRITE_INSPECTIONS]
        )
        use_case = StartProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus),
        )
        result = await use_case.execute(
            actor, production_order_id=1, cmd=StartProductionOrderCommand()
        )
        assert result.status == ProductionOrderStatus.IN_PROGRESS.value

    async def test_resuming_a_paused_inspection_also_requires_write_inspections(self):
        """Resume goes through StartProductionOrder (PAUSED -> IN_PROGRESS),
        so the gate has to hold there too, not only on the first start."""
        await self._make_inspection_position()
        self.order_repo._orders[1].status = ProductionOrderStatus.PAUSED
        give_status_facts(self.order_repo._orders[1])
        use_case = StartProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus),
        )
        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(
                self.actor, production_order_id=1, cmd=StartProductionOrderCommand()
            )

    async def test_start_on_a_fabrication_position_is_unaffected(self):
        """The new gate must not leak onto ordinary machine work."""
        use_case = StartProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus),
        )
        result = await use_case.execute(
            self.actor, production_order_id=1, cmd=StartProductionOrderCommand()
        )
        assert result.status == ProductionOrderStatus.IN_PROGRESS.value

    async def test_start_still_rejects_machineless_order_with_machine_step(self):
        self.position.steps = [
            make_step(id=1, fabrication_method_requires_machine=False),
            make_step(id=2, fabrication_method_id=2, fabrication_method_requires_machine=True),
        ]
        await self.lot_repo.save(self.lot)
        self.order_repo._orders[1].machine_id = None
        use_case = StartProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus),
        )
        with pytest.raises(ProductionOrderNoMachineAssignedError):
            await use_case.execute(
                self.actor, production_order_id=1, cmd=StartProductionOrderCommand()
            )

    async def test_start_rejects_when_lot_is_on_hold(self):
        self.lot.status = LotStatus.ON_HOLD
        await self.lot_repo.save(self.lot)
        use_case = StartProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus),
        )
        with pytest.raises(ProductionOrderInvalidStatusTransitionError):
            await use_case.execute(
                self.actor, production_order_id=1, cmd=StartProductionOrderCommand()
            )

    async def test_start_rejects_order_on_canceled_lot(self):
        self.lot.status = LotStatus.CANCELED
        await self.lot_repo.save(self.lot)
        use_case = StartProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus),
        )
        with pytest.raises(ProductionOrderInvalidStatusTransitionError):
            await use_case.execute(
                self.actor, production_order_id=1, cmd=StartProductionOrderCommand()
            )
        assert (await self.order_repo.get_by_id(1)).status == ProductionOrderStatus.QUEUED.value

    async def test_start_rejects_order_on_completed_lot(self):
        self.lot.status = LotStatus.COMPLETED
        await self.lot_repo.save(self.lot)
        use_case = StartProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus),
        )
        with pytest.raises(ProductionOrderInvalidStatusTransitionError):
            await use_case.execute(
                self.actor, production_order_id=1, cmd=StartProductionOrderCommand()
            )
        assert (await self.order_repo.get_by_id(1)).status == ProductionOrderStatus.QUEUED.value

    async def test_start_requires_operator_for_shared_account(self):
        use_case = StartProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus),
        )
        shared_actor = make_user(
            id=2, permissions=[Permission.WRITE_PRODUCTION_ORDERS], is_shared_account=True
        )
        with pytest.raises(OperatorSelectionRequiredError):
            await use_case.execute(
                shared_actor, production_order_id=1, cmd=StartProductionOrderCommand()
            )

    async def test_start_with_operator_for_shared_account_succeeds(self):
        use_case = StartProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus),
        )
        shared_actor = make_user(
            id=2,
            permissions=[Permission.WRITE_PRODUCTION_ORDERS],
            is_shared_account=True,
            member_ids=[5],
        )
        result = await use_case.execute(
            shared_actor, production_order_id=1, cmd=StartProductionOrderCommand(operator_id=5)
        )
        assert result.status == ProductionOrderStatus.IN_PROGRESS.value

    async def test_start_rejects_operator_not_a_member_of_shared_account(self):
        use_case = StartProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus),
        )
        shared_actor = make_user(
            id=2,
            permissions=[Permission.WRITE_PRODUCTION_ORDERS],
            is_shared_account=True,
            member_ids=[5],
        )
        with pytest.raises(OperatorNotAssignedError):
            await use_case.execute(
                shared_actor, production_order_id=1, cmd=StartProductionOrderCommand(operator_id=99)
            )

    async def test_start_sets_started_operator_id(self):
        """The resolved operator lands on started_operator_id too, not just
        the changelog text; see the module docstring."""
        use_case = StartProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus),
        )
        result = await use_case.execute(
            self.actor, production_order_id=1, cmd=StartProductionOrderCommand()
        )
        assert result.started_operator_id == self.actor.id

    async def test_pause_transitions(self):
        self.order_repo._orders[1].status = ProductionOrderStatus.IN_PROGRESS
        give_status_facts(self.order_repo._orders[1])
        use_case = PauseProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus),
        )
        result = await use_case.execute(
            self.actor, production_order_id=1, cmd=PauseProductionOrderCommand(reason="urgent job")
        )
        assert result.status == ProductionOrderStatus.PAUSED.value

    async def test_pause_keeps_started_operator_id(self):
        """A pause is not a new run; started_operator_id must survive it
        untouched (only start/resume ever write it)."""
        start_use_case = StartProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus),
        )
        await start_use_case.execute(
            self.actor, production_order_id=1, cmd=StartProductionOrderCommand()
        )

        pause_use_case = PauseProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus),
        )
        result = await pause_use_case.execute(
            self.actor, production_order_id=1, cmd=PauseProductionOrderCommand()
        )
        assert result.started_operator_id == self.actor.id

    async def test_a_pause_records_the_operator_a_shared_account_names(self):
        collaborators = lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus)
        start = StartProductionOrder(
            self.order_repo, self.lot_repo, event_bus=self.bus, uow=self.uow, **collaborators
        )
        await start.execute(self.actor, production_order_id=1, cmd=StartProductionOrderCommand())
        terminal = make_user(
            id=50,
            permissions=[Permission.WRITE_PRODUCTION_ORDERS],
            is_shared_account=True,
            member_ids=[9],
        )

        await PauseProductionOrder(
            self.order_repo, self.lot_repo, event_bus=self.bus, uow=self.uow, **collaborators
        ).execute(terminal, production_order_id=1, cmd=PauseProductionOrderCommand(operator_id=9))

        [pause] = (await self.order_repo.get_by_id(1)).interruptions
        assert (pause.paused_by_id, pause.paused_operator_id) == (50, 9)

    async def test_resuming_with_a_different_operator_overwrites_started_operator_id(self):
        """Resume goes through StartProductionOrder again (PAUSED ->
        IN_PROGRESS): started_operator_id must overwrite, not accumulate,
        so it always reads "who started the current/last run"."""
        start_use_case = StartProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus),
        )
        first = await start_use_case.execute(
            self.actor, production_order_id=1, cmd=StartProductionOrderCommand()
        )
        assert first.started_operator_id == self.actor.id

        pause_use_case = PauseProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus),
        )
        await pause_use_case.execute(
            self.actor, production_order_id=1, cmd=PauseProductionOrderCommand()
        )

        # A personal account is its own operator, so another one resumes it.
        other = make_user(id=42, permissions=[Permission.WRITE_PRODUCTION_ORDERS])
        resumed = await start_use_case.execute(
            other, production_order_id=1, cmd=StartProductionOrderCommand()
        )
        assert resumed.started_operator_id == 42

    async def test_cancel_transitions(self):
        use_case = CancelProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus),
        )
        result = await use_case.execute(
            self.actor, production_order_id=1, cmd=CancelProductionOrderCommand()
        )
        assert result.status == ProductionOrderStatus.CANCELED.value

    async def test_cancel_last_order_reverts_position_to_unassigned(self):
        use_case = CancelProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus),
        )
        await use_case.execute(
            self.actor, production_order_id=1, cmd=CancelProductionOrderCommand()
        )

        position = await self.lot_repo.get_position_by_id(1)
        assert position.kind == LotPositionKind.UNASSIGNED.value
        assert position.status == LotPositionStatus.PENDING.value

    async def test_cancel_last_order_recomputes_project_time_budget_across_lots(self):
        """Canceling the sole order on an INTERNAL position drops it out of
        {INTERNAL, MIXED}, the exact eligibility boundary for the
        project's shared time-budget pool (time_budget_service.py). A
        sibling lot in the SAME project, never directly touched by this
        cancel, must still get its apportioned share recalculated."""
        step_a = make_step(id=10, position_id=1, estimated_minutes_per_piece=None)
        position_a = make_position(
            id=1, quantity=5.0, kind=LotPositionKind.INTERNAL, steps=[step_a]
        )
        lot_a = make_lot(id=1, quantity=5.0, positions=[position_a])

        step_b = make_step(id=20, position_id=2, estimated_minutes_per_piece=None)
        position_b = make_position(
            id=2, quantity=5.0, kind=LotPositionKind.INTERNAL, steps=[step_b]
        )
        lot_b = make_lot(id=2, quantity=5.0, positions=[position_b])

        lot_repo = FakeProductionLotRepository([lot_a, lot_b])
        order_repo = FakeProductionOrderRepository([make_order(id=1, lot_position_id=1)])
        project = Project(
            id=1,
            created=datetime(2026, 1, 1),
            project_number="P1",
            production_time_budget=100,
        )
        project_repo = FakeProjectRepository([project])

        use_case = CancelProductionOrder(
            order_repo,
            lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            project_repo=project_repo,
            **lifecycle_collaborators(order_repo, lot_repo, self.bus),
        )
        await use_case.execute(
            self.actor, production_order_id=1, cmd=CancelProductionOrderCommand()
        )

        # Position 1 reverted to UNASSIGNED (no live orders left) and drops
        # out of the pool entirely.
        assert (await lot_repo.get_position_by_id(1)).kind == LotPositionKind.UNASSIGNED.value
        assert (await lot_repo.get_step_by_id(10)).time_budget_per_piece is None
        # Lot B was never touched by this cancel, but it's now the ONLY
        # eligible step in the project, so it must get the whole 100-minute
        # pool (100 / 5 qty), not the stale/never-computed value.
        assert (await lot_repo.get_step_by_id(20)).time_budget_per_piece == 20.0

    async def test_cancel_one_of_split_orders_keeps_position_internal(self):
        self.order_repo._orders[2] = make_order(id=2, lot_position_id=1, queue_sequence=2)
        use_case = CancelProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus),
        )
        await use_case.execute(
            self.actor, production_order_id=1, cmd=CancelProductionOrderCommand()
        )

        position = await self.lot_repo.get_position_by_id(1)
        assert position.kind == LotPositionKind.INTERNAL.value

    async def test_cancel_last_order_keeps_position_internal_when_progress_was_made(self):
        # The order's completed count follows from its completion rows, so
        # the progress is a row of 4 accepted pieces.
        await self.order_repo.save_completion(
            ProductionOrderCompletion(
                id=0,
                production_order_id=1,
                quantity=4.0,
                quantity_accepted=4.0,
                quantity_rejected=0.0,
                completion_date=date(2026, 1, 2),
                note=None,
                operator_id=1,
                recorded_by_id=1,
                created=datetime(2026, 1, 2, tzinfo=UTC),
            )
        )
        self.order_repo._orders[1].quantity_completed = 4.0
        self.position.quantity_completed = 4.0
        await self.lot_repo.save_position(self.position)
        use_case = CancelProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus),
        )
        await use_case.execute(
            self.actor, production_order_id=1, cmd=CancelProductionOrderCommand()
        )

        position = await self.lot_repo.get_position_by_id(1)
        assert position.kind == LotPositionKind.INTERNAL.value

    async def test_cancel_rejects_already_terminal(self):
        self.order_repo._orders[1].status = ProductionOrderStatus.COMPLETED
        use_case = CancelProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus),
        )
        with pytest.raises(ProductionOrderInvalidStatusTransitionError):
            await use_case.execute(
                self.actor, production_order_id=1, cmd=CancelProductionOrderCommand()
            )

    async def test_cancel_rejects_another_users_order_without_manage(self):
        other_actor = make_user(id=99, permissions=[Permission.WRITE_PRODUCTION_ORDERS])
        use_case = CancelProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus),
        )
        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(
                other_actor, production_order_id=1, cmd=CancelProductionOrderCommand()
            )

    # test_cancel_transitions above only exercises QUEUED -> CANCELED
    # (the setup default status).
    # The cancel rule of the production order intent table also takes
    # IN_PROGRESS and PAUSED orders; neither was covered anywhere in this
    # file, and QUEUED -> PAUSED is invalid and was likewise untested.
    @pytest.mark.parametrize(
        "source_status",
        [ProductionOrderStatus.IN_PROGRESS, ProductionOrderStatus.PAUSED],
    )
    async def test_cancel_transitions_from_in_progress_or_paused(self, source_status):
        self.order_repo._orders[1].status = source_status
        use_case = CancelProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus),
        )
        result = await use_case.execute(
            self.actor, production_order_id=1, cmd=CancelProductionOrderCommand()
        )
        assert result.status == ProductionOrderStatus.CANCELED.value

    async def test_pause_rejects_a_queued_order(self):
        # self.order_repo's order defaults to QUEUED (setup_method); only
        # IN_PROGRESS -> PAUSED is legal.
        use_case = PauseProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus),
        )
        with pytest.raises(ProductionOrderInvalidStatusTransitionError):
            await use_case.execute(
                self.actor,
                production_order_id=1,
                cmd=PauseProductionOrderCommand(reason="too soon"),
            )


class TestStartProductionOrderUpstreamGating:
    def setup_method(self):
        self.predecessor = make_position(
            id=1, sequence=1, quantity=10.0, kind=LotPositionKind.INTERNAL
        )
        self.position = make_position(
            id=2, sequence=2, quantity=10.0, kind=LotPositionKind.INTERNAL
        )
        self.lot = make_lot(positions=[self.predecessor, self.position])
        self.lot_repo = FakeProductionLotRepository([self.lot])
        self.order_repo = FakeProductionOrderRepository([make_order(id=1, lot_position_id=2)])
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.WRITE_PRODUCTION_ORDERS])
        self.use_case = StartProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus),
        )

    async def test_rejects_start_when_predecessor_has_produced_nothing(self):
        with pytest.raises(LotPositionOverflowError):
            await self.use_case.execute(
                self.actor, production_order_id=1, cmd=StartProductionOrderCommand()
            )

    async def test_allows_start_once_predecessor_has_partial_progress(self):
        self.predecessor.quantity_completed = 2.0
        await self.lot_repo.save_position(self.predecessor)

        result = await self.use_case.execute(
            self.actor, production_order_id=1, cmd=StartProductionOrderCommand()
        )
        assert result.status == ProductionOrderStatus.IN_PROGRESS.value

    async def test_rejects_start_once_this_position_already_caught_up_to_predecessor(self):
        self.predecessor.quantity_completed = 2.0
        await self.lot_repo.save_position(self.predecessor)
        self.position.quantity_completed = 2.0
        await self.lot_repo.save_position(self.position)

        with pytest.raises(LotPositionOverflowError):
            await self.use_case.execute(
                self.actor, production_order_id=1, cmd=StartProductionOrderCommand()
            )

    async def test_first_position_blocked_when_source_material_not_yet_arrived(self):
        # Sequence-1 INTERNAL/MIXED positions treat the lot's raw-material
        # demand as a virtual predecessor, no demand linked yet resolves
        # to 0.0 arrived (never unconstrained), so starting the mill on
        # step 1 is blocked until its source material exists and arrives.
        order_repo = FakeProductionOrderRepository([make_order(id=1, lot_position_id=1)])
        use_case = StartProductionOrder(
            order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(order_repo, self.lot_repo, self.bus),
        )
        with pytest.raises(LotPositionOverflowError):
            await use_case.execute(
                self.actor, production_order_id=1, cmd=StartProductionOrderCommand()
            )

    async def test_first_position_starts_once_source_material_has_arrived(self):
        self.lot.input_demand_id = 5
        lot_repo = FakeProductionLotRepository([self.lot], raw_material_arrived_by_demand={5: 10.0})
        order_repo = FakeProductionOrderRepository([make_order(id=1, lot_position_id=1)])
        use_case = StartProductionOrder(
            order_repo,
            lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(order_repo, lot_repo, self.bus),
        )
        result = await use_case.execute(
            self.actor, production_order_id=1, cmd=StartProductionOrderCommand()
        )
        assert result.status == ProductionOrderStatus.IN_PROGRESS.value

    async def test_first_position_of_a_rework_lot_is_never_gated_by_source_material(self):
        # A rework/alteration lot (source_made_item_id set) has no source-item
        # demand to track at all, its position 1 stays unconstrained.
        self.lot.source_made_item_id = 99
        order_repo = FakeProductionOrderRepository([make_order(id=1, lot_position_id=1)])
        use_case = StartProductionOrder(
            order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(order_repo, self.lot_repo, self.bus),
        )
        result = await use_case.execute(
            self.actor, production_order_id=1, cmd=StartProductionOrderCommand()
        )
        assert result.status == ProductionOrderStatus.IN_PROGRESS.value
