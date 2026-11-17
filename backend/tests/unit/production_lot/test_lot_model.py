"""
A rule-based model of a lot of two positions, the first one running an
order from the start, run by Hypothesis over the real use cases, the
lifecycle reconciler and in-memory fakes: start or resume, completion, scrap
and cancel of the production orders, assigning the second position
internally and topping it up, deleting its step while it is untouched, and
hold, resume, cancel and force-complete of the lot. A request the use case
refuses rolls the fakes back as its transaction would. Lot cancel, force
complete, order cancel, hold and the step delete are drawn less often, so
most runs get to work before the lot ends.

After every step the stored lot status and each position's kind, status
and completed count equal a fresh derivation from the facts, and a
reconciler run over the lot changes nothing; each position counts the
pieces of all its orders, canceled ones included; a lot whose positions are
all complete, or that was force-completed, is COMPLETED, whether held or
not; no position holds more pieces than the one before it; every lot and
position
status change of the step published exactly one status event; no live order
remains under a terminal lot; completed counts stay within their position's
quantity and available input; and the lot is ON_HOLD exactly while it is
held and not terminal. A refused request restores every fake it may write,
the made demands, order lines and orders included.
"""

import asyncio
import copy
import itertools
from collections.abc import Awaitable
from collections.abc import Callable

from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine
from hypothesis.stateful import invariant
from hypothesis.stateful import precondition
from hypothesis.stateful import rule

from src.modules.fulfillment.application.dto.production_lot_dto import CancelLotCommand
from src.modules.fulfillment.application.dto.production_lot_dto import CompleteLotCommand
from src.modules.fulfillment.application.dto.production_lot_dto import HoldLotCommand
from src.modules.fulfillment.application.dto.production_order_dto import (
    AssignInternalPositionCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    AssignInternalPositionOrderInput,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    CancelProductionOrderCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import StartProductionOrderCommand
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import CancelLot
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import CompleteLot
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import HoldLot
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import ResumeLot
from src.modules.fulfillment.application.use_cases.production_lot.lot_steps import DeleteLotStep
from src.modules.fulfillment.application.use_cases.production_order.assign_internal_position import (
    AssignInternalPosition,
)
from src.modules.fulfillment.application.use_cases.production_order.production_order_lifecycle import (
    CancelProductionOrder,
)
from src.modules.fulfillment.application.use_cases.production_order.production_order_lifecycle import (
    StartProductionOrder,
)
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.events.lot_events import LotPositionStatusChanged
from src.modules.fulfillment.domain.events.lot_events import LotStatusChanged
from src.modules.fulfillment.domain.services.lifecycle.intents import PRODUCTION_ORDER_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.snapshot import LifecycleSnapshot
from src.modules.fulfillment.domain.services.lifecycle.snapshot import derive_snapshot
from src.modules.fulfillment.domain.services.lot_rules import TERMINAL_LOT_STATUSES
from src.modules.fulfillment.domain.services.lot_rules import available_input
from src.modules.fulfillment.domain.services.lot_rules import compute_position_remaining
from src.modules.fulfillment.domain.services.lot_rules import has_progress
from src.modules.fulfillment.domain.services.production_order_rules import production_order_context
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.platform.domain.exceptions import DomainError
from src.modules.platform.domain.value_objects.permission import Permission
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction
from tests.factories import make_user
from tests.unit.lifecycle._profiles import EXPENSIVE
from tests.unit.lifecycle._profiles import model_settings
from tests.unit.production_lot._floor import NOW
from tests.unit.production_lot._floor import Floor
from tests.unit.production_lot._helpers import make_machine
from tests.unit.production_lot.fakes import FakeAdminSettingsRepository
from tests.unit.production_lot.fakes import FakeBoughtItemAllocationRepository
from tests.unit.production_lot.fakes import FakeProductionMachineRepository
from tests.unit.production_lot.fakes import FakeProductionOrderRepository
from tests.unit.production_lot.fakes import FakeSourceItemAllocationRepository
from tests.unit.production_lot.fakes import FakeSourceItemDemandRepository
from tests.unit.production_lot.fakes import lot_reconciler
from tests.unit.production_order.fakes import FakeProductionOrderInterruptionRepository

_EPS = 1e-6
_ENDED = frozenset({ProductionOrderStatus.COMPLETED.value, ProductionOrderStatus.CANCELED.value})
_ACTOR = make_user(
    id=7,
    permissions=[
        Permission.WRITE_PRODUCTION_ORDERS,
        Permission.MANAGE_PRODUCTION_ORDERS,
        Permission.WRITE_LOTS,
        Permission.MANAGE_LOTS,
        Permission.WRITE_INSPECTIONS,
    ],
)
_LOT_QUANTITY = 6.0
_HOLDABLE = frozenset(
    {LotStatus.PARTIALLY_PLANNED.value, LotStatus.PLANNED.value, LotStatus.IN_PROGRESS.value}
)

type Collaborators = dict[str, object]


class LotModel(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self.floor = Floor(positions=2)
        self.floor.operator = _ACTOR
        self.floor.planner = _ACTOR
        lot = asyncio.run(self.floor.lot(_LOT_QUANTITY))
        self.lot_id = lot.id
        first = lot.positions[0]
        asyncio.run(self.floor.order(first))
        asyncio.run(self.floor.settle(lot.id))

    # ── State ────────────────────────────────────────────────────────

    @property
    def lot(self) -> ProductionLot:
        return self.floor.lots._hydrate(self.floor.lots._lots[self.lot_id])

    def positions(self) -> list[LotPosition]:
        return self.lot.positions

    def orders(self) -> list[ProductionOrder]:
        return sorted(self.floor.orders._orders.values(), key=lambda o: o.id)

    def allowing(self, *actions: LifecycleAction) -> list[int]:
        """The orders whose intent table allows one of `actions` now."""
        lot = self.lot
        held = lot.status == LotStatus.ON_HOLD.value
        terminal = lot.status in TERMINAL_LOT_STATUSES
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

    def second(self) -> LotPosition | None:
        positions = self.positions()
        return positions[1] if len(positions) > 1 else None

    # ── Requests ─────────────────────────────────────────────────────

    def request(self, call: Callable[[Collaborators], Awaitable[object]]) -> None:
        """Runs one request with a reconciler of its own. A refusal restores
        the fakes; a success must have published one status event per lot
        and position status change."""
        floor = self.floor
        repos = self.rolled_back()
        saved = copy.deepcopy(tuple(repo.__dict__ for repo in repos))
        lot_before = self.lot.status
        positions_before = {p.id: p.status for p in self.positions()}
        floor.bus.published.clear()
        collaborators: Collaborators = {
            "reconciler": lot_reconciler(floor.lots, floor.orders, bus=floor.bus),
            "interruption_repo": FakeProductionOrderInterruptionRepository(floor.orders._orders),
        }
        try:
            asyncio.run(call(collaborators))
        except DomainError:
            for repo, state in zip(repos, saved, strict=True):
                repo.__dict__.clear()
                repo.__dict__.update(state)
            floor.interruptions = FakeProductionOrderInterruptionRepository(floor.orders._orders)
            floor.bus.published.clear()
            return
        floor.interruptions = FakeProductionOrderInterruptionRepository(floor.orders._orders)
        self.assert_status_events(lot_before, positions_before)

    def rolled_back(self) -> tuple[object, ...]:
        """The fakes a refused request restores, copied together so the
        references between them survive."""
        floor = self.floor
        return (
            floor.lots,
            floor.orders,
            floor.made_allocations,
            floor.made_demands,
            floor.source_demands,
            floor.order_items,
            floor.parent_orders,
        )

    def assert_status_events(self, lot_before: str, positions_before: dict[int, str]) -> None:
        published = self.floor.bus.published
        lot_events = [
            (e.old_status.value, e.new_status.value)
            for e in published
            if isinstance(e, LotStatusChanged)
        ]
        after = self.lot.status
        assert lot_events == ([(lot_before, after)] if after != lot_before else [])
        positions_after = {p.id: p.status for p in self.positions()}
        changed = sorted(
            (position_id, old, positions_after[position_id])
            for position_id, old in positions_before.items()
            if position_id in positions_after and positions_after[position_id] != old
        )
        position_events = sorted(
            (e.position_id, e.old_status.value, e.new_status.value)
            for e in published
            if isinstance(e, LotPositionStatusChanged)
        )
        assert position_events == changed

    # ── Order rules ──────────────────────────────────────────────────

    def startable(self) -> list[int]:
        """The orders a start or resume is offered for that the use case
        accepts: the intent table allows it and the position has input
        beyond what it completed, as StartProductionOrder checks."""
        lot = self.lot
        raw = self.floor.lots._raw_material_arrived_by_demand.get(lot.input_demand_id or 0)
        positions = {p.id: p for p in lot.positions}
        startable = []
        for order_id in self.allowing(LifecycleAction.START, LifecycleAction.RESUME):
            position = positions.get(self.floor.orders._orders[order_id].lot_position_id)
            if position is None:
                continue
            available = available_input(
                lot.positions,
                lot.quantity,
                position.sequence,
                raw if position.sequence == 1 else None,
            )
            if available > position.quantity_completed + _EPS:
                startable.append(order_id)
        return startable

    @precondition(lambda self: self.startable())
    @rule(data=st.data())
    def start_or_resume(self, data: st.DataObject) -> None:
        order_id = data.draw(st.sampled_from(self.startable()))
        self.request(
            lambda c: StartProductionOrder(
                self.floor.orders,
                self.floor.lots,
                event_bus=self.floor.bus,
                uow=self.floor.uow,
                **c,  # type: ignore[arg-type]
            ).execute(_ACTOR, order_id, StartProductionOrderCommand())
        )

    @precondition(lambda self: self.allowing(LifecycleAction.RECORD_COMPLETION))
    @rule(data=st.data(), all_of_it=st.booleans())
    def record_completion(self, data: st.DataObject, all_of_it: bool) -> None:
        order_id = data.draw(st.sampled_from(self.allowing(LifecycleAction.RECORD_COMPLETION)))
        order = self.floor.orders._orders[order_id]
        remaining = order.quantity - sum(c.quantity for c in order.completions)
        if remaining <= _EPS:
            return
        quantity = remaining if all_of_it else min(remaining, 1.0)
        self.request(lambda _c: self.floor.complete(order_id, quantity))

    @precondition(lambda self: self.allowing(LifecycleAction.SCRAP))
    @rule(data=st.data(), now=st.integers(0, 2))
    def scrap(self, data: st.DataObject, now: int) -> None:
        """Drawn one time in three, so the lot keeps most of its pieces."""
        if now:
            return
        order_id = data.draw(st.sampled_from(self.allowing(LifecycleAction.SCRAP)))
        self.request(lambda _c: self.floor.scrap(order_id, 1.0))

    @precondition(lambda self: self.allowing(LifecycleAction.CANCEL))
    @rule(data=st.data(), now=st.integers(0, 3))
    def cancel_order(self, data: st.DataObject, now: int) -> None:
        """Drawn one time in four, so most orders get to work."""
        if now:
            return
        order_id = data.draw(st.sampled_from(self.allowing(LifecycleAction.CANCEL)))
        self.request(
            lambda c: CancelProductionOrder(
                self.floor.orders,
                self.floor.lots,
                event_bus=self.floor.bus,
                uow=self.floor.uow,
                **c,  # type: ignore[arg-type]
            ).execute(_ACTOR, order_id, CancelProductionOrderCommand())
        )

    # ── Structure rules ──────────────────────────────────────────────

    def second_remaining(self) -> float:
        """What the second position still lacks in live work, 0 without it."""
        position = self.second()
        if position is None:
            return 0.0
        return compute_position_remaining(
            position.quantity, position.order_item_quantity, position.production_orders
        )

    @precondition(
        lambda self: self.lot.status not in TERMINAL_LOT_STATUSES and self.second_remaining() >= 1.0
    )
    @rule(all_of_it=st.booleans())
    def assign_or_top_up_the_second_position(self, all_of_it: bool) -> None:
        """Assigns what is left, or one piece of it."""
        position = self.second()
        assert position is not None
        quantity = self.second_remaining() if all_of_it else 1.0
        machine = make_machine(1)
        machine.fabrication_method_ids = [1]
        self.request(
            lambda c: AssignInternalPosition(
                self.floor.lots,
                FakeProductionMachineRepository([machine]),
                self.floor.orders,
                FakeAdminSettingsRepository(),
                event_bus=self.floor.bus,
                uow=self.floor.uow,
                reconciler=c["reconciler"],  # type: ignore[arg-type]
            ).execute(
                _ACTOR,
                self.lot_id,
                position.id,
                AssignInternalPositionCommand(
                    orders=[AssignInternalPositionOrderInput(machine_id=1, quantity=quantity)]
                ),
            )
        )

    @precondition(
        lambda self: (
            self.lot.status not in TERMINAL_LOT_STATUSES
            and (position := self.second()) is not None
            and position.kind == LotPositionKind.UNASSIGNED.value
            and not has_progress(position)
        )
    )
    @rule(now=st.integers(0, 3))
    def delete_the_untouched_second_step(self, now: int) -> None:
        """Drawn one time in four, so the second position usually stays."""
        if now:
            return
        position = self.second()
        assert position is not None
        [step] = position.steps
        self.request(
            lambda c: DeleteLotStep(
                self.floor.lots,
                order_item_repo=self.floor.order_items,
                order_repo=FakeProductionOrderRepository(),
                uow=self.floor.uow,
                reconciler=c["reconciler"],  # type: ignore[arg-type]
            ).execute(_ACTOR, step.id)
        )

    # ── Lot rules ────────────────────────────────────────────────────

    @precondition(lambda self: self.lot.status in _HOLDABLE)
    @rule(now=st.integers(0, 2))
    def hold_lot(self, now: int) -> None:
        """Drawn one time in three."""
        if now:
            return
        self.request(
            lambda c: HoldLot(
                self.floor.lots,
                self.floor.orders,
                event_bus=self.floor.bus,
                uow=self.floor.uow,
                **c,  # type: ignore[arg-type]
            ).execute(_ACTOR, self.lot_id, HoldLotCommand(reason="Material check"))
        )

    @precondition(lambda self: self.lot.status == LotStatus.ON_HOLD.value)
    @rule()
    def resume_lot(self) -> None:
        self.request(
            lambda c: ResumeLot(
                self.floor.lots,
                self.floor.orders,
                event_bus=self.floor.bus,
                uow=self.floor.uow,
                **c,  # type: ignore[arg-type]
            ).execute(_ACTOR, self.lot_id)
        )

    @precondition(lambda self: self.lot.status not in TERMINAL_LOT_STATUSES)
    @rule(now=st.integers(0, 9))
    def cancel_lot(self, now: int) -> None:
        """Drawn one time in ten, so most runs keep the lot going."""
        if now:
            return
        floor = self.floor
        self.request(
            lambda c: CancelLot(
                floor.lots,
                floor.orders,
                floor.order_items,
                FakeBoughtItemAllocationRepository(),
                floor.made_allocations,
                floor.source_demands,
                floor.source_allocations,
                event_bus=floor.bus,
                uow=floor.uow,
                parent_order_repo=floor.parent_orders,
                **c,  # type: ignore[arg-type]
            ).execute(_ACTOR, self.lot_id, CancelLotCommand(reason="Customer dropped it"))
        )

    @precondition(
        lambda self: (
            self.lot.status not in TERMINAL_LOT_STATUSES and self.lot.quantity_completed > _EPS
        )
    )
    @rule(now=st.integers(0, 2))
    def force_complete_lot(self, now: int) -> None:
        """Only once the lot produced something, which a force-complete
        needs, and drawn one time in three."""
        if now:
            return
        self.force_complete()

    def finishing_order(self) -> int | None:
        """An order that can record a piece on the lot's last position once
        an untouched second position is gone, None without one."""
        positions = self.positions()
        second = self.second()
        untouched = (
            second is not None
            and second.kind == LotPositionKind.UNASSIGNED.value
            and not has_progress(second)
        )
        last = positions[0] if untouched else positions[-1]
        return next(
            (
                o
                for o in self.allowing(LifecycleAction.RECORD_COMPLETION)
                if self.floor.orders._orders[o].lot_position_id == last.id
            ),
            None,
        )

    @precondition(lambda self: self.lot.status in _HOLDABLE and self.finishing_order() is not None)
    @rule()
    def produce_hold_and_force_complete(self) -> None:
        """Requests that end a held lot by force: an untouched second step
        deleted, a piece made on the last position, a hold, and the
        force-complete."""
        order_id = self.finishing_order()
        assert order_id is not None
        second = self.second()
        if second is not None and second.kind == LotPositionKind.UNASSIGNED.value:
            [step] = second.steps
            self.request(
                lambda c: DeleteLotStep(
                    self.floor.lots,
                    order_item_repo=self.floor.order_items,
                    order_repo=FakeProductionOrderRepository(),
                    uow=self.floor.uow,
                    reconciler=c["reconciler"],  # type: ignore[arg-type]
                ).execute(_ACTOR, step.id)
            )
        self.request(lambda _c: self.floor.complete(order_id, 1.0))
        if self.lot.status in _HOLDABLE:
            self.request(
                lambda c: HoldLot(
                    self.floor.lots,
                    self.floor.orders,
                    event_bus=self.floor.bus,
                    uow=self.floor.uow,
                    **c,  # type: ignore[arg-type]
                ).execute(_ACTOR, self.lot_id, HoldLotCommand(reason="Material check"))
            )
        if self.lot.status not in TERMINAL_LOT_STATUSES:
            self.force_complete()

    def force_complete(self) -> None:
        floor = self.floor
        self.request(
            lambda c: CompleteLot(
                floor.lots,
                floor.orders,
                floor.order_items,
                event_bus=floor.bus,
                uow=floor.uow,
                parent_order_repo=floor.parent_orders,
                made_item_demand_repo=floor.made_demands,
                made_item_allocation_repo=floor.made_allocations,
                **c,  # type: ignore[arg-type],
                source_item_demand_repo=FakeSourceItemDemandRepository(),
                source_item_allocation_repo=FakeSourceItemAllocationRepository(),
                bought_allocation_repo=FakeBoughtItemAllocationRepository(),
            ).execute(_ACTOR, self.lot_id, CompleteLotCommand())
        )

    @rule()
    def look_again(self) -> None:
        """Changes nothing; it keeps a step available on a terminal lot."""

    # ── Invariants ───────────────────────────────────────────────────

    @invariant()
    def stored_values_equal_a_fresh_derivation(self) -> None:
        lot = self.lot
        views = {}
        for order in self.orders():
            view = copy.copy(order)
            view.lot_id = self.lot_id
            views[order.id] = view
        derived = derive_snapshot(LifecycleSnapshot(lots={lot.id: lot}, production_orders=views))
        assert lot.status == derived.lots[lot.id].status.value.value
        for position in lot.positions:
            fresh = derived.positions[position.id]
            assert position.kind == fresh.kind.value.value, position.id
            assert position.status == fresh.status.value.value, position.id
            assert (
                abs(position.quantity_completed - min(fresh.quantity_completed, position.quantity))
                <= _EPS
            ), position.id

    @invariant()
    def a_position_counts_every_piece_its_orders_completed(self) -> None:
        """Counted here from the orders alone, a canceled one's included."""
        for position in self.positions():
            made = sum(
                o.quantity_completed for o in self.orders() if o.lot_position_id == position.id
            )
            assert abs(position.quantity_completed - min(made, position.quantity)) <= _EPS

    @invariant()
    def a_lot_with_every_position_done_or_forced_is_completed(self) -> None:
        lot = self.lot
        if lot.canceled_at is not None or lot.quantity <= _EPS or not lot.positions:
            return
        if lot.force_completed_at is not None or all(
            p.status == "completed" for p in lot.positions
        ):
            assert lot.status == LotStatus.COMPLETED.value

    @invariant()
    def no_position_holds_more_than_the_one_before_it(self) -> None:
        quantities = [p.quantity for p in self.positions()]
        for earlier, later in itertools.pairwise(quantities):
            assert later <= earlier + _EPS

    @invariant()
    def a_reconciler_run_changes_nothing(self) -> None:
        reconciler = lot_reconciler(self.floor.lots, self.floor.orders)
        reconciler.touch_lots([self.lot_id])
        result = asyncio.run(reconciler.run(_ACTOR, NOW))
        assert result.changes == ()

    @invariant()
    def no_live_order_under_a_terminal_lot(self) -> None:
        if self.lot.status not in TERMINAL_LOT_STATUSES:
            return
        positions = {p.id for p in self.positions()}
        for order in self.orders():
            if order.lot_position_id in positions:
                assert order.status in _ENDED, order.id

    @invariant()
    def completed_counts_stay_within_quantity_and_input(self) -> None:
        lot = self.lot
        for position in lot.positions:
            assert position.quantity_completed <= position.quantity + _EPS, position.id
            raw = self.floor.lots._raw_material_arrived_by_demand.get(lot.input_demand_id or 0)
            available = available_input(lot.positions, lot.quantity, position.sequence, raw)
            assert position.quantity_completed <= available + _EPS, position.id

    @invariant()
    def on_hold_exactly_while_held_and_not_terminal(self) -> None:
        lot = self.lot
        if lot.status == LotStatus.ON_HOLD.value:
            assert lot.held_at is not None
        elif lot.held_at is not None:
            assert lot.status in TERMINAL_LOT_STATUSES


LotModel.TestCase.settings = model_settings(steps=40, weight=EXPENSIVE)
TestLotModel = LotModel.TestCase
