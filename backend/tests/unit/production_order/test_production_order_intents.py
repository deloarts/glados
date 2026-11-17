"""
Start, resume, pause and cancel of a production order, and its completion,
record facts and intents only, and the lifecycle reconciler derives the
order's status from them: the status the response and the store show, the
actual_end stamp, the status events, and the refusals of the production
order intent table. The lot is locked before the order through the
request's lock plan, and both are read again after the locks. No database,
no HTTP; the fakes return their stored objects, so the reconciler writes
onto what the assertions read.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

import pytest

from src.modules.fulfillment.application.dto.production_order_dto import (
    CancelProductionOrderCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import PauseProductionOrderCommand
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
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.errors import LotPositionOverflowError
from src.modules.fulfillment.domain.errors import ProductionOrderInvalidStatusTransitionError
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderCanceled
from src.modules.fulfillment.domain.events.production_order_events import (
    ProductionOrderStatusChanged,
)
from src.modules.fulfillment.domain.value_objects.interruption_reason import InterruptionReason
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.infrastructure.events.codec import deserialize
from src.modules.platform.infrastructure.events.codec import serialize
from tests.factories import make_user
from tests.unit.production_lot._helpers import NoLotCreation
from tests.unit.production_lot.fakes import FakeMadeItemAllocationRepository
from tests.unit.production_lot.fakes import FakeMadeItemDemandRepository
from tests.unit.production_lot.fakes import completion_collaborators
from tests.unit.production_order._helpers import SEEDED_PAUSE
from tests.unit.production_order._helpers import SEEDED_START
from tests.unit.production_order._helpers import make_lot
from tests.unit.production_order._helpers import make_order
from tests.unit.production_order._helpers import make_position
from tests.unit.production_order.fakes import FakeEventBus
from tests.unit.production_order.fakes import FakeProductionLotRepository
from tests.unit.production_order.fakes import FakeProductionOrderFileRepository
from tests.unit.production_order.fakes import FakeProductionOrderRepository
from tests.unit.production_order.fakes import FakeUnitOfWork
from tests.unit.production_order.fakes import lifecycle_collaborators
from tests.unit.production_order.fakes import production_order_reconciler

_QUEUED = ProductionOrderStatus.QUEUED
_IN_PROGRESS = ProductionOrderStatus.IN_PROGRESS
_PAUSED = ProductionOrderStatus.PAUSED
_COMPLETED = ProductionOrderStatus.COMPLETED
_CANCELED = ProductionOrderStatus.CANCELED


class _LoggedLots(FakeProductionLotRepository):
    def __init__(self, lots: list[ProductionLot], calls: list[str]) -> None:
        super().__init__(lots)
        self._calls = calls

    async def lock_for_update(self, ids: list[int]) -> None:
        self._calls.append(f"lock lots {ids}")
        await super().lock_for_update(ids)

    async def get_by_id_for_update(self, id: int) -> ProductionLot | None:
        self._calls.append(f"read lot {id}")
        return await super().get_by_id_for_update(id)


class _LoggedOrders(FakeProductionOrderRepository):
    def __init__(self, orders: list[ProductionOrder], calls: list[str]) -> None:
        super().__init__(orders)
        self._calls = calls

    async def lock_for_update(self, ids: list[int]) -> None:
        self._calls.append(f"lock production orders {ids}")
        await super().lock_for_update(ids)

    async def get_by_id_for_update(self, id: int) -> ProductionOrder | None:
        self._calls.append(f"read order {id}")
        return await super().get_by_id_for_update(id)

    async def save(self, order: ProductionOrder) -> ProductionOrder:
        self._calls.append(f"save order {order.id}")
        return await super().save(order)


class _Floor:
    """One lot with one internal position, or a second one behind a
    predecessor, and the orders on it, with the use cases built over them."""

    def __init__(
        self,
        *orders: ProductionOrder,
        lot_status: LotStatus = LotStatus.IN_PROGRESS,
        positions: list[LotPosition] | None = None,
    ) -> None:
        self.calls: list[str] = []
        self.lot = make_lot(
            status=lot_status,
            positions=positions
            or [make_position(id=1, quantity=10.0, kind=LotPositionKind.INTERNAL)],
        )
        # A rework lot, which never waits for raw material.
        self.lot.source_made_item_id = 99
        self.lot_repo = _LoggedLots([self.lot], self.calls)
        self.order_repo = _LoggedOrders(list(orders), self.calls)
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        # Not the orders' creator; canceling another user's order needs
        # the manage permission.
        self.actor = make_user(
            id=7,
            permissions=[
                Permission.WRITE_PRODUCTION_ORDERS,
                Permission.MANAGE_PRODUCTION_ORDERS,
            ],
        )

    def lifecycle[T](self, use_case: type[T]) -> T:
        return use_case(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus),
        )

    def completion(self) -> RecordProductionOrderCompletion:
        return RecordProductionOrderCompletion(
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
        )

    def order(self, order_id: int = 1) -> ProductionOrder:
        return self.order_repo._orders[order_id]

    def event_names(self) -> list[str]:
        return [type(e).__name__ for e in self.bus.published]

    def order_event_names(self) -> list[str]:
        """The production order events in publishing order, without the
        status events of the order's position and lot."""
        return [name for name in self.event_names() if name.startswith("ProductionOrder")]

    def status_changes(self) -> list[tuple[ProductionOrderStatus, ProductionOrderStatus]]:
        return [
            (e.old_status, e.new_status)
            for e in self.bus.published
            if isinstance(e, ProductionOrderStatusChanged)
        ]


async def _start(floor: _Floor, order_id: int = 1):
    return await floor.lifecycle(StartProductionOrder).execute(
        floor.actor, production_order_id=order_id, cmd=StartProductionOrderCommand()
    )


class TestStart:
    async def test_the_first_start_derives_in_progress_from_actual_start(self):
        floor = _Floor(make_order(id=1, lot_position_id=1))

        result = await _start(floor)

        assert result.status == _IN_PROGRESS.value
        assert floor.order().status == _IN_PROGRESS.value
        assert floor.order().actual_start is not None
        assert floor.uow.commits == 1

    async def test_the_status_change_is_published_before_the_start(self):
        floor = _Floor(make_order(id=1, lot_position_id=1))

        await _start(floor)

        assert floor.order_event_names()[:2] == [
            "ProductionOrderStatusChanged",
            "ProductionOrderStarted",
        ]
        changed = floor.bus.published[0]
        assert isinstance(changed, ProductionOrderStatusChanged)
        assert (changed.old_status, changed.new_status) == (_QUEUED, _IN_PROGRESS)
        assert (changed.actor_id, changed.creator_id) == (7, 1)

    async def test_the_lot_is_locked_before_the_order_and_both_are_read_after(self):
        floor = _Floor(make_order(id=1, lot_position_id=1))

        await _start(floor)

        assert floor.calls[:4] == [
            "lock lots [1]",
            "lock production orders [1]",
            "read lot 1",
            "read order 1",
        ]
        assert "save order 1" in floor.calls[4:]

    async def test_a_running_order_cannot_be_started_again(self):
        floor = _Floor(make_order(id=1, lot_position_id=1, status=_IN_PROGRESS))

        with pytest.raises(ProductionOrderInvalidStatusTransitionError, match="in_progress"):
            await _start(floor)

        assert floor.uow.commits == 0
        assert floor.bus.published == []


class TestResume:
    async def test_resume_closes_the_manual_pause_and_keeps_the_first_start(self):
        floor = _Floor(make_order(id=1, lot_position_id=1, status=_PAUSED))

        result = await _start(floor)

        order = floor.order()
        assert result.status == _IN_PROGRESS.value
        assert order.status == _IN_PROGRESS.value
        assert order.actual_start == SEEDED_START
        [row] = order.interruptions
        assert row.reason == InterruptionReason.MANUAL.value
        assert row.resumed_at is not None and row.resumed_at > SEEDED_PAUSE
        assert row.resumed_by_id == 7

    async def test_resume_publishes_the_status_change_the_start_and_the_resume(self):
        floor = _Floor(make_order(id=1, lot_position_id=1, status=_PAUSED))

        await _start(floor)

        assert floor.order_event_names()[:3] == [
            "ProductionOrderStatusChanged",
            "ProductionOrderStarted",
            "ProductionOrderResumed",
        ]
        assert floor.status_changes() == [(_PAUSED, _IN_PROGRESS)]

    async def test_a_pause_of_the_lots_hold_is_not_resumed_by_the_order(self):
        floor = _Floor(
            make_order(
                id=1,
                lot_position_id=1,
                status=_PAUSED,
                interruption_reason=InterruptionReason.LOT_HOLD,
            )
        )

        with pytest.raises(
            ProductionOrderInvalidStatusTransitionError, match="an open manual interruption"
        ):
            await _start(floor)

        order = floor.order()
        assert order.status == _PAUSED.value
        assert [r.resumed_at for r in order.interruptions] == [None]
        assert floor.uow.commits == 0
        assert floor.bus.published == []

    async def test_a_paused_order_of_a_held_lot_is_not_resumed(self):
        floor = _Floor(
            make_order(id=1, lot_position_id=1, status=_PAUSED),
            lot_status=LotStatus.ON_HOLD,
        )

        with pytest.raises(ProductionOrderInvalidStatusTransitionError, match="on hold"):
            await _start(floor)

        assert [r.resumed_at for r in floor.order().interruptions] == [None]
        assert floor.uow.commits == 0

    async def test_resume_waits_for_input_from_upstream(self):
        predecessor = make_position(id=1, sequence=1, quantity=10.0, kind=LotPositionKind.INTERNAL)
        position = make_position(id=2, sequence=2, quantity=10.0, kind=LotPositionKind.INTERNAL)
        floor = _Floor(
            make_order(id=1, lot_position_id=2, status=_PAUSED),
            positions=[predecessor, position],
        )

        with pytest.raises(LotPositionOverflowError):
            await _start(floor)

        assert floor.order().status == _PAUSED.value
        assert [r.resumed_at for r in floor.order().interruptions] == [None]
        assert floor.uow.commits == 0


class TestPause:
    async def test_pause_opens_a_manual_interruption_which_derives_paused(self):
        floor = _Floor(make_order(id=1, lot_position_id=1, status=_IN_PROGRESS))

        result = await floor.lifecycle(PauseProductionOrder).execute(
            floor.actor, production_order_id=1, cmd=PauseProductionOrderCommand(reason="Tooling")
        )

        order = floor.order()
        assert result.status == _PAUSED.value
        assert order.status == _PAUSED.value
        [row] = order.interruptions
        assert (row.reason, row.paused_by_id, row.resumed_at) == (
            InterruptionReason.MANUAL.value,
            7,
            None,
        )
        assert floor.order_event_names()[:2] == [
            "ProductionOrderStatusChanged",
            "ProductionOrderPaused",
        ]
        assert floor.status_changes() == [(_IN_PROGRESS, _PAUSED)]

    async def test_a_queued_order_cannot_be_paused(self):
        floor = _Floor(make_order(id=1, lot_position_id=1))

        with pytest.raises(ProductionOrderInvalidStatusTransitionError, match="queued"):
            await floor.lifecycle(PauseProductionOrder).execute(
                floor.actor, production_order_id=1, cmd=PauseProductionOrderCommand()
            )

        assert floor.order().interruptions == []
        assert floor.uow.commits == 0


class TestCancel:
    async def test_cancel_stamps_canceled_at_and_closes_the_open_pause(self):
        floor = _Floor(make_order(id=1, lot_position_id=1, status=_PAUSED))

        result = await floor.lifecycle(CancelProductionOrder).execute(
            floor.actor, production_order_id=1, cmd=CancelProductionOrderCommand()
        )

        order = floor.order()
        assert result.status == _CANCELED.value
        assert order.status == _CANCELED.value
        assert order.canceled_at is not None
        [row] = order.interruptions
        assert (row.resumed_at, row.resumed_by_id) == (order.canceled_at, 7)

    async def test_cancel_keeps_the_schedule_adherence_baseline(self):
        baseline = datetime(2026, 2, 1, 12, 0, tzinfo=UTC)
        order = make_order(id=1, lot_position_id=1, status=_IN_PROGRESS)
        order.planned_end_at_start = baseline
        floor = _Floor(order)

        await floor.lifecycle(CancelProductionOrder).execute(
            floor.actor, production_order_id=1, cmd=CancelProductionOrderCommand()
        )

        assert floor.order().planned_end_at_start == baseline

    async def test_the_reconciler_publishes_the_only_canceled_event(self):
        floor = _Floor(make_order(id=1, lot_position_id=1, status=_PAUSED))

        await floor.lifecycle(CancelProductionOrder).execute(
            floor.actor, production_order_id=1, cmd=CancelProductionOrderCommand()
        )

        assert floor.order_event_names()[:2] == [
            "ProductionOrderStatusChanged",
            "ProductionOrderCanceled",
        ]
        canceled = [e for e in floor.bus.published if isinstance(e, ProductionOrderCanceled)]
        assert len(canceled) == 1
        assert (canceled[0].actor_id, canceled[0].creator_id) == (7, 1)
        assert floor.status_changes() == [(_PAUSED, _CANCELED)]

    async def test_a_completed_order_cannot_be_canceled(self):
        floor = _Floor(make_order(id=1, lot_position_id=1, status=_COMPLETED))

        with pytest.raises(ProductionOrderInvalidStatusTransitionError, match="completed"):
            await floor.lifecycle(CancelProductionOrder).execute(
                floor.actor, production_order_id=1, cmd=CancelProductionOrderCommand()
            )

        assert floor.order().canceled_at is None
        assert floor.uow.commits == 0


class TestCompletion:
    async def test_the_last_pieces_complete_the_order_and_stamp_actual_end(self):
        floor = _Floor(make_order(id=1, lot_position_id=1, status=_IN_PROGRESS))

        result = await floor.completion().execute(
            floor.actor,
            production_order_id=1,
            cmd=RecordProductionOrderCompletionCommand(
                quantity=10.0, completion_date=date(2026, 1, 2)
            ),
        )

        order = floor.order()
        [row] = order.completions
        assert result.status == _COMPLETED.value
        assert order.status == _COMPLETED.value
        assert order.actual_end == row.created
        assert floor.status_changes() == [(_IN_PROGRESS, _COMPLETED)]
        names = floor.event_names()
        assert names.count("ProductionOrderCompleted") == 1
        assert names.index("ProductionOrderCompleted") < names.index(
            "ProductionOrderCompletionRecorded"
        )

    async def test_a_partial_completion_keeps_the_order_running(self):
        floor = _Floor(make_order(id=1, lot_position_id=1, status=_IN_PROGRESS))

        result = await floor.completion().execute(
            floor.actor,
            production_order_id=1,
            cmd=RecordProductionOrderCompletionCommand(
                quantity=4.0, completion_date=date(2026, 1, 2)
            ),
        )

        assert result.status == _IN_PROGRESS.value
        assert floor.order().actual_end is None
        assert floor.status_changes() == []
        assert "ProductionOrderCompleted" not in floor.event_names()

    async def test_a_paused_order_takes_no_completion(self):
        floor = _Floor(make_order(id=1, lot_position_id=1, status=_PAUSED))

        with pytest.raises(ProductionOrderInvalidStatusTransitionError, match="paused"):
            await floor.completion().execute(
                floor.actor,
                production_order_id=1,
                cmd=RecordProductionOrderCompletionCommand(
                    quantity=1.0, completion_date=date(2026, 1, 2)
                ),
            )

        assert floor.order().completions == []
        assert floor.uow.commits == 0


def test_the_status_change_event_round_trips_with_its_enum_members():
    event = ProductionOrderStatusChanged(
        production_order_id=3,
        old_status=_PAUSED,
        new_status=_CANCELED,
        actor_id=7,
        creator_id=1,
    )

    restored = deserialize(serialize(event))

    assert restored == event
    assert isinstance(restored.old_status, ProductionOrderStatus)
    assert isinstance(restored.new_status, ProductionOrderStatus)
