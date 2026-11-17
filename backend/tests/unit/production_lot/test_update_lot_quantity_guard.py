"""
UpdateLot refuses a DRAFT lot's quantity below what made demands have
allocated to the lot, and reads the lot with its row lock. No database, no
HTTP, in-memory fakes only.
"""

from datetime import date

import pytest

from src.modules.fulfillment.application.dto.production_lot_dto import UpdateLotCommand
from src.modules.fulfillment.application.use_cases.production_lot.update_lot import UpdateLot
from src.modules.fulfillment.domain.entities.made_item_allocation import MadeItemDemandAllocation
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.errors import AllocationOverflowError
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.production_lot.fakes import FakeMadeItemAllocationRepository
from tests.unit.production_lot.fakes import FakeProductionLotRepository
from tests.unit.production_lot.fakes import FakeProductionOrderRepository
from tests.unit.production_lot.fakes import FakeUnitOfWork
from tests.unit.production_lot.fakes import lot_reconciler


class TestUpdateLotQuantityGuard:
    async def _setup(self, quantity: float, allocated: list[float]) -> ProductionLot:
        self.lot_repo = FakeProductionLotRepository()
        lot = await self.lot_repo.save(
            ProductionLot(
                id=0,
                created=date(2026, 1, 1),
                changed=None,
                changes=[],
                lot_number="LOT-1",
                quantity=quantity,
                status=LotStatus.DRAFT,
                priority=UrgencyClass.NORMAL,
                note=None,
                creator_id=1,
                made_item_id=1,
                project_id=1,
                input_demand_id=None,
            )
        )
        allocations = [
            MadeItemDemandAllocation(demand_item_id=index + 1, lot_id=lot.id, quantity=q)
            for index, q in enumerate(allocated)
        ]
        self.uow = FakeUnitOfWork()
        self.use_case = UpdateLot(
            lot_repo=self.lot_repo,
            order_repo=FakeProductionOrderRepository(),
            uow=self.uow,
            made_allocation_repo=FakeMadeItemAllocationRepository(allocations),
            reconciler=lot_reconciler(self.lot_repo),
        )
        self.actor = make_user(permissions=[Permission.WRITE_LOTS])
        return lot

    async def test_a_lot_cut_below_its_allocations_is_refused(self):
        # A lot of 10 allocated 10 is cut to 5.
        lot = await self._setup(quantity=10.0, allocated=[6.0, 4.0])

        with pytest.raises(AllocationOverflowError, match="allocated to demands"):
            await self.use_case.execute(self.actor, lot.id, UpdateLotCommand(quantity=5.0))

        assert (await self.lot_repo.get_by_id(lot.id)).quantity == 10.0
        assert not self.uow.committed

    async def test_a_lot_cut_down_to_its_allocations_is_accepted(self):
        lot = await self._setup(quantity=12.0, allocated=[6.0, 4.0])

        result = await self.use_case.execute(self.actor, lot.id, UpdateLotCommand(quantity=10.0))

        assert result.quantity == 10.0
        assert self.uow.committed

    async def test_raising_a_lot_is_accepted(self):
        lot = await self._setup(quantity=10.0, allocated=[10.0])

        result = await self.use_case.execute(self.actor, lot.id, UpdateLotCommand(quantity=15.0))

        assert result.quantity == 15.0

    async def test_a_note_edit_on_an_over_allocated_lot_is_accepted(self):
        lot = await self._setup(quantity=5.0, allocated=[10.0])

        result = await self.use_case.execute(
            self.actor, lot.id, UpdateLotCommand(quantity=5.0, note="Rush")
        )

        assert result.note == "Rush"
        assert result.quantity == 5.0

    async def test_the_lot_is_read_with_the_lock(self):
        lot = await self._setup(quantity=10.0, allocated=[])

        await self.use_case.execute(self.actor, lot.id, UpdateLotCommand(quantity=8.0))

        assert self.lot_repo.for_update_calls == [lot.id]
