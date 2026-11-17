"""
Unit tests for TestLotSteps, TestUpdateLotStep. No database, no HTTP. All
dependencies replaced with in-memory fakes.
"""

from datetime import date

import pytest

from src.modules.catalogue.domain.errors import FabricationMethodArchivedError
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.application.dto.production_lot_dto import AddLotStepCommand
from src.modules.fulfillment.application.dto.production_lot_dto import ReorderLotStepsCommand
from src.modules.fulfillment.application.dto.production_lot_dto import UpdateLotStepCommand
from src.modules.fulfillment.application.use_cases.production_lot.lot_steps import AddLotStep
from src.modules.fulfillment.application.use_cases.production_lot.lot_steps import DeleteLotStep
from src.modules.fulfillment.application.use_cases.production_lot.lot_steps import ReorderLotSteps
from src.modules.fulfillment.application.use_cases.production_lot.lot_steps import UpdateLotStep
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.errors import LotPositionAlreadyAssignedError
from src.modules.fulfillment.domain.errors import LotPositionGroupingInvalidError
from src.modules.fulfillment.domain.errors import LotPositionInUseError
from src.modules.fulfillment.domain.errors import LotStructureLockedError
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.production_lot._helpers import make_fabrication_method
from tests.unit.production_lot._helpers import make_inspection_method
from tests.unit.production_lot._helpers import make_order_item
from tests.unit.production_lot._helpers import make_production_order
from tests.unit.production_lot.fakes import FakeFabricationMethodRepository
from tests.unit.production_lot.fakes import FakeInspectionMethodRepository
from tests.unit.production_lot.fakes import FakeOrderItemRepository
from tests.unit.production_lot.fakes import FakeProductionLotRepository
from tests.unit.production_lot.fakes import FakeProductionOrderRepository
from tests.unit.production_lot.fakes import FakeRecomputeMachineSchedule
from tests.unit.production_lot.fakes import FakeUnitOfWork
from tests.unit.production_lot.fakes import lot_reconciler


class TestLotSteps:
    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.lot_repo = FakeProductionLotRepository()
        self.fabrication_methods = FakeFabricationMethodRepository([make_fabrication_method(1)])
        self.inspection_methods = FakeInspectionMethodRepository([make_inspection_method(1)])
        self.actor = make_user(permissions=[Permission.WRITE_LOTS])

        # Build a DRAFT lot with one position and two steps directly via the fake repo.
        lot = ProductionLot(
            id=0,
            created=date(2026, 1, 1),
            changed=None,
            changes=[],
            lot_number="LOT-1",
            quantity=5.0,
            status=LotStatus.DRAFT,
            priority=UrgencyClass.NORMAL,
            note=None,
            creator_id=1,
            made_item_id=1,
            project_id=1,
            input_demand_id=None,
        )
        self.lot = await self.lot_repo.save(lot)
        position = LotPosition(
            id=0,
            created=date(2026, 1, 1),
            changed=None,
            changes=[],
            sequence=1,
            kind=LotPositionKind.UNASSIGNED,
            status=LotPositionStatus.PENDING,
            quantity=5.0,
            quantity_completed=0.0,
            note=None,
            creator_id=1,
            lot_id=self.lot.id,
        )
        self.position = await self.lot_repo.save_position(position)
        for seq in (1, 2):
            step = LotStep(
                id=0,
                created=date(2026, 1, 1),
                note=None,
                estimated_setup_minutes=None,
                estimated_minutes_per_piece=None,
                sequence=seq,
                creator_id=1,
                fabrication_method_id=1,
                lot_id=self.lot.id,
                position_id=self.position.id,
                source_process_id=None,
            )
            await self.lot_repo.save_step(step)

    async def test_add_step_appends_at_end(self):
        use_case = AddLotStep(
            self.lot_repo,
            self.fabrication_methods,
            self.inspection_methods,
            order_repo=FakeProductionOrderRepository(),
            uow=FakeUnitOfWork(),
            reconciler=lot_reconciler(self.lot_repo),
        )
        result = await use_case.execute(
            self.actor,
            self.lot.id,
            AddLotStepCommand(position_id=self.position.id, fabrication_method_id=1),
        )
        assert result.sequence == 3
        assert result.source_process_id is None

    async def test_add_step_requires_write_lots(self):
        permissionless = make_user(permissions=[])
        use_case = AddLotStep(
            self.lot_repo,
            self.fabrication_methods,
            self.inspection_methods,
            order_repo=FakeProductionOrderRepository(),
            uow=FakeUnitOfWork(),
            reconciler=lot_reconciler(self.lot_repo),
        )
        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(
                permissionless,
                self.lot.id,
                AddLotStepCommand(position_id=self.position.id, fabrication_method_id=1),
            )
        # Structure unchanged (setup created two steps).
        assert len(await self.lot_repo.get_steps(self.lot.id)) == 2

    async def test_add_inspection_step_to_a_fresh_empty_position_needs_no_method(self):
        empty_position = await self.lot_repo.save_position(
            LotPosition(
                id=0,
                created=date(2026, 1, 1),
                changed=None,
                changes=[],
                sequence=2,
                kind=LotPositionKind.UNASSIGNED,
                status=LotPositionStatus.PENDING,
                quantity=5.0,
                quantity_completed=0.0,
                note=None,
                creator_id=1,
                lot_id=self.lot.id,
            )
        )
        use_case = AddLotStep(
            self.lot_repo,
            self.fabrication_methods,
            self.inspection_methods,
            order_repo=FakeProductionOrderRepository(),
            uow=FakeUnitOfWork(),
            reconciler=lot_reconciler(self.lot_repo),
        )
        result = await use_case.execute(
            self.actor,
            self.lot.id,
            AddLotStepCommand(
                position_id=empty_position.id,
                role=StepRole.INSPECTION.value,
                inspection_method_id=1,
            ),
        )
        assert result.role == "inspection"
        assert result.inspection_method_id == 1
        assert result.fabrication_method_id is None

    async def test_add_inspection_step_to_a_populated_position_raises(self):
        use_case = AddLotStep(
            self.lot_repo,
            self.fabrication_methods,
            self.inspection_methods,
            order_repo=FakeProductionOrderRepository(),
            uow=FakeUnitOfWork(),
            reconciler=lot_reconciler(self.lot_repo),
        )
        with pytest.raises(LotPositionGroupingInvalidError):
            await use_case.execute(
                self.actor,
                self.lot.id,
                AddLotStepCommand(
                    position_id=self.position.id,
                    role=StepRole.INSPECTION.value,
                    inspection_method_id=1,
                ),
            )

    async def test_delete_last_step_removes_empty_position(self):
        use_case = DeleteLotStep(
            self.lot_repo,
            order_repo=FakeProductionOrderRepository(),
            uow=FakeUnitOfWork(),
            reconciler=lot_reconciler(self.lot_repo),
        )
        steps = await self.lot_repo.get_steps(self.lot.id)
        await use_case.execute(self.actor, steps[0].id)
        await use_case.execute(self.actor, steps[1].id)
        assert await self.lot_repo.get_positions(self.lot.id) == []

    async def test_delete_last_step_still_removes_position_when_unreferenced(self):
        """order_item_repo wired but reports no match: unaffected."""
        order_item_repo = FakeOrderItemRepository()
        use_case = DeleteLotStep(
            self.lot_repo,
            order_item_repo=order_item_repo,
            order_repo=FakeProductionOrderRepository(),
            uow=FakeUnitOfWork(),
            reconciler=lot_reconciler(self.lot_repo),
        )
        steps = await self.lot_repo.get_steps(self.lot.id)
        await use_case.execute(self.actor, steps[0].id)
        await use_case.execute(self.actor, steps[1].id)
        assert await self.lot_repo.get_positions(self.lot.id) == []

    async def test_delete_last_step_blocked_when_position_referenced_by_order_item(self):
        order_item = make_order_item(id=1, lot_position_id=self.position.id)
        order_item_repo = FakeOrderItemRepository([order_item])
        use_case = DeleteLotStep(
            self.lot_repo,
            order_item_repo=order_item_repo,
            order_repo=FakeProductionOrderRepository(),
            uow=FakeUnitOfWork(),
            reconciler=lot_reconciler(self.lot_repo),
        )
        steps = await self.lot_repo.get_steps(self.lot.id)
        await use_case.execute(self.actor, steps[0].id)
        with pytest.raises(LotPositionInUseError):
            await use_case.execute(self.actor, steps[1].id)
        # Position survives the rejected delete.
        assert len(await self.lot_repo.get_positions(self.lot.id)) == 1

    async def test_rejected_delete_of_last_step_changes_nothing(self):
        order_item = make_order_item(id=1, lot_position_id=self.position.id)
        uow = FakeUnitOfWork()
        use_case = DeleteLotStep(
            self.lot_repo,
            order_item_repo=FakeOrderItemRepository([order_item]),
            order_repo=FakeProductionOrderRepository(),
            uow=uow,
            reconciler=lot_reconciler(self.lot_repo),
        )
        steps = await self.lot_repo.get_steps(self.lot.id)
        await use_case.execute(self.actor, steps[0].id)
        commits_before = uow.commits
        with pytest.raises(LotPositionInUseError):
            await use_case.execute(self.actor, steps[1].id)
        assert [s.id for s in await self.lot_repo.get_steps(self.lot.id)] == [steps[1].id]
        assert uow.commits == commits_before

    async def test_reorder_within_position_succeeds(self):
        use_case = ReorderLotSteps(
            self.lot_repo, uow=FakeUnitOfWork(), reconciler=lot_reconciler(self.lot_repo)
        )
        steps = await self.lot_repo.get_steps(self.lot.id)
        reversed_ids = [steps[1].id, steps[0].id]
        result = await use_case.execute(
            self.actor, self.lot.id, ReorderLotStepsCommand(ordered_step_ids=reversed_ids)
        )
        assert [r.id for r in result] == reversed_ids

    async def test_reorder_that_would_fragment_a_position_raises(self):
        # Append a second position with its own step, then attempt an
        # interleaved reorder that splits position 1's steps apart.
        other_position = await self.lot_repo.save_position(
            LotPosition(
                id=0,
                created=date(2026, 1, 1),
                changed=None,
                changes=[],
                sequence=2,
                kind=LotPositionKind.UNASSIGNED,
                status=LotPositionStatus.PENDING,
                quantity=5.0,
                quantity_completed=0.0,
                note=None,
                creator_id=1,
                lot_id=self.lot.id,
            )
        )
        other_step = await self.lot_repo.save_step(
            LotStep(
                id=0,
                created=date(2026, 1, 1),
                note=None,
                estimated_setup_minutes=None,
                estimated_minutes_per_piece=None,
                sequence=3,
                creator_id=1,
                fabrication_method_id=1,
                lot_id=self.lot.id,
                position_id=other_position.id,
                source_process_id=None,
            )
        )
        steps = await self.lot_repo.get_steps(self.lot.id)
        pos1_steps = [s for s in steps if s.position_id == self.position.id]
        interleaved = [pos1_steps[0].id, other_step.id, pos1_steps[1].id]
        use_case = ReorderLotSteps(
            self.lot_repo, uow=FakeUnitOfWork(), reconciler=lot_reconciler(self.lot_repo)
        )
        with pytest.raises(LotPositionGroupingInvalidError):
            await use_case.execute(
                self.actor, self.lot.id, ReorderLotStepsCommand(ordered_step_ids=interleaved)
            )

    async def _append_assigned_inspection_position(self) -> LotStep:
        """A born-INTERNAL QA singleton at the end of the lot, the shape
        create_lot._auto_queue_inspection_position produces."""
        qa_position = await self.lot_repo.save_position(
            LotPosition(
                id=0,
                created=date(2026, 1, 1),
                changed=None,
                changes=[],
                sequence=2,
                kind=LotPositionKind.INTERNAL,
                status=LotPositionStatus.ORDERED_OR_QUEUED,
                quantity=5.0,
                quantity_completed=0.0,
                note=None,
                creator_id=1,
                lot_id=self.lot.id,
            )
        )
        return await self.lot_repo.save_step(
            LotStep(
                id=0,
                created=date(2026, 1, 1),
                note=None,
                estimated_setup_minutes=None,
                estimated_minutes_per_piece=None,
                sequence=3,
                creator_id=1,
                fabrication_method_id=None,
                lot_id=self.lot.id,
                position_id=qa_position.id,
                source_process_id=None,
                role=StepRole.INSPECTION,
                inspection_method_id=1,
            )
        )

    async def test_reorder_around_assigned_inspection_singleton_succeeds(self):
        qa_step = await self._append_assigned_inspection_position()
        steps = await self.lot_repo.get_steps(self.lot.id)
        fabrication_ids = [s.id for s in steps if s.id != qa_step.id]
        new_order = [fabrication_ids[1], fabrication_ids[0], qa_step.id]
        use_case = ReorderLotSteps(
            self.lot_repo, uow=FakeUnitOfWork(), reconciler=lot_reconciler(self.lot_repo)
        )
        result = await use_case.execute(
            self.actor, self.lot.id, ReorderLotStepsCommand(ordered_step_ids=new_order)
        )
        assert [r.id for r in result] == new_order

    async def test_reorder_refuses_to_move_an_assigned_position(self):
        # The born-INTERNAL QA singleton is committed to its place in the
        # sequence: its input comes from the position before it, so moving it
        # to the front is refused and nothing is reordered.
        qa_step = await self._append_assigned_inspection_position()
        steps = await self.lot_repo.get_steps(self.lot.id)
        fabrication_ids = [s.id for s in steps if s.id != qa_step.id]
        use_case = ReorderLotSteps(
            self.lot_repo, uow=FakeUnitOfWork(), reconciler=lot_reconciler(self.lot_repo)
        )
        with pytest.raises(LotPositionAlreadyAssignedError):
            await use_case.execute(
                self.actor,
                self.lot.id,
                ReorderLotStepsCommand(ordered_step_ids=[qa_step.id, *fabrication_ids]),
            )
        assert [s.id for s in await self.lot_repo.get_steps(self.lot.id)] == [
            *fabrication_ids,
            qa_step.id,
        ]

    async def test_reorder_renumbers_positions_to_match_the_new_step_order(self):
        # LotPosition.sequence is what drives the production chain, so a
        # drag that moves an unassigned position to the front has to move the
        # position too, not just the step rows.
        moved = await self.lot_repo.save_position(
            LotPosition(
                id=0,
                created=date(2026, 1, 1),
                changed=None,
                changes=[],
                sequence=2,
                kind=LotPositionKind.UNASSIGNED,
                status=LotPositionStatus.PENDING,
                quantity=5.0,
                quantity_completed=0.0,
                note=None,
                creator_id=1,
                lot_id=self.lot.id,
            )
        )
        moved_step = await self.lot_repo.save_step(
            LotStep(
                id=0,
                created=date(2026, 1, 1),
                note=None,
                estimated_setup_minutes=None,
                estimated_minutes_per_piece=None,
                sequence=3,
                creator_id=1,
                fabrication_method_id=1,
                lot_id=self.lot.id,
                position_id=moved.id,
                source_process_id=None,
            )
        )
        steps = await self.lot_repo.get_steps(self.lot.id)
        first_ids = [s.id for s in steps if s.id != moved_step.id]

        await ReorderLotSteps(
            self.lot_repo, uow=FakeUnitOfWork(), reconciler=lot_reconciler(self.lot_repo)
        ).execute(
            self.actor,
            self.lot.id,
            ReorderLotStepsCommand(ordered_step_ids=[moved_step.id, *first_ids]),
        )

        positions = await self.lot_repo.get_positions(self.lot.id)
        assert [p.id for p in positions] == [moved.id, self.position.id]
        assert [p.sequence for p in positions] == [1, 2]

    async def test_non_terminal_status_allows_structural_edits(self):
        self.lot.status = LotStatus.PLANNED
        await self.lot_repo.save(self.lot)
        use_case = AddLotStep(
            self.lot_repo,
            self.fabrication_methods,
            self.inspection_methods,
            order_repo=FakeProductionOrderRepository(),
            uow=FakeUnitOfWork(),
            reconciler=lot_reconciler(self.lot_repo),
        )
        result = await use_case.execute(
            self.actor,
            self.lot.id,
            AddLotStepCommand(position_id=self.position.id, fabrication_method_id=1),
        )
        assert result.sequence == 3

    async def test_completed_lot_blocks_structural_edits(self):
        self.lot.status = LotStatus.COMPLETED
        await self.lot_repo.save(self.lot)
        use_case = AddLotStep(
            self.lot_repo,
            self.fabrication_methods,
            self.inspection_methods,
            order_repo=FakeProductionOrderRepository(),
            uow=FakeUnitOfWork(),
            reconciler=lot_reconciler(self.lot_repo),
        )
        with pytest.raises(LotStructureLockedError):
            await use_case.execute(
                self.actor,
                self.lot.id,
                AddLotStepCommand(position_id=self.position.id, fabrication_method_id=1),
            )

    async def test_assigned_position_blocks_step_edit(self):
        self.position.kind = LotPositionKind.EXTERNAL
        await self.lot_repo.save_position(self.position)
        use_case = AddLotStep(
            self.lot_repo,
            self.fabrication_methods,
            self.inspection_methods,
            order_repo=FakeProductionOrderRepository(),
            uow=FakeUnitOfWork(),
            reconciler=lot_reconciler(self.lot_repo),
        )
        with pytest.raises(LotPositionAlreadyAssignedError):
            await use_case.execute(
                self.actor,
                self.lot.id,
                AddLotStepCommand(position_id=self.position.id, fabrication_method_id=1),
            )

    async def test_archived_fabrication_method_blocks_new_step(self):
        self.fabrication_methods._methods[3] = make_fabrication_method(id=3, archived=True)
        use_case = AddLotStep(
            self.lot_repo,
            self.fabrication_methods,
            self.inspection_methods,
            order_repo=FakeProductionOrderRepository(),
            uow=FakeUnitOfWork(),
            reconciler=lot_reconciler(self.lot_repo),
        )
        with pytest.raises(FabricationMethodArchivedError):
            await use_case.execute(
                self.actor,
                self.lot.id,
                AddLotStepCommand(position_id=self.position.id, fabrication_method_id=3),
            )


class TestUpdateLotStep:
    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.lot_repo = FakeProductionLotRepository()
        self.fabrication_methods = FakeFabricationMethodRepository(
            [make_fabrication_method(1), make_fabrication_method(2)]
        )
        self.inspection_methods = FakeInspectionMethodRepository([make_inspection_method(1)])
        self.order_repo = FakeProductionOrderRepository()
        self.recompute = FakeRecomputeMachineSchedule()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.WRITE_LOTS])

        lot = ProductionLot(
            id=0,
            created=date(2026, 1, 1),
            changed=None,
            changes=[],
            lot_number="LOT-1",
            quantity=5.0,
            status=LotStatus.PLANNED,
            priority=UrgencyClass.NORMAL,
            note=None,
            creator_id=1,
            made_item_id=1,
            project_id=1,
            input_demand_id=None,
        )
        self.lot = await self.lot_repo.save(lot)
        # An already-assigned (internal) position, which must not block
        # every step edit on its own.
        position = LotPosition(
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
            lot_id=self.lot.id,
        )
        self.position = await self.lot_repo.save_position(position)
        step = LotStep(
            id=0,
            created=date(2026, 1, 1),
            note=None,
            estimated_setup_minutes=10,
            estimated_minutes_per_piece=2,
            sequence=1,
            creator_id=1,
            fabrication_method_id=1,
            lot_id=self.lot.id,
            position_id=self.position.id,
            source_process_id=None,
        )
        self.step = await self.lot_repo.save_step(step)

        self.use_case = UpdateLotStep(
            self.lot_repo,
            self.fabrication_methods,
            self.inspection_methods,
            order_repo=self.order_repo,
            recompute_schedule=self.recompute,
            uow=self.uow,
            lock_plan=lot_reconciler(self.lot_repo, self.order_repo).lock_plan,
        )

    async def test_time_estimate_edit_on_assigned_position_succeeds(self):
        result = await self.use_case.execute(
            self.actor,
            self.step.id,
            UpdateLotStepCommand(
                fabrication_method_id=1,
                note=None,
                estimated_setup_minutes=15,
                estimated_minutes_per_piece=3,
            ),
        )
        assert result.estimated_minutes_per_piece == 3
        assert self.uow.committed

    async def test_note_only_edit_on_assigned_position_succeeds(self):
        result = await self.use_case.execute(
            self.actor,
            self.step.id,
            UpdateLotStepCommand(
                fabrication_method_id=1,
                note="updated note",
                estimated_setup_minutes=10,
                estimated_minutes_per_piece=2,
            ),
        )
        assert result.note == "updated note"

    async def test_changing_fabrication_method_on_assigned_position_raises(self):
        with pytest.raises(LotPositionAlreadyAssignedError):
            await self.use_case.execute(
                self.actor,
                self.step.id,
                UpdateLotStepCommand(
                    fabrication_method_id=2,
                    note=None,
                    estimated_setup_minutes=10,
                    estimated_minutes_per_piece=2,
                ),
            )

    async def test_changing_inspection_method_on_assigned_position_succeeds(self):
        # A QA step's position is born INTERNAL (auto-queued at lot
        # creation), so gating its method on assignment would lock it
        # forever. The inspection method stays changeable even planned
        # or in progress (only FABRICATION method changes are gated).
        self.inspection_methods._methods[2] = make_inspection_method(id=2)
        qa_position = await self.lot_repo.save_position(
            LotPosition(
                id=0,
                created=date(2026, 1, 1),
                changed=None,
                changes=[],
                sequence=2,
                kind=LotPositionKind.INTERNAL,
                status=LotPositionStatus.ORDERED_OR_QUEUED,
                quantity=5.0,
                quantity_completed=0.0,
                note=None,
                creator_id=1,
                lot_id=self.lot.id,
            )
        )
        qa_step = await self.lot_repo.save_step(
            LotStep(
                id=0,
                created=date(2026, 1, 1),
                note=None,
                estimated_setup_minutes=None,
                estimated_minutes_per_piece=None,
                sequence=2,
                creator_id=1,
                fabrication_method_id=None,
                lot_id=self.lot.id,
                position_id=qa_position.id,
                source_process_id=None,
                role=StepRole.INSPECTION,
                inspection_method_id=1,
            )
        )
        result = await self.use_case.execute(
            self.actor,
            qa_step.id,
            UpdateLotStepCommand(
                role=StepRole.INSPECTION.value,
                fabrication_method_id=None,
                inspection_method_id=2,
                note=None,
                estimated_setup_minutes=None,
                estimated_minutes_per_piece=None,
            ),
        )
        assert result.inspection_method_id == 2

    async def test_changing_role_on_update_raises(self):
        with pytest.raises(LotPositionGroupingInvalidError):
            await self.use_case.execute(
                self.actor,
                self.step.id,
                UpdateLotStepCommand(
                    role=StepRole.INSPECTION.value,
                    fabrication_method_id=None,
                    inspection_method_id=1,
                    note=None,
                    estimated_setup_minutes=10,
                    estimated_minutes_per_piece=2,
                ),
            )

    async def test_changing_to_archived_fabrication_method_raises(self):
        self.position.kind = LotPositionKind.UNASSIGNED
        await self.lot_repo.save_position(self.position)
        self.fabrication_methods._methods[3] = make_fabrication_method(id=3, archived=True)
        with pytest.raises(FabricationMethodArchivedError):
            await self.use_case.execute(
                self.actor,
                self.step.id,
                UpdateLotStepCommand(
                    fabrication_method_id=3,
                    note=None,
                    estimated_setup_minutes=10,
                    estimated_minutes_per_piece=2,
                ),
            )

    async def test_editing_unrelated_field_on_step_with_now_archived_method_succeeds(self):
        # The step's own method (id=1) becomes archived after assignment;
        # note/setup edits that don't change the method still succeed.
        self.fabrication_methods._methods[1] = make_fabrication_method(id=1, archived=True)
        result = await self.use_case.execute(
            self.actor,
            self.step.id,
            UpdateLotStepCommand(
                fabrication_method_id=1,
                note="still editable",
                estimated_setup_minutes=10,
                estimated_minutes_per_piece=2,
            ),
        )
        assert result.note == "still editable"

    async def test_time_estimate_edit_resnapshots_queued_sibling_order_duration(self):
        await self.order_repo.save(
            make_production_order(
                1, self.position.id, status=ProductionOrderStatus.QUEUED, machine_id=7
            )
        )
        await self.use_case.execute(
            self.actor,
            self.step.id,
            UpdateLotStepCommand(
                fabrication_method_id=1,
                note=None,
                estimated_setup_minutes=20,
                estimated_minutes_per_piece=4,
            ),
        )
        updated_order = (await self.order_repo.get_by_lot_position_id(self.position.id))[0]
        # setup_total + qty * per_piece_total = 20 + 5 * 4 = 40
        assert updated_order.estimated_duration_minutes == 40
        assert self.recompute.calls == 1

    async def test_time_estimate_edit_skips_in_progress_sibling_order(self):
        await self.order_repo.save(
            make_production_order(
                1, self.position.id, status=ProductionOrderStatus.IN_PROGRESS, machine_id=7
            )
        )
        await self.use_case.execute(
            self.actor,
            self.step.id,
            UpdateLotStepCommand(
                fabrication_method_id=1,
                note=None,
                estimated_setup_minutes=20,
                estimated_minutes_per_piece=4,
            ),
        )
        untouched_order = (await self.order_repo.get_by_lot_position_id(self.position.id))[0]
        assert untouched_order.estimated_duration_minutes == 30
        assert self.recompute.calls == 0

    async def test_unchanged_time_estimate_does_not_trigger_recompute(self):
        await self.order_repo.save(
            make_production_order(
                1, self.position.id, status=ProductionOrderStatus.QUEUED, machine_id=7
            )
        )
        await self.use_case.execute(
            self.actor,
            self.step.id,
            UpdateLotStepCommand(
                fabrication_method_id=1,
                note="just a note change",
                estimated_setup_minutes=10,
                estimated_minutes_per_piece=2,
            ),
        )
        assert self.recompute.calls == 0
