"""
A production order snapshots its duration from its position's steps, the
time budget per piece included. Every edit that recomputes a project's time
budgets copies a changed budget onto the queued and paused orders of every
lot of the project in the same transaction, not only onto the orders of the
lot it edits. Those orders are locked through the request's lock plan
before the time budget lock, with the edit's other rows, and an order the
plan does not hold is never written: the edit is refused as a concurrent
change instead.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

import pytest

from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.application.dto.production_lot_dto import ReplaceLotStructureCommand
from src.modules.fulfillment.application.dto.production_lot_dto import (
    ReplaceLotStructurePositionInput,
)
from src.modules.fulfillment.application.dto.production_lot_dto import ReplaceLotStructureStepInput
from src.modules.fulfillment.application.dto.production_lot_dto import UpdateLotStepCommand
from src.modules.fulfillment.application.services.lifecycle_loader import AggregateIds
from src.modules.fulfillment.application.services.project_work_propagation import (
    ProjectWorkPropagation,
)
from src.modules.fulfillment.application.services.time_budget_propagation import BudgetOrders
from src.modules.fulfillment.application.services.time_budget_propagation import (
    recompute_project_time_budgets,
)
from src.modules.fulfillment.application.use_cases.production_lot.lot_steps import UpdateLotStep
from src.modules.fulfillment.application.use_cases.production_lot.replace_structure import (
    ReplaceLotStructure,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.exceptions import ConcurrentModificationError
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.workspace.application.dto.project_dto import UpdateProjectCommand
from src.modules.workspace.application.use_cases.project.update_project import UpdateProject
from src.modules.workspace.domain.entities.project import Project
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
from tests.unit.test_project_use_cases import FakeEventBus
from tests.unit.test_project_use_cases import FakeProjectRepository as SavingProjectRepository
from tests.unit.test_project_use_cases import FakeSettingsRepository
from tests.unit.test_project_use_cases import FakeUserRepository

_BUDGET = 1000
# Two lots of 5 pieces with one budgeted step each share the budget.
_PER_PIECE = _BUDGET / 10


def _project(budget: int = _BUDGET) -> Project:
    return Project(
        id=1,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        project_number="P-0001",
        designated_user_id=1,
        production_time_budget=budget,
    )


class TestTimeBudgetResnapshot:
    """Lot A is edited; lot B of the same project holds a queued, a paused
    and a started order on a step that draws from the budget."""

    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.lot_repo = FakeProductionLotRepository()
        self.order_repo = FakeProductionOrderRepository()
        self.lot_repo.production_orders = self.order_repo.orders
        self.fabrication_methods = FakeFabricationMethodRepository([make_fabrication_method(1)])
        self.inspection_methods = FakeInspectionMethodRepository([make_inspection_method(1)])
        self.projects = FakeProjectRepository([_project()])
        self.recompute = FakeRecomputeMachineSchedule()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(
            permissions=[
                Permission.WRITE_LOTS,
                Permission.WRITE_PROJECTS,
                Permission.MANAGE_PROJECTS,
            ]
        )

        self.lot_a = await self._lot("LOT-A")
        self.position_a = await self._position(self.lot_a)
        self.step_a = await self._step(self.position_a, setup=10)
        self.lot_b = await self._lot("LOT-B")
        self.position_b = await self._position(self.lot_b)
        await self._step(self.position_b, setup=0)
        self.queued_a = await self._order(
            1, self.position_a, ProductionOrderStatus.QUEUED, machine_id=7
        )
        self.queued_b = await self._order(
            2, self.position_b, ProductionOrderStatus.QUEUED, machine_id=8
        )
        self.paused_b = await self._order(
            3, self.position_b, ProductionOrderStatus.PAUSED, machine_id=8
        )
        self.started_b = await self._order(
            4, self.position_b, ProductionOrderStatus.IN_PROGRESS, machine_id=9
        )

        lock_orders = self.order_repo.lock_for_update

        # Each order lock with its place in the journal, so what was locked
        # before the time budget lock can be read off.
        self.order_locks: list[tuple[int, list[int]]] = []

        async def journaled_lock(ids: list[int]) -> None:
            self.order_locks.append((len(self.lot_repo.journal), list(ids)))
            self.lot_repo.journal.append("lock production orders")
            await lock_orders(ids)

        self.order_repo.lock_for_update = journaled_lock  # type: ignore[method-assign]
        self.lot_repo.journal.clear()
        self.reconciler = lot_reconciler(self.lot_repo, self.order_repo)

    async def _lot(self, number: str) -> ProductionLot:
        return await self.lot_repo.save(
            ProductionLot(
                id=0,
                created=date(2026, 1, 1),
                changed=None,
                changes=[],
                lot_number=number,
                quantity=5.0,
                status=LotStatus.PLANNED,
                priority=UrgencyClass.NORMAL,
                note=None,
                creator_id=1,
                made_item_id=1,
                project_id=1,
                input_demand_id=None,
            )
        )

    async def _position(self, lot: ProductionLot) -> LotPosition:
        return await self.lot_repo.save_position(
            LotPosition(
                id=0,
                created=date(2026, 1, 1),
                changed=None,
                changes=[],
                sequence=1,
                kind=LotPositionKind.INTERNAL,
                status=LotPositionStatus.ORDERED_OR_QUEUED,
                quantity=5.0,
                quantity_completed=0.0,
                note=None,
                creator_id=1,
                lot_id=lot.id,
            )
        )

    async def _step(self, position: LotPosition, *, setup: int) -> LotStep:
        return await self.lot_repo.save_step(
            LotStep(
                id=0,
                created=date(2026, 1, 1),
                note=None,
                estimated_setup_minutes=setup,
                estimated_minutes_per_piece=None,
                sequence=1,
                creator_id=1,
                fabrication_method_id=1,
                lot_id=position.lot_id,
                position_id=position.id,
                source_process_id=None,
                time_budget_per_piece=_PER_PIECE,
            )
        )

    async def _order(
        self,
        order_id: int,
        position: LotPosition,
        status: ProductionOrderStatus,
        *,
        machine_id: int,
    ) -> int:
        order = make_production_order(
            order_id, position.id, status=status, machine_id=machine_id, quantity=2.0
        )
        order.estimated_duration_minutes = round(
            (10 if position.id == self.position_a.id else 0) + 2 * _PER_PIECE
        )
        await self.order_repo.save(order)
        return order_id

    def _duration(self, order_id: int) -> int:
        return self.order_repo.orders[order_id].estimated_duration_minutes

    def _assert_other_lot_orders_locked_before_the_budget_lock(self) -> None:
        budget_lock = self.lot_repo.journal.index("lock time budgets")
        locked = {
            order_id for place, ids in self.order_locks if place < budget_lock for order_id in ids
        }
        assert {self.queued_b, self.paused_b} <= locked

    async def test_an_estimate_edit_resnapshots_the_orders_of_the_other_lot(self):
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

        # A measured estimate takes lot A's step out of the budget, so lot
        # B's step draws the whole budget over its 5 pieces.
        await use_case.execute(
            self.actor,
            self.step_a.id,
            UpdateLotStepCommand(
                fabrication_method_id=1,
                note=None,
                estimated_setup_minutes=10,
                estimated_minutes_per_piece=4,
            ),
            lot_id=self.lot_a.id,
        )

        assert self.uow.commits == 1
        assert self._duration(self.queued_a) == 10 + 2 * 4
        assert self._duration(self.queued_b) == 2 * 200
        assert self._duration(self.paused_b) == 2 * 200
        # A started order keeps the duration it started with.
        assert self._duration(self.started_b) == 2 * _PER_PIECE
        self._assert_other_lot_orders_locked_before_the_budget_lock()
        assert self.recompute.calls == 1

    async def test_a_structure_save_resnapshots_the_orders_of_the_other_lot(self):
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

        await use_case.execute(
            self.actor,
            self.lot_a.id,
            ReplaceLotStructureCommand(
                positions=[
                    ReplaceLotStructurePositionInput(
                        steps=[
                            ReplaceLotStructureStepInput(
                                id=self.step_a.id,
                                role=StepRole.FABRICATION.value,
                                fabrication_method_id=1,
                                note=None,
                                estimated_setup_minutes=10,
                                estimated_minutes_per_piece=4,
                            )
                        ]
                    )
                ]
            ),
        )

        assert self.uow.commits == 1
        assert self._duration(self.queued_b) == 2 * 200
        assert self._duration(self.paused_b) == 2 * 200
        assert self._duration(self.started_b) == 2 * _PER_PIECE
        self._assert_other_lot_orders_locked_before_the_budget_lock()
        assert self.recompute.calls == 1

    async def test_a_project_budget_edit_resnapshots_the_orders_of_every_lot(self):
        project = _project()
        projects = SavingProjectRepository(projects=[project])
        use_case = UpdateProject(
            projects,
            FakeUserRepository(users=[self.actor]),
            uow=self.uow,
            event_bus=FakeEventBus(),
            settings_repo=FakeSettingsRepository(),
            work=projects,
            propagation=ProjectWorkPropagation(
                projects,
                lot_repo=self.lot_repo,
                lock_plan=self.reconciler.lock_plan,
                order_repo=self.order_repo,
            ),
            recompute_schedule=self.recompute,
        )

        await use_case.execute(
            self.actor,
            project.id,
            UpdateProjectCommand(
                project_number=project.project_number, production_time_budget=2 * _BUDGET
            ),
        )

        assert self.uow.commits == 1
        assert self._duration(self.queued_a) == 10 + 2 * 200
        assert self._duration(self.queued_b) == 2 * 200
        assert self._duration(self.paused_b) == 2 * 200
        assert self._duration(self.started_b) == 2 * _PER_PIECE
        self._assert_other_lot_orders_locked_before_the_budget_lock()
        assert self.recompute.calls == 1

    async def test_an_order_the_lock_plan_does_not_hold_refuses_the_recompute(self):
        """An order queued after the edit read which orders to lock is not
        written without its lock; the request runs again on the new state."""
        lock_plan = self.reconciler.lock_plan
        await lock_plan.acquire(
            AggregateIds.of({LifecycleAggregate.PRODUCTION_ORDERS: [self.queued_a]})
        )
        self.projects = FakeProjectRepository([_project(2 * _BUDGET)])

        with pytest.raises(ConcurrentModificationError):
            await recompute_project_time_budgets(
                1, self.projects, self.lot_repo, BudgetOrders(self.order_repo, lock_plan)
            )
