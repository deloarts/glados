"""
AssignExternalPosition checks the position again on the locked lot's own
position object, so an assignment or a production order committed between
its unlocked checks and the lot lock counts. The lot fake hands out a copy of
the position on the unlocked read, as a session does once the locked read has
refreshed the row, and applies the concurrent change when the lot is locked.
No database, no HTTP.
"""

import dataclasses
from collections.abc import Callable
from datetime import date

import pytest

from src.modules.fulfillment.application.dto.production_lot_dto import AssignExternalPositionCommand
from src.modules.fulfillment.application.use_cases.production_lot.assign_external_position import (
    AssignExternalPosition,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.errors import LotPositionAlreadyAssignedError
from src.modules.fulfillment.domain.errors import LotPositionQuantityExceedsRemainingError
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.lifecycle.fake_reconciler import order_reconciler
from tests.unit.production_lot._helpers import make_made_item
from tests.unit.production_lot._helpers import make_order
from tests.unit.production_lot._helpers import make_production_order
from tests.unit.production_lot.fakes import FakeEventBus
from tests.unit.production_lot.fakes import FakeMadeItemRepository
from tests.unit.production_lot.fakes import FakeOrderItemRepository
from tests.unit.production_lot.fakes import FakeOrderRepository
from tests.unit.production_lot.fakes import FakeProductionLotRepository
from tests.unit.production_lot.fakes import FakeProjectRepository
from tests.unit.production_lot.fakes import FakeUnitOfWork


class _ChangedBeforeTheLock(FakeProductionLotRepository):
    def __init__(self, change: Callable[[LotPosition], None]) -> None:
        super().__init__()
        self._change = change

    async def get_position_by_id(self, position_id: int) -> LotPosition | None:
        position = await super().get_position_by_id(position_id)
        return dataclasses.replace(position) if position else None

    async def get_by_id_for_update(self, id: int) -> ProductionLot | None:
        lot = await super().get_by_id_for_update(id)
        if lot is not None:
            for position in lot.positions:
                self._change(position)
        return lot


def _assigned_to_another_order(position: LotPosition) -> None:
    position.order_item_id = 99
    position.kind = LotPositionKind.EXTERNAL


def _queued_internally(position: LotPosition) -> None:
    position.kind = LotPositionKind.INTERNAL
    position.production_orders = [
        make_production_order(7, position.id, status=ProductionOrderStatus.QUEUED, quantity=5.0)
    ]


class TestAssignExternalPositionUnderTheLock:
    def setup_method(self) -> None:
        self.made_item_repo = FakeMadeItemRepository([make_made_item()])
        self.order_repo = FakeOrderRepository([make_order(id=1, supplier_id=7)])
        self.order_item_repo = FakeOrderItemRepository()
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.WRITE_LOTS, Permission.WRITE_ORDERS])

    async def _seed(self, lot_repo: FakeProductionLotRepository) -> tuple[int, int]:
        lot = await lot_repo.save(
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
        position = await lot_repo.save_position(
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
                lot_id=lot.id,
            )
        )
        return lot.id, position.id

    def _use_case(self, lot_repo: FakeProductionLotRepository) -> AssignExternalPosition:
        return AssignExternalPosition(
            lot_repo,
            self.made_item_repo,
            self.order_repo,
            self.order_item_repo,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=order_reconciler(self.order_repo, self.order_item_repo),
            project_repo=FakeProjectRepository(),
        )

    async def test_an_assignment_committed_before_the_lock_is_refused(self):
        lot_repo = _ChangedBeforeTheLock(_assigned_to_another_order)
        lot_id, position_id = await self._seed(lot_repo)

        with pytest.raises(LotPositionAlreadyAssignedError):
            await self._use_case(lot_repo).execute(
                self.actor,
                lot_id,
                position_id,
                AssignExternalPositionCommand(order_id=1, unit="pcs"),
            )

        assert await self.order_item_repo.get_by_lot_position_id(position_id) is None
        assert self.uow.commits == 0

    async def test_production_orders_queued_before_the_lock_count_toward_the_remainder(self):
        lot_repo = _ChangedBeforeTheLock(_queued_internally)
        lot_id, position_id = await self._seed(lot_repo)

        with pytest.raises(LotPositionQuantityExceedsRemainingError):
            await self._use_case(lot_repo).execute(
                self.actor,
                lot_id,
                position_id,
                AssignExternalPositionCommand(order_id=1, unit="pcs", quantity=5.0),
            )

        assert await self.order_item_repo.get_by_lot_position_id(position_id) is None
        assert self.uow.commits == 0
