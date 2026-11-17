"""
Net work time of a production order that was paused. actual_start records
the first start only, a resume closes the open interruption, and a cancel
closes every interruption still open, so a start at 08:00, a pause at 10:00,
a resume at 11:00 and the completion at 12:00 count three hours of work. A
settable clock stands in for the datetime class of the clock module, which
every now_utc() call reads; every other dependency is an in-memory fake.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import tzinfo

import pytest

from src.modules.fulfillment.application.dto.production_order_dto import (
    CancelProductionOrderCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import PauseProductionOrderCommand
from src.modules.fulfillment.application.dto.production_order_dto import ProductionOrderResult
from src.modules.fulfillment.application.dto.production_order_dto import (
    RecordProductionOrderCompletionCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import StartProductionOrderCommand
from src.modules.fulfillment.application.use_cases.production_order.production_order_lifecycle import (
    CancelProductionOrder,
)
from src.modules.fulfillment.application.use_cases.production_order.production_order_lifecycle import (
    PauseProductionOrder,
)
from src.modules.fulfillment.application.use_cases.production_order.production_order_lifecycle import (
    StartProductionOrder,
)
from src.modules.fulfillment.application.use_cases.production_order.record_production_order_completion import (
    RecordProductionOrderCompletion,
)
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.services.production_time_rules import net_work_minutes
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.quality.domain.services.kpi_rules import CapacityRow
from src.modules.quality.domain.services.kpi_rules import CompletedOrderRow
from src.modules.quality.domain.services.kpi_rules import FabricationMethodRef
from src.modules.quality.domain.services.kpi_rules import compute_estimate_accuracy
from src.modules.quality.domain.services.kpi_rules import compute_utilization
from src.shared_kernel.domain.services import clock as clock_module
from tests.factories import make_user
from tests.unit.production_lot._helpers import NoLotCreation
from tests.unit.production_lot.fakes import FakeMadeItemAllocationRepository
from tests.unit.production_lot.fakes import FakeMadeItemDemandRepository
from tests.unit.production_lot.fakes import FakeRecomputeMachineSchedule
from tests.unit.production_lot.fakes import completion_collaborators
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


def _at(hour: int, minute: int = 0) -> datetime:
    """An instant on Monday 2026-03-02, in UTC."""
    return datetime(2026, 3, 2, hour, minute, tzinfo=UTC)


class _Clock(datetime):
    """Stands in for the datetime class of the clock module, so every
    now_utc() call returns the instant the test set last."""

    current = datetime(2026, 3, 2, 8, 0, tzinfo=UTC)

    @classmethod
    def now(cls, tz: tzinfo | None = None) -> datetime:
        return cls.current


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> type[_Clock]:
    monkeypatch.setattr(_Clock, "current", _at(8))
    monkeypatch.setattr(clock_module, "datetime", _Clock)
    return _Clock


class _OrderOnTheFloor:
    """The actor's own order #1 of a rework lot (exempt from raw-material
    gating) on one internal position of ten pieces, estimated at three
    hours, with the lifecycle and completion use cases sharing the same
    fakes."""

    def setup_method(self) -> None:
        position = make_position(id=1, quantity=10.0, kind=LotPositionKind.INTERNAL)
        self.lot = make_lot(positions=[position])
        self.lot.source_made_item_id = 99
        self.actor = make_user(id=7, permissions=[Permission.WRITE_PRODUCTION_ORDERS])
        order = make_order(id=1, lot_position_id=1, quantity=10.0)
        order.creator_id = self.actor.id
        order.estimated_duration_minutes = 180
        self.lot_repo = FakeProductionLotRepository([self.lot])
        self.order_repo = FakeProductionOrderRepository([order])
        self.interruptions = FakeProductionOrderInterruptionRepository(self.order_repo._orders)
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()

    async def _start(self) -> ProductionOrderResult:
        return await StartProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            interruption_repo=self.interruptions,
            reconciler=production_order_reconciler(self.order_repo, self.lot_repo, self.bus),
        ).execute(self.actor, production_order_id=1, cmd=StartProductionOrderCommand())

    async def _pause(self) -> ProductionOrderResult:
        return await PauseProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            interruption_repo=self.interruptions,
            reconciler=production_order_reconciler(self.order_repo, self.lot_repo, self.bus),
        ).execute(self.actor, production_order_id=1, cmd=PauseProductionOrderCommand())

    async def _cancel(self) -> ProductionOrderResult:
        return await CancelProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            interruption_repo=self.interruptions,
            reconciler=production_order_reconciler(self.order_repo, self.lot_repo, self.bus),
        ).execute(self.actor, production_order_id=1, cmd=CancelProductionOrderCommand())

    async def _complete_all_pieces(self) -> ProductionOrderResult:
        return await RecordProductionOrderCompletion(
            self.order_repo,
            self.lot_repo,
            FakeProductionOrderFileRepository(),
            event_bus=self.bus,
            uow=self.uow,
            reconciler=production_order_reconciler(self.order_repo, self.lot_repo, self.bus),
            made_item_demand_repo=FakeMadeItemDemandRepository(),
            made_item_allocation_repo=FakeMadeItemAllocationRepository(),
            create_lot=NoLotCreation(),
            **completion_collaborators(self.order_repo),
        ).execute(
            self.actor,
            production_order_id=1,
            cmd=RecordProductionOrderCompletionCommand(
                quantity=10.0, completion_date=date(2026, 3, 2)
            ),
        )

    async def _order(self) -> ProductionOrder:
        order = await self.order_repo.get_by_id(1)
        assert order is not None
        return order


class TestActualStartAndNetWork(_OrderOnTheFloor):
    async def _run_start_pause_resume_complete(self, clock: type[_Clock]) -> None:
        await self._start()
        clock.current = _at(10)
        await self._pause()
        clock.current = _at(11)
        await self._start()
        clock.current = _at(12)
        await self._complete_all_pieces()

    async def test_resume_keeps_the_first_actual_start(self, clock: type[_Clock]) -> None:
        await self._start()
        clock.current = _at(10)
        await self._pause()
        clock.current = _at(11)

        resumed = await self._start()

        assert resumed.status == ProductionOrderStatus.IN_PROGRESS.value
        assert resumed.actual_start == _at(8)
        [interruption] = self.interruptions.rows
        assert (interruption.paused_at, interruption.resumed_at) == (_at(10), _at(11))

    async def test_start_pause_resume_complete_nets_three_hours_of_work(
        self, clock: type[_Clock]
    ) -> None:
        await self._run_start_pause_resume_complete(clock)

        order = await self._order()
        net_minutes = net_work_minutes(
            order.actual_start, order.actual_end, self.interruptions.rows
        )
        assert order.status == ProductionOrderStatus.COMPLETED.value
        assert (order.actual_start, order.actual_end) == (_at(8), _at(12))
        assert net_minutes == 180

    async def test_kpis_count_three_hours_for_the_paused_order(self, clock: type[_Clock]) -> None:
        await self._run_start_pause_resume_complete(clock)
        order = await self._order()
        assert order.actual_end is not None
        row = CompletedOrderRow(
            order_id=order.id,
            machine_id=order.machine_id,
            lot_id=self.lot.id,
            actual_start=order.actual_start,
            actual_end=order.actual_end,
            planned_end_at_start=order.planned_end_at_start,
            estimated_duration_minutes=order.estimated_duration_minutes,
            interruptions=tuple(self.interruptions.rows),
            fabrication_methods=(FabricationMethodRef(id=1, name="Method 1"),),
        )

        utilization = compute_utilization(
            [row], [CapacityRow(machine_id=1, machine_internal_name="M1", available_minutes=480)]
        )
        accuracy = compute_estimate_accuracy([row])

        assert utilization[0].machine_id == 1
        assert utilization[0].net_minutes == 180
        assert accuracy[0].median_ratio == 1.0


class TestCancelClosesInterruptions(_OrderOnTheFloor):
    async def test_cancel_closes_the_open_interruption_of_a_paused_order(
        self, clock: type[_Clock]
    ) -> None:
        await self._start()
        clock.current = _at(10)
        await self._pause()
        clock.current = _at(10, 30)

        result = await self._cancel()

        assert result.status == ProductionOrderStatus.CANCELED.value
        [interruption] = self.interruptions.rows
        assert interruption.resumed_at == _at(10, 30)
        assert interruption.resumed_by_id == self.actor.id

    async def test_cancel_after_a_resume_leaves_the_closed_interruption_alone(
        self, clock: type[_Clock]
    ) -> None:
        await self._start()
        clock.current = _at(10)
        await self._pause()
        clock.current = _at(11)
        await self._start()
        clock.current = _at(11, 30)

        await self._cancel()

        [interruption] = self.interruptions.rows
        assert (interruption.paused_at, interruption.resumed_at) == (_at(10), _at(11))


class TestStartAndPauseRequestAWalk(_OrderOnTheFloor):
    async def test_a_start_and_a_pause_each_request_one_schedule_walk(
        self, clock: type[_Clock]
    ) -> None:
        recompute = FakeRecomputeMachineSchedule()

        def lifecycle(cls: type) -> object:
            return cls(
                self.order_repo,
                self.lot_repo,
                event_bus=self.bus,
                uow=self.uow,
                interruption_repo=self.interruptions,
                reconciler=production_order_reconciler(self.order_repo, self.lot_repo, self.bus),
                recompute_schedule=recompute,
            )

        await lifecycle(StartProductionOrder).execute(  # type: ignore[attr-defined]
            self.actor, production_order_id=1, cmd=StartProductionOrderCommand()
        )
        started = recompute.calls
        clock.current = _at(10)
        await lifecycle(PauseProductionOrder).execute(  # type: ignore[attr-defined]
            self.actor, production_order_id=1, cmd=PauseProductionOrderCommand()
        )

        assert (started, recompute.calls) == (1, 2)
