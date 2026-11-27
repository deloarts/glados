"""
A lot hold pauses the lot's running orders by an interruption of the hold,
and the lot's resume ends exactly those, so an order an operator paused by
hand stays paused and the hold does not count as work time. The force
cancel and force complete cascades close every interruption still open on
the orders they end. The lifecycle reconciler derives every order status
from these facts and publishes the status events. A settable clock stands
in for the datetime class of the clock module, which every now_utc() call
reads; every other dependency is an in-memory fake.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import tzinfo

import pytest

from src.modules.fulfillment.application.dto.production_lot_dto import CancelLotCommand
from src.modules.fulfillment.application.dto.production_lot_dto import CompleteLotCommand
from src.modules.fulfillment.application.dto.production_lot_dto import HoldLotCommand
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import CancelLot
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import CompleteLot
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import HoldLot
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import ResumeLot
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderCanceled
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderCompleted
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderPaused
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderResumed
from src.modules.fulfillment.domain.events.production_order_events import (
    ProductionOrderStatusChanged,
)
from src.modules.fulfillment.domain.services.production_time_rules import net_work_minutes
from src.modules.fulfillment.domain.value_objects.interruption_ended_by import InterruptionEndedBy
from src.modules.fulfillment.domain.value_objects.interruption_reason import InterruptionReason
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.domain.value_objects.permission import Permission
from src.shared_kernel.domain.services import clock as clock_module
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

_MANUAL = InterruptionReason.MANUAL
_LOT_HOLD = InterruptionReason.LOT_HOLD
_QUEUED = ProductionOrderStatus.QUEUED
_IN_PROGRESS = ProductionOrderStatus.IN_PROGRESS
_PAUSED = ProductionOrderStatus.PAUSED
_COMPLETED = ProductionOrderStatus.COMPLETED
_CANCELED = ProductionOrderStatus.CANCELED


def _at(hour: int, minute: int = 0) -> datetime:
    """An instant on the day the seeded orders started, at 08:00 UTC."""
    return datetime(2026, 1, 1, hour, minute, tzinfo=UTC)


class _Clock(datetime):
    """Stands in for the datetime class of the clock module, so every
    now_utc() call returns the instant the test set last."""

    current = _at(9)

    @classmethod
    def now(cls, tz: tzinfo | None = None) -> datetime:
        return cls.current


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> type[_Clock]:
    monkeypatch.setattr(_Clock, "current", _at(9))
    monkeypatch.setattr(clock_module, "datetime", _Clock)
    return _Clock


class TestHoldAndResume:
    """Order 1 runs, order 2 waits in the queue, order 3 was paused by hand
    at 10:00; both started at 08:00."""

    @pytest.fixture(autouse=True)
    async def _floor(self, clock: type[_Clock]) -> None:
        self.clock = clock
        self.lot_repo = FakeProductionLotRepository()
        self.lot = await self.lot_repo.save(
            ProductionLot(
                id=0,
                created=date(2026, 1, 1),
                changed=None,
                changes=[],
                lot_number="LOT-HOLD",
                quantity=15.0,
                status=LotStatus.IN_PROGRESS,
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
                kind=LotPositionKind.INTERNAL,
                status=LotPositionStatus.IN_PROGRESS,
                quantity=15.0,
                quantity_completed=0.0,
                note=None,
                creator_id=1,
                lot_id=self.lot.id,
            )
        )
        self.order_repo = FakeProductionOrderRepository(
            [
                make_production_order(1, self.position.id, status=_IN_PROGRESS),
                make_production_order(2, self.position.id, status=_QUEUED),
                make_production_order(3, self.position.id, status=_PAUSED),
            ]
        )
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(id=5, permissions=[Permission.WRITE_LOTS, Permission.MANAGE_LOTS])

    def order(self, order_id: int) -> ProductionOrder:
        return self.order_repo._orders[order_id]

    def _collaborators(self) -> dict[str, object]:
        """A request's reconciler and interruption repository."""
        return lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus)

    async def hold(self, at: datetime) -> None:
        self.clock.current = at
        await HoldLot(
            self.lot_repo,
            self.order_repo,
            event_bus=self.bus,
            uow=self.uow,
            **self._collaborators(),
        ).execute(self.actor, self.lot.id, HoldLotCommand(reason="Material check"))

    async def resume(self, at: datetime) -> None:
        self.clock.current = at
        await ResumeLot(
            self.lot_repo,
            self.order_repo,
            event_bus=self.bus,
            uow=self.uow,
            **self._collaborators(),
        ).execute(self.actor, self.lot.id)

    async def cancel(self, at: datetime) -> None:
        self.clock.current = at
        await CancelLot(
            self.lot_repo,
            self.order_repo,
            FakeOrderItemRepository(),
            FakeBoughtItemAllocationRepository(),
            FakeMadeItemAllocationRepository(),
            FakeSourceItemDemandRepository(),
            FakeSourceItemAllocationRepository(),
            event_bus=self.bus,
            uow=self.uow,
            parent_order_repo=FakeOrderRepository([]),
            **self._collaborators(),
        ).execute(self.actor, self.lot.id, CancelLotCommand())

    async def complete(self, at: datetime) -> None:
        self.clock.current = at
        await CompleteLot(
            self.lot_repo,
            self.order_repo,
            FakeOrderItemRepository(),
            event_bus=self.bus,
            uow=self.uow,
            parent_order_repo=FakeOrderRepository([]),
            made_item_demand_repo=FakeMadeItemDemandRepository(),
            made_item_allocation_repo=FakeMadeItemAllocationRepository(),
            **self._collaborators(),
            source_item_demand_repo=FakeSourceItemDemandRepository(),
            source_item_allocation_repo=FakeSourceItemAllocationRepository(),
            bought_allocation_repo=FakeBoughtItemAllocationRepository(),
        ).execute(self.actor, self.lot.id, CompleteLotCommand())

    def status_changes(self) -> list[tuple[int, ProductionOrderStatus, ProductionOrderStatus]]:
        return [
            (e.production_order_id, e.old_status, e.new_status)
            for e in self.bus.published
            if isinstance(e, ProductionOrderStatusChanged)
        ]

    def rows(self, order_id: int) -> list[tuple[str, datetime | None]]:
        return [(r.reason, r.resumed_at) for r in self.order(order_id).interruptions]

    # ── Hold ─────────────────────────────────────────────────────────

    async def test_hold_pauses_only_the_running_order_by_an_interruption_of_the_hold(self):
        await self.hold(_at(11))

        [row] = self.order(1).interruptions
        assert (row.reason, row.paused_at, row.paused_by_id, row.resumed_at) == (
            _LOT_HOLD,
            _at(11),
            5,
            None,
        )
        assert self.order(1).status == _PAUSED.value
        assert self.order(2).status == _QUEUED.value
        assert self.order(2).interruptions == []
        assert self.order(3).status == _PAUSED.value
        assert self.rows(3) == [(_MANUAL, None)]

    async def test_hold_publishes_the_status_change_and_one_pause(self):
        await self.hold(_at(11))

        assert self.status_changes() == [(1, _IN_PROGRESS, _PAUSED)]
        paused = [e for e in self.bus.published if isinstance(e, ProductionOrderPaused)]
        assert [(e.production_order_id, e.actor_id) for e in paused] == [(1, 5)]

    async def test_hold_locks_the_lot_before_the_running_order(self):
        await self.hold(_at(11))

        assert self.lot_repo.lock_calls == [[self.lot.id]]
        assert self.order_repo.lock_calls == [[1]]

    # ── Resume ───────────────────────────────────────────────────────

    async def test_resume_ends_the_hold_and_keeps_the_pause_made_by_hand(self):
        await self.hold(_at(11))
        self.bus.published.clear()

        await self.resume(_at(12))

        [row] = self.order(1).interruptions
        assert (row.resumed_at, row.resumed_by_id) == (_at(12), 5)
        assert self.order(1).status == _IN_PROGRESS.value
        assert self.order(3).status == _PAUSED.value
        assert self.rows(3) == [(_MANUAL, None)]
        assert self.status_changes() == [(1, _PAUSED, _IN_PROGRESS)]
        resumed = [e for e in self.bus.published if isinstance(e, ProductionOrderResumed)]
        assert [e.production_order_id for e in resumed] == [1]

    async def test_the_hold_does_not_count_as_work(self):
        await self.hold(_at(11))
        await self.resume(_at(12))

        order = self.order(1)
        assert order.actual_start == _at(8)
        # Six hours from 08:00 to 14:00 less the hour on hold.
        assert net_work_minutes(order.actual_start, _at(14), order.interruptions) == 300

    # ── Force cancel and force complete ─────────────────────────────

    async def test_force_cancel_closes_every_open_interruption(self):
        await self.hold(_at(11))
        self.bus.published.clear()

        await self.cancel(_at(13))

        for order_id in (1, 2, 3):
            order = self.order(order_id)
            assert order.status == _CANCELED.value
            assert order.canceled_at == _at(13)
            assert all(r.resumed_at == _at(13) for r in order.interruptions)
        assert sorted(self.status_changes()) == [
            (1, _PAUSED, _CANCELED),
            (2, _QUEUED, _CANCELED),
            (3, _PAUSED, _CANCELED),
        ]
        canceled = [e for e in self.bus.published if isinstance(e, ProductionOrderCanceled)]
        assert sorted(e.production_order_id for e in canceled) == [1, 2, 3]

    async def _record(self, order_id: int, pieces: float) -> None:
        """A completion of `pieces` accepted pieces on the order and its
        position."""
        self.order(order_id).quantity_completed += pieces
        await self.order_repo.save_completion(
            ProductionOrderCompletion(
                id=0,
                production_order_id=order_id,
                quantity=pieces,
                quantity_accepted=pieces,
                quantity_rejected=0.0,
                completion_date=date(2026, 1, 1),
                note=None,
                operator_id=5,
                recorded_by_id=5,
                created=_at(9),
            )
        )
        self.position.quantity_completed += pieces
        await self.lot_repo.save_position(self.position)

    async def test_force_complete_closes_the_pause_and_ends_each_order_at_what_it_did(self):
        # The lot closes at what it produced: the running order and the one
        # paused by hand processed pieces and complete at them, the queued
        # one processed none and is canceled.
        await self._record(1, 2.0)
        await self._record(3, 1.0)

        await self.complete(_at(13))

        for order_id in (1, 3):
            order = self.order(order_id)
            assert order.status == _COMPLETED.value
            assert order.actual_end == _at(13)
            assert all(r.resumed_at == _at(13) for r in order.interruptions)
        assert self.order(2).status == _CANCELED.value
        assert self.order(2).canceled_at == _at(13)
        assert self.order(1).actual_start == _at(8)
        completed = [e for e in self.bus.published if isinstance(e, ProductionOrderCompleted)]
        assert sorted(e.production_order_id for e in completed) == [1, 3]

    # ── What closed the interruption ─────────────────────────────────

    async def test_a_lot_resume_closes_the_hold_as_a_resume_without_an_operator(self):
        # The lot resume names no operator, so the work after it keeps the
        # operator of the order's last start.
        await self.hold(_at(11))

        await self.resume(_at(12))

        [row] = self.order(1).interruptions
        assert row.ended_by is InterruptionEndedBy.RESUME
        assert row.resumed_operator_id is None

    async def test_a_force_cancel_closes_every_interruption_as_a_cancel(self):
        await self.hold(_at(11))

        await self.cancel(_at(13))

        for order_id in (1, 3):
            assert [r.ended_by for r in self.order(order_id).interruptions] == [
                InterruptionEndedBy.CANCEL
            ]

    async def test_a_force_complete_cuts_the_pause_of_an_order_that_processed_pieces(self):
        # Order 3, paused by hand, ends at the piece it processed, so its
        # pause ends by the cut and no work follows it.
        await self._record(3, 1.0)

        await self.complete(_at(13))

        assert [r.ended_by for r in self.order(3).interruptions] == [InterruptionEndedBy.CUT]
        assert [r.resumed_operator_id for r in self.order(3).interruptions] == [None]
