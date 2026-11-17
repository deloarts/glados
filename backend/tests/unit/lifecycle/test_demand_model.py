"""
A rule-based model of two bought demands and the order they are covered
through, run by Hypothesis over the real use cases, the lifecycle reconciler
and in-memory fakes: allocate a demand to a line, take some of it from
stock, release an allocation, mark the pending line ordered, deliver on a
line, cancel a demand and mark one fulfilled. The quantities include
fractions, in metres since a quantity in pieces is whole, whose floating
point sums the derivation compares within the shared tolerance. A use case may refuse a step,
such as an allocation larger than what is open; a refused request rolls the
fakes back as its transaction would.

After every step a second reconciler run over everything changes nothing,
so every stored status is its derivation from the facts; every status change
of the step published exactly one status event; no demand holds more than
its quantity and no line more than its quantity; and a canceled demand holds
no allocation, since a cancel releases them all.
"""

import asyncio
import copy
from collections import Counter
from collections.abc import Awaitable
from collections.abc import Callable
from datetime import UTC
from datetime import datetime
from typing import Any

from hypothesis import event
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine
from hypothesis.stateful import invariant
from hypothesis.stateful import precondition
from hypothesis.stateful import rule

from src.modules.catalogue.domain.events.bought_item_events import DemandItemStatusChanged
from src.modules.fulfillment.application.dto.allocation_dto import CreateAllocationCommand
from src.modules.fulfillment.application.dto.allocation_dto import FulfillFromStockCommand
from src.modules.fulfillment.application.services.allocation_fill import LineFillRepos
from src.modules.fulfillment.application.use_cases.bought_item_demand.cancel_demand_item import (
    CancelDemandItem,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.create_allocation import (
    CreateAllocation,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.create_allocation import (
    DeleteAllocation,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.fulfill_from_stock import (
    FulfillDemandFromStock,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.update_demand_item_status import (
    UpdateDemandItemStatus,
)
from src.modules.fulfillment.application.use_cases.order.mark_order_item_ordered import (
    MarkOrderItemOrdered,
)
from src.modules.fulfillment.application.use_cases.order.process_order_item_delivery import (
    ProcessOrderItemDelivery,
)
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.platform.domain.exceptions import DomainError
from src.modules.platform.domain.value_objects.permission import Permission
from tests.factories import make_user
from tests.unit.lifecycle._profiles import model_settings
from tests.unit.lifecycle.fake_demand_reconciler import demand_reconciler_harness
from tests.unit.lifecycle.fake_reconciler import give_order_facts
from tests.unit.lifecycle.fake_reconciler import give_order_item_facts
from tests.unit.order._helpers import FakeEventBus
from tests.unit.order._helpers import FakeOrderRepository
from tests.unit.order._helpers import FakeUnitOfWork
from tests.unit.order._helpers import make_order
from tests.unit.production_lot._helpers import NoLotCreation
from tests.unit.production_lot.fakes import FakeMadeItemAllocationRepository
from tests.unit.production_lot.fakes import FakeMadeItemDemandRepository
from tests.unit.production_lot.fakes import FakeSourceItemAllocationRepository
from tests.unit.production_lot.fakes import delivery_collaborators
from tests.unit.test_bought_item_allocation_use_cases import FakeAllocationRepository
from tests.unit.test_bought_item_allocation_use_cases import FakeDemandRepository
from tests.unit.test_bought_item_allocation_use_cases import FakeOrderItemRepository
from tests.unit.test_bought_item_allocation_use_cases import make_demand
from tests.unit.test_bought_item_allocation_use_cases import make_order_item
from tests.unit.test_bought_item_delivery import FakeDeliveryRepository

_EPS = 1e-6
_ACTOR = make_user(
    id=7,
    permissions=[
        Permission.WRITE_ORDERS,
        Permission.MANAGE_ORDERS,
        Permission.RECEIVE_DELIVERIES,
        Permission.WRITE_ALLOCATIONS,
        Permission.WRITE_DEMAND_ITEMS,
        Permission.MANAGE_DEMAND_ITEMS,
    ],
)
_DEMAND_IDS = (1, 2)
_LINE_IDS = (1, 2)
_BOUGHT = LifecycleAggregate.BOUGHT_DEMANDS

Call = Callable[[Any], Awaitable[object]]


_UNIT = "M"


def _line(id: int, status: OrderItemStatus, quantity: float) -> OrderItem:
    line = make_order_item(id=id, order_id=1, status=status, quantity=quantity)
    line.unit = _UNIT
    return give_order_item_facts(line)


def _demand(id: int, quantity: float) -> Any:
    demand = make_demand(id=id, quantity=quantity)
    demand.unit = _UNIT
    return demand


class DemandModel(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self.demands = FakeDemandRepository([_demand(1, 1.5), _demand(2, 1.0)])
        self.allocations = FakeAllocationRepository()
        self.lines = FakeOrderItemRepository(
            [
                _line(1, OrderItemStatus.ORDERED, 2.0),
                _line(2, OrderItemStatus.PENDING, 1.5),
            ]
        )
        self.orders = FakeOrderRepository(
            [give_order_facts(make_order(id=1, status=OrderStatus.ORDERED))]
        )
        self.deliveries = FakeDeliveryRepository()

    # ── State ────────────────────────────────────────────────────────

    def demand(self, demand_id: int) -> BoughtItemDemandItem:
        return self.demands._demands[demand_id]

    def line(self, line_id: int) -> OrderItem:
        return self.lines._items[line_id]

    def _repos(self) -> tuple[Any, ...]:
        return (self.demands, self.allocations, self.lines, self.orders, self.deliveries)

    def _harness(self) -> Any:
        return demand_reconciler_harness(
            bought_demands=self.demands,
            bought_allocations=self.allocations,
            order_items=self.lines,
            orders=self.orders,
        )

    def _statuses(self) -> dict[int, str]:
        return {i: self.demand(i).status for i in _DEMAND_IDS}

    def request(self, call: Call) -> None:
        """Runs one request with its own reconciler. A refusal restores the
        fakes as they were, as the request's rollback would; a success must
        have published one status event per demand status change."""
        saved = copy.deepcopy([repo.__dict__ for repo in self._repos()])
        before = self._statuses()
        harness = self._harness()
        try:
            asyncio.run(call(harness.reconciler))
        except DomainError:
            for repo, state in zip(self._repos(), saved, strict=True):
                repo.__dict__.clear()
                repo.__dict__.update(state)
            return
        after = self._statuses()
        changes = sorted((i, before[i], after[i]) for i in _DEMAND_IDS if before[i] != after[i])
        events = sorted(
            (e.demand_id, e.old_status.value, e.new_status.value)
            for e in harness.bus.published
            if isinstance(e, DemandItemStatusChanged)
        )
        assert changes == events

    # ── Use cases ────────────────────────────────────────────────────

    def _cancel(self, reconciler: Any) -> CancelDemandItem:
        return CancelDemandItem(
            self.demands, self.allocations, uow=FakeUnitOfWork(), reconciler=reconciler
        )

    # ── Rules ────────────────────────────────────────────────────────

    @rule(
        demand_id=st.sampled_from(_DEMAND_IDS),
        line_id=st.sampled_from(_LINE_IDS),
        quantity=st.sampled_from((0.3, 0.5, 1.0, 1.5)),
    )
    def allocate(self, demand_id: int, line_id: int, quantity: float) -> None:
        command = CreateAllocationCommand(
            demand_item_id=demand_id, order_item_id=line_id, quantity=quantity
        )
        if any(
            a.order_item_id == line_id and a.demand_item_id == demand_id
            for a in self.allocations._allocations
        ):
            # One allocation per demand and line; a second would replace the
            # first in this fake, which the use case does not intend.
            return
        self.request(
            lambda r: CreateAllocation(
                self.allocations,
                self.demands,
                self.lines,
                uow=FakeUnitOfWork(),
                reconciler=r,
                fill_repos=LineFillRepos(
                    bought=self.allocations, source=FakeSourceItemAllocationRepository()
                ),
            ).execute(_ACTOR, command)
        )

    @rule(demand_id=st.sampled_from(_DEMAND_IDS), quantity=st.sampled_from((0.1, 0.5, 1.0)))
    def take_from_stock(self, demand_id: int, quantity: float) -> None:
        command = FulfillFromStockCommand(demand_item_id=demand_id, quantity=quantity)
        self.request(
            lambda r: FulfillDemandFromStock(
                self.demands, self.allocations, self.lines, uow=FakeUnitOfWork(), reconciler=r
            ).execute(_ACTOR, command)
        )

    def line_allocations(self) -> list[tuple[int, int]]:
        return sorted(
            (a.demand_item_id, a.order_item_id)
            for a in self.allocations._allocations
            if a.order_item_id is not None
        )

    @precondition(lambda self: self.line_allocations())
    @rule(data=st.data())
    def release(self, data: st.DataObject) -> None:
        demand_id, line_id = data.draw(st.sampled_from(self.line_allocations()))
        self.release_one(demand_id, line_id)

    def release_one(self, demand_id: int, line_id: int) -> None:
        self.request(
            lambda r: DeleteAllocation(
                self.allocations,
                self.demands,
                self.lines,
                uow=FakeUnitOfWork(),
                reconciler=r,
                fill_repos=LineFillRepos(
                    bought=self.allocations, source=FakeSourceItemAllocationRepository()
                ),
            ).execute(_ACTOR, demand_id, line_id)
        )

    @precondition(lambda self: self.line(2).status == OrderItemStatus.PENDING.value)
    @rule()
    def mark_the_pending_line_ordered(self) -> None:
        self.request(
            lambda r: MarkOrderItemOrdered(
                self.lines, self.orders, uow=FakeUnitOfWork(), reconciler=r
            ).execute(_ACTOR, 1, 2)
        )

    @rule(line_id=st.sampled_from(_LINE_IDS), quantity=st.sampled_from((0.1, 0.7, 1.0)))
    def deliver(self, line_id: int, quantity: float) -> None:
        self.request(
            lambda r: ProcessOrderItemDelivery(
                self.lines,
                self.orders,
                self.deliveries,
                event_bus=FakeEventBus(),
                uow=FakeUnitOfWork(),
                reconciler=r,
                made_item_demand_repo=FakeMadeItemDemandRepository(),
                made_item_allocation_repo=FakeMadeItemAllocationRepository(),
                create_lot=NoLotCreation(),
                **delivery_collaborators(bought_item_allocation_repo=self.allocations),
            ).execute(_ACTOR, line_id, quantity=quantity)
        )

    @rule(line_id=st.sampled_from(_LINE_IDS))
    def deliver_the_open_rest(self, line_id: int) -> None:
        """Delivers what the line still awaits, so the demands it covers in
        full can be fulfilled by their deliveries."""
        line = self.line(line_id)
        rest = round(line.quantity - line.quantity_delivered, 6)
        if rest <= _EPS:
            return
        self.deliver(line_id, rest)

    # The two intents end a demand, so they are drawn one time in eight and
    # most runs keep both demands live for a while.
    @rule(demand_id=st.sampled_from(_DEMAND_IDS), draw=st.integers(0, 7))
    def cancel(self, demand_id: int, draw: int) -> None:
        if draw:
            return
        self.request(lambda r: self._cancel(r).execute(_ACTOR, demand_id))

    @rule(demand_id=st.sampled_from(_DEMAND_IDS), draw=st.integers(0, 7))
    def mark_fulfilled(self, demand_id: int, draw: int) -> None:
        if draw:
            return
        self.request(
            lambda r: UpdateDemandItemStatus(
                self.demands,
                self._cancel(r),
                uow=FakeUnitOfWork(),
                reconciler=r,
                allocation_repo=self.allocations,
                source_allocation_repo=FakeSourceItemAllocationRepository(),
                order_item_repo=self.lines,
            ).execute(_ACTOR, demand_id, "fulfilled")
        )

    # ── Invariants ───────────────────────────────────────────────────

    @invariant()
    def record_the_derivation_rules_reached(self) -> None:
        """Names the derivation row each demand reads, so a run reports how
        often the model reached each one (see test_each_derivation_rule_is_reached)."""
        for demand_id in _DEMAND_IDS:
            reached = derivation_rule(self, demand_id)
            if reached is not None:
                event(reached)
                REACHED[reached] += 1

    @invariant()
    def a_reconciler_run_changes_nothing(self) -> None:
        before = self._statuses()
        harness = self._harness()
        harness.reconciler.touch_demands(_BOUGHT, _DEMAND_IDS)
        harness.reconciler.touch_order_items(_LINE_IDS)
        asyncio.run(harness.reconciler.run(_ACTOR, datetime.now(UTC)))
        assert self._statuses() == before
        assert harness.bus.published == []

    @invariant()
    def no_demand_holds_more_than_its_quantity(self) -> None:
        for demand_id in _DEMAND_IDS:
            held = sum(
                a.quantity for a in self.allocations._allocations if a.demand_item_id == demand_id
            )
            assert held <= self.demand(demand_id).quantity + _EPS

    @invariant()
    def no_line_holds_more_than_its_quantity(self) -> None:
        for line_id in _LINE_IDS:
            held = sum(
                a.quantity for a in self.allocations._allocations if a.order_item_id == line_id
            )
            assert held <= self.line(line_id).quantity + _EPS

    @invariant()
    def a_canceled_demand_holds_no_allocation(self) -> None:
        for demand_id in _DEMAND_IDS:
            if self.demand(demand_id).canceled_at is not None:
                assert not any(a.demand_item_id == demand_id for a in self.allocations.allocations)


def derivation_rule(model: DemandModel, demand_id: int) -> str | None:
    """The derivation row a demand of the model reads by its facts, None
    for an open demand or one whose status comes from an intent."""
    demand = model.demand(demand_id)
    if demand.canceled_at is not None or demand.fulfilled_manually_at is not None:
        return None
    held = [a for a in model.allocations._allocations if a.demand_item_id == demand_id]
    if demand.status == "fulfilled":
        if all(a.order_item_id is None for a in held):
            return "rule 3: fulfilled by stock alone"
        return "rule 3: fulfilled by delivery"
    if demand.status == "ordered":
        return "rule 4: ordered with full cover"
    if demand.status == "allocated":
        return "rule 5: allocated"
    return None


REACHED: Counter[str] = Counter()


def test_each_derivation_rule_is_reached() -> None:
    """One fixed sequence through the model that reads every derivation row
    by facts: stock alone fulfils demand 2, demand 1 is allocated on the
    pending line, ordered once that line is placed and fulfilled by the
    deliveries of both lines. The invariants hold after every step."""
    model = DemandModel()

    def step(action: Callable[[], None]) -> None:
        action()
        model.a_reconciler_run_changes_nothing()
        model.no_demand_holds_more_than_its_quantity()
        model.no_line_holds_more_than_its_quantity()

    step(lambda: model.take_from_stock(demand_id=2, quantity=1.0))
    assert derivation_rule(model, 2) == "rule 3: fulfilled by stock alone"
    step(lambda: model.allocate(demand_id=1, line_id=2, quantity=0.5))
    step(lambda: model.allocate(demand_id=1, line_id=1, quantity=1.0))
    assert derivation_rule(model, 1) == "rule 5: allocated"
    step(model.mark_the_pending_line_ordered)
    assert derivation_rule(model, 1) == "rule 4: ordered with full cover"
    step(lambda: model.deliver_the_open_rest(line_id=1))
    step(lambda: model.deliver_the_open_rest(line_id=2))
    assert derivation_rule(model, 1) == "rule 3: fulfilled by delivery"


DemandModel.TestCase.settings = model_settings(steps=30)
TestDemandModel = DemandModel.TestCase


class TestDemandsSharingALine:
    """The pieces that reach a demand depend on the allocations ahead of it
    on its line, so writing one demand's allocation derives the others on
    the line again."""

    def _shared_line(self) -> DemandModel:
        # Demand 1 holds 0.3 of line 1 ahead of demand 2's 1.0, and the line
        # received 1.0: demand 2 is reached by 0.7 only.
        state = DemandModel()
        state.allocate(demand_id=1, line_id=1, quantity=0.3)
        state.deliver(line_id=1, quantity=1.0)
        state.allocate(demand_id=2, line_id=1, quantity=1.0)
        assert state.demand(2).status == "ordered"
        return state

    def test_releasing_the_allocation_ahead_derives_the_one_behind(self) -> None:
        state = self._shared_line()
        state.release_one(demand_id=1, line_id=1)
        assert state.demand(2).status == "fulfilled"
        state.a_reconciler_run_changes_nothing()

    def test_canceling_the_demand_ahead_derives_the_one_behind(self) -> None:
        state = self._shared_line()
        state.cancel(demand_id=1, draw=0)
        assert state.demand(2).status == "fulfilled"
        state.a_reconciler_run_changes_nothing()

    def test_allocating_ahead_of_arrived_pieces_is_refused(self) -> None:
        """Demand 1 sorts ahead of demand 2 on the line, so its allocation
        would take pieces that already arrived for demand 2; the writer
        refuses it and demand 2 stays fulfilled."""
        state = DemandModel()
        state.allocate(demand_id=2, line_id=1, quantity=1.0)
        state.deliver(line_id=1, quantity=1.0)
        assert state.demand(2).status == "fulfilled"
        state.allocate(demand_id=1, line_id=1, quantity=0.3)
        assert state.demand(2).status == "fulfilled"
        assert not any(a.demand_item_id == 1 for a in state.allocations._allocations)
        state.a_reconciler_run_changes_nothing()
