"""
Unit tests for TestReplaceLotStructure. No database, no HTTP. All
dependencies replaced with in-memory fakes.
"""

from datetime import date

import pytest

from src.modules.catalogue.domain.errors import FabricationMethodArchivedError
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.application.dto.production_lot_dto import ReplaceLotStructureCommand
from src.modules.fulfillment.application.dto.production_lot_dto import (
    ReplaceLotStructurePositionInput,
)
from src.modules.fulfillment.application.dto.production_lot_dto import ReplaceLotStructureStepInput
from src.modules.fulfillment.application.use_cases.production_lot.replace_structure import (
    ReplaceLotStructure,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.errors import LotPositionAlreadyAssignedError
from src.modules.fulfillment.domain.errors import LotPositionGroupingInvalidError
from src.modules.fulfillment.domain.errors import LotPositionInUseError
from src.modules.fulfillment.domain.errors import LotStepNotFoundError
from src.modules.fulfillment.domain.errors import LotStructureLockedError
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.production_lot._helpers import make_fabrication_method
from tests.unit.production_lot._helpers import make_inspection_method
from tests.unit.production_lot._helpers import make_order_item
from tests.unit.production_lot.fakes import FakeFabricationMethodRepository
from tests.unit.production_lot.fakes import FakeInspectionMethodRepository
from tests.unit.production_lot.fakes import FakeOrderItemRepository
from tests.unit.production_lot.fakes import FakeProductionLotRepository
from tests.unit.production_lot.fakes import FakeProductionOrderRepository
from tests.unit.production_lot.fakes import FakeUnitOfWork
from tests.unit.production_lot.fakes import lot_reconciler


class TestReplaceLotStructure:
    """The step editor's single transactional save. Structure-level rules
    live in the use case (see its module docstring); these cover the
    reconciliation itself: what is kept, created, deleted and renumbered."""

    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.lot_repo = FakeProductionLotRepository()
        self.fabrication_methods = FakeFabricationMethodRepository(
            [make_fabrication_method(1), make_fabrication_method(2)]
        )
        self.inspection_methods = FakeInspectionMethodRepository(
            [make_inspection_method(1), make_inspection_method(2)]
        )
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
                status=LotStatus.DRAFT,
                priority=UrgencyClass.NORMAL,
                note=None,
                creator_id=1,
                made_item_id=1,
                project_id=1,
                input_demand_id=None,
            )
        )
        self.position = await self.lot_repo.save_position(
            LotPosition(
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
        )
        self.step_ids = []
        for seq in (1, 2):
            saved = await self.lot_repo.save_step(
                LotStep(
                    id=0,
                    created=date(2026, 1, 1),
                    note=None,
                    estimated_setup_minutes=10,
                    estimated_minutes_per_piece=2,
                    sequence=seq,
                    creator_id=1,
                    fabrication_method_id=1,
                    lot_id=self.lot.id,
                    position_id=self.position.id,
                    source_process_id=None,
                )
            )
            self.step_ids.append(saved.id)

        self.use_case = ReplaceLotStructure(
            self.lot_repo,
            self.fabrication_methods,
            self.inspection_methods,
            order_repo=FakeProductionOrderRepository(),
            uow=self.uow,
            reconciler=lot_reconciler(self.lot_repo),
        )

    def _step(self, step_id: int | None = None, **overrides):
        payload = {
            "id": step_id,
            "role": StepRole.FABRICATION.value,
            "fabrication_method_id": 1,
            "note": None,
            "estimated_setup_minutes": 10,
            "estimated_minutes_per_piece": 2,
        }
        payload.update(overrides)
        return ReplaceLotStructureStepInput(**payload)

    async def _execute(self, positions):
        return await self.use_case.execute(
            self.actor,
            self.lot.id,
            ReplaceLotStructureCommand(
                positions=[ReplaceLotStructurePositionInput(steps=p) for p in positions]
            ),
        )

    async def test_splitting_a_position_keeps_both_steps_and_renumbers(self):
        result = await self._execute(
            [[self._step(self.step_ids[0])], [self._step(self.step_ids[1])]]
        )

        assert [p.sequence for p in result] == [1, 2]
        assert [len(p.steps) for p in result] == [1, 1]
        assert {s.id for s in await self.lot_repo.get_steps(self.lot.id)} == set(self.step_ids)
        assert self.uow.committed

    async def test_replace_requires_write_lots(self):
        permissionless = make_user(permissions=[])
        before = {s.id for s in await self.lot_repo.get_steps(self.lot.id)}
        with pytest.raises(InsufficientPermissionsError):
            await self.use_case.execute(
                permissionless,
                self.lot.id,
                ReplaceLotStructureCommand(
                    positions=[
                        ReplaceLotStructurePositionInput(steps=[self._step(self.step_ids[0])])
                    ]
                ),
            )
        # Structure unchanged.
        assert {s.id for s in await self.lot_repo.get_steps(self.lot.id)} == before

    async def test_split_still_succeeds_when_order_item_repo_has_no_match(self):
        """order_item_repo wired but reports no match: unaffected."""
        use_case = ReplaceLotStructure(
            self.lot_repo,
            self.fabrication_methods,
            self.inspection_methods,
            order_item_repo=FakeOrderItemRepository(),
            order_repo=FakeProductionOrderRepository(),
            uow=self.uow,
            reconciler=lot_reconciler(self.lot_repo),
        )
        result = await use_case.execute(
            self.actor,
            self.lot.id,
            ReplaceLotStructureCommand(
                positions=[
                    ReplaceLotStructurePositionInput(steps=[self._step(self.step_ids[0])]),
                    ReplaceLotStructurePositionInput(steps=[self._step(self.step_ids[1])]),
                ]
            ),
        )
        assert [p.sequence for p in result] == [1, 2]

    async def test_split_blocked_when_deleted_position_referenced_by_order_item(self):
        order_item = make_order_item(id=1, lot_position_id=self.position.id)
        order_item_repo = FakeOrderItemRepository([order_item])
        use_case = ReplaceLotStructure(
            self.lot_repo,
            self.fabrication_methods,
            self.inspection_methods,
            order_item_repo=order_item_repo,
            order_repo=FakeProductionOrderRepository(),
            uow=self.uow,
            reconciler=lot_reconciler(self.lot_repo),
        )
        with pytest.raises(LotPositionInUseError):
            await use_case.execute(
                self.actor,
                self.lot.id,
                ReplaceLotStructureCommand(
                    positions=[
                        ReplaceLotStructurePositionInput(steps=[self._step(self.step_ids[0])]),
                        ReplaceLotStructurePositionInput(steps=[self._step(self.step_ids[1])]),
                    ]
                ),
            )

    async def test_a_position_whose_step_set_is_unchanged_keeps_its_row(self):
        await self._execute([[self._step(self.step_ids[0]), self._step(self.step_ids[1])]])

        positions = await self.lot_repo.get_positions(self.lot.id)
        assert [p.id for p in positions] == [self.position.id]

    async def test_omitting_a_step_deletes_it(self):
        await self._execute([[self._step(self.step_ids[0])]])

        remaining = await self.lot_repo.get_steps(self.lot.id)
        assert [s.id for s in remaining] == [self.step_ids[0]]

    async def test_a_new_step_is_created_in_its_own_position(self):
        result = await self._execute(
            [
                [self._step(self.step_ids[0]), self._step(self.step_ids[1])],
                [
                    self._step(
                        None,
                        role=StepRole.INSPECTION.value,
                        fabrication_method_id=None,
                        inspection_method_id=1,
                        estimated_setup_minutes=None,
                        estimated_minutes_per_piece=None,
                    )
                ],
            ]
        )

        assert len(result) == 2
        qa_step = result[1].steps[0]
        assert qa_step.role == "inspection"
        assert qa_step.inspection_method_id == 1
        assert qa_step.sequence == 3

    async def test_field_edits_are_applied_to_existing_steps(self):
        await self._execute(
            [
                [
                    self._step(self.step_ids[0], fabrication_method_id=2, note="reworked"),
                    self._step(self.step_ids[1]),
                ]
            ]
        )

        step = await self.lot_repo.get_step_by_id(self.step_ids[0])
        assert step.fabrication_method_id == 2
        assert step.note == "reworked"

    async def test_reordering_puts_the_steps_in_the_submitted_order(self):
        await self._execute([[self._step(self.step_ids[1])], [self._step(self.step_ids[0])]])

        assert [s.id for s in await self.lot_repo.get_steps(self.lot.id)] == [
            self.step_ids[1],
            self.step_ids[0],
        ]

    async def test_inspection_step_cannot_share_a_position(self):
        with pytest.raises(LotPositionGroupingInvalidError):
            await self._execute(
                [
                    [
                        self._step(self.step_ids[0]),
                        self._step(
                            None,
                            role=StepRole.INSPECTION.value,
                            fabrication_method_id=None,
                            inspection_method_id=1,
                        ),
                    ],
                    [self._step(self.step_ids[1])],
                ]
            )

    async def test_unknown_step_id_raises(self):
        with pytest.raises(LotStepNotFoundError):
            await self._execute([[self._step(9999)]])

    async def test_changing_a_role_raises(self):
        with pytest.raises(LotPositionGroupingInvalidError):
            await self._execute(
                [
                    [
                        self._step(
                            self.step_ids[0],
                            role=StepRole.INSPECTION.value,
                            fabrication_method_id=None,
                            inspection_method_id=1,
                        )
                    ],
                    [self._step(self.step_ids[1])],
                ]
            )

    async def test_regrouping_an_assigned_position_raises(self):
        self.position.kind = LotPositionKind.INTERNAL
        await self.lot_repo.save_position(self.position)

        with pytest.raises(LotPositionAlreadyAssignedError):
            await self._execute([[self._step(self.step_ids[0])], [self._step(self.step_ids[1])]])

    async def test_changing_a_fabrication_method_on_an_assigned_position_raises(self):
        self.position.kind = LotPositionKind.INTERNAL
        await self.lot_repo.save_position(self.position)

        with pytest.raises(LotPositionAlreadyAssignedError):
            await self._execute(
                [
                    [
                        self._step(self.step_ids[0], fabrication_method_id=2),
                        self._step(self.step_ids[1]),
                    ]
                ]
            )

    async def test_editing_notes_and_times_on_an_assigned_position_is_allowed(self):
        self.position.kind = LotPositionKind.INTERNAL
        await self.lot_repo.save_position(self.position)

        await self._execute(
            [
                [
                    self._step(self.step_ids[0], note="still editable", estimated_setup_minutes=30),
                    self._step(self.step_ids[1]),
                ]
            ]
        )

        step = await self.lot_repo.get_step_by_id(self.step_ids[0])
        assert step.note == "still editable"
        assert step.estimated_setup_minutes == 30

    async def test_completed_lot_cannot_be_restructured(self):
        self.lot.status = LotStatus.COMPLETED
        await self.lot_repo.save(self.lot)

        with pytest.raises(LotStructureLockedError):
            await self._execute([[self._step(self.step_ids[0])], [self._step(self.step_ids[1])]])

    async def test_newly_selected_archived_method_raises_but_an_existing_one_survives(self):
        self.fabrication_methods._methods[3] = make_fabrication_method(id=3, archived=True)
        with pytest.raises(FabricationMethodArchivedError):
            await self._execute(
                [
                    [
                        self._step(self.step_ids[0], fabrication_method_id=3),
                        self._step(self.step_ids[1]),
                    ]
                ]
            )

        # The method a step already carries may be archived afterwards;
        # editing anything else about that step must still work.
        self.fabrication_methods._methods[1] = make_fabrication_method(id=1, archived=True)
        await self._execute(
            [[self._step(self.step_ids[0], note="untouched method"), self._step(self.step_ids[1])]]
        )
        assert (await self.lot_repo.get_step_by_id(self.step_ids[0])).note == "untouched method"
