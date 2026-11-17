"""
Unit tests for ProductionLot.completed_at, which the lifecycle reconciler
keeps set exactly while the lot is COMPLETED: stamped when CompleteLot
force-completes a lot, cleared when ResumeLot leaves a lot that is not
complete. The stamp of a lot its positions complete is covered with the
stored fields (lifecycle/test_stored_fields.py). No database, no HTTP,
dependencies replaced with in-memory fakes.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

import pytest

from src.modules.fulfillment.application.dto.production_lot_dto import CompleteLotCommand
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import CompleteLot
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import ResumeLot
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.production_lot._helpers import make_production_order
from tests.unit.production_lot.fakes import FakeBoughtItemAllocationRepository
from tests.unit.production_lot.fakes import FakeEventBus
from tests.unit.production_lot.fakes import FakeMadeItemAllocationRepository
from tests.unit.production_lot.fakes import FakeMadeItemDemandRepository
from tests.unit.production_lot.fakes import FakeOrderItemRepository
from tests.unit.production_lot.fakes import FakeOrderRepository
from tests.unit.production_lot.fakes import FakeProductionLotRepository
from tests.unit.production_lot.fakes import FakeProductionOrderRepository
from tests.unit.production_lot.fakes import FakeSourceItemAllocationRepository
from tests.unit.production_lot.fakes import FakeSourceItemDemandRepository
from tests.unit.production_lot.fakes import FakeUnitOfWork
from tests.unit.production_order.fakes import lifecycle_collaborators


def _make_lot(**overrides) -> ProductionLot:
    fields = {
        "id": 0,
        "created": date(2026, 1, 1),
        "changed": None,
        "changes": [],
        "lot_number": "LOT-CAT-1",
        "quantity": 5.0,
        "status": LotStatus.IN_PROGRESS,
        "priority": UrgencyClass.NORMAL,
        "note": None,
        "creator_id": 1,
        "made_item_id": 1,
        "project_id": 1,
        "input_demand_id": None,
    }
    fields.update(overrides)
    return ProductionLot(**fields)


class TestCompleteLotStampsCompletedAt:
    @pytest.fixture(autouse=True)
    async def _setup(self):
        self.lot_repo = FakeProductionLotRepository()
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.WRITE_LOTS, Permission.MANAGE_LOTS])
        self.lot = await self.lot_repo.save(_make_lot())
        # Two of five pieces made, so the lot has something to close at.
        position = await self.lot_repo.save_position(
            LotPosition(
                id=0,
                created=date(2026, 1, 1),
                changed=None,
                changes=[],
                sequence=1,
                kind=LotPositionKind.INTERNAL,
                status=LotPositionStatus.PARTIALLY_COMPLETED,
                quantity=5.0,
                quantity_completed=2.0,
                note=None,
                creator_id=1,
                lot_id=self.lot.id,
            )
        )
        self.order = make_production_order(1, position.id, quantity=5.0)
        self.order.quantity_completed = 2.0
        self.order.completions = [
            ProductionOrderCompletion(
                id=1,
                production_order_id=1,
                quantity=2.0,
                quantity_accepted=2.0,
                quantity_rejected=0.0,
                completion_date=date(2026, 1, 2),
                note=None,
                operator_id=1,
                recorded_by_id=1,
                created=datetime(2026, 1, 2, tzinfo=UTC),
            )
        ]

    async def test_force_complete_sets_completed_at(self):
        order_repo = FakeProductionOrderRepository([self.order])
        use_case = CompleteLot(
            self.lot_repo,
            order_repo,
            FakeOrderItemRepository(),
            event_bus=self.bus,
            uow=self.uow,
            parent_order_repo=FakeOrderRepository([]),
            made_item_demand_repo=FakeMadeItemDemandRepository(),
            made_item_allocation_repo=FakeMadeItemAllocationRepository(),
            **lifecycle_collaborators(order_repo, self.lot_repo, self.bus),
            source_item_demand_repo=FakeSourceItemDemandRepository(),
            source_item_allocation_repo=FakeSourceItemAllocationRepository(),
            bought_allocation_repo=FakeBoughtItemAllocationRepository(),
        )
        result = await use_case.execute(self.actor, self.lot.id, CompleteLotCommand())
        assert result.status == LotStatus.COMPLETED.value
        assert result.completed_at is not None


class TestResumeLotClearsCompletedAt:
    async def test_resume_clears_a_stale_completed_at(self):
        """Defensive: a lot on hold has no completed_at, since COMPLETED wins
        over the hold in the lot derivation, but ResumeLot clears completed_at
        unconditionally rather than assume that invariant holds forever."""
        lot_repo = FakeProductionLotRepository()
        bus = FakeEventBus()
        uow = FakeUnitOfWork()
        actor = make_user(permissions=[Permission.WRITE_LOTS])
        lot = await lot_repo.save(
            _make_lot(
                status=LotStatus.ON_HOLD,
                completed_at=datetime(2026, 1, 2, tzinfo=UTC),
            )
        )

        order_repo = FakeProductionOrderRepository()
        use_case = ResumeLot(
            lot_repo,
            order_repo,
            event_bus=bus,
            uow=uow,
            **lifecycle_collaborators(order_repo, lot_repo, bus),
        )
        result = await use_case.execute(actor, lot.id)

        assert result.completed_at is None
