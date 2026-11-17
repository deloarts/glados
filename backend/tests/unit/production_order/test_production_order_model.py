"""
A rule-based model of the production orders on one lot position, run by
Hypothesis over the real use cases, the lifecycle reconciler and in-memory
fakes: start, resume, pause, cancel, completion, scrap, split and merge of
an order, and hold and resume of its lot. Each order action is chosen only
where the production order intent table allows it; the use case may still
refuse it for a reason the table leaves to it, such as missing input, and a
refused request rolls the fakes back as its transaction would.

After every step the stored statuses equal their derivation from the facts,
a second reconciler run changes nothing, every status change of the step
published exactly one status event and every ending its Completed or
Canceled event, at most one interruption is open per order and none on an
ended order, and the recorded quantities and times stay consistent. A
settable clock moves ten minutes per request.
"""

import asyncio
import copy
from collections.abc import Awaitable
from collections.abc import Callable
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from datetime import tzinfo
from typing import Any
from unittest import mock

from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine
from hypothesis.stateful import invariant
from hypothesis.stateful import precondition
from hypothesis.stateful import rule

from src.modules.fulfillment.application.dto.production_lot_dto import HoldLotCommand
from src.modules.fulfillment.application.dto.production_order_dto import (
    CancelProductionOrderCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    MergeProductionOrdersCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import PauseProductionOrderCommand
from src.modules.fulfillment.application.dto.production_order_dto import (
    RecordProductionOrderCompletionCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    ScrapProductionPiecesCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import SplitProductionOrderCommand
from src.modules.fulfillment.application.dto.production_order_dto import StartProductionOrderCommand
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import HoldLot
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import ResumeLot
from src.modules.fulfillment.application.use_cases.production_order.merge_production_orders import (
    MergeProductionOrders,
)
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
from src.modules.fulfillment.application.use_cases.production_order.scrap_production_pieces import (
    ScrapProductionPieces,
)
from src.modules.fulfillment.application.use_cases.production_order.split_production_order import (
    SplitProductionOrder,
)
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderCanceled
from src.modules.fulfillment.domain.events.production_order_events import ProductionOrderCompleted
from src.modules.fulfillment.domain.events.production_order_events import (
    ProductionOrderStatusChanged,
)
from src.modules.fulfillment.domain.services.lifecycle.intents import PRODUCTION_ORDER_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.production_order import (
    derive_production_order_status,
)
from src.modules.fulfillment.domain.services.lifecycle.snapshot import production_order_facts
from src.modules.fulfillment.domain.services.production_order_rules import production_order_context
from src.modules.fulfillment.domain.services.production_time_rules import net_work_minutes
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.scrap_reason import ScrapReason
from src.modules.platform.domain.exceptions import DomainError
from src.modules.platform.domain.value_objects.permission import Permission
from src.shared_kernel.domain.services import clock
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction
from tests.factories import make_user
from tests.unit.lifecycle._profiles import model_settings
from tests.unit.production_lot._helpers import NoLotCreation
from tests.unit.production_lot.fakes import FakeMadeItemAllocationRepository
from tests.unit.production_lot.fakes import FakeMadeItemDemandRepository
from tests.unit.production_lot.fakes import completion_collaborators
from tests.unit.production_lot.fakes import disposition_collaborators
from tests.unit.production_order._helpers import make_lot
from tests.unit.production_order._helpers import make_order
from tests.unit.production_order._helpers import make_position
from tests.unit.production_order.fakes import FakeAdminSettingsRepository
from tests.unit.production_order.fakes import FakeEventBus
from tests.unit.production_order.fakes import FakeProductionLotRepository
from tests.unit.production_order.fakes import FakeProductionOrderFileRepository
from tests.unit.production_order.fakes import FakeProductionOrderRepository
from tests.unit.production_order.fakes import FakeUnitOfWork
from tests.unit.production_order.fakes import lifecycle_collaborators
from tests.unit.production_order.fakes import production_order_reconciler

_EPS = 1e-6
_ENDED = frozenset({ProductionOrderStatus.COMPLETED.value, ProductionOrderStatus.CANCELED.value})
_TERMINAL_LOT = frozenset(
    {LotStatus.COMPLETED.value, LotStatus.CANCELED.value, LotStatus.SCRAPPED.value}
)
_STEP = timedelta(minutes=10)
_ACTOR = make_user(
    id=7,
    permissions=[
        Permission.WRITE_PRODUCTION_ORDERS,
        Permission.MANAGE_PRODUCTION_ORDERS,
        Permission.WRITE_LOTS,
        Permission.MANAGE_LOTS,
    ],
)


class _Clock(datetime):
    """Stands in for the datetime class of the clock module, so every
    now_utc() call returns the instant the model set last."""

    current = datetime(2026, 5, 4, 6, 0, tzinfo=UTC)

    @classmethod
    def now(cls, tz: tzinfo | None = None) -> datetime:
        return cls.current


class ProductionOrderModel(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self._clock_patch = mock.patch.object(clock, "datetime", _Clock)
        self._clock_patch.start()
        _Clock.current = datetime(2026, 5, 4, 6, 0, tzinfo=UTC)
        position = make_position(
            id=1,
            quantity=12.0,
            kind=LotPositionKind.INTERNAL,
            status=LotPositionStatus.ORDERED_OR_QUEUED,
        )
        lot = make_lot(status=LotStatus.PLANNED, quantity=12.0, positions=[position])
        # A rework lot, which never waits for raw material.
        lot.source_made_item_id = 99
        self.lot_repo = FakeProductionLotRepository([lot])
        self.order_repo = FakeProductionOrderRepository(
            [
                make_order(id=1, quantity=6.0, queue_sequence=1),
                make_order(id=2, quantity=6.0, queue_sequence=2),
            ]
        )
        self.bus = FakeEventBus()
        self.uow = FakeUnitOfWork()

    def teardown(self) -> None:
        self._clock_patch.stop()

    # ── State ────────────────────────────────────────────────────────

    @property
    def lot(self) -> ProductionLot:
        return self.lot_repo._lots[1]

    def orders(self) -> list[ProductionOrder]:
        return sorted(self.order_repo._orders.values(), key=lambda o: o.id)

    def allowing(self, *actions: LifecycleAction) -> list[int]:
        """The orders whose intent table allows one of `actions` now."""
        held = self.lot.status == LotStatus.ON_HOLD.value
        terminal = self.lot.status in _TERMINAL_LOT
        return [
            order.id
            for order in self.orders()
            if set(actions)
            & set(
                PRODUCTION_ORDER_INTENTS.allowed_actions(
                    order,
                    production_order_context(order, lot_held=held, lot_terminal=terminal),
                    _ACTOR,
                )
            )
        ]

    def splittable(self) -> list[int]:
        """The orders a split allows that have a piece to split off."""
        return [
            order_id
            for order_id in self.allowing(LifecycleAction.SPLIT)
            if self.order_repo._orders[order_id].quantity >= 2.0
        ]

    def mergeable(self) -> list[tuple[int, int]]:
        queued = self.allowing(LifecycleAction.MERGE)
        return [(a, b) for a in queued for b in queued if a < b]

    # ── Requests ─────────────────────────────────────────────────────

    def request(self, call: Callable[[dict[str, Any]], Awaitable[object]]) -> None:
        """Runs one request with its own reconciler. A refusal restores the
        fakes as they were, as the request's rollback would; a success must
        have published one status event per status change."""
        saved = copy.deepcopy((self.order_repo.__dict__, self.lot_repo.__dict__))
        before = {o.id: o.status for o in self.orders()}
        self.bus.published.clear()
        _Clock.current += _STEP
        try:
            asyncio.run(call(lifecycle_collaborators(self.order_repo, self.lot_repo, self.bus)))
        except DomainError:
            self.order_repo.__dict__.clear()
            self.order_repo.__dict__.update(saved[0])
            self.lot_repo.__dict__.clear()
            self.lot_repo.__dict__.update(saved[1])
            self.bus.published.clear()
            return
        self.assert_status_events(before)

    def assert_status_events(self, before: dict[int, str]) -> None:
        after = {o.id: o.status for o in self.orders()}
        changed = sorted(
            (order_id, old, after[order_id])
            for order_id, old in before.items()
            if after[order_id] != old
        )
        published = self.bus.published
        status_events = sorted(
            (e.production_order_id, e.old_status.value, e.new_status.value)
            for e in published
            if isinstance(e, ProductionOrderStatusChanged)
        )
        assert status_events == changed
        assert sorted(
            e.production_order_id for e in published if isinstance(e, ProductionOrderCompleted)
        ) == [i for i, _old, new in changed if new == ProductionOrderStatus.COMPLETED.value]
        assert sorted(
            e.production_order_id for e in published if isinstance(e, ProductionOrderCanceled)
        ) == [i for i, _old, new in changed if new == ProductionOrderStatus.CANCELED.value]

    # ── Rules ────────────────────────────────────────────────────────

    @precondition(lambda self: self.allowing(LifecycleAction.START, LifecycleAction.RESUME))
    @rule(data=st.data())
    def start_or_resume(self, data: st.DataObject) -> None:
        order_id = data.draw(
            st.sampled_from(self.allowing(LifecycleAction.START, LifecycleAction.RESUME))
        )
        self.request(
            lambda c: StartProductionOrder(
                self.order_repo, self.lot_repo, event_bus=self.bus, uow=self.uow, **c
            ).execute(_ACTOR, order_id, StartProductionOrderCommand())
        )

    @precondition(lambda self: self.allowing(LifecycleAction.PAUSE))
    @rule(data=st.data())
    def pause(self, data: st.DataObject) -> None:
        order_id = data.draw(st.sampled_from(self.allowing(LifecycleAction.PAUSE)))
        self.request(
            lambda c: PauseProductionOrder(
                self.order_repo, self.lot_repo, event_bus=self.bus, uow=self.uow, **c
            ).execute(_ACTOR, order_id, PauseProductionOrderCommand())
        )

    @precondition(lambda self: self.allowing(LifecycleAction.CANCEL))
    @rule(data=st.data())
    def cancel(self, data: st.DataObject) -> None:
        order_id = data.draw(st.sampled_from(self.allowing(LifecycleAction.CANCEL)))
        self.request(
            lambda c: CancelProductionOrder(
                self.order_repo, self.lot_repo, event_bus=self.bus, uow=self.uow, **c
            ).execute(_ACTOR, order_id, CancelProductionOrderCommand())
        )

    @precondition(lambda self: self.allowing(LifecycleAction.RECORD_COMPLETION))
    @rule(data=st.data(), all_of_it=st.booleans())
    def record_completion(self, data: st.DataObject, all_of_it: bool) -> None:
        order_id = data.draw(st.sampled_from(self.allowing(LifecycleAction.RECORD_COMPLETION)))
        order = self.order_repo._orders[order_id]
        remaining = order.quantity - sum(c.quantity for c in order.completions)
        quantity = remaining if all_of_it else min(remaining, 1.0)
        self.request(
            lambda c: RecordProductionOrderCompletion(
                self.order_repo,
                self.lot_repo,
                FakeProductionOrderFileRepository(),
                event_bus=self.bus,
                uow=self.uow,
                reconciler=c["reconciler"],
                made_item_demand_repo=FakeMadeItemDemandRepository(),
                made_item_allocation_repo=FakeMadeItemAllocationRepository(),
                create_lot=NoLotCreation(),
                **completion_collaborators(self.order_repo),
            ).execute(
                _ACTOR,
                order_id,
                RecordProductionOrderCompletionCommand(
                    quantity=quantity, completion_date=date(2026, 5, 4)
                ),
            )
        )

    @precondition(lambda self: self.allowing(LifecycleAction.SCRAP))
    @rule(data=st.data())
    def scrap(self, data: st.DataObject) -> None:
        order_id = data.draw(st.sampled_from(self.allowing(LifecycleAction.SCRAP)))
        self.request(
            lambda c: ScrapProductionPieces(
                self.order_repo,
                self.lot_repo,
                event_bus=self.bus,
                uow=self.uow,
                reconciler=c["reconciler"],
                interruption_repo=c["interruption_repo"],
                **disposition_collaborators(),
                made_item_demand_repo=FakeMadeItemDemandRepository(),
                made_item_allocation_repo=FakeMadeItemAllocationRepository(),
                create_lot=NoLotCreation(),
            ).execute(
                _ACTOR,
                ScrapProductionPiecesCommand(
                    production_order_id=order_id,
                    quantity=1.0,
                    reason=ScrapReason.OTHER,
                    create_replacement=False,
                ),
            )
        )

    @precondition(lambda self: self.splittable())
    @rule(data=st.data())
    def split(self, data: st.DataObject) -> None:
        order_id = data.draw(st.sampled_from(self.splittable()))
        quantity = self.order_repo._orders[order_id].quantity
        self.request(
            lambda c: SplitProductionOrder(
                self.order_repo,
                self.lot_repo,
                FakeAdminSettingsRepository(),
                event_bus=self.bus,
                uow=self.uow,
                reconciler=c["reconciler"],
            ).execute(
                _ACTOR,
                order_id,
                SplitProductionOrderCommand(quantities=[quantity - 1.0, 1.0]),
            )
        )

    @precondition(lambda self: self.mergeable())
    @rule(data=st.data())
    def merge(self, data: st.DataObject) -> None:
        pair = data.draw(st.sampled_from(self.mergeable()))
        self.request(
            lambda c: MergeProductionOrders(
                self.order_repo,
                self.lot_repo,
                event_bus=self.bus,
                uow=self.uow,
                reconciler=c["reconciler"],
            ).execute(_ACTOR, MergeProductionOrdersCommand(production_order_ids=list(pair)))
        )

    @rule()
    def hold_lot(self) -> None:
        self.request(
            lambda c: HoldLot(
                self.lot_repo, self.order_repo, event_bus=self.bus, uow=self.uow, **c
            ).execute(_ACTOR, 1, HoldLotCommand(reason="Material check"))
        )

    @precondition(lambda self: self.lot.status == LotStatus.ON_HOLD.value)
    @rule()
    def resume_lot(self) -> None:
        self.request(
            lambda c: ResumeLot(
                self.lot_repo, self.order_repo, event_bus=self.bus, uow=self.uow, **c
            ).execute(_ACTOR, 1)
        )

    # ── Invariants ───────────────────────────────────────────────────

    @invariant()
    def every_status_is_derived_from_the_facts(self) -> None:
        for order in self.orders():
            derived = derive_production_order_status(production_order_facts(order)).value
            assert order.status == derived.value, order.id

    @invariant()
    def a_second_run_changes_nothing(self) -> None:
        reconciler = production_order_reconciler(self.order_repo, self.lot_repo, FakeEventBus())
        reconciler.touch_production_orders([o.id for o in self.orders()])
        result = asyncio.run(reconciler.run(_ACTOR, _Clock.current))
        assert result.changes == ()

    @invariant()
    def at_most_one_pause_is_open_and_none_on_an_ended_order(self) -> None:
        for order in self.orders():
            open_rows = [r for r in order.interruptions if r.resumed_at is None]
            assert len(open_rows) <= (0 if order.status in _ENDED else 1), order.id

    @invariant()
    def work_has_a_start_and_its_times_are_ordered(self) -> None:
        for order in self.orders():
            if order.interruptions or order.completions:
                assert order.actual_start is not None, order.id
            for row in order.interruptions:
                assert order.actual_start is not None
                assert row.paused_at >= order.actual_start
                assert row.resumed_at is None or row.resumed_at >= row.paused_at
            if order.status == ProductionOrderStatus.COMPLETED.value:
                assert order.actual_end is not None
                minutes = net_work_minutes(
                    order.actual_start, order.actual_end, order.interruptions
                )
                assert minutes is not None and minutes >= 0
            else:
                assert order.actual_end is None, order.id

    @invariant()
    def processed_and_accepted_stay_within_the_order(self) -> None:
        for order in self.orders():
            processed = sum(c.quantity for c in order.completions)
            assert processed <= order.quantity + _EPS, order.id
            assert order.quantity_completed <= processed + _EPS, order.id


ProductionOrderModel.TestCase.settings = model_settings(steps=30)
TestProductionOrderModel = ProductionOrderModel.TestCase
