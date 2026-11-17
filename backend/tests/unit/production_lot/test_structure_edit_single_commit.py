"""
Structure edits do their whole work in one transaction: the step writes,
the project's time budgets and the duration snapshot of queued and paused
orders commit together, so a lost race anywhere in them leaves nothing
committed and the request can run again. The rows are locked in the lock
order first, the time budget lock after them, and only then is a step
written, so the edit never waits for the time budget lock while it holds
step rows another recompute writes.
"""

from datetime import date

import pytest

from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.application.dto.production_lot_dto import AddLotStepCommand
from src.modules.fulfillment.application.dto.production_lot_dto import ReplaceLotStructureCommand
from src.modules.fulfillment.application.dto.production_lot_dto import (
    ReplaceLotStructurePositionInput,
)
from src.modules.fulfillment.application.dto.production_lot_dto import ReplaceLotStructureStepInput
from src.modules.fulfillment.application.dto.production_lot_dto import UpdateLotStepCommand
from src.modules.fulfillment.application.use_cases.production_lot.lot_steps import AddLotStep
from src.modules.fulfillment.application.use_cases.production_lot.lot_steps import DeleteLotStep
from src.modules.fulfillment.application.use_cases.production_lot.lot_steps import UpdateLotStep
from src.modules.fulfillment.application.use_cases.production_lot.replace_structure import (
    ReplaceLotStructure,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.production_lot._helpers import make_fabrication_method
from tests.unit.production_lot._helpers import make_inspection_method
from tests.unit.production_lot._helpers import make_production_order
from tests.unit.production_lot.fakes import FakeFabricationMethodRepository
from tests.unit.production_lot.fakes import FakeInspectionMethodRepository
from tests.unit.production_lot.fakes import FakeProductionLotRepository
from tests.unit.production_lot.fakes import FakeProductionOrderRepository
from tests.unit.production_lot.fakes import FakeProjectRepository
from tests.unit.production_lot.fakes import FakeRecomputeMachineSchedule
from tests.unit.production_lot.fakes import FakeUnitOfWork
from tests.unit.production_lot.fakes import lot_reconciler


class TestStructureEditsCommitOnce:
    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.lot_repo = FakeProductionLotRepository()
        self.order_repo = FakeProductionOrderRepository()
        self.lot_repo.production_orders = self.order_repo.orders
        self.fabrication_methods = FakeFabricationMethodRepository([make_fabrication_method(1)])
        self.inspection_methods = FakeInspectionMethodRepository([make_inspection_method(1)])
        self.projects = FakeProjectRepository()
        self.recompute = FakeRecomputeMachineSchedule()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.WRITE_LOTS])

        self.lot = await self.lot_repo.save(
            ProductionLot(
                id=0,
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
        )
        self.open_position = await self._position(
            1, kind=LotPositionKind.UNASSIGNED, status=LotPositionStatus.PENDING
        )
        self.open_steps = [await self._step(self.open_position, seq) for seq in (1, 2)]
        self.queued_position = await self._position(
            2, kind=LotPositionKind.INTERNAL, status=LotPositionStatus.ORDERED_OR_QUEUED
        )
        self.queued_step = await self._step(self.queued_position, 3)
        await self.order_repo.save(
            make_production_order(
                1, self.queued_position.id, status=ProductionOrderStatus.QUEUED, machine_id=7
            )
        )

        # A shared journal, so the order of the production order locks, the
        # time budget lock and the step writes can be read off one list.
        lock_orders = self.order_repo.lock_for_update

        async def journaled_lock(ids: list[int]) -> None:
            self.lot_repo.journal.append("lock production orders")
            await lock_orders(ids)

        self.order_repo.lock_for_update = journaled_lock  # type: ignore[method-assign]
        self.lot_repo.journal.clear()
        self.reconciler = lot_reconciler(self.lot_repo, self.order_repo)

    async def _position(
        self, sequence: int, *, kind: LotPositionKind, status: LotPositionStatus
    ) -> LotPosition:
        return await self.lot_repo.save_position(
            LotPosition(
                id=0,
                created=date(2026, 1, 1),
                changed=None,
                changes=[],
                sequence=sequence,
                kind=kind,
                status=status,
                quantity=5.0,
                quantity_completed=0.0,
                note=None,
                creator_id=1,
                lot_id=self.lot.id,
            )
        )

    async def _step(self, position: LotPosition, sequence: int) -> LotStep:
        return await self.lot_repo.save_step(
            LotStep(
                id=0,
                created=date(2026, 1, 1),
                note=None,
                estimated_setup_minutes=10,
                estimated_minutes_per_piece=4,
                sequence=sequence,
                creator_id=1,
                fabrication_method_id=1,
                lot_id=self.lot.id,
                position_id=position.id,
                source_process_id=None,
            )
        )

    def _assert_budget_lock_between_row_locks_and_step_writes(self) -> None:
        # The recompute takes the time budget lock again, which is a no-op
        # within the transaction that holds it.
        journal = self.lot_repo.journal
        budget_lock = journal.index("lock time budgets")
        first_write = journal.index("write step")
        last_row_lock = max(
            i
            for i, entry in enumerate(journal)
            if entry.startswith("lock ") and entry != "lock time budgets"
        )
        assert last_row_lock < budget_lock < first_write

    def _queued_duration(self) -> int:
        return self.order_repo.orders[1].estimated_duration_minutes

    async def test_adding_a_step_commits_once(self):
        use_case = AddLotStep(
            self.lot_repo,
            self.fabrication_methods,
            self.inspection_methods,
            self.projects,
            uow=self.uow,
            reconciler=self.reconciler,
            order_repo=self.order_repo,
        )

        await use_case.execute(
            self.actor,
            self.lot.id,
            AddLotStepCommand(position_id=self.open_position.id, fabrication_method_id=1),
        )

        assert self.uow.commits == 1
        self._assert_budget_lock_between_row_locks_and_step_writes()

    async def test_deleting_a_step_commits_once(self):
        use_case = DeleteLotStep(
            self.lot_repo,
            self.projects,
            uow=self.uow,
            reconciler=self.reconciler,
            order_repo=self.order_repo,
            recompute_schedule=self.recompute,
        )

        await use_case.execute(self.actor, self.open_steps[1].id, lot_id=self.lot.id)

        assert self.uow.commits == 1
        self._assert_budget_lock_between_row_locks_and_step_writes()
        assert self.recompute.calls == 1

    async def test_an_estimate_edit_resnapshots_the_queued_order_in_the_same_transaction(self):
        use_case = UpdateLotStep(
            self.lot_repo,
            self.fabrication_methods,
            self.inspection_methods,
            self.projects,
            order_repo=self.order_repo,
            recompute_schedule=self.recompute,
            uow=self.uow,
            lock_plan=self.reconciler.lock_plan,
        )

        await use_case.execute(
            self.actor,
            self.queued_step.id,
            UpdateLotStepCommand(
                fabrication_method_id=1,
                note=None,
                estimated_setup_minutes=20,
                estimated_minutes_per_piece=4,
            ),
            lot_id=self.lot.id,
        )

        assert self.uow.commits == 1
        # 20 setup + 5 pieces * 4 minutes.
        assert self._queued_duration() == 40
        assert "lock production orders" in self.lot_repo.journal
        self._assert_budget_lock_between_row_locks_and_step_writes()
        assert self.recompute.calls == 1

    async def test_a_structure_save_resnapshots_the_queued_order_in_the_same_transaction(self):
        use_case = ReplaceLotStructure(
            self.lot_repo,
            self.fabrication_methods,
            self.inspection_methods,
            self.projects,
            order_repo=self.order_repo,
            recompute_schedule=self.recompute,
            uow=self.uow,
            reconciler=self.reconciler,
        )

        def step(step_id: int, setup: int) -> ReplaceLotStructureStepInput:
            return ReplaceLotStructureStepInput(
                id=step_id,
                role=StepRole.FABRICATION.value,
                fabrication_method_id=1,
                note=None,
                estimated_setup_minutes=setup,
                estimated_minutes_per_piece=4,
            )

        await use_case.execute(
            self.actor,
            self.lot.id,
            ReplaceLotStructureCommand(
                positions=[
                    ReplaceLotStructurePositionInput(
                        steps=[step(s.id, 10) for s in self.open_steps]
                    ),
                    ReplaceLotStructurePositionInput(steps=[step(self.queued_step.id, 20)]),
                ]
            ),
        )

        assert self.uow.commits == 1
        assert self._queued_duration() == 40
        assert "lock production orders" in self.lot_repo.journal
        self._assert_budget_lock_between_row_locks_and_step_writes()
        assert self.recompute.calls == 1
