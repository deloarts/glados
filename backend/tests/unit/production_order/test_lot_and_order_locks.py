"""
RecordProductionOrderCompletion and ScrapProductionPieces take their row
locks in the shared order, the lot first and then the production order, and
read what they check only after both: the order's status, the processed total
behind the cap, and the position they update. The fakes stand in for a commit
that lands between the unlocked pre-check and the lock. No database, no HTTP.
"""

import dataclasses
from datetime import UTC
from datetime import date
from datetime import datetime

import pytest

from src.modules.fulfillment.application.dto.production_order_dto import (
    RecordProductionOrderCompletionCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    ScrapProductionPiecesCommand,
)
from src.modules.fulfillment.application.use_cases.production_order.record_production_order_completion import (
    RecordProductionOrderCompletion,
)
from src.modules.fulfillment.application.use_cases.production_order.scrap_production_pieces import (
    ScrapProductionPieces,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)
from src.modules.fulfillment.domain.errors import ProductionOrderInvalidStatusTransitionError
from src.modules.fulfillment.domain.errors import ProductionOrderQuantityOverflowError
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.production_lot._helpers import NoLotCreation
from tests.unit.production_lot._helpers import RecordingLotCreation
from tests.unit.production_lot.fakes import FakeMadeItemAllocationRepository
from tests.unit.production_lot.fakes import FakeMadeItemDemandRepository
from tests.unit.production_lot.fakes import completion_collaborators
from tests.unit.production_lot.fakes import disposition_collaborators
from tests.unit.production_order._helpers import make_lot
from tests.unit.production_order._helpers import make_order
from tests.unit.production_order._helpers import make_position
from tests.unit.production_order.fakes import FakeEventBus
from tests.unit.production_order.fakes import FakeProductionLotRepository
from tests.unit.production_order.fakes import FakeProductionOrderFileRepository
from tests.unit.production_order.fakes import FakeProductionOrderInterruptionRepository
from tests.unit.production_order.fakes import FakeProductionOrderRepository
from tests.unit.production_order.fakes import FakeUnitOfWork
from tests.unit.production_order.fakes import production_order_reconciler


class _LoggingLotRepository(FakeProductionLotRepository):
    def __init__(self, lots: list[ProductionLot], calls: list[str]) -> None:
        super().__init__(lots)
        self._calls = calls

    async def get_by_id_for_update(self, id: int) -> ProductionLot | None:
        self._calls.append(f"lock lot {id}")
        return await super().get_by_id_for_update(id)


class _LoggingOrderRepository(FakeProductionOrderRepository):
    def __init__(self, orders: list[ProductionOrder], calls: list[str]) -> None:
        super().__init__(orders)
        self._calls = calls

    async def get_by_id_for_update(self, id: int) -> ProductionOrder | None:
        self._calls.append(f"lock order {id}")
        return await super().get_by_id_for_update(id)

    async def get_completions(self, production_order_id: int) -> list[ProductionOrderCompletion]:
        self._calls.append(f"read completions {production_order_id}")
        return await super().get_completions(production_order_id)

    async def save(self, order: ProductionOrder) -> ProductionOrder:
        self._calls.append(f"save order {order.id}")
        return await super().save(order)


class _LeftInProgressBeforeTheLock(FakeProductionOrderRepository):
    """A cancel or a pause commits after the unlocked pre-check saw the order
    IN_PROGRESS and before this request takes the lock."""

    def __init__(self, orders: list[ProductionOrder], status: ProductionOrderStatus) -> None:
        super().__init__(orders)
        self._status = status

    async def get_by_id_for_update(self, id: int) -> ProductionOrder | None:
        order = await super().get_by_id_for_update(id)
        assert order is not None
        order.status = self._status
        return order


class _CompletedBeforeTheLock(FakeProductionOrderRepository):
    """Another terminal's completion of 6 commits after the unlocked
    pre-check and before this request takes the lock."""

    async def get_by_id_for_update(self, id: int) -> ProductionOrder | None:
        order = await super().get_by_id_for_update(id)
        assert order is not None
        await self.save_completion(
            ProductionOrderCompletion(
                id=0,
                production_order_id=order.id,
                quantity=6.0,
                quantity_accepted=6.0,
                quantity_rejected=0.0,
                quantity_rework=0.0,
                quantity_scrap=0.0,
                scrap_reason=None,
                completion_date=date(2026, 1, 2),
                note=None,
                operator_id=2,
                recorded_by_id=2,
                created=datetime(2026, 1, 2, 9, 0, tzinfo=UTC),
            )
        )
        order.quantity_completed = 6.0
        return order


class _CopyingPositionReads(FakeProductionLotRepository):
    """Hands out a copy of the position on the unlocked read, as a session
    does once the locked read has refreshed the row: only the lot's own
    position object reaches the database."""

    async def get_position_by_id(self, position_id: int) -> LotPosition | None:
        position = await super().get_position_by_id(position_id)
        return dataclasses.replace(position) if position else None

    def stored_position(self, position_id: int) -> LotPosition | None:
        """The object the last save_position call stored."""
        return self._positions.get(position_id)


def _running_order() -> ProductionOrder:
    return make_order(
        id=1, lot_position_id=1, quantity=10.0, status=ProductionOrderStatus.IN_PROGRESS
    )


class _LockTestBase:
    def setup_method(self) -> None:
        self.position = make_position(id=1, quantity=10.0, kind=LotPositionKind.INTERNAL)
        self.lot = make_lot(positions=[self.position])
        # A rework lot, so position 1 is not gated on raw material.
        self.lot.source_made_item_id = 99
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.WRITE_PRODUCTION_ORDERS])


class TestCompletionLocks(_LockTestBase):
    def _use_case(
        self, order_repo: FakeProductionOrderRepository, lot_repo: FakeProductionLotRepository
    ) -> RecordProductionOrderCompletion:
        return RecordProductionOrderCompletion(
            order_repo,
            lot_repo,
            FakeProductionOrderFileRepository(),
            event_bus=self.bus,
            uow=self.uow,
            reconciler=production_order_reconciler(order_repo, lot_repo, self.bus),
            made_item_demand_repo=FakeMadeItemDemandRepository(),
            made_item_allocation_repo=FakeMadeItemAllocationRepository(),
            create_lot=NoLotCreation(),
            **completion_collaborators(order_repo),
        )

    @staticmethod
    def _cmd(quantity: float) -> RecordProductionOrderCompletionCommand:
        return RecordProductionOrderCompletionCommand(
            quantity=quantity, completion_date=date(2026, 1, 2)
        )

    async def test_locks_the_lot_then_the_order_before_reading_the_processed_total(self):
        calls: list[str] = []
        order_repo = _LoggingOrderRepository([_running_order()], calls)
        lot_repo = _LoggingLotRepository([self.lot], calls)

        await self._use_case(order_repo, lot_repo).execute(
            self.actor, production_order_id=1, cmd=self._cmd(3.0)
        )

        # The second save is the reconciler writing the completed count it
        # derives from the new row.
        assert calls == [
            "lock lot 1",
            "lock order 1",
            "read completions 1",
            "save order 1",
            "save order 1",
        ]

    async def test_an_order_canceled_after_the_pre_check_is_refused_under_the_lock(self):
        order_repo = _LeftInProgressBeforeTheLock(
            [_running_order()], ProductionOrderStatus.CANCELED
        )
        lot_repo = FakeProductionLotRepository([self.lot])

        with pytest.raises(ProductionOrderInvalidStatusTransitionError):
            await self._use_case(order_repo, lot_repo).execute(
                self.actor, production_order_id=1, cmd=self._cmd(3.0)
            )

        assert await order_repo.get_completions(1) == []
        assert self.position.quantity_completed == 0.0
        assert self.uow.commits == 0

    async def test_a_completion_committed_after_the_pre_check_counts_toward_the_cap(self):
        order_repo = _CompletedBeforeTheLock([_running_order()])
        lot_repo = FakeProductionLotRepository([self.lot])

        with pytest.raises(ProductionOrderQuantityOverflowError):
            await self._use_case(order_repo, lot_repo).execute(
                self.actor, production_order_id=1, cmd=self._cmd(6.0)
            )

        assert [c.quantity for c in await order_repo.get_completions(1)] == [6.0]
        order = await order_repo.get_by_id(1)
        assert order is not None
        assert order.quantity_completed == 6.0
        assert self.uow.commits == 0

    async def test_updates_the_locked_lots_own_position_object(self):
        order_repo = FakeProductionOrderRepository([_running_order()])
        lot_repo = _CopyingPositionReads([self.lot])

        await self._use_case(order_repo, lot_repo).execute(
            self.actor, production_order_id=1, cmd=self._cmd(3.0)
        )

        assert lot_repo.stored_position(1) is self.position
        assert self.position.quantity_completed == 3.0


class TestScrapLocks(_LockTestBase):
    def _use_case(
        self, order_repo: FakeProductionOrderRepository, lot_repo: FakeProductionLotRepository
    ) -> ScrapProductionPieces:
        return ScrapProductionPieces(
            order_repo,
            lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            reconciler=production_order_reconciler(order_repo, lot_repo, self.bus),
            interruption_repo=FakeProductionOrderInterruptionRepository(order_repo._orders),
            **disposition_collaborators(),
            made_item_demand_repo=FakeMadeItemDemandRepository(),
            made_item_allocation_repo=FakeMadeItemAllocationRepository(),
            create_lot=RecordingLotCreation(),
        )

    @staticmethod
    def _cmd(quantity: float) -> ScrapProductionPiecesCommand:
        return ScrapProductionPiecesCommand(
            production_order_id=1, quantity=quantity, reason="tool_breakage"
        )

    async def test_locks_the_lot_then_the_order_before_reading_the_processed_total(self):
        calls: list[str] = []
        order_repo = _LoggingOrderRepository([_running_order()], calls)
        lot_repo = _LoggingLotRepository([self.lot], calls)

        await self._use_case(order_repo, lot_repo).execute(self.actor, self._cmd(1.0))

        assert calls == ["lock lot 1", "lock order 1", "read completions 1", "save order 1"]

    async def test_an_order_paused_after_the_pre_check_is_refused_under_the_lock(self):
        order_repo = _LeftInProgressBeforeTheLock([_running_order()], ProductionOrderStatus.PAUSED)
        lot_repo = FakeProductionLotRepository([self.lot])

        with pytest.raises(ProductionOrderInvalidStatusTransitionError):
            await self._use_case(order_repo, lot_repo).execute(self.actor, self._cmd(1.0))

        assert await order_repo.get_completions(1) == []
        assert self.lot.quantity == 10.0
        assert self.uow.commits == 0
