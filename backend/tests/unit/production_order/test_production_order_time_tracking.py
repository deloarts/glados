"""
Unit tests for the KPI data-foundation changes to the production order
lifecycle: the planned_end_at_start baseline (frozen once at start, kept on
cancel) and the pause/resume interruption trail. No database, no HTTP,
dependencies replaced with in-memory fakes.
"""

from datetime import UTC
from datetime import datetime

from src.modules.fulfillment.application.dto.production_order_dto import (
    CancelProductionOrderCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import PauseProductionOrderCommand
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
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderPaused
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderResumed
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.production_order._helpers import make_lot
from tests.unit.production_order._helpers import make_order
from tests.unit.production_order._helpers import make_position
from tests.unit.production_order.fakes import FakeEventBus
from tests.unit.production_order.fakes import FakeProductionLotRepository
from tests.unit.production_order.fakes import FakeProductionOrderInterruptionRepository
from tests.unit.production_order.fakes import FakeProductionOrderRepository
from tests.unit.production_order.fakes import FakeUnitOfWork
from tests.unit.production_order.fakes import lifecycle_collaborators
from tests.unit.production_order.fakes import production_order_reconciler


class TestPlannedEndAtStartBaseline:
    def setup_method(self):
        self.position = make_position(id=1, quantity=10.0, kind=LotPositionKind.INTERNAL)
        self.lot = make_lot(positions=[self.position])
        self.lot.source_made_item_id = 99  # rework lot, exempt raw-material gating
        self.lot_repo = FakeProductionLotRepository([self.lot])
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(permissions=[Permission.WRITE_PRODUCTION_ORDERS])

    async def test_start_freezes_baseline_from_planned_end(self):
        order = make_order(id=1, lot_position_id=1)
        order.planned_end = datetime(2026, 2, 1, 12, 0, tzinfo=UTC)
        order_repo = FakeProductionOrderRepository([order])
        use_case = StartProductionOrder(
            order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(order_repo, self.lot_repo, self.bus),
        )

        result = await use_case.execute(
            self.actor, production_order_id=1, cmd=StartProductionOrderCommand()
        )

        assert result.planned_end_at_start == order.planned_end

    async def test_start_leaves_baseline_none_when_planned_end_was_never_set(self):
        order_repo = FakeProductionOrderRepository([make_order(id=1, lot_position_id=1)])
        use_case = StartProductionOrder(
            order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(order_repo, self.lot_repo, self.bus),
        )

        result = await use_case.execute(
            self.actor, production_order_id=1, cmd=StartProductionOrderCommand()
        )

        assert result.planned_end_at_start is None

    async def test_resume_never_rewrites_an_already_set_baseline(self):
        """A schedule recompute moves planned_end while the order is
        paused (the live field keeps changing); resuming must not let the
        new value leak into the frozen baseline."""
        order = make_order(id=1, lot_position_id=1)
        order.planned_end = datetime(2026, 2, 1, 12, 0, tzinfo=UTC)
        order_repo = FakeProductionOrderRepository([order])
        start_use_case = StartProductionOrder(
            order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(order_repo, self.lot_repo, self.bus),
        )
        first = await start_use_case.execute(
            self.actor, production_order_id=1, cmd=StartProductionOrderCommand()
        )
        assert first.planned_end_at_start == datetime(2026, 2, 1, 12, 0, tzinfo=UTC)

        pause_use_case = PauseProductionOrder(
            order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(order_repo, self.lot_repo, self.bus),
        )
        await pause_use_case.execute(
            self.actor, production_order_id=1, cmd=PauseProductionOrderCommand()
        )

        # Simulate a schedule recompute moving the live planned_end while paused.
        order_repo._orders[1].planned_end = datetime(2026, 2, 5, 9, 0, tzinfo=UTC)

        resumed = await start_use_case.execute(
            self.actor, production_order_id=1, cmd=StartProductionOrderCommand()
        )
        assert resumed.planned_end_at_start == datetime(2026, 2, 1, 12, 0, tzinfo=UTC)

    async def test_cancel_keeps_the_baseline(self):
        order = make_order(id=1, lot_position_id=1)
        order.planned_end = datetime(2026, 2, 1, 12, 0, tzinfo=UTC)
        order_repo = FakeProductionOrderRepository([order])
        start_use_case = StartProductionOrder(
            order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(order_repo, self.lot_repo, self.bus),
        )
        await start_use_case.execute(
            self.actor, production_order_id=1, cmd=StartProductionOrderCommand()
        )

        cancel_use_case = CancelProductionOrder(
            order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(order_repo, self.lot_repo, self.bus),
        )
        result = await cancel_use_case.execute(
            self.actor, production_order_id=1, cmd=CancelProductionOrderCommand()
        )

        assert result.status == ProductionOrderStatus.CANCELED.value
        assert result.planned_end_at_start == datetime(2026, 2, 1, 12, 0, tzinfo=UTC)


class TestPauseResumeInterruptions:
    def setup_method(self):
        self.position = make_position(id=1, quantity=10.0, kind=LotPositionKind.INTERNAL)
        self.lot = make_lot(positions=[self.position])
        self.lot.source_made_item_id = 99  # rework lot, exempt raw-material gating
        self.lot_repo = FakeProductionLotRepository([self.lot])
        self.order_repo = FakeProductionOrderRepository([make_order(id=1, lot_position_id=1)])
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()
        self.actor = make_user(id=7, permissions=[Permission.WRITE_PRODUCTION_ORDERS])
        self.interruptions = FakeProductionOrderInterruptionRepository(self.order_repo._orders)

    async def _start(self) -> None:
        await StartProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            interruption_repo=self.interruptions,
            reconciler=production_order_reconciler(self.order_repo, self.lot_repo, self.bus),
        ).execute(self.actor, production_order_id=1, cmd=StartProductionOrderCommand())

    async def test_pause_opens_an_interruption_row_and_publishes_the_event(self):
        await self._start()
        use_case = PauseProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            interruption_repo=self.interruptions,
            reconciler=production_order_reconciler(self.order_repo, self.lot_repo, self.bus),
        )
        await use_case.execute(self.actor, production_order_id=1, cmd=PauseProductionOrderCommand())

        assert len(self.interruptions.rows) == 1
        row = self.interruptions.rows[0]
        assert row.production_order_id == 1
        assert row.paused_by_id == self.actor.id
        assert row.resumed_at is None
        assert any(isinstance(e, ProductionOrderPaused) for e in self.bus.published)

    async def test_resume_closes_the_open_interruption_and_publishes_the_event(self):
        await self._start()
        await PauseProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            interruption_repo=self.interruptions,
            reconciler=production_order_reconciler(self.order_repo, self.lot_repo, self.bus),
        ).execute(self.actor, production_order_id=1, cmd=PauseProductionOrderCommand())

        await StartProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            interruption_repo=self.interruptions,
            reconciler=production_order_reconciler(self.order_repo, self.lot_repo, self.bus),
        ).execute(self.actor, production_order_id=1, cmd=StartProductionOrderCommand())

        assert len(self.interruptions.rows) == 1
        row = self.interruptions.rows[0]
        assert row.resumed_at is not None
        assert row.resumed_by_id == self.actor.id
        assert any(isinstance(e, ProductionOrderResumed) for e in self.bus.published)

    async def test_fresh_start_does_not_publish_resumed(self):
        await self._start()
        assert not any(isinstance(e, ProductionOrderResumed) for e in self.bus.published)

    async def test_pause_and_resume_put_the_order_back_in_progress(self):
        """The pause is the interruption row and the resume closes it, so the
        order the reconciler derives is in progress again."""
        await StartProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus),
        ).execute(self.actor, production_order_id=1, cmd=StartProductionOrderCommand())

        await PauseProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus),
        ).execute(self.actor, production_order_id=1, cmd=PauseProductionOrderCommand())

        result = await StartProductionOrder(
            self.order_repo,
            self.lot_repo,
            event_bus=self.bus,
            uow=self.uow,
            **lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus),
        ).execute(self.actor, production_order_id=1, cmd=StartProductionOrderCommand())

        assert result.status == ProductionOrderStatus.IN_PROGRESS.value
