"""
A rule-based model of every lifecycle aggregate at once, run by Hypothesis
over the real use cases, one lifecycle reconciler per request with every
aggregate enabled, and the in-memory world of model_world.py: a lot of one
to three fabrication steps and an optional inspection, with up to three
made demands and its raw material demand; a supplier order with bought
lines, an optional SOURCE line for the raw material, the MADE lines of
external positions and bought demands, and a second order lines may move
to, and optionally a second lot that the first made demand shares with a
made demand of a lower id. Lots and their pieces are whole numbers; the bought and raw material
lines and demands are in metres and include fractions, which the derivation
compares within the shared tolerance.

The rules plan positions internally and externally and unassign external
ones, run the production orders (start, resume, pause, completion with an
inspection's rework and scrap, the reversal of a completion, scrap with or
without a replacement lot, split, merge, cancel), hold, resume, cancel and
force-complete the lot, request, submit, cancel and deliver all of the
order, mark, deliver, correct, close short, cancel, move and edit the
quantity of its lines, create, update and release bought allocations,
allocate the raw material demand to the SOURCE line, take bought and source
demands from stock, and cancel and fulfil demands of all three families.
Each subject is chosen where its intent table allows the action, and a use
case may still refuse it for a reason the table leaves to it; a refused
request rolls the world back as its transaction would. Composite rules take
runs to the ends of lots and orders: plan every position, run an order
through, book a piece and reverse it, split an order and merge it back,
order and receive a MADE line, finish a lot on hold, make a piece on a lot's
last position and force-complete it, scrap a whole lot, cancel a line and
deliver the rest of its order, and allocate exactly up to a line's capacity
or just past it. One rule takes an action an intent table refuses and
asserts the use case refuses it too; asking for the state a demand is
already in may also change nothing. Not driven here: appending a position,
demand and lot quantity edits and delete project, which their own tests
cover.

After every step: every stored status, kind and completed count equals a
fresh derivation of the whole world; oracles computed here from the rows
agree (an order is DELIVERED exactly when its live lines all received
their quantity, a demand FULFILLED or ORDERED exactly as its allocation
rows, delivery rows and lot counts say); a reconciler run over everything
changes nothing; the step published one status event per status change of
every aggregate and wrote one status line per event into that aggregate's
changelog; an aggregate that was terminal changed only through an intent
on an aggregate it shares a lot, an order or a line with; and the quantity
invariants of lines, production orders, positions, lots and allocations
hold, a live line never holding more allocations than its quantity and a
canceled one none, and an ended production order keeps no planned window.
A held lot whose positions all complete is COMPLETED.

The tests at the end pin cases in fixed sequences: an allocation onto a
canceled line and deliver-all on a draft order are refused, a placed MADE
line keeps its quantity when a disposition shrinks its position, and a made
demand cancel that cancels its lot ends the lot's completed position.
"""

import itertools
import sys
from collections.abc import Callable
from typing import Any

from hypothesis import currently_in_test_context
from hypothesis import event
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine
from hypothesis.stateful import initialize
from hypothesis.stateful import invariant
from hypothesis.stateful import precondition
from hypothesis.stateful import rule

from src.modules.catalogue.domain.events.bought_item_events import DemandItemStatusChanged
from src.modules.catalogue.domain.events.made_item_events import MadeItemDemandItemStatusChanged
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.errors import AllocationOrderItemCanceledError
from src.modules.fulfillment.domain.events.lot_events import LotPositionStatusChanged
from src.modules.fulfillment.domain.events.lot_events import LotStatusChanged
from src.modules.fulfillment.domain.events.order_events import OrderItemStatusChanged
from src.modules.fulfillment.domain.events.order_events import OrderStatusChanged
from src.modules.fulfillment.domain.events.production_order_events import (
    ProductionOrderStatusChanged,
)
from src.modules.fulfillment.domain.events.source_item_demand_events import (
    SourceItemDemandStatusChanged,
)
from src.modules.fulfillment.domain.services.lifecycle.intents import DEMAND_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import ORDER_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import ORDER_ITEM_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import PRODUCTION_ORDER_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import DemandContext
from src.modules.fulfillment.domain.services.lifecycle.intents import OrderItemContext
from src.modules.fulfillment.domain.services.lifecycle.snapshot import derive_snapshot
from src.modules.fulfillment.domain.services.lifecycle.stored import stored_completed_count
from src.modules.fulfillment.domain.services.lot_rules import TERMINAL_LOT_STATUSES
from src.modules.fulfillment.domain.services.lot_rules import assert_lot_action
from src.modules.fulfillment.domain.services.lot_rules import available_input
from src.modules.fulfillment.domain.services.lot_rules import compute_position_remaining
from src.modules.fulfillment.domain.services.order_rules import order_item_context
from src.modules.fulfillment.domain.services.production_order_rules import production_order_context
from src.modules.fulfillment.domain.services.production_time_rules import net_work_minutes
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.rejection_outcome import RejectionOutcome
from src.modules.platform.domain.exceptions import DomainError
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction
from tests.unit.lifecycle._profiles import EXPENSIVE
from tests.unit.lifecycle._profiles import model_settings
from tests.unit.lifecycle._transitions import record as record_transitions
from tests.unit.lifecycle.model_world import ACTOR
from tests.unit.lifecycle.model_world import ORDER_ID
from tests.unit.lifecycle.model_world import OTHER_ORDER_ID
from tests.unit.lifecycle.model_world import Outcome
from tests.unit.lifecycle.model_world import Spec
from tests.unit.lifecycle.model_world import World

_EPS = 1e-6
_A = LifecycleAction

# The statuses no further work leaves, per aggregate kind of status_table.
_TERMINAL = {
    "lot": frozenset({"completed", "canceled", "scrapped"}),
    "position": frozenset({"completed", "canceled"}),
    "production_order": frozenset({"completed", "canceled"}),
    "order": frozenset({"delivered", "canceled"}),
    "line": frozenset({"delivered", "canceled"}),
    "bought_demand": frozenset({"fulfilled", "canceled"}),
    "made_demand": frozenset({"fulfilled", "canceled"}),
    "source_demand": frozenset({"fulfilled", "canceled"}),
}
_ENDED = frozenset({ProductionOrderStatus.COMPLETED.value, ProductionOrderStatus.CANCELED.value})
_HOLDABLE = frozenset(
    {LotStatus.PARTIALLY_PLANNED.value, LotStatus.PLANNED.value, LotStatus.IN_PROGRESS.value}
)
# Which status_table key each status event reports, and its id field.
_EVENT_KEYS: dict[type, tuple[str, str]] = {
    LotStatusChanged: ("lot", "lot_id"),
    LotPositionStatusChanged: ("position", "position_id"),
    ProductionOrderStatusChanged: ("production_order", "production_order_id"),
    OrderStatusChanged: ("order", "order_id"),
    OrderItemStatusChanged: ("line", "order_item_id"),
    DemandItemStatusChanged: ("bought_demand", "demand_id"),
    MadeItemDemandItemStatusChanged: ("made_demand", "demand_id"),
    SourceItemDemandStatusChanged: ("source_demand", "demand_id"),
}
_PRODUCTION_ORDER_ACTIONS = (_A.START, _A.RESUME, _A.PAUSE, _A.CANCEL, _A.RECORD_COMPLETION)
_LOT_ACTIONS = (_A.HOLD, _A.RESUME, _A.CANCEL, _A.FORCE_COMPLETE)
# Deliver-all books each line by the line rule and refuses no order as a
# whole, so the order's DELIVER rule is not checked for refusals.
_ORDER_ACTIONS = (_A.MARK_REQUESTED, _A.MARK_ORDERED, _A.CANCEL)
_LINE_ACTIONS = (
    _A.MARK_REQUESTED,
    _A.MARK_ORDERED,
    _A.DELIVER,
    _A.CORRECT_DELIVERY,
    _A.CLOSE_SHORT,
    _A.CANCEL,
    _A.MOVE,
)
_DEMAND_ACTIONS = (_A.CANCEL, _A.FULFIL, _A.ALLOCATE)

_LOT_QUANTITIES = (1.0, 2.0, 4.0, 6.0, 20.0)
_SHARES = (0.25, 0.5)


def _note(text: str) -> None:
    """Counts `text` in Hypothesis' statistics when a run records them; a
    fixed test calling the model's steps records nothing."""
    if currently_in_test_context():
        event(text)


def _kind(key: str) -> str:
    return key.split("#", 1)[0]


class LifecycleModel(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self.world: World | None = None

    @initialize(
        # Short lots are drawn more often, so runs reach their end.
        steps=st.sampled_from((1, 1, 2, 3)),
        inspection_last=st.sampled_from((False, False, True)),
        lot_quantity=st.sampled_from(_LOT_QUANTITIES),
        made_shares=st.lists(st.sampled_from(_SHARES), max_size=3),
        bought_lines=st.lists(st.sampled_from((1.0, 2.5, 4.0)), min_size=1, max_size=2),
        bought_demands=st.lists(st.sampled_from((0.5, 1.5, 3.0, 5.0, 5.0)), min_size=1, max_size=2),
        source_line=st.sampled_from((None, 2.0, 6.0)),
        neighbour_lot=st.sampled_from((None, None, 2.0, 4.0)),
    )
    def build(
        self,
        steps: int,
        inspection_last: bool,
        lot_quantity: float,
        made_shares: list[float],
        bought_lines: list[float],
        bought_demands: list[float],
        source_line: float | None,
        neighbour_lot: float | None,
    ) -> None:
        made: list[float] = []
        for share in made_shares:
            pieces = float(int(share * lot_quantity))
            if pieces > 0 and sum(made) + pieces <= lot_quantity + _EPS:
                made.append(pieces)
        self.world = World(
            Spec(
                steps=steps + (1 if inspection_last else 0),
                inspection_last=inspection_last,
                lot_quantity=lot_quantity,
                made_demands=tuple(made),
                bought_lines=tuple(bought_lines),
                bought_demands=tuple(bought_demands),
                source_line=source_line,
                neighbour_lot=neighbour_lot,
            )
        )

    @property
    def w(self) -> World:
        assert self.world is not None
        return self.world

    # ── Steps ────────────────────────────────────────────────────────

    def step(self, subject: str, call: Callable[[], Outcome]) -> Outcome:
        """Runs one request on `subject` (a status_table key) and checks
        what it did against the stored statuses before and after."""
        before = self.w.status_table()
        trees = self.trees()
        changelogs = self.changelog_lengths()
        self.w.last_request = ""
        outcome = call()
        # The calling rule's name, so a run's statistics show how often each
        # rule went through.
        rule_name = sys._getframe(1).f_code.co_name
        _note(f"{rule_name}: {'refused' if outcome.refused else 'done'}")
        if outcome.refused is None:
            after = self.w.status_table()
            assert self.w.last_request, "the request ran through no World method"
            record_transitions(before, after, subject, self.w.last_request)
            for key, tree in self.trees().items():
                trees[key] = trees.get(key, set()) | tree
            self.assert_status_events(before, after, outcome.published)
            self.assert_changelog_lines(changelogs, outcome.published)
            self.assert_terminal_changes(subject, before, after, trees)
        return outcome

    def refused(self, call: Callable[[], Outcome], *, same_again: bool = False) -> None:
        """Runs a request the intent table refuses: the use case must refuse
        it too. With `same_again`, the request asks for the state the
        subject is already in (cancel a canceled made demand), which a use
        case may also answer by changing nothing."""
        before = (self.w.status_table(), self.changelog_lengths())
        outcome = call()
        if outcome.refused is not None:
            return
        assert same_again, "the use case accepted what its table refuses"
        assert outcome.published == []
        assert (self.w.status_table(), self.changelog_lengths()) == before

    def assert_status_events(
        self, before: dict[str, str], after: dict[str, str], published: list[object]
    ) -> None:
        """One status event per status change of an existing aggregate, and
        at most one, ending at its stored status, for a new one."""
        reported: dict[str, list[tuple[str, str]]] = {}
        for e in published:
            found = _EVENT_KEYS.get(type(e))
            if found is None:
                continue
            kind, id_field = found
            key = f"{kind}#{getattr(e, id_field)}"
            reported.setdefault(key, []).append(
                (e.old_status.value, e.new_status.value)  # type: ignore[attr-defined]
            )
        for key, new in after.items():
            status = new.split("/")[0]
            if key in before:
                old = before[key].split("/")[0]
                expected = [(old, status)] if old != status else []
                assert reported.pop(key, []) == expected, key
            else:
                events = reported.pop(key, [])
                assert len(events) <= 1 and all(e[1] == status for e in events), key
        assert not reported, reported

    def changelog_lengths(self) -> dict[str, int]:
        return {key: len(changes) for key, changes in self.changelogs().items()}

    def changelogs(self) -> dict[str, list[str]]:
        w = self.w
        found: dict[str, list[str]] = {}
        for lot in w.lots():
            found[f"lot#{lot.id}"] = lot.changes
            for p in lot.positions:
                found[f"position#{p.id}"] = p.changes
        for o in w.production_orders():
            found[f"production_order#{o.id}"] = o.changes
        for order in w.orders._orders.values():
            found[f"order#{order.id}"] = order.changes
        for line in w.order_lines():
            found[f"line#{line.id}"] = line.changes
        for d in w.bought_demands._demands.values():
            found[f"bought_demand#{d.id}"] = d.changes
        for d in w.floor.made_demands._demands.values():
            found[f"made_demand#{d.id}"] = d.changes
        for d in w.floor.source_demands._demands.values():
            found[f"source_demand#{d.id}"] = d.changes
        return found

    def assert_changelog_lines(self, lengths: dict[str, int], published: list[object]) -> None:
        """The reconciler writes one `Status: old → new` line into an
        aggregate's changelog for each status change it publishes."""
        events: dict[str, int] = {}
        for e in published:
            found = _EVENT_KEYS.get(type(e))
            if found is not None:
                key = f"{found[0]}#{getattr(e, found[1])}"
                events[key] = events.get(key, 0) + 1
        for key, changes in self.changelogs().items():
            added = changes[lengths.get(key, 0) :]
            lines = sum(1 for line in added if ", Status: " in line and " → " in line)
            assert lines == events.get(key, 0), (key, added)

    def ancestors(self, key: str) -> set[str]:
        """What `key` rolls up into: a position's lot, a production order's
        position and lot, a line's order and, for a MADE line, its position
        and lot, and a demand's allocated lines and lots with theirs."""
        w = self.w
        kind, raw = key.split("#", 1)
        row_id = int(raw)
        positions = w.floor.lots._positions
        found: set[str] = set()
        if kind == "position" and row_id in positions:
            found.add(f"lot#{positions[row_id].lot_id}")
        elif kind == "production_order":
            order = w.floor.orders._orders.get(row_id)
            if order is not None and order.lot_position_id in positions:
                found.add(f"position#{order.lot_position_id}")
                found |= self.ancestors(f"position#{order.lot_position_id}")
        elif kind == "line":
            line = w.lines._items.get(row_id)
            if line is not None:
                found.add(f"order#{line.order_id}")
                if line.lot_position_id in positions:
                    found.add(f"position#{line.lot_position_id}")
                    found |= self.ancestors(f"position#{line.lot_position_id}")
        elif kind == "bought_demand":
            for a in w.bought_allocations._allocations:
                if a.demand_item_id == row_id and a.order_item_id is not None:
                    found.add(f"line#{a.order_item_id}")
                    found |= self.ancestors(f"line#{a.order_item_id}")
        elif kind == "made_demand":
            for a in w.floor.made_allocations._allocations:
                if a.demand_item_id == row_id and a.lot_id is not None:
                    found.add(f"lot#{a.lot_id}")
        elif kind == "source_demand":
            demand = w.floor.source_demands._demands.get(row_id)
            if demand is not None and demand.lot_id is not None:
                found.add(f"lot#{demand.lot_id}")
            for a in w.floor.source_allocations.allocations:
                if a.demand_item_id == row_id and a.order_item_id is not None:
                    found.add(f"line#{a.order_item_id}")
                    found |= self.ancestors(f"line#{a.order_item_id}")
        return found

    def trees(self) -> dict[str, set[str]]:
        """Every aggregate with what it rolls up into, itself included."""
        return {key: {key} | self.ancestors(key) for key in self.w.status_table()}

    def assert_terminal_changes(
        self,
        subject: str,
        before: dict[str, str],
        after: dict[str, str],
        trees: dict[str, set[str]],
    ) -> None:
        """An aggregate that was terminal changes only through an intent on
        an aggregate it shares a lot, an order or a line with, before or
        after the step: itself, what it rolls up into (a line reopening its
        order), what rolls up into it (a lot cancel ending its positions), a
        sibling (a new MADE line reopening a delivered order), or a demand
        allocated to the same lot or line (a made demand cancel that cancels
        its lot), never through an intent on an unrelated aggregate.
        `trees` holds each aggregate's tree from before and after the step,
        since the step may delete the allocation that linked them."""
        for key, old in before.items():
            status = old.split("/")[0]
            if status not in _TERMINAL[_kind(key)] or after.get(key, old) == old:
                continue
            related = bool(trees.get(subject, {subject}) & trees.get(key, {key})) or any(
                subject in tree and key in tree for tree in trees.values()
            )
            assert related, (subject, key, old, after[key])

    # ── Choosing subjects ────────────────────────────────────────────

    def lot_of(self, order: ProductionOrder) -> ProductionLot | None:
        position = self.w.floor.lots._positions.get(order.lot_position_id)
        if position is None:
            return None
        return self.w.floor.lots._hydrate(self.w.floor.lots._lots[position.lot_id])

    def order_allows(self, order: ProductionOrder, action: LifecycleAction) -> bool:
        lot = self.lot_of(order)
        held = lot is not None and lot.status == LotStatus.ON_HOLD.value
        terminal = lot is not None and lot.status in TERMINAL_LOT_STATUSES
        context = production_order_context(order, lot_held=held, lot_terminal=terminal)
        return PRODUCTION_ORDER_INTENTS.check(action, order, context, ACTOR) is None

    def orders_allowing(self, *actions: LifecycleAction) -> list[int]:
        return [
            o.id
            for o in self.w.production_orders()
            if any(self.order_allows(o, action) for action in actions)
        ]

    def startable(self) -> list[int]:
        """Orders a start or resume is offered for whose position has input
        beyond what it completed, as StartProductionOrder checks."""
        found = []
        for order_id in self.orders_allowing(_A.START, _A.RESUME):
            order = self.w.floor.orders._orders[order_id]
            lot = self.lot_of(order)
            if lot is None:
                continue
            position = next(p for p in lot.positions if p.id == order.lot_position_id)
            raw = self.w.floor.lots._raw_material_arrived_by_demand.get(lot.input_demand_id or 0)
            available = available_input(
                lot.positions,
                lot.quantity,
                position.sequence,
                raw if position.sequence == 1 else None,
            )
            if available > position.quantity_completed + _EPS:
                found.append(order_id)
        return found

    def lot_allows(self, lot: ProductionLot, action: LifecycleAction) -> bool:
        try:
            assert_lot_action(action, lot, ACTOR)
        except DomainError:
            return False
        return True

    def lots_allowing(self, action: LifecycleAction) -> list[int]:
        return [lot.id for lot in self.w.lots() if self.lot_allows(lot, action)]

    def line_allows(self, line_id: int, action: LifecycleAction) -> bool:
        line = self.w.lines._items[line_id]
        context = order_item_context(self.w.orders._orders[line.order_id])
        return ORDER_ITEM_INTENTS.check(action, line, context, ACTOR) is None

    def lines_allowing(self, action: LifecycleAction) -> list[int]:
        return [line.id for line in self.w.order_lines() if self.line_allows(line.id, action)]

    def order_allows_action(self, action: LifecycleAction) -> bool:
        order = self.w.orders._orders[ORDER_ID]
        return action in ORDER_INTENTS.allowed_actions(order, None, ACTOR)

    def bought_demand_allows(self, demand_id: int, action: LifecycleAction) -> bool:
        demand = self.w.bought_demands._demands[demand_id]
        held = any(a.demand_item_id == demand_id for a in self.w.bought_allocations._allocations)
        context = DemandContext(has_allocations=held)
        return DEMAND_INTENTS.check(action, demand, context, ACTOR) is None

    def made_demand_allows(self, demand_id: int, action: LifecycleAction) -> bool:
        demand = self.w.floor.made_demands._demands[demand_id]
        held = any(
            a.demand_item_id == demand_id for a in self.w.floor.made_allocations._allocations
        )
        context = DemandContext(has_allocations=held)
        return DEMAND_INTENTS.check(action, demand, context, ACTOR) is None

    def source_demand_allows(self, demand_id: int, action: LifecycleAction) -> bool:
        demand = self.w.floor.source_demands._demands[demand_id]
        held = any(
            a.demand_item_id == demand_id for a in self.w.floor.source_allocations.allocations
        )
        context = DemandContext(has_allocations=held)
        return DEMAND_INTENTS.check(action, demand, context, ACTOR) is None

    def plannable(self) -> list[tuple[int, float]]:
        """(position, quantity no live work covers yet) of every position of
        a lot that is not terminal."""
        found = []
        for lot in self.w.lots():
            if lot.status in TERMINAL_LOT_STATUSES:
                continue
            for p in lot.positions:
                line = next(
                    (
                        i
                        for i in self.w.made_lines()
                        if i.lot_position_id == p.id and i.status != OrderItemStatus.CANCELED.value
                    ),
                    None,
                )
                remaining = compute_position_remaining(
                    p.quantity, line.quantity if line else None, p.production_orders
                )
                if remaining > _EPS:
                    found.append((p.id, round(remaining, 6)))
        return found

    def is_inspection(self, position: LotPosition) -> bool:
        return any(s.role == StepRole.INSPECTION.value for s in position.steps)

    def position_of(self, order: ProductionOrder) -> LotPosition:
        return self.w.floor.lots._hydrate(
            self.w.floor.lots._lots[self.w.floor.lots._positions[order.lot_position_id].lot_id]
        ).positions[
            [
                p.id
                for p in self.w.floor.lots._hydrate(
                    self.w.floor.lots._lots[
                        self.w.floor.lots._positions[order.lot_position_id].lot_id
                    ]
                ).positions
            ].index(order.lot_position_id)
        ]

    # ── Planning rules ───────────────────────────────────────────────

    @precondition(lambda self: self.world is not None and self.plannable())
    @rule(data=st.data(), all_of_it=st.booleans())
    def assign_internal(self, data: st.DataObject, all_of_it: bool) -> None:
        position_id, remaining = data.draw(st.sampled_from(self.plannable()))
        quantity = remaining if all_of_it else min(remaining, 1.0)
        self.step(f"position#{position_id}", lambda: self.w.assign_internal(position_id, quantity))

    @precondition(lambda self: self.world is not None and self.plannable())
    @rule(data=st.data(), all_of_it=st.booleans())
    def assign_external(self, data: st.DataObject, all_of_it: bool) -> None:
        position_id, remaining = data.draw(st.sampled_from(self.plannable()))
        quantity = None if all_of_it else min(remaining, 1.0)
        self.step(f"position#{position_id}", lambda: self.w.assign_external(position_id, quantity))

    @precondition(lambda self: self.world is not None and self.plannable())
    @rule(data=st.data())
    def plan_every_position(self, data: st.DataObject) -> None:
        """Plans everything left on every position, each internally or
        externally as drawn, so runs get to work on whole lots."""
        for position_id, remaining in self.plannable():
            external = data.draw(st.booleans(), label="external")
            self.step(f"position#{position_id}", self.planning(position_id, remaining, external))

    def planning(self, position_id: int, remaining: float, external: bool) -> Callable[[], Outcome]:
        """The request that plans what is left on a position."""
        if external:
            return lambda: self.w.assign_external(position_id)
        return lambda: self.w.assign_internal(position_id, remaining)

    @precondition(lambda self: self.world is not None and self.w.made_lines())
    @rule(data=st.data(), now=st.integers(0, 2))
    def unassign_external(self, data: st.DataObject, now: int) -> None:
        """Drawn one time in three."""
        if now:
            return
        line = data.draw(st.sampled_from(self.w.made_lines()))
        if line.lot_position_id is None:
            return
        self.step(
            f"position#{line.lot_position_id}",
            lambda: self.w.unassign_external(line.lot_position_id or 0),
        )

    # ── Production order rules ───────────────────────────────────────

    @precondition(lambda self: self.world is not None and self.startable())
    @rule(data=st.data())
    def start_or_resume(self, data: st.DataObject) -> None:
        order_id = data.draw(st.sampled_from(self.startable()))
        self.step(f"production_order#{order_id}", lambda: self.w.start(order_id))

    @precondition(lambda self: self.world is not None and self.orders_allowing(_A.PAUSE))
    @rule(data=st.data())
    def pause(self, data: st.DataObject) -> None:
        order_id = data.draw(st.sampled_from(self.orders_allowing(_A.PAUSE)))
        self.step(f"production_order#{order_id}", lambda: self.w.pause(order_id))

    @precondition(
        lambda self: self.world is not None and self.orders_allowing(_A.RECORD_COMPLETION)
    )
    @rule(data=st.data(), split=st.sampled_from(("one", "all", "rework", "scrap")))
    def record_completion(self, data: st.DataObject, split: str) -> None:
        """Records one piece or all that is left; on an inspection position a
        rejected piece is reworked or scrapped."""
        order_id = data.draw(st.sampled_from(self.orders_allowing(_A.RECORD_COMPLETION)))
        order = self.w.floor.orders._orders[order_id]
        remaining = round(order.quantity - sum(c.quantity for c in order.completions), 6)
        if remaining <= _EPS:
            return
        quantity = remaining if split == "all" else min(remaining, 1.0)
        inspection = self.is_inspection(self.position_of(order))
        if inspection and split in ("rework", "scrap"):
            rejected = min(quantity, 1.0)
            rework, scrap = (rejected, 0.0) if split == "rework" else (0.0, rejected)
            outcome = lambda: self.w.complete(  # noqa: E731
                order_id, quantity, rejected=rejected, rework=rework, scrap=scrap
            )
        else:
            outcome = lambda: self.w.complete(order_id, quantity)  # noqa: E731
        self.step(f"production_order#{order_id}", outcome)

    @precondition(lambda self: self.world is not None and self.orders_allowing(_A.SCRAP))
    @rule(data=st.data(), now=st.integers(0, 2), replace=st.booleans())
    def scrap(self, data: st.DataObject, now: int, replace: bool) -> None:
        """Drawn one time in three, so the lot keeps most of its pieces."""
        if now:
            return
        order_id = data.draw(st.sampled_from(self.orders_allowing(_A.SCRAP)))
        self.step(
            f"production_order#{order_id}", lambda: self.w.scrap(order_id, 1.0, replace=replace)
        )

    @precondition(lambda self: self.world is not None and self.orders_allowing(_A.CANCEL))
    @rule(data=st.data(), now=st.integers(0, 3))
    def cancel_production_order(self, data: st.DataObject, now: int) -> None:
        """Drawn one time in four."""
        if now:
            return
        order_id = data.draw(st.sampled_from(self.orders_allowing(_A.CANCEL)))
        self.step(f"production_order#{order_id}", lambda: self.w.cancel_production_order(order_id))

    def reversible(self) -> list[tuple[int, int]]:
        """(order, completion) pairs a reversal is offered for: a completion
        that rejected nothing, is no reversal and is not reversed yet, on
        an order whose table allows the reversal."""
        found = []
        for order_id in self.orders_allowing(_A.REVERSE_COMPLETION):
            completions = self.w.floor.orders._orders[order_id].completions
            reversed_ids = {c.reverses_completion_id for c in completions}
            found.extend(
                (order_id, c.id)
                for c in completions
                if c.reverses_completion_id is None
                and c.id not in reversed_ids
                and c.quantity_rejected <= _EPS
            )
        return found

    @precondition(lambda self: self.world is not None and self.reversible())
    @rule(data=st.data())
    def reverse_completion(self, data: st.DataObject) -> None:
        order_id, completion_id = data.draw(st.sampled_from(self.reversible()))
        self.step(
            f"production_order#{order_id}",
            lambda: self.w.reverse_completion(order_id, completion_id),
        )

    def splittable(self) -> list[int]:
        return [
            order_id
            for order_id in self.orders_allowing(_A.SPLIT)
            if self.w.floor.orders._orders[order_id].quantity >= 2.0
        ]

    @precondition(lambda self: self.world is not None and self.splittable())
    @rule(data=st.data())
    def split(self, data: st.DataObject) -> None:
        order_id = data.draw(st.sampled_from(self.splittable()))
        quantity = self.w.floor.orders._orders[order_id].quantity
        self.step(
            f"production_order#{order_id}", lambda: self.w.split(order_id, [quantity - 1.0, 1.0])
        )

    def mergeable(self) -> list[tuple[int, int]]:
        """Pairs of queued orders of one position, machine and pool."""
        orders = [self.w.floor.orders._orders[i] for i in self.orders_allowing(_A.MERGE)]
        return [
            (a.id, b.id)
            for a, b in itertools.combinations(orders, 2)
            if (a.lot_position_id, a.machine_id, a.machine_pool_id)
            == (b.lot_position_id, b.machine_id, b.machine_pool_id)
        ]

    @precondition(lambda self: self.world is not None and self.mergeable())
    @rule(data=st.data())
    def merge(self, data: st.DataObject) -> None:
        pair = data.draw(st.sampled_from(self.mergeable()))
        self.step(f"production_order#{pair[0]}", lambda: self.w.merge(list(pair)))

    @precondition(
        lambda self: self.world is not None and self.orders_allowing(_A.RECORD_COMPLETION)
    )
    @rule(data=st.data(), all_of_it=st.booleans())
    def complete_then_reverse(self, data: st.DataObject, all_of_it: bool) -> None:
        """Books one piece, or every piece left, which completes the order,
        and takes the booking back, as a miscounted completion is."""
        order_id = data.draw(st.sampled_from(self.orders_allowing(_A.RECORD_COMPLETION)))
        order = self.w.floor.orders._orders[order_id]
        remaining = round(order.quantity - sum(c.quantity for c in order.completions), 6)
        if remaining < 1.0 - _EPS:
            return
        quantity = remaining if all_of_it else 1.0
        booked = {c.id for c in order.completions}
        outcome = self.step(
            f"production_order#{order_id}", lambda: self.w.complete(order_id, quantity)
        )
        if outcome.refused is not None:
            return
        completed = self.w.floor.orders._orders[order_id].completions
        new_id = next(c.id for c in completed if c.id not in booked)
        self.step(
            f"production_order#{order_id}",
            lambda: self.w.reverse_completion(order_id, new_id),
        )

    @precondition(lambda self: self.world is not None and self.splittable())
    @rule(data=st.data())
    def split_then_merge(self, data: st.DataObject) -> None:
        """Splits a queued order and merges its parts back into one."""
        order_id = data.draw(st.sampled_from(self.splittable()))
        quantity = self.w.floor.orders._orders[order_id].quantity
        before = set(self.w.floor.orders._orders)
        outcome = self.step(
            f"production_order#{order_id}", lambda: self.w.split(order_id, [quantity - 1.0, 1.0])
        )
        if outcome.refused is not None:
            return
        parts = [order_id, *sorted(set(self.w.floor.orders._orders) - before)]
        self.step(f"production_order#{order_id}", lambda: self.w.merge(parts))

    # ── Lot rules ────────────────────────────────────────────────────

    @precondition(lambda self: self.world is not None and self.lots_allowing(_A.HOLD))
    @rule(data=st.data(), now=st.integers(0, 2))
    def hold(self, data: st.DataObject, now: int) -> None:
        """Drawn one time in three."""
        if now:
            return
        lot_id = data.draw(st.sampled_from(self.lots_allowing(_A.HOLD)))
        self.step(f"lot#{lot_id}", lambda: self.w.hold(lot_id))

    @precondition(lambda self: self.world is not None and self.lots_allowing(_A.RESUME))
    @rule(data=st.data())
    def resume_lot(self, data: st.DataObject) -> None:
        lot_id = data.draw(st.sampled_from(self.lots_allowing(_A.RESUME)))
        self.step(f"lot#{lot_id}", lambda: self.w.resume_lot(lot_id))

    @precondition(lambda self: self.world is not None and self.lots_allowing(_A.CANCEL))
    @rule(data=st.data(), now=st.integers(0, 9))
    def cancel_lot(self, data: st.DataObject, now: int) -> None:
        """Drawn one time in ten, so most runs keep the lot going."""
        if now:
            return
        lot_id = data.draw(st.sampled_from(self.lots_allowing(_A.CANCEL)))
        self.step(f"lot#{lot_id}", lambda: self.w.cancel_lot_request(lot_id))

    def lots_with_live_work(self) -> list[int]:
        """Lots the cancel rule accepts that still hold a production order
        that has not ended, a live MADE line or a made allocation above zero,
        which a lot cancel must end or release."""
        w = self.w
        found = []
        for lot_id in self.lots_allowing(_A.CANCEL):
            lot = w.floor.lots._hydrate(w.floor.lots._lots[lot_id])
            orders = any(o.status not in _ENDED for p in lot.positions for o in p.production_orders)
            lines = any(self.live_made_line(p.id) is not None for p in lot.positions)
            held = any(
                a.lot_id == lot_id and a.quantity > _EPS
                for a in w.floor.made_allocations._allocations
            )
            if orders or lines or held:
                found.append(lot_id)
        return found

    @precondition(lambda self: self.world is not None and self.lots_with_live_work())
    @rule(data=st.data(), now=st.integers(0, 2))
    def cancel_a_lot_with_live_work(self, data: st.DataObject, now: int) -> None:
        """Cancels a lot while it still has work and allocations to end,
        drawn one time in three, so the cancel cascade is exercised before
        the composite rules finish the lots."""
        if now:
            return
        lot_id = data.draw(st.sampled_from(self.lots_with_live_work()))
        outcome = self.step(f"lot#{lot_id}", lambda: self.w.cancel_lot_request(lot_id))
        _note(f"lot cancel with live work: {outcome.refused is None}")

    @precondition(lambda self: self.world is not None and self.lots_allowing(_A.FORCE_COMPLETE))
    @rule(data=st.data(), now=st.integers(0, 2))
    def force_complete(self, data: st.DataObject, now: int) -> None:
        """Drawn one time in three, once a lot produced something."""
        if now:
            return
        lot_id = data.draw(st.sampled_from(self.lots_allowing(_A.FORCE_COMPLETE)))
        self.step(f"lot#{lot_id}", lambda: self.w.force_complete(lot_id))

    @precondition(lambda self: self.world is not None and self.startable())
    @rule(data=st.data(), split=st.sampled_from(("all", "rework", "scrap")))
    def run_a_production_order_through(self, data: st.DataObject, split: str) -> None:
        """Starts an order and records what it has left in one completion,
        on an inspection position with one piece reworked or scrapped, so
        runs reach completed positions and lots."""
        order_id = data.draw(st.sampled_from(self.startable()))
        self.step(f"production_order#{order_id}", lambda: self.w.start(order_id))
        order = self.w.floor.orders._orders[order_id]
        if not self.order_allows(order, _A.RECORD_COMPLETION):
            return
        remaining = round(order.quantity - sum(c.quantity for c in order.completions), 6)
        if remaining <= _EPS:
            return
        if self.is_inspection(self.position_of(order)) and split != "all":
            rejected = min(remaining, 1.0)
            rework, scrap = (rejected, 0.0) if split == "rework" else (0.0, rejected)
            self.step(
                f"production_order#{order_id}",
                lambda: self.w.complete(
                    order_id, remaining, rejected=rejected, rework=rework, scrap=scrap
                ),
            )
        else:
            self.step(f"production_order#{order_id}", lambda: self.w.complete(order_id, remaining))

    def unplaced_made_lines(self) -> list[int]:
        return [
            line.id for line in self.w.made_lines() if self.line_allows(line.id, _A.MARK_ORDERED)
        ]

    @precondition(lambda self: self.world is not None and self.unplaced_made_lines())
    @rule(data=st.data(), all_of_it=st.booleans())
    def order_and_receive_a_made_line(self, data: st.DataObject, all_of_it: bool) -> None:
        """Marks a MADE line ordered and receives what it awaits, or one
        piece of it, so runs reach the external ladder of a position."""
        line_id = data.draw(st.sampled_from(self.unplaced_made_lines()))
        self.step(f"line#{line_id}", lambda: self.w.mark_ordered(line_id))
        if self.line_allows(line_id, _A.DELIVER):
            accepted = None if all_of_it else 1.0
            self.step(f"line#{line_id}", lambda: self.w.deliver(line_id, accepted))

    def finishing_positions(self) -> list[int]:
        """Last positions, not inspections, of lots that are not ended or
        held, which are untouched or carry a live MADE line for their whole
        quantity: once the earlier positions are done, receiving everything
        on such a position completes its lot."""
        found = []
        for lot_id in self.drivable_lots():
            lot = self.w.floor.lots._hydrate(self.w.floor.lots._lots[lot_id])
            last = lot.positions[-1]
            if self.is_inspection(last):
                continue
            line = self.live_made_line(last.id)
            if line is not None:
                whole = abs(line.quantity - last.quantity) <= _EPS
                if whole and line.status in ("pending", "requested", "ordered"):
                    found.append(last.id)
            elif self.untouched(last):
                found.append(last.id)
        return found

    def live_made_line(self, position_id: int) -> Any:
        return next(
            (
                line
                for line in self.w.made_lines()
                if line.lot_position_id == position_id
                and line.status != OrderItemStatus.CANCELED.value
            ),
            None,
        )

    @precondition(lambda self: self.world is not None and self.finishing_positions())
    @rule(data=st.data())
    def hold_then_receive_the_last_position(self, data: st.DataObject) -> None:
        """Finishes a lot's earlier positions, gives its last position a
        MADE line if it has none, orders the line, holds the lot and receives
        what the line still awaits: the held lot completes through its own
        facts."""
        position_id = data.draw(st.sampled_from(self.finishing_positions()))
        lot_id = self.w.floor.lots._positions[position_id].lot_id
        lots = self.w.floor.lots
        for earlier in lots._hydrate(lots._lots[lot_id]).positions[:-1]:
            self.work_on(earlier.id, None)
        if self.live_made_line(position_id) is None:
            self.step(f"position#{position_id}", lambda: self.w.assign_external(position_id))
        line = self.live_made_line(position_id)
        if line is None:
            return
        line_id = line.id
        if self.line_allows(line_id, _A.MARK_ORDERED):
            self.step(f"line#{line_id}", lambda: self.w.mark_ordered(line_id))
        self.step(f"lot#{lot_id}", lambda: self.w.hold(lot_id))
        if self.line_allows(line_id, _A.DELIVER):
            self.step(f"line#{line_id}", lambda: self.w.deliver(line_id, None))
        _note(f"held lot after its last receipt: {self.w.floor.lots._lots[lot_id].status}")

    def untouched(self, position: LotPosition) -> bool:
        """No production order, no live MADE line and nothing completed."""
        return (
            not position.production_orders
            and self.live_made_line(position.id) is None
            and position.quantity_completed <= _EPS
        )

    def drivable_lots(self) -> list[int]:
        """Lots that are neither ended nor held."""
        return [
            lot.id
            for lot in self.w.lots()
            if lot.positions
            and lot.status not in TERMINAL_LOT_STATUSES
            and lot.status != LotStatus.ON_HOLD.value
        ]

    def work_on(self, position_id: int, quantity: float | None) -> None:
        """Puts `quantity` pieces (None: all it lacks) on a position: plans an
        untouched one internally, starts and records its live orders, or
        orders and receives its MADE line. A refused request just stops."""
        w = self.w
        lots = w.floor.lots
        position = next(
            p
            for p in lots._hydrate(lots._lots[lots._positions[position_id].lot_id]).positions
            if p.id == position_id
        )
        if self.untouched(position):
            self.step(
                f"position#{position_id}",
                lambda: w.assign_internal(position_id, position.quantity),
            )
        line = self.live_made_line(position_id)
        if line is not None:
            line_id = line.id
            if self.line_allows(line_id, _A.MARK_ORDERED):
                self.step(f"line#{line_id}", lambda: w.mark_ordered(line_id))
            if self.line_allows(line_id, _A.DELIVER):
                self.step(f"line#{line_id}", lambda: w.deliver(line_id, quantity))
        for order in [o for o in w.production_orders() if o.lot_position_id == position_id]:
            self.run_order(order, quantity)

    def run_order(self, order: ProductionOrder, quantity: float | None) -> None:
        """Starts an order if it can and records `quantity` pieces (None: all
        it has left) on it."""
        w, order_id = self.w, order.id
        if order_id in self.startable():
            self.step(f"production_order#{order_id}", lambda: w.start(order_id))
        if not self.order_allows(order, _A.RECORD_COMPLETION):
            return
        remaining = round(order.quantity - sum(c.quantity for c in order.completions), 6)
        pieces = remaining if quantity is None else min(remaining, quantity)
        if pieces > _EPS:
            self.step(f"production_order#{order_id}", lambda: w.complete(order_id, pieces))

    @precondition(lambda self: self.world is not None and self.drivable_lots())
    @rule(data=st.data())
    def produce_on_the_last_position_then_force_complete(self, data: st.DataObject) -> None:
        """Finishes a lot's earlier positions, makes one piece on its last
        one and force-completes the lot, which needs a produced piece; a
        refused request on the way leaves the rest to other rules."""
        lot_id = data.draw(st.sampled_from(self.drivable_lots()))
        w = self.w
        positions = [p.id for p in w.floor.lots._hydrate(w.floor.lots._lots[lot_id]).positions]
        for position_id in positions[:-1]:
            self.work_on(position_id, None)
        self.work_on(positions[-1], 1.0)
        lot = w.floor.lots._hydrate(w.floor.lots._lots[lot_id])
        if self.lot_allows(lot, _A.FORCE_COMPLETE):
            outcome = self.step(f"lot#{lot_id}", lambda: w.force_complete(lot_id))
            _note(f"force-complete after a piece: {outcome.refused is None}")

    def scrappable_lots(self) -> list[tuple[int, int | None]]:
        """(lot, production order) for lots that made nothing yet, whose first
        position has an order that can start or be scrapped, or is untouched
        and gets one (None)."""
        found: list[tuple[int, int | None]] = []
        able = set(self.startable()) | set(self.orders_allowing(_A.SCRAP))
        for lot in self.w.lots():
            if lot.status in TERMINAL_LOT_STATUSES or not lot.positions:
                continue
            if lot.status == LotStatus.ON_HOLD.value:
                continue
            if any(p.quantity_completed > _EPS for p in lot.positions):
                continue
            first = lot.positions[0]
            found += [(lot.id, o.id) for o in first.production_orders if o.id in able]
            if self.untouched(first):
                found.append((lot.id, None))
        return found

    @precondition(lambda self: self.world is not None and self.scrappable_lots())
    @rule(data=st.data())
    def scrap_the_whole_lot(self, data: st.DataObject) -> None:
        """Plans a lot's first position in one order if it is untouched,
        starts it and scraps the lot's whole quantity on it, which leaves the
        lot SCRAPPED."""
        lot_id, order_id = data.draw(st.sampled_from(self.scrappable_lots()))
        w = self.w
        if order_id is None:
            first = w.floor.lots._hydrate(w.floor.lots._lots[lot_id]).positions[0]
            self.step(f"position#{first.id}", lambda: w.assign_internal(first.id, first.quantity))
            orders = [o.id for o in w.production_orders() if o.lot_position_id == first.id]
            if not orders:
                return
            order_id = orders[-1]
        chosen = order_id
        order = w.floor.orders._orders[chosen]
        if not self.order_allows(order, _A.SCRAP):
            self.step(f"production_order#{chosen}", lambda: w.start(chosen))
        lot = self.lot_of(order)
        if lot is None or not self.order_allows(order, _A.SCRAP):
            return
        quantity = lot.quantity
        outcome = self.step(f"production_order#{chosen}", lambda: w.scrap(chosen, quantity))
        _note(f"whole-lot scrap: {outcome.refused is None}")

    # ── Order rules ──────────────────────────────────────────────────

    @precondition(
        lambda self: self.world is not None and self.order_allows_action(_A.MARK_REQUESTED)
    )
    @rule()
    def request_order(self) -> None:
        self.step(f"order#{ORDER_ID}", self.w.request_order)

    @precondition(lambda self: self.world is not None and self.order_allows_action(_A.MARK_ORDERED))
    @rule()
    def submit_order(self) -> None:
        self.step(f"order#{ORDER_ID}", self.w.submit_order)

    @precondition(lambda self: self.world is not None and self.order_allows_action(_A.CANCEL))
    @rule(now=st.integers(0, 7))
    def cancel_order(self, now: int) -> None:
        """Drawn one time in eight."""
        if now:
            return
        self.step(f"order#{ORDER_ID}", self.w.cancel_order)

    @precondition(lambda self: self.world is not None and self.lines_allowing(_A.DELIVER))
    @rule(now=st.integers(0, 2))
    def deliver_all(self, now: int) -> None:
        """Drawn one time in three, so lines also take partial deliveries."""
        if now:
            return
        self.step(f"order#{ORDER_ID}", self.w.deliver_all)

    @precondition(lambda self: self.world is not None and self.lines_allowing(_A.DELIVER))
    @rule(data=st.data(), now=st.integers(0, 3))
    def deliver_all_losing_a_piece(self, data: st.DataObject, now: int) -> None:
        """Drawn one time in four: deliver-all with one piece of a line lost
        at receipt, a MADE line's loss reaching its lot."""
        if now:
            return
        line_id = data.draw(st.sampled_from(self.lines_allowing(_A.DELIVER)))
        self.step(f"order#{ORDER_ID}", lambda: self.w.deliver_all(losing=line_id))

    @precondition(lambda self: self.world is not None and self.w.made_lines())
    @rule(data=st.data())
    def record_provision(self, data: st.DataObject) -> None:
        """Hands one piece to the supplier of a bought-in position, which the
        position's later changes must keep."""
        line = data.draw(st.sampled_from(self.w.made_lines()))
        if line.lot_position_id is None:
            return
        position_id = line.lot_position_id
        self.step(f"position#{position_id}", lambda: self.w.record_provision(position_id, 1.0))

    @precondition(lambda self: self.world is not None and self.lines_allowing(_A.MARK_REQUESTED))
    @rule(data=st.data())
    def mark_requested(self, data: st.DataObject) -> None:
        line_id = data.draw(st.sampled_from(self.lines_allowing(_A.MARK_REQUESTED)))
        self.step(f"line#{line_id}", lambda: self.w.mark_requested(line_id))

    @precondition(lambda self: self.world is not None and self.lines_allowing(_A.MARK_ORDERED))
    @rule(data=st.data())
    def mark_ordered(self, data: st.DataObject) -> None:
        line_id = data.draw(st.sampled_from(self.lines_allowing(_A.MARK_ORDERED)))
        self.step(f"line#{line_id}", lambda: self.w.mark_ordered(line_id))

    @precondition(lambda self: self.world is not None and self.lines_allowing(_A.DELIVER))
    @rule(
        data=st.data(),
        accepted=st.sampled_from((None, 0.5, 1.0)),
        rejected=st.sampled_from((0.0, 0.0, 1.0)),
        outcome=st.sampled_from((RejectionOutcome.LOST.value, RejectionOutcome.REDELIVER.value)),
    )
    def deliver(
        self, data: st.DataObject, accepted: float | None, rejected: float, outcome: str
    ) -> None:
        line_id = data.draw(st.sampled_from(self.lines_allowing(_A.DELIVER)))
        self.step(
            f"line#{line_id}",
            lambda: self.w.deliver(line_id, accepted, rejected=rejected, outcome=outcome),
        )

    def correctable(self) -> list[tuple[int, int, float]]:
        return [
            (line_id, row_id, open_pieces)
            for line_id in self.lines_allowing(_A.CORRECT_DELIVERY)
            for row_id, open_pieces in self.w.open_rows(line_id)
        ]

    @precondition(lambda self: self.world is not None and self.correctable())
    @rule(data=st.data(), all_of_it=st.booleans())
    def correct_delivery(self, data: st.DataObject, all_of_it: bool) -> None:
        line_id, row_id, open_pieces = data.draw(st.sampled_from(self.correctable()))
        quantity = open_pieces if all_of_it else min(open_pieces, 0.5)
        self.step(f"line#{line_id}", lambda: self.w.correct(line_id, row_id, quantity))

    def cancelable_beside_others(self) -> list[int]:
        """Lines the cancel rule accepts whose order has another live line."""
        found = []
        for line_id in self.lines_allowing(_A.CANCEL):
            order_id = self.w.lines._items[line_id].order_id
            others = [
                line
                for line in self.w.order_lines()
                if line.order_id == order_id and line.id != line_id and line.canceled_at is None
            ]
            if others:
                found.append(line_id)
        return found

    @precondition(lambda self: self.world is not None and self.cancelable_beside_others())
    @rule(data=st.data())
    def cancel_a_line_and_deliver_the_rest(self, data: st.DataObject) -> None:
        """Cancels one line of an order, places the order if it can be and
        delivers everything else on it, so orders with a canceled line beside
        delivered ones are reached."""
        line_id = data.draw(st.sampled_from(self.cancelable_beside_others()))
        order_id = self.w.lines._items[line_id].order_id
        self.step(f"line#{line_id}", lambda: self.w.cancel_line(line_id))
        if order_id != ORDER_ID:
            return
        if self.order_allows_action(_A.MARK_ORDERED):
            self.step(f"order#{ORDER_ID}", self.w.submit_order)
        if self.lines_allowing(_A.DELIVER):
            self.step(f"order#{ORDER_ID}", self.w.deliver_all)

    @precondition(lambda self: self.world is not None and self.lines_allowing(_A.CLOSE_SHORT))
    @rule(data=st.data(), now=st.integers(0, 2))
    def close_short(self, data: st.DataObject, now: int) -> None:
        """Drawn one time in three."""
        if now:
            return
        line_id = data.draw(st.sampled_from(self.lines_allowing(_A.CLOSE_SHORT)))
        self.step(f"line#{line_id}", lambda: self.w.close_short(line_id))

    def move_allows(self, line_id: int) -> bool:
        line = self.w.lines._items[line_id]
        target = self.w.orders._orders[self.target_of(line_id)]
        context = OrderItemContext(
            order_status=OrderStatus(self.w.orders._orders[line.order_id].status),
            target_order_canceled=target.canceled_at is not None,
        )
        return ORDER_ITEM_INTENTS.check(_A.MOVE, line, context, ACTOR) is None

    def target_of(self, line_id: int) -> int:
        """The other of the two orders."""
        own = self.w.lines._items[line_id].order_id
        return OTHER_ORDER_ID if own == ORDER_ID else ORDER_ID

    def movable(self) -> list[int]:
        return [line.id for line in self.w.order_lines() if self.move_allows(line.id)]

    @precondition(lambda self: self.world is not None and self.movable())
    @rule(data=st.data(), now=st.integers(0, 2))
    def move_line(self, data: st.DataObject, now: int) -> None:
        """Moves a line to the other order, drawn one time in three."""
        if now:
            return
        line_id = data.draw(st.sampled_from(self.movable()))
        self.step(f"line#{line_id}", lambda: self.w.move(line_id, self.target_of(line_id)))

    @precondition(lambda self: self.world is not None and self.lines_allowing(_A.CANCEL))
    @rule(data=st.data(), now=st.integers(0, 3))
    def cancel_line(self, data: st.DataObject, now: int) -> None:
        """Drawn one time in four."""
        if now:
            return
        line_id = data.draw(st.sampled_from(self.lines_allowing(_A.CANCEL)))
        self.step(f"line#{line_id}", lambda: self.w.cancel_line(line_id))

    # ── Demand rules ─────────────────────────────────────────────────

    def bought_lines(self) -> list[int]:
        """The bought lines an allocation may name, canceled ones included,
        which the allocation use case refuses."""
        return [
            line.id for line in self.w.order_lines() if line.line_type == OrderLineType.BOUGHT.value
        ]

    @precondition(lambda self: self.world is not None and self.w.bought_demands._demands)
    @rule(data=st.data(), quantity=st.sampled_from((0.5, 1.0, 1.5)))
    def allocate(self, data: st.DataObject, quantity: float) -> None:
        demand_id = data.draw(st.sampled_from(sorted(self.w.bought_demands._demands)))
        lines = self.bought_lines()
        if not lines:
            return
        line_id = data.draw(st.sampled_from(lines))
        if any(
            a.demand_item_id == demand_id and a.order_item_id == line_id
            for a in self.w.bought_allocations._allocations
        ):
            return
        self.step(
            f"bought_demand#{demand_id}", lambda: self.w.allocate(demand_id, line_id, quantity)
        )

    @precondition(lambda self: self.world is not None and self.w.bought_demands._demands)
    @rule(data=st.data(), quantity=st.sampled_from((0.5, 1.0)))
    def take_from_stock(self, data: st.DataObject, quantity: float) -> None:
        demand_id = data.draw(st.sampled_from(sorted(self.w.bought_demands._demands)))
        self.step(f"bought_demand#{demand_id}", lambda: self.w.take_from_stock(demand_id, quantity))

    def line_allocations(self) -> list[tuple[int, int]]:
        return sorted(
            (a.demand_item_id, a.order_item_id)
            for a in self.w.bought_allocations._allocations
            if a.order_item_id is not None
        )

    @precondition(lambda self: self.world is not None and self.line_allocations())
    @rule(data=st.data())
    def release(self, data: st.DataObject) -> None:
        demand_id, line_id = data.draw(st.sampled_from(self.line_allocations()))
        self.step(f"bought_demand#{demand_id}", lambda: self.w.release(demand_id, line_id))

    def free_on(self, line_id: int) -> float:
        """What a line may still take in allocations of both families."""
        w = self.w
        held = sum(
            a.quantity for a in w.bought_allocations._allocations if a.order_item_id == line_id
        ) + sum(
            a.quantity for a in w.floor.source_allocations.allocations if a.order_item_id == line_id
        )
        return round(w.lines._items[line_id].quantity - held, 6)

    def open_on(self, demand: Any, allocations: list[Any]) -> float:
        held = sum(a.quantity for a in allocations if a.demand_item_id == demand.id)
        return round(demand.quantity - held, 6)

    @precondition(lambda self: self.world is not None and self.w.bought_demands._demands)
    @rule(data=st.data(), past_the_brim=st.booleans())
    def allocate_to_the_brim(self, data: st.DataObject, past_the_brim: bool) -> None:
        """Allocates exactly what a bought line still takes, or half a piece
        more, which its capacity must refuse; the demand is chosen so its own
        open quantity does not refuse it first."""
        w = self.w
        pairs = [
            (demand.id, line_id, self.free_on(line_id))
            for demand in w.bought_demands._demands.values()
            for line_id in self.bought_lines()
            if not any(
                a.demand_item_id == demand.id and a.order_item_id == line_id
                for a in w.bought_allocations._allocations
            )
        ]
        quantity_of = (lambda free: free + 0.5) if past_the_brim else (lambda free: free)
        fitting = [
            (d, line, quantity_of(free))
            for d, line, free in pairs
            if quantity_of(free) > _EPS
            and quantity_of(free)
            <= self.open_on(w.bought_demands._demands[d], w.bought_allocations._allocations) + _EPS
        ]
        if not fitting:
            return
        demand_id, line_id, quantity = data.draw(st.sampled_from(fitting))
        outcome = self.step(
            f"bought_demand#{demand_id}", lambda: w.allocate(demand_id, line_id, quantity)
        )
        _note(f"to the brim{' and past it' if past_the_brim else ''}: {outcome.refused is None}")

    @precondition(lambda self: self.world is not None and self.line_allocations())
    @rule(data=st.data(), quantity=st.sampled_from((0.5, 1.0, 2.0, 4.0)))
    def update_allocation(self, data: st.DataObject, quantity: float) -> None:
        demand_id, line_id = data.draw(st.sampled_from(self.line_allocations()))
        self.step(
            f"bought_demand#{demand_id}",
            lambda: self.w.update_allocation(demand_id, line_id, quantity),
        )

    @precondition(lambda self: self.world is not None and self.lines_allowing(_A.EDIT_QUANTITY))
    @rule(data=st.data(), quantity=st.sampled_from((0.5, 1.0, 2.5, 6.0)))
    def edit_line_quantity(self, data: st.DataObject, quantity: float) -> None:
        line_id = data.draw(st.sampled_from(self.lines_allowing(_A.EDIT_QUANTITY)))
        self.step(f"line#{line_id}", lambda: self.w.edit_line_quantity(line_id, quantity))

    def source_lines(self) -> list[int]:
        return [
            line.id for line in self.w.order_lines() if line.line_type == OrderLineType.SOURCE.value
        ]

    @precondition(
        lambda self: (
            self.world is not None and self.source_lines() and self.w.floor.source_demands._demands
        )
    )
    @rule(data=st.data(), quantity=st.sampled_from((0.5, 1.0, 2.0, 6.0)))
    def allocate_source(self, data: st.DataObject, quantity: float) -> None:
        w = self.w
        demand_id = data.draw(st.sampled_from(sorted(w.floor.source_demands._demands)))
        line_id = data.draw(st.sampled_from(self.source_lines()))
        if any(
            a.demand_item_id == demand_id and a.order_item_id == line_id
            for a in w.floor.source_allocations.allocations
        ):
            return
        self.step(
            f"source_demand#{demand_id}", lambda: w.allocate_source(demand_id, line_id, quantity)
        )

    @precondition(lambda self: self.world is not None and self.w.floor.source_demands._demands)
    @rule(data=st.data(), quantity=st.sampled_from((0.5, 1.0, 2.0)))
    def take_source_from_stock(self, data: st.DataObject, quantity: float) -> None:
        demand_id = data.draw(st.sampled_from(sorted(self.w.floor.source_demands._demands)))
        self.step(
            f"source_demand#{demand_id}", lambda: self.w.source_from_stock(demand_id, quantity)
        )

    @precondition(lambda self: self.world is not None)
    @rule(data=st.data(), action=st.sampled_from((_A.CANCEL, _A.FULFIL)), now=st.integers(0, 7))
    def end_a_demand(self, data: st.DataObject, action: LifecycleAction, now: int) -> None:
        """Cancels or fulfils a live demand of any family by hand, drawn one
        time in eight so most demands stay live for a while."""
        if now:
            return
        w = self.w
        candidates = (
            [
                f"bought_demand#{d}"
                for d in sorted(w.bought_demands._demands)
                if self.bought_demand_allows(d, action)
            ]
            + [
                f"made_demand#{d}"
                for d in sorted(w.floor.made_demands._demands)
                if self.made_demand_allows(d, action)
            ]
            + [
                f"source_demand#{d}"
                for d in sorted(w.floor.source_demands._demands)
                if self.source_demand_allows(d, action)
            ]
        )
        if not candidates:
            return
        key = data.draw(st.sampled_from(candidates))
        kind, raw = key.split("#")
        demand_id = int(raw)
        calls = {
            ("bought_demand", _A.CANCEL): w.cancel_bought_demand_request,
            ("bought_demand", _A.FULFIL): w.fulfil_bought_demand,
            ("made_demand", _A.CANCEL): w.cancel_made_demand_request,
            ("made_demand", _A.FULFIL): w.fulfil_made_demand,
            ("source_demand", _A.CANCEL): w.cancel_source_demand_request,
            ("source_demand", _A.FULFIL): w.fulfil_source_demand,
        }
        call = calls[(kind, action)]
        self.step(key, lambda: call(demand_id))

    # ── Refusals ─────────────────────────────────────────────────────

    def a_refused_production_order_action_is_refused(
        self, data: st.DataObject, action: LifecycleAction
    ) -> None:
        refused = [o.id for o in self.w.production_orders() if not self.order_allows(o, action)]
        if not refused:
            return
        order_id = data.draw(st.sampled_from(refused))
        w = self.w
        calls: dict[LifecycleAction, Callable[[], Outcome]] = {
            _A.START: lambda: w.start(order_id),
            _A.RESUME: lambda: w.start(order_id),
            _A.PAUSE: lambda: w.pause(order_id),
            _A.CANCEL: lambda: w.cancel_production_order(order_id),
            _A.RECORD_COMPLETION: lambda: w.complete(order_id, 1.0),
        }
        if action in (_A.START, _A.RESUME):
            # One use case serves both: it is refused only when neither applies.
            order = w.floor.orders._orders[order_id]
            if self.order_allows(order, _A.START) or self.order_allows(order, _A.RESUME):
                return
        self.refused(calls[action])

    def a_refused_lot_action_is_refused(self, data: st.DataObject, action: LifecycleAction) -> None:
        refused = [lot.id for lot in self.w.lots() if not self.lot_allows(lot, action)]
        if not refused:
            return
        lot_id = data.draw(st.sampled_from(refused))
        w = self.w
        calls: dict[LifecycleAction, Callable[[], Outcome]] = {
            _A.HOLD: lambda: w.hold(lot_id),
            _A.RESUME: lambda: w.resume_lot(lot_id),
            _A.CANCEL: lambda: w.cancel_lot_request(lot_id),
            _A.FORCE_COMPLETE: lambda: w.force_complete(lot_id),
        }
        self.refused(calls[action])

    def a_refused_order_action_is_refused(self, action: LifecycleAction) -> None:
        if self.order_allows_action(action):
            return
        w = self.w
        calls: dict[LifecycleAction, Callable[[], Outcome]] = {
            _A.MARK_REQUESTED: w.request_order,
            _A.MARK_ORDERED: w.submit_order,
            _A.CANCEL: w.cancel_order,
        }
        self.refused(calls[action])

    def a_refused_line_action_is_refused(
        self, data: st.DataObject, action: LifecycleAction
    ) -> None:
        allows = self.move_allows if action is _A.MOVE else (lambda i: self.line_allows(i, action))
        refused = [line.id for line in self.w.order_lines() if not allows(line.id)]
        if not refused:
            return
        line_id = data.draw(st.sampled_from(refused))
        w = self.w
        rows = [r.id for r in w.deliveries._deliveries if r.order_item_id == line_id]
        calls: dict[LifecycleAction, Callable[[], Outcome]] = {
            _A.MARK_REQUESTED: lambda: w.mark_requested(line_id),
            _A.MARK_ORDERED: lambda: w.mark_ordered(line_id),
            _A.DELIVER: lambda: w.deliver(line_id, 0.5),
            _A.CORRECT_DELIVERY: lambda: w.correct(line_id, rows[0] if rows else 1, 0.5),
            _A.CLOSE_SHORT: lambda: w.close_short(line_id),
            _A.CANCEL: lambda: w.cancel_line(line_id),
            _A.MOVE: lambda: w.move(line_id, self.target_of(line_id)),
        }
        self.refused(calls[action])

    def a_refused_demand_action_is_refused(
        self, data: st.DataObject, action: LifecycleAction
    ) -> None:
        w = self.w
        bought = [
            d for d in sorted(w.bought_demands._demands) if not self.bought_demand_allows(d, action)
        ]
        made = [
            d
            for d in sorted(w.floor.made_demands._demands)
            if not self.made_demand_allows(d, action) and action is not _A.ALLOCATE
        ]
        source = [
            d
            for d in sorted(w.floor.source_demands._demands)
            if not self.source_demand_allows(d, action) and action is not _A.ALLOCATE
        ]
        candidates = (
            [("bought_demand", d) for d in bought]
            + [("made_demand", d) for d in made]
            + [("source_demand", d) for d in source]
        )
        if not candidates:
            return
        kind, demand_id = data.draw(st.sampled_from(candidates))
        lines = self.bought_lines()
        calls: dict[tuple[str, LifecycleAction], Callable[[], Outcome]] = {
            ("bought_demand", _A.CANCEL): lambda: w.cancel_bought_demand_request(demand_id),
            ("bought_demand", _A.FULFIL): lambda: w.fulfil_bought_demand(demand_id),
            ("bought_demand", _A.ALLOCATE): lambda: (
                w.allocate(demand_id, lines[0], 0.5) if lines else w.take_from_stock(demand_id, 0.5)
            ),
            ("made_demand", _A.CANCEL): lambda: w.cancel_made_demand_request(demand_id),
            ("made_demand", _A.FULFIL): lambda: w.fulfil_made_demand(demand_id),
            ("source_demand", _A.CANCEL): lambda: w.cancel_source_demand_request(demand_id),
            ("source_demand", _A.FULFIL): lambda: w.fulfil_source_demand(demand_id),
        }
        families = {
            "bought_demand": w.bought_demands._demands,
            "made_demand": w.floor.made_demands._demands,
            "source_demand": w.floor.source_demands._demands,
        }
        demand = families[kind][demand_id]
        target = {_A.CANCEL: "canceled", _A.FULFIL: "fulfilled"}.get(action)
        self.refused(calls[(kind, action)], same_again=demand.status == target)

    @precondition(lambda self: self.world is not None)
    @rule(
        data=st.data(),
        table=st.sampled_from(("production_order", "lot", "order", "line", "demand")),
    )
    def a_refused_action_is_refused(self, data: st.DataObject, table: str) -> None:
        """Takes an action one intent table refuses on a subject and asserts
        the use case refuses it as well."""
        if table == "production_order":
            action = data.draw(st.sampled_from(_PRODUCTION_ORDER_ACTIONS))
            self.a_refused_production_order_action_is_refused(data, action)
        elif table == "lot":
            self.a_refused_lot_action_is_refused(data, data.draw(st.sampled_from(_LOT_ACTIONS)))
        elif table == "order":
            self.a_refused_order_action_is_refused(data.draw(st.sampled_from(_ORDER_ACTIONS)))
        elif table == "line":
            if self.w.order_lines():
                action = data.draw(st.sampled_from(_LINE_ACTIONS))
                self.a_refused_line_action_is_refused(data, action)
        else:
            self.a_refused_demand_action_is_refused(
                data, data.draw(st.sampled_from(_DEMAND_ACTIONS))
            )

    @rule()
    def look_again(self) -> None:
        """Changes nothing; it keeps a step available when nothing else is."""

    # ── Invariants ───────────────────────────────────────────────────

    @invariant()
    def stored_values_equal_a_fresh_derivation(self) -> None:
        if self.world is None:
            return
        w = self.w
        derived = derive_snapshot(w.snapshot())
        for lot in w.lots():
            fresh = derived.lots[lot.id]
            assert lot.status == fresh.status.value.value, (lot.id, fresh.status.rule)
            for p in lot.positions:
                position = derived.positions[p.id]
                assert p.kind == position.kind.value.value, p.id
                assert p.status == position.status.value.value, (p.id, position.status.rule)
                assert abs(p.quantity_completed - stored_completed_count(p, position)) <= _EPS
            _note(f"lot row {fresh.status.rule.number}")
        for o in w.production_orders():
            assert o.status == derived.production_orders[o.id].value.value, o.id
        for order in w.orders._orders.values():
            assert order.status == derived.orders[order.id].value.value, order.id
        for line in w.order_lines():
            assert line.status == derived.order_items[line.id].value.value, line.id
        for d in w.bought_demands._demands.values():
            fresh_demand = derived.bought_demands[d.id]
            assert d.status == fresh_demand.value.value, d.id
            _note(f"bought demand row {fresh_demand.rule.number}")
        for d in w.floor.made_demands._demands.values():
            fresh_demand = derived.made_demands[d.id]
            assert d.status == fresh_demand.value.value, d.id
            _note(f"made demand row {fresh_demand.rule.number}")
        for d in w.floor.source_demands._demands.values():
            fresh_demand = derived.source_demands[d.id]
            assert d.status == fresh_demand.value.value, d.id
            _note(f"source demand row {fresh_demand.rule.number}")
        for line in w.made_lines():
            if line.status != OrderItemStatus.CANCELED.value:
                _note(f"made line {line.status}")

    def settled(self, line_id: int) -> float:
        """Accepted and lost pieces of a line, summed from its delivery rows."""
        rows = [r for r in self.w.deliveries._deliveries if r.order_item_id == line_id]
        lost = sum(
            r.quantity_rejected for r in rows if r.rejection_outcome == RejectionOutcome.LOST.value
        )
        return sum(r.quantity for r in rows) + lost

    def line_arrived(self, line_id: int | None) -> tuple[float, bool]:
        """(arrived pieces, placed) of an order line for the demands on it,
        its accepted pieces from its rows, as a lost piece never arrived:
        nothing for a missing or canceled line."""
        line = self.w.lines._items.get(line_id) if line_id is not None else None
        if line is None or line.canceled_at is not None or line.quantity <= _EPS:
            return 0.0, False
        rows = [r for r in self.w.deliveries._deliveries if r.order_item_id == line.id]
        return sum(r.quantity for r in rows), line.ordered_date is not None

    def lot_arrived(self, lot_id: int | None) -> tuple[float, bool]:
        """(arrived pieces, placed) of a lot for the demands on it, its
        completed count: nothing for a missing or canceled lot."""
        lots = self.w.floor.lots._lots
        lot = lots.get(lot_id) if lot_id is not None else None
        if lot is None or lot.canceled_at is not None or lot.quantity <= _EPS:
            return 0.0, False
        placed = lot.status not in ("draft", "canceled", "scrapped")
        return lot.quantity_completed, placed

    @invariant()
    def statuses_agree_with_oracles_computed_from_the_rows(self) -> None:
        """Checks computed here from the stored rows, independent of the
        derivation tables: an order not canceled is DELIVERED exactly when it
        has a live line and every live line received its quantity; a live
        demand is FULFILLED exactly when the pieces that reach it in the fill
        of its lines and lots plus stock cover it, and ORDERED exactly when, short of that, its
        allocations cover it and every one of them is placed."""
        if self.world is None:
            return
        w = self.w
        for order in w.orders._orders.values():
            if order.canceled_at is not None:
                continue
            live = [
                line
                for line in w.order_lines()
                if line.order_id == order.id and line.canceled_at is None
            ]
            delivered = bool(live) and all(
                self.settled(line.id) >= line.quantity - _EPS for line in live
            )
            assert (order.status == "delivered") == delivered, order.id
        # A line or lot fills its allocations in order, the bought demands
        # before the source demands on a line, each family by demand id; an
        # allocation receives what arrived beyond the ones ahead of it.
        families: list[tuple[str, dict[int, Any], list[Any], str, int]] = [
            ("bought", w.bought_demands._demands, w.bought_allocations._allocations, "line", 0),
            (
                "made",
                w.floor.made_demands._demands,
                w.floor.made_allocations._allocations,
                "lot",
                0,
            ),
            (
                "source",
                w.floor.source_demands._demands,
                w.floor.source_allocations.allocations,
                "line",
                1,
            ),
        ]
        fill: dict[tuple[str, int], list[tuple[int, int, float]]] = {}
        for _, _, allocations, via, rank in families:
            for a in allocations:
                ref = a.order_item_id if via == "line" else a.lot_id
                if ref is not None:
                    fill.setdefault((via, ref), []).append((rank, a.demand_item_id, a.quantity))
        for family, demands, allocations, via, rank in families:
            for demand in demands.values():
                if demand.canceled_at is not None or demand.fulfilled_manually_at is not None:
                    continue
                stock = arrived = allocated = 0.0
                placed = True
                for a in allocations:
                    if a.demand_item_id != demand.id:
                        continue
                    ref = a.order_item_id if via == "line" else a.lot_id
                    if ref is None:
                        stock += a.quantity
                        continue
                    pieces, is_placed = (
                        self.line_arrived(ref) if via == "line" else self.lot_arrived(ref)
                    )
                    ahead = sum(q for r, d, q in fill[(via, ref)] if (r, d) < (rank, demand.id))
                    arrived += min(max(pieces - ahead, 0.0), a.quantity)
                    allocated += a.quantity
                    placed = placed and (is_placed or a.quantity <= _EPS)
                fulfilled = arrived + stock >= demand.quantity - _EPS
                ordered = not fulfilled and placed and allocated + stock >= demand.quantity - _EPS
                assert (demand.status == "fulfilled") == fulfilled, (family, demand.id)
                assert (demand.status == "ordered") == ordered, (family, demand.id)

    @invariant()
    def a_reconciler_run_over_everything_changes_nothing(self) -> None:
        if self.world is None:
            return
        assert self.w.settle() == []

    @invariant()
    def line_quantities_hold(self) -> None:
        if self.world is None:
            return
        w = self.w
        positions = w.floor.lots._positions
        for line in w.order_lines():
            rows = [r for r in w.deliveries._deliveries if r.order_item_id == line.id]
            assert abs(line.quantity_delivered - sum(r.quantity for r in rows)) <= _EPS, line.id
            settled = line.quantity_delivered + line.quantity_rejected_lost
            allocated = sum(
                a.quantity for a in w.bought_allocations._allocations if a.order_item_id == line.id
            ) + sum(
                a.quantity
                for a in w.floor.source_allocations.allocations
                if a.order_item_id == line.id
            )
            if line.status == OrderItemStatus.CANCELED.value:
                assert allocated <= _EPS, line.id
            else:
                assert -_EPS <= settled <= line.quantity + _EPS, line.id
                assert allocated <= line.quantity + _EPS, line.id
            if line.lot_position_id in positions and line.status != OrderItemStatus.CANCELED.value:
                # A MADE line never brings its position more than it needs.
                # A disposition shrinks only lines not yet ordered, so a placed
                # line keeps its quantity above a shrunk position: see
                # test_a_placed_made_line_keeps_its_quantity_when_its_position_shrinks.
                quantity = positions[line.lot_position_id].quantity
                assert line.quantity_delivered <= quantity + _EPS, line.id
                if line.status in ("pending", "requested"):
                    net = line.quantity - line.quantity_rejected_lost
                    assert net <= quantity + _EPS, line.id

    @invariant()
    def production_order_quantities_and_times_hold(self) -> None:
        if self.world is None:
            return
        for order in self.w.production_orders():
            processed = sum(c.quantity for c in order.completions)
            assert processed <= order.quantity + _EPS, order.id
            assert order.quantity_completed <= processed + _EPS, order.id
            open_rows = [r for r in order.interruptions if r.resumed_at is None]
            assert len(open_rows) <= (0 if order.status in _ENDED else 1), order.id
            if order.status == ProductionOrderStatus.COMPLETED.value and order.actual_start:
                assert order.actual_end is not None
                minutes = net_work_minutes(
                    order.actual_start, order.actual_end, order.interruptions
                )
                assert minutes is not None and minutes >= 0, order.id

    @invariant()
    def lot_and_position_quantities_hold(self) -> None:
        if self.world is None:
            return
        w = self.w
        for lot in w.lots():
            raw = w.floor.lots._raw_material_arrived_by_demand.get(lot.input_demand_id or 0)
            for p in lot.positions:
                assert p.quantity_completed <= p.quantity + _EPS, p.id
                available = available_input(
                    lot.positions, lot.quantity, p.sequence, raw if p.sequence == 1 else None
                )
                assert p.quantity_completed <= available + _EPS, p.id
            for earlier, later in itertools.pairwise(p.quantity for p in lot.positions):
                assert later <= earlier + _EPS, lot.id
            if lot.positions:
                assert abs(lot.quantity_completed - lot.positions[-1].quantity_completed) <= _EPS
            on_lot = [a for a in w.floor.made_allocations._allocations if a.lot_id == lot.id]
            assert sum(a.quantity for a in on_lot) <= lot.quantity + _EPS, lot.id
            if lot.status == LotStatus.CANCELED.value:
                assert all(a.quantity <= _EPS for a in on_lot), lot.id

    @invariant()
    def demand_allocations_hold(self) -> None:
        if self.world is None:
            return
        w = self.w
        families: list[tuple[dict[int, Any], list[Any]]] = [
            (w.bought_demands._demands, w.bought_allocations._allocations),
            (w.floor.made_demands._demands, w.floor.made_allocations._allocations),
        ]
        for demands, allocations in families:
            for demand in demands.values():
                held = sum(a.quantity for a in allocations if a.demand_item_id == demand.id)
                assert held <= demand.quantity + _EPS, demand.id
                if demand.canceled_at is not None:
                    assert held <= _EPS, demand.id

    @invariant()
    def an_ended_production_order_keeps_no_planned_window(self) -> None:
        if self.world is None:
            return
        for order in self.w.production_orders():
            if order.status in _ENDED:
                assert (order.planned_start, order.planned_end) == (None, None), order.id

    @invariant()
    def a_lot_with_every_position_done_or_forced_is_completed(self) -> None:
        if self.world is None:
            return
        for lot in self.w.lots():
            if lot.canceled_at is not None or lot.quantity <= _EPS or not lot.positions:
                continue
            if lot.force_completed_at is not None or all(
                p.status == "completed" for p in lot.positions
            ):
                if lot.held_at is not None:
                    _note("a held lot completed")
                assert lot.status == LotStatus.COMPLETED.value, lot.id

    @invariant()
    def on_hold_exactly_while_held_and_not_terminal(self) -> None:
        if self.world is None:
            return
        for lot in self.w.lots():
            if lot.status == LotStatus.ON_HOLD.value:
                assert lot.held_at is not None, lot.id
            elif lot.held_at is not None:
                assert lot.status in TERMINAL_LOT_STATUSES, lot.id

    @invariant()
    def no_live_production_order_under_a_terminal_lot(self) -> None:
        if self.world is None:
            return
        for order in self.w.production_orders():
            lot = self.lot_of(order)
            if lot is not None and lot.status in TERMINAL_LOT_STATUSES:
                assert order.status in _ENDED, order.id


LifecycleModel.TestCase.settings = model_settings(steps=40, weight=EXPENSIVE)
TestLifecycleModel = LifecycleModel.TestCase


class LifecycleModelWithRejectionAfterReceipt(LifecycleModel):
    """The lifecycle model with one more step: pieces of a delivery taken
    back as rejected ones after receipt, lost or sent back for redelivery,
    under every invariant of the model. It is a model of its own rather than
    a rule of LifecycleModel, whose seeded exploration feeds the transition
    table (test_state_transitions.py): a new rule there would make the fixed
    seeds draw other examples. The transitions this step makes are driven by
    the scenarios of test_rare_transitions.py instead."""

    @precondition(lambda self: self.world is not None and self.correctable())
    @rule(
        data=st.data(),
        all_of_it=st.booleans(),
        rejected_as=st.sampled_from(
            (RejectionOutcome.LOST.value, RejectionOutcome.REDELIVER.value)
        ),
    )
    def reject_after_receipt(self, data: st.DataObject, all_of_it: bool, rejected_as: str) -> None:
        line_id, row_id, open_pieces = data.draw(st.sampled_from(self.correctable()))
        quantity = open_pieces if all_of_it else min(open_pieces, 0.5)
        self.step(
            f"line#{line_id}",
            lambda: self.w.correct(line_id, row_id, quantity, rejected_as=rejected_as),
        )


LifecycleModelWithRejectionAfterReceipt.TestCase.settings = model_settings(
    steps=40, weight=EXPENSIVE
)
TestLifecycleModelWithRejectionAfterReceipt = LifecycleModelWithRejectionAfterReceipt.TestCase


# ── Cases the model found, each pinned by a test of its own ─────────────


def test_an_allocation_onto_a_canceled_line_is_refused() -> None:
    """A canceled line keeps its quantity, so its free capacity alone would
    take the allocation; the writer refuses the canceled line."""
    world = World(Spec(steps=1, bought_lines=(4.0,), bought_demands=(2.0,)))
    assert world.cancel_line(1).refused is None

    outcome = world.allocate(1, 1, 1.0)

    assert isinstance(outcome.refused, AllocationOrderItemCanceledError)
    assert world.bought_allocations.allocations == []


def test_deliver_all_on_a_partially_ordered_order_books_the_line_marked_ordered() -> None:
    """An order with one line marked ordered on its own is partially
    ordered: deliver-all books that line as a single delivery would and
    skips the pending one."""
    world = World(Spec(steps=1, bought_lines=(4.0, 1.0), bought_demands=()))
    assert world.mark_ordered(2).refused is None
    assert world.orders.orders[ORDER_ID].status == "partially_ordered"

    outcome = world.deliver_all()

    assert outcome.refused is None
    assert [d.order_item_id for d in world.deliveries.deliveries] == [2]
    assert world.settle() == []


def test_a_placed_made_line_keeps_its_quantity_when_its_position_shrinks() -> None:
    """Pieces lost at an earlier position shrink the later one, but a MADE
    line already placed with the supplier keeps its quantity: a disposition
    shrinks only lines not yet ordered. The line never brings the position
    more than it needs, because what it delivers is capped there."""
    world = World(Spec(steps=2, lot_quantity=4.0, bought_lines=(), bought_demands=()))
    first, second = (p.id for p in world.lot.positions)
    assert world.assign_external(first).refused is None
    assert world.assign_external(second).refused is None
    assert world.submit_order().refused is None
    upstream, downstream = (line.id for line in world.made_lines())

    assert world.deliver(upstream, 1.0, rejected=1.0, outcome="lost").refused is None

    position = world.floor.lots._positions[second]
    line = world.lines._items[downstream]
    assert (position.quantity, line.quantity, line.status) == (3.0, 4.0, "ordered")
    assert world.settle() == []


def test_a_made_demand_cancel_is_refused_while_its_lot_holds_good_pieces() -> None:
    """Canceling the only made demand of a lot would cancel the lot, whose
    first position already completed good pieces; the lot cancel refuses
    that and points to force-complete, so the demand, the lot and its
    positions stay as they were."""
    model = LifecycleModel()
    model.world = World(
        Spec(steps=2, lot_quantity=20.0, made_demands=(5.0,), bought_lines=(), bought_demands=())
    )
    w = model.w
    first, second = (p.id for p in w.lot.positions)
    model.step(f"position#{first}", lambda: w.assign_external(first))
    model.step(f"position#{second}", lambda: w.assign_external(second))
    line = w.made_lines()[0].id
    model.step(f"line#{line}", lambda: w.mark_ordered(line))
    model.step(f"line#{line}", lambda: w.deliver(line, None))
    assert w.status_table()[f"position#{first}"] == "completed/external"
    before = w.status_table()

    outcome = model.step("made_demand#101", lambda: w.cancel_made_demand_request(101))

    assert outcome.refused is not None
    assert "force-complete" in str(outcome.refused)
    assert w.status_table() == before
    model.statuses_agree_with_oracles_computed_from_the_rows()
    assert w.settle() == []


def test_an_award_of_a_raw_material_share_and_a_made_line_settles_every_aggregate() -> None:
    """An award whose SOURCE line allocates the lot's raw material demand
    and whose MADE line assigns a position of the same lot, which covers a
    made demand, locks everything it touches in one acquisition, the request
    last, and leaves nothing for the reconciler to change. Canceling the
    MADE line then voids its award and opens the request again."""
    world = World(Spec(steps=1, made_demands=(6.0,), bought_lines=(), bought_demands=()))
    position_id = world.lot.positions[0].id
    request = world.quote_request(source_share=2.0, position_id=position_id)

    outcome = world.award(request.id)

    assert outcome.refused is None
    assert world.quote_requests.requests[request.id].status == "awarded"
    assert sorted(line.line_type for line in world.order_lines()) == ["MADE", "SOURCE"]
    assert world.settle() == []

    [made] = world.made_lines()
    assert world.cancel_line(made.id).refused is None

    assert world.quote_requests.requests[request.id].status == "sent"
    view = world.quote_requests.view(world.quote_requests.requests[request.id])
    assert [line.award_voided for line in view.lines] == [False, True]
    assert world.settle() == []
