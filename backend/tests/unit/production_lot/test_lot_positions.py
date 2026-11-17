"""
Unit tests for TestRegroupLotPositions, TestAppendLotPosition. No database, no HTTP. All
dependencies replaced with in-memory fakes.
"""

from datetime import date

import pytest

from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.application.dto.production_lot_dto import AppendLotPositionCommand
from src.modules.fulfillment.application.dto.production_lot_dto import AppendLotPositionStepInput
from src.modules.fulfillment.application.dto.production_lot_dto import RegroupLotPositionsCommand
from src.modules.fulfillment.application.use_cases.production_lot.lot_positions import (
    AppendLotPosition,
)
from src.modules.fulfillment.application.use_cases.production_lot.lot_positions import (
    RegroupLotPositions,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.errors import LotPositionAlreadyAssignedError
from src.modules.fulfillment.domain.errors import LotPositionGroupingInvalidError
from src.modules.fulfillment.domain.errors import LotPositionInUseError
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.entities.user import User
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
from tests.unit.production_lot.fakes import FakeUnitOfWork
from tests.unit.production_lot.fakes import lot_reconciler


class TestRegroupLotPositions:
    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.lot_repo = FakeProductionLotRepository()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.WRITE_LOTS])

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
        saved_position = await self.lot_repo.save_position(position)
        self.step_ids = []
        for seq in (1, 2, 3):
            step = await self.lot_repo.save_step(
                LotStep(
                    id=0,
                    created=date(2026, 1, 1),
                    note=None,
                    estimated_setup_minutes=None,
                    estimated_minutes_per_piece=None,
                    sequence=seq,
                    creator_id=1,
                    fabrication_method_id=1,
                    lot_id=self.lot.id,
                    position_id=saved_position.id,
                    source_process_id=None,
                )
            )
            self.step_ids.append(step.id)

    async def test_splits_into_two_contiguous_positions(self):
        use_case = RegroupLotPositions(
            self.lot_repo, uow=self.uow, reconciler=lot_reconciler(self.lot_repo)
        )
        result = await use_case.execute(
            self.actor,
            self.lot.id,
            RegroupLotPositionsCommand(
                groups=[[self.step_ids[0]], [self.step_ids[1], self.step_ids[2]]]
            ),
        )
        assert len(result) == 2
        assert [p.sequence for p in result] == [1, 2]
        assert len(result[0].steps) == 1
        assert len(result[1].steps) == 2
        # Steps themselves survive regrouping (only reassigned, never deleted).
        assert await self.lot_repo.get_step_by_id(self.step_ids[0]) is not None

    async def test_regroup_still_splits_when_order_item_repo_has_no_match(self):
        """order_item_repo wired but reports no match: unaffected."""
        order_item_repo = FakeOrderItemRepository()
        use_case = RegroupLotPositions(
            self.lot_repo,
            order_item_repo=order_item_repo,
            uow=self.uow,
            reconciler=lot_reconciler(self.lot_repo),
        )
        result = await use_case.execute(
            self.actor,
            self.lot.id,
            RegroupLotPositionsCommand(
                groups=[[self.step_ids[0]], [self.step_ids[1], self.step_ids[2]]]
            ),
        )
        assert len(result) == 2

    async def test_regroup_blocked_when_removed_position_referenced_by_order_item(self):
        original_position_id = (await self.lot_repo.get_positions(self.lot.id))[0].id
        order_item = make_order_item(id=1, lot_position_id=original_position_id)
        order_item_repo = FakeOrderItemRepository([order_item])
        use_case = RegroupLotPositions(
            self.lot_repo,
            order_item_repo=order_item_repo,
            uow=self.uow,
            reconciler=lot_reconciler(self.lot_repo),
        )
        with pytest.raises(LotPositionInUseError):
            await use_case.execute(
                self.actor,
                self.lot.id,
                RegroupLotPositionsCommand(
                    groups=[[self.step_ids[0]], [self.step_ids[1], self.step_ids[2]]]
                ),
            )

    async def test_non_contiguous_grouping_raises(self):
        use_case = RegroupLotPositions(
            self.lot_repo, uow=self.uow, reconciler=lot_reconciler(self.lot_repo)
        )
        with pytest.raises(LotPositionGroupingInvalidError):
            await use_case.execute(
                self.actor,
                self.lot.id,
                RegroupLotPositionsCommand(
                    groups=[[self.step_ids[0], self.step_ids[2]], [self.step_ids[1]]]
                ),
            )

    async def test_regroup_requires_write_lots(self):
        permissionless = make_user(permissions=[])
        before = [p.id for p in await self.lot_repo.get_positions(self.lot.id)]
        use_case = RegroupLotPositions(
            self.lot_repo, uow=self.uow, reconciler=lot_reconciler(self.lot_repo)
        )
        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(
                permissionless,
                self.lot.id,
                RegroupLotPositionsCommand(
                    groups=[[self.step_ids[0]], [self.step_ids[1], self.step_ids[2]]]
                ),
            )
        # Positions unchanged.
        assert [p.id for p in await self.lot_repo.get_positions(self.lot.id)] == before

    async def test_missing_step_raises(self):
        use_case = RegroupLotPositions(
            self.lot_repo, uow=self.uow, reconciler=lot_reconciler(self.lot_repo)
        )
        with pytest.raises(LotPositionGroupingInvalidError):
            await use_case.execute(
                self.actor,
                self.lot.id,
                RegroupLotPositionsCommand(groups=[[self.step_ids[0], self.step_ids[1]]]),
            )

    async def test_regroup_preserves_assigned_qa_singleton_with_unchanged_group(self):
        # A born-INTERNAL QA singleton (create_lot._auto_queue_inspection_
        # position) whose group is submitted unchanged must ride along
        # untouched while the fabrication steps regroup around it, not
        # reject the whole regroup.
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
                sequence=4,
                creator_id=1,
                fabrication_method_id=None,
                lot_id=self.lot.id,
                position_id=qa_position.id,
                source_process_id=None,
                role=StepRole.INSPECTION,
                inspection_method_id=1,
            )
        )

        # Its auto-queued order is what keeps it internal.
        orders = FakeProductionOrderRepository(
            [
                make_production_order(
                    1, qa_position.id, status=ProductionOrderStatus.QUEUED, quantity=5.0
                )
            ]
        )

        use_case = RegroupLotPositions(
            self.lot_repo, uow=self.uow, reconciler=lot_reconciler(self.lot_repo, orders)
        )
        result = await use_case.execute(
            self.actor,
            self.lot.id,
            RegroupLotPositionsCommand(
                groups=[
                    [self.step_ids[0]],
                    [self.step_ids[1], self.step_ids[2]],
                    [qa_step.id],
                ]
            ),
        )

        assert len(result) == 3
        assert [p.sequence for p in result] == [1, 2, 3]
        # Same row survived (not deleted and recreated) and stayed internal.
        preserved = await self.lot_repo.get_position_by_id(qa_position.id)
        assert preserved is not None
        assert preserved.kind == "internal"
        assert preserved.sequence == 3
        assert (await self.lot_repo.get_step_by_id(qa_step.id)).position_id == qa_position.id

    async def test_regroup_rejects_changing_an_assigned_position_membership(self):
        # Splitting an assigned position's own steps is still rejected;
        # only positions whose membership is UNCHANGED are preserved.
        existing_position = (await self.lot_repo.get_positions(self.lot.id))[0]
        existing_position.kind = LotPositionKind.INTERNAL
        await self.lot_repo.save_position(existing_position)

        use_case = RegroupLotPositions(
            self.lot_repo, uow=self.uow, reconciler=lot_reconciler(self.lot_repo)
        )
        with pytest.raises(LotPositionAlreadyAssignedError):
            await use_case.execute(
                self.actor,
                self.lot.id,
                RegroupLotPositionsCommand(
                    groups=[[self.step_ids[0]], [self.step_ids[1], self.step_ids[2]]]
                ),
            )

    async def test_regroup_rejects_already_assigned_position(self):
        existing_position = (await self.lot_repo.get_positions(self.lot.id))[0]
        existing_position.kind = LotPositionKind.EXTERNAL
        await self.lot_repo.save_position(existing_position)

        use_case = RegroupLotPositions(
            self.lot_repo, uow=self.uow, reconciler=lot_reconciler(self.lot_repo)
        )
        with pytest.raises(LotPositionAlreadyAssignedError):
            await use_case.execute(
                self.actor,
                self.lot.id,
                RegroupLotPositionsCommand(
                    groups=[[self.step_ids[0]], [self.step_ids[1], self.step_ids[2]]]
                ),
            )

    async def test_regroup_allowed_at_any_non_terminal_status(self):
        self.lot.status = LotStatus.PLANNED
        await self.lot_repo.save(self.lot)
        use_case = RegroupLotPositions(
            self.lot_repo, uow=self.uow, reconciler=lot_reconciler(self.lot_repo)
        )
        result = await use_case.execute(
            self.actor,
            self.lot.id,
            RegroupLotPositionsCommand(
                groups=[[self.step_ids[0]], [self.step_ids[1], self.step_ids[2]]]
            ),
        )
        assert len(result) == 2


class TestAppendLotPosition:
    async def test_appends_at_any_non_terminal_status(self):
        lot_repo = FakeProductionLotRepository()
        fabrication_methods = FakeFabricationMethodRepository([make_fabrication_method(1)])
        inspection_methods = FakeInspectionMethodRepository([make_inspection_method(1)])
        uow = FakeUnitOfWork()
        actor = make_user(permissions=[Permission.WRITE_LOTS])

        lot = ProductionLot(
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
        lot = await lot_repo.save(lot)

        use_case = AppendLotPosition(
            lot_repo,
            fabrication_methods,
            inspection_methods,
            uow=uow,
            reconciler=lot_reconciler(lot_repo),
        )
        result = await use_case.execute(
            actor,
            lot.id,
            AppendLotPositionCommand(steps=[AppendLotPositionStepInput(fabrication_method_id=1)]),
        )
        assert result.sequence == 1
        assert result.kind == "unassigned"
        assert len(result.steps) == 1

    async def test_append_requires_write_lots(self):
        lot_repo, lot, _ = await self._lot_for_append()
        fabrication_methods = FakeFabricationMethodRepository([make_fabrication_method(1)])
        inspection_methods = FakeInspectionMethodRepository([make_inspection_method(1)])
        uow = FakeUnitOfWork()
        permissionless = make_user(permissions=[])
        use_case = AppendLotPosition(
            lot_repo,
            fabrication_methods,
            inspection_methods,
            uow=uow,
            reconciler=lot_reconciler(lot_repo),
        )
        with pytest.raises(InsufficientPermissionsError):
            await use_case.execute(
                permissionless,
                lot.id,
                AppendLotPositionCommand(
                    steps=[AppendLotPositionStepInput(fabrication_method_id=1)]
                ),
            )
        # No position created.
        assert await lot_repo.get_positions(lot.id) == []

    async def _lot_for_append(self) -> tuple[FakeProductionLotRepository, ProductionLot, User]:
        lot_repo = FakeProductionLotRepository()
        actor = make_user(permissions=[Permission.WRITE_LOTS])
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
        return lot_repo, await lot_repo.save(lot), actor

    async def test_appends_a_lone_inspection_step(self):
        lot_repo, lot, actor = await self._lot_for_append()
        fabrication_methods = FakeFabricationMethodRepository([make_fabrication_method(1)])
        inspection_methods = FakeInspectionMethodRepository([make_inspection_method(1)])
        uow = FakeUnitOfWork()
        use_case = AppendLotPosition(
            lot_repo,
            fabrication_methods,
            inspection_methods,
            uow=uow,
            reconciler=lot_reconciler(lot_repo),
        )
        result = await use_case.execute(
            actor,
            lot.id,
            AppendLotPositionCommand(
                steps=[
                    AppendLotPositionStepInput(
                        role=StepRole.INSPECTION.value,
                        inspection_method_id=1,
                    )
                ]
            ),
        )
        assert len(result.steps) == 1
        assert result.steps[0].role == "inspection"
        assert result.steps[0].inspection_method_id == 1
        assert result.steps[0].fabrication_method_id is None

    async def test_mixed_append_with_inspection_step_raises(self):
        lot_repo, lot, actor = await self._lot_for_append()
        fabrication_methods = FakeFabricationMethodRepository([make_fabrication_method(1)])
        inspection_methods = FakeInspectionMethodRepository([make_inspection_method(1)])
        uow = FakeUnitOfWork()
        use_case = AppendLotPosition(
            lot_repo,
            fabrication_methods,
            inspection_methods,
            uow=uow,
            reconciler=lot_reconciler(lot_repo),
        )
        with pytest.raises(LotPositionGroupingInvalidError):
            await use_case.execute(
                actor,
                lot.id,
                AppendLotPositionCommand(
                    steps=[
                        AppendLotPositionStepInput(fabrication_method_id=1),
                        AppendLotPositionStepInput(
                            role=StepRole.INSPECTION.value,
                            inspection_method_id=1,
                        ),
                    ]
                ),
            )
