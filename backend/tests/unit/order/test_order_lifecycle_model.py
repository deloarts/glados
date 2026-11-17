"""
A rule-based model of two supplier orders and their lines, run by Hypothesis
over the real use cases, the lifecycle reconciler and in-memory fakes:
request, submit, cancel and deliver all of an order; add, mark requested,
mark ordered, deliver with accepted, lost or redelivered pieces, cancel,
close short, change the quantity of, move and remove a line; and correct a
delivery. The lines are bought or free-text lines without allocations. Each
action is chosen where its intent table allows it, and the use case may
still refuse it for a reason the table leaves to it, such as a delivery
larger than what is open; a refused request rolls the fakes back as its
transaction would. A line action the table refuses is refused by its use
case as well.

After every step the stored statuses equal their derivation from the facts,
a second reconciler run changes nothing, every status change of the step
published exactly one status event, each line's delivered, rejected and lost
totals are the sums of its delivery rows, no correction takes back more than
its row accepted, no live line holds more delivered and lost pieces than its
quantity, an order reads ORDERED only with its ordered date, and an order
carries its delivery date exactly while it reads DELIVERED.
"""

import asyncio
import copy
from collections.abc import Awaitable
from collections.abc import Callable
from datetime import UTC
from datetime import datetime
from typing import Any

from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine
from hypothesis.stateful import invariant
from hypothesis.stateful import precondition
from hypothesis.stateful import rule

from src.modules.fulfillment.application.dto.order_dto import CreateOrderItemCommand
from src.modules.fulfillment.application.dto.order_dto import UpdateOrderItemCommand
from src.modules.fulfillment.application.use_cases.order.cancel_order_item import CancelOrderItem
from src.modules.fulfillment.application.use_cases.order.close_order_item_short import (
    CloseOrderItemShort,
)
from src.modules.fulfillment.application.use_cases.order.correct_order_item_delivery import (
    CorrectOrderItemDelivery,
)
from src.modules.fulfillment.application.use_cases.order.create_order_item import CreateOrderItem
from src.modules.fulfillment.application.use_cases.order.delete_order_item import RemoveOrderItem
from src.modules.fulfillment.application.use_cases.order.mark_order_item_ordered import (
    MarkOrderItemOrdered,
)
from src.modules.fulfillment.application.use_cases.order.mark_order_item_ordered import (
    MarkOrderItemRequested,
)
from src.modules.fulfillment.application.use_cases.order.move_order_item import MoveOrderItem
from src.modules.fulfillment.application.use_cases.order.process_order_item_delivery import (
    DeliverAllOrderItems,
)
from src.modules.fulfillment.application.use_cases.order.process_order_item_delivery import (
    ProcessOrderItemDelivery,
)
from src.modules.fulfillment.application.use_cases.order.update_order import CancelOrder
from src.modules.fulfillment.application.use_cases.order.update_order import RequestOrder
from src.modules.fulfillment.application.use_cases.order.update_order import SubmitOrder
from src.modules.fulfillment.application.use_cases.order.update_order_item import UpdateOrderItem
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.order_item_delivery import OrderItemDelivery
from src.modules.fulfillment.domain.events.order_events import OrderItemStatusChanged
from src.modules.fulfillment.domain.events.order_events import OrderStatusChanged
from src.modules.fulfillment.domain.services.lifecycle.facts import OrderFacts
from src.modules.fulfillment.domain.services.lifecycle.intents import ORDER_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import ORDER_ITEM_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import OrderItemContext
from src.modules.fulfillment.domain.services.lifecycle.order import derive_order_status
from src.modules.fulfillment.domain.services.lifecycle.order_item import derive_order_item_status
from src.modules.fulfillment.domain.services.lifecycle.snapshot import order_item_facts
from src.modules.fulfillment.domain.services.order_rules import order_item_context
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.rejection_after_receipt import (
    RejectionAfterReceipt,
)
from src.modules.fulfillment.domain.value_objects.rejection_outcome import RejectionOutcome
from src.modules.platform.domain.exceptions import DomainError
from src.modules.platform.domain.value_objects.permission import Permission
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction
from tests.factories import make_user
from tests.unit.lifecycle._profiles import model_settings
from tests.unit.lifecycle.fake_reconciler import order_reconciler_harness
from tests.unit.order._helpers import ExistingSuppliers
from tests.unit.order._helpers import FakeAllocationRepository
from tests.unit.order._helpers import FakeCatalogueRepository
from tests.unit.order._helpers import FakeDemandRepository
from tests.unit.order._helpers import FakeEventBus
from tests.unit.order._helpers import FakeOrderItemRepository
from tests.unit.order._helpers import FakeOrderRepository
from tests.unit.order._helpers import FakeSourceItemRepository
from tests.unit.order._helpers import FakeUnitOfWork
from tests.unit.order._helpers import make_order
from tests.unit.order._helpers import make_order_item
from tests.unit.production_lot._helpers import NoLotCreation
from tests.unit.production_lot.fakes import FakeMadeItemAllocationRepository
from tests.unit.production_lot.fakes import FakeMadeItemDemandRepository
from tests.unit.production_lot.fakes import FakeProjectRepository
from tests.unit.production_lot.fakes import delivery_collaborators
from tests.unit.test_bought_item_delivery import FakeDeliveryRepository

_EPS = 1e-6
_ACTOR = make_user(
    id=7,
    permissions=[
        Permission.WRITE_ORDERS,
        Permission.MANAGE_ORDERS,
        Permission.RECEIVE_DELIVERIES,
    ],
)
_A = LifecycleAction
_ORDER_IDS = (1, 2)
# The line actions whose refusal by the intent table the use cases enforce.
_LINE_ACTIONS = (
    _A.MARK_REQUESTED,
    _A.MARK_ORDERED,
    _A.DELIVER,
    _A.CLOSE_SHORT,
    _A.CANCEL,
    _A.EDIT_QUANTITY,
    _A.REMOVE,
)

Call = Callable[[Any], Awaitable[object]]


def _seed_line(id: int, order_id: int) -> OrderItem:
    line = make_order_item(id=id, order_id=order_id, status=OrderItemStatus.PENDING)
    line.quantity = 4.0
    return line


class OrderModel(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self.orders = FakeOrderRepository([make_order(id=i) for i in _ORDER_IDS])
        self.lines = FakeOrderItemRepository([_seed_line(1, 1), _seed_line(2, 1), _seed_line(3, 2)])
        self.deliveries = FakeDeliveryRepository()
        self.status_events: list[object] = []

    # ── State ────────────────────────────────────────────────────────

    def order(self, order_id: int) -> Order:
        return self.orders._orders[order_id]

    def all_lines(self) -> list[OrderItem]:
        return sorted(self.lines._items.values(), key=lambda line: line.id)

    def rows(self, line_id: int) -> list[OrderItemDelivery]:
        return [r for r in self.deliveries._deliveries if r.order_item_id == line_id]

    def orders_allowing(self, action: LifecycleAction) -> list[int]:
        return [
            order_id
            for order_id in _ORDER_IDS
            if action in ORDER_INTENTS.allowed_actions(self.order(order_id), None, _ACTOR)
        ]

    def line_allows(self, line: OrderItem, action: LifecycleAction) -> bool:
        context = order_item_context(self.order(line.order_id))
        return ORDER_ITEM_INTENTS.check(action, line, context, _ACTOR) is None

    def lines_allowing(self, action: LifecycleAction) -> list[int]:
        return [line.id for line in self.all_lines() if self.line_allows(line, action)]

    def movable(self) -> list[tuple[int, int]]:
        """(line, target order) pairs the move rule accepts."""
        pairs = []
        for line in self.all_lines():
            target = 3 - line.order_id
            context = OrderItemContext(
                order_status=OrderStatus(self.order(line.order_id).status),
                target_order_canceled=self.order(target).canceled_at is not None,
            )
            if ORDER_ITEM_INTENTS.check(_A.MOVE, line, context, _ACTOR) is None:
                pairs.append((line.id, target))
        return pairs

    def correctable(self) -> list[tuple[int, int, float]]:
        """(line, delivery row, accepted pieces no correction took back yet)
        for every row a correction may take pieces back from."""
        found = []
        for line_id in self.lines_allowing(_A.CORRECT_DELIVERY):
            rows = self.rows(line_id)
            for row in rows:
                if row.corrects_delivery_id is not None:
                    continue
                taken = -sum(r.quantity for r in rows if r.corrects_delivery_id == row.id)
                if row.quantity - taken > _EPS:
                    found.append((line_id, row.id, row.quantity - taken))
        return found

    # ── Requests ─────────────────────────────────────────────────────

    def _snapshot(self) -> object:
        return copy.deepcopy((self.orders.__dict__, self.lines.__dict__, self.deliveries.__dict__))

    def _restore(self, saved: Any) -> None:
        for repo, state in zip((self.orders, self.lines, self.deliveries), saved, strict=True):
            repo.__dict__.clear()
            repo.__dict__.update(state)

    def _statuses(self) -> tuple[dict[int, str], dict[int, str]]:
        return (
            {i: self.order(i).status for i in _ORDER_IDS},
            {line.id: line.status for line in self.all_lines()},
        )

    def request(self, call: Call) -> None:
        """Runs one request with its own reconciler. A refusal restores the
        fakes as they were, as the request's rollback would; a success must
        have published one status event per status change."""
        saved = self._snapshot()
        before = self._statuses()
        harness = order_reconciler_harness(self.orders, self.lines)
        try:
            asyncio.run(call(harness.reconciler))
        except DomainError:
            self._restore(saved)
            return
        self._assert_status_events(before, harness.bus.published)

    def refuse(self, call: Call) -> None:
        """Runs a request the intent table refuses: the use case must refuse
        it too. The fakes are restored as the rollback would."""
        saved = self._snapshot()
        harness = order_reconciler_harness(self.orders, self.lines)
        try:
            asyncio.run(call(harness.reconciler))
        except DomainError:
            self._restore(saved)
            return
        raise AssertionError("The use case accepted an action its intent table refuses.")

    def _assert_status_events(
        self, before: tuple[dict[int, str], dict[int, str]], published: list[object]
    ) -> None:
        orders_before, lines_before = before
        orders_after, lines_after = self._statuses()
        order_changes = sorted(
            (i, old, orders_after[i]) for i, old in orders_before.items() if orders_after[i] != old
        )
        line_changes = sorted(
            (i, old, lines_after[i])
            for i, old in lines_before.items()
            if i in lines_after and lines_after[i] != old
        )
        assert order_changes == sorted(
            (e.order_id, e.old_status.value, e.new_status.value)
            for e in published
            if isinstance(e, OrderStatusChanged)
        )
        assert line_changes == sorted(
            (e.order_item_id, e.old_status.value, e.new_status.value)
            for e in published
            if isinstance(e, OrderItemStatusChanged)
        )

    # ── Use cases ────────────────────────────────────────────────────

    def _deliver(self, reconciler: Any) -> ProcessOrderItemDelivery:
        return ProcessOrderItemDelivery(
            self.lines,
            self.orders,
            self.deliveries,
            event_bus=FakeEventBus(),
            uow=FakeUnitOfWork(),
            reconciler=reconciler,
            made_item_demand_repo=FakeMadeItemDemandRepository(),
            made_item_allocation_repo=FakeMadeItemAllocationRepository(),
            create_lot=NoLotCreation(),
            **delivery_collaborators(),
        )

    def _cancel_line(self, reconciler: Any) -> CancelOrderItem:
        return CancelOrderItem(
            self.orders,
            self.lines,
            FakeAllocationRepository(),
            uow=FakeUnitOfWork(),
            reconciler=reconciler,
        )

    def _close_short(self, reconciler: Any) -> CloseOrderItemShort:
        return CloseOrderItemShort(
            self.orders,
            self.lines,
            FakeAllocationRepository(),
            uow=FakeUnitOfWork(),
            reconciler=reconciler,
        )

    def _update(self, reconciler: Any) -> UpdateOrderItem:
        return UpdateOrderItem(
            order_item_repo=self.lines,
            order_repo=self.orders,
            catalogue_repo=FakeCatalogueRepository(),
            allocation_repo=FakeAllocationRepository(),
            demand_repo=FakeDemandRepository(),
            uow=FakeUnitOfWork(),
            reconciler=reconciler,
            project_repo=FakeProjectRepository(),
        )

    def _remove(self, reconciler: Any) -> RemoveOrderItem:
        return RemoveOrderItem(
            self.orders,
            self.lines,
            FakeAllocationRepository(),
            uow=FakeUnitOfWork(),
            reconciler=reconciler,
        )

    def _mark_ordered(self, reconciler: Any) -> MarkOrderItemOrdered:
        return MarkOrderItemOrdered(
            self.lines,
            self.orders,
            uow=FakeUnitOfWork(),
            reconciler=reconciler,
        )

    def _mark_requested(self, reconciler: Any) -> MarkOrderItemRequested:
        return MarkOrderItemRequested(
            self.lines, self.orders, uow=FakeUnitOfWork(), reconciler=reconciler
        )

    def _line_action(self, action: LifecycleAction, line: OrderItem) -> Call:
        """The request that takes `action` on the line."""
        order_id, line_id = line.order_id, line.id
        if action is _A.MARK_REQUESTED:
            return lambda r: self._mark_requested(r).execute(_ACTOR, order_id, line_id)
        if action is _A.MARK_ORDERED:
            return lambda r: self._mark_ordered(r).execute(_ACTOR, order_id, line_id)
        if action is _A.DELIVER:
            return lambda r: self._deliver(r).execute(_ACTOR, line_id, quantity=1.0)
        if action is _A.CLOSE_SHORT:
            return lambda r: self._close_short(r).execute(_ACTOR, order_id, line_id)
        if action is _A.CANCEL:
            return lambda r: self._cancel_line(r).execute(_ACTOR, order_id, line_id)
        if action is _A.EDIT_QUANTITY:
            command = UpdateOrderItemCommand(quantity=line.quantity + 1.0, unit=line.unit)
            return lambda r: self._update(r).execute(_ACTOR, order_id, line_id, command)
        return lambda r: self._remove(r).execute(_ACTOR, order_id, line_id)

    # ── Order rules ──────────────────────────────────────────────────

    @precondition(lambda self: self.orders_allowing(_A.MARK_REQUESTED))
    @rule(data=st.data())
    def request_order(self, data: st.DataObject) -> None:
        order_id = data.draw(st.sampled_from(self.orders_allowing(_A.MARK_REQUESTED)))
        self.request(
            lambda r: RequestOrder(
                self.orders,
                event_bus=FakeEventBus(),
                uow=FakeUnitOfWork(),
                reconciler=r,
                order_item_repo=self.lines,
            ).execute(_ACTOR, order_id)
        )

    @precondition(lambda self: self.orders_allowing(_A.MARK_ORDERED))
    @rule(data=st.data())
    def submit_order(self, data: st.DataObject) -> None:
        order_id = data.draw(st.sampled_from(self.orders_allowing(_A.MARK_ORDERED)))
        self.request(
            lambda r: SubmitOrder(
                self.orders,
                event_bus=FakeEventBus(),
                uow=FakeUnitOfWork(),
                reconciler=r,
                order_item_repo=self.lines,
            ).execute(_ACTOR, order_id)
        )

    @precondition(lambda self: self.orders_allowing(_A.CANCEL))
    @rule(data=st.data())
    def cancel_order(self, data: st.DataObject) -> None:
        order_id = data.draw(st.sampled_from(self.orders_allowing(_A.CANCEL)))
        self.request(
            lambda r: CancelOrder(
                self.orders,
                self.lines,
                FakeAllocationRepository(),
                event_bus=FakeEventBus(),
                uow=FakeUnitOfWork(),
                reconciler=r,
            ).execute(_ACTOR, order_id)
        )

    @rule(order_id=st.sampled_from(_ORDER_IDS))
    def deliver_all(self, order_id: int) -> None:
        self.request(
            lambda r: DeliverAllOrderItems(
                self.orders,
                self.lines,
                self._deliver(r),
                event_bus=FakeEventBus(),
                uow=FakeUnitOfWork(),
                reconciler=r,
            ).execute(_ACTOR, order_id)
        )

    @rule(order_id=st.sampled_from(_ORDER_IDS), quantity=st.sampled_from([2.0, 4.0, 6.0]))
    def add_line(self, order_id: int, quantity: float) -> None:
        command = CreateOrderItemCommand(
            order_id=order_id,
            supplier_id=1,
            project_id=1,
            virtual_name="Freight",
            quantity=quantity,
            unit="pcs",
        )
        self.request(
            lambda r: CreateOrderItem(
                project_repo=FakeProjectRepository(),
                supplier_repo=ExistingSuppliers(),
                order_item_repo=self.lines,
                item_repo=FakeCatalogueRepository(),
                order_repo=self.orders,
                demand_repo=FakeDemandRepository(),
                allocation_repo=FakeAllocationRepository(),
                source_item_repo=FakeSourceItemRepository(),
                uow=FakeUnitOfWork(),
                reconciler=r,
            ).execute(_ACTOR, command)
        )

    # ── Line rules ───────────────────────────────────────────────────

    @precondition(lambda self: self.lines_allowing(_A.MARK_REQUESTED))
    @rule(data=st.data())
    def mark_requested(self, data: st.DataObject) -> None:
        line_id = data.draw(st.sampled_from(self.lines_allowing(_A.MARK_REQUESTED)))
        self.request(self._line_action(_A.MARK_REQUESTED, self.lines._items[line_id]))

    @precondition(lambda self: self.lines_allowing(_A.MARK_ORDERED))
    @rule(data=st.data())
    def mark_ordered(self, data: st.DataObject) -> None:
        line_id = data.draw(st.sampled_from(self.lines_allowing(_A.MARK_ORDERED)))
        self.request(self._line_action(_A.MARK_ORDERED, self.lines._items[line_id]))

    @precondition(lambda self: self.lines_allowing(_A.DELIVER))
    @rule(
        data=st.data(),
        accepted=st.sampled_from([None, 1.0]),
        rejected=st.sampled_from([0.0, 1.0]),
        outcome=st.sampled_from([RejectionOutcome.LOST.value, RejectionOutcome.REDELIVER.value]),
    )
    def deliver(
        self, data: st.DataObject, accepted: float | None, rejected: float, outcome: str
    ) -> None:
        line_id = data.draw(st.sampled_from(self.lines_allowing(_A.DELIVER)))
        self.request(
            lambda r: self._deliver(r).execute(
                _ACTOR,
                line_id,
                quantity=accepted,
                quantity_rejected=rejected,
                rejection_reason="supplier_damage" if rejected else None,
                rejection_outcome=outcome if rejected else None,
            )
        )

    @precondition(lambda self: self.lines_allowing(_A.CANCEL))
    @rule(data=st.data())
    def cancel_line(self, data: st.DataObject) -> None:
        line_id = data.draw(st.sampled_from(self.lines_allowing(_A.CANCEL)))
        self.request(self._line_action(_A.CANCEL, self.lines._items[line_id]))

    @precondition(lambda self: self.lines_allowing(_A.CLOSE_SHORT))
    @rule(data=st.data())
    def close_short(self, data: st.DataObject) -> None:
        line_id = data.draw(st.sampled_from(self.lines_allowing(_A.CLOSE_SHORT)))
        self.request(self._line_action(_A.CLOSE_SHORT, self.lines._items[line_id]))

    @precondition(lambda self: self.correctable())
    @rule(
        data=st.data(),
        all_of_it=st.booleans(),
        rejected_as=st.sampled_from((None, RejectionOutcome.LOST, RejectionOutcome.REDELIVER)),
    )
    def correct_delivery(
        self, data: st.DataObject, all_of_it: bool, rejected_as: RejectionOutcome | None
    ) -> None:
        """Takes pieces back as a miscount, or as pieces rejected after
        receipt with `rejected_as`."""
        line_id, row_id, open_pieces = data.draw(st.sampled_from(self.correctable()))
        line = self.lines._items[line_id]
        quantity = open_pieces if all_of_it else min(open_pieces, 1.0)
        rejection = (
            RejectionAfterReceipt(reason="transport_damage", outcome=rejected_as)
            if rejected_as is not None
            else None
        )
        self.request(
            lambda r: CorrectOrderItemDelivery(
                self.orders,
                self.lines,
                self.deliveries,
                FakeAllocationRepository(),
                FakeDemandRepository(),
                uow=FakeUnitOfWork(),
                reconciler=r,
            ).execute(
                _ACTOR,
                line.order_id,
                line_id,
                row_id,
                quantity,
                None if rejection is not None else "Counted twice",
                rejection=rejection,
            )
        )

    @precondition(lambda self: self.lines_allowing(_A.EDIT_QUANTITY))
    @rule(data=st.data(), quantity=st.sampled_from([2.0, 4.0, 8.0]))
    def edit_quantity(self, data: st.DataObject, quantity: float) -> None:
        line_id = data.draw(st.sampled_from(self.lines_allowing(_A.EDIT_QUANTITY)))
        line = self.lines._items[line_id]
        command = UpdateOrderItemCommand(quantity=quantity, unit=line.unit)
        self.request(lambda r: self._update(r).execute(_ACTOR, line.order_id, line_id, command))

    @precondition(lambda self: self.movable())
    @rule(data=st.data())
    def move_line(self, data: st.DataObject) -> None:
        line_id, target = data.draw(st.sampled_from(self.movable()))
        source = self.lines._items[line_id].order_id
        self.request(
            lambda r: MoveOrderItem(
                self.orders, self.lines, uow=FakeUnitOfWork(), reconciler=r
            ).execute(_ACTOR, source, line_id, target)
        )

    @precondition(lambda self: self.lines_allowing(_A.REMOVE))
    @rule(data=st.data())
    def remove_line(self, data: st.DataObject) -> None:
        line_id = data.draw(st.sampled_from(self.lines_allowing(_A.REMOVE)))
        self.request(self._line_action(_A.REMOVE, self.lines._items[line_id]))

    @rule(data=st.data(), action=st.sampled_from(_LINE_ACTIONS))
    def a_refused_line_action_is_refused(
        self, data: st.DataObject, action: LifecycleAction
    ) -> None:
        refused = [line for line in self.all_lines() if not self.line_allows(line, action)]
        if not refused:
            return
        line = data.draw(st.sampled_from(refused))
        self.refuse(self._line_action(action, line))

    # ── Invariants ───────────────────────────────────────────────────

    @invariant()
    def every_status_is_derived_from_the_facts(self) -> None:
        derived_lines = {
            line.id: derive_order_item_status(order_item_facts(line)).value
            for line in self.all_lines()
        }
        for line in self.all_lines():
            assert line.status == derived_lines[line.id].value, line.id
        for order_id in _ORDER_IDS:
            order = self.order(order_id)
            facts = OrderFacts(
                requested_at=order.requested_at,
                ordered_date=order.ordered_date,
                canceled_at=order.canceled_at,
                line_statuses=tuple(
                    derived_lines[line.id] for line in self.all_lines() if line.order_id == order_id
                ),
            )
            assert order.status == derive_order_status(facts).value.value, order_id

    @invariant()
    def a_second_run_changes_nothing(self) -> None:
        harness = order_reconciler_harness(self.orders, self.lines)
        harness.reconciler.touch_orders(_ORDER_IDS)
        harness.reconciler.touch_order_items([line.id for line in self.all_lines()])
        result = asyncio.run(harness.reconciler.run(_ACTOR, datetime.now(UTC)))
        assert result.changes == ()

    @invariant()
    def line_totals_are_the_sums_of_their_rows(self) -> None:
        for line in self.all_lines():
            rows = self.rows(line.id)
            lost = [r for r in rows if r.rejection_outcome == RejectionOutcome.LOST.value]
            assert abs(line.quantity_delivered - sum(r.quantity for r in rows)) <= _EPS
            assert abs(line.quantity_rejected - sum(r.quantity_rejected for r in rows)) <= _EPS
            assert abs(line.quantity_rejected_lost - sum(r.quantity_rejected for r in lost)) <= _EPS

    @invariant()
    def no_correction_takes_back_more_than_its_row_accepted(self) -> None:
        rows = self.deliveries._deliveries
        for row in rows:
            if row.corrects_delivery_id is None:
                taken = -sum(r.quantity for r in rows if r.corrects_delivery_id == row.id)
                assert taken <= row.quantity + _EPS, row.id
            else:
                # A correction says why: a miscount names its reason, a
                # rejection after receipt rejects the pieces it takes back.
                assert row.quantity < 0, row.id
                assert row.correction_reason or row.quantity_rejected == -row.quantity, row.id

    @invariant()
    def no_live_line_holds_more_than_its_quantity(self) -> None:
        for line in self.all_lines():
            if line.status == OrderItemStatus.CANCELED.value:
                assert line.quantity_delivered + line.quantity_rejected_lost <= _EPS, line.id
            else:
                settled = line.quantity_delivered + line.quantity_rejected_lost
                assert -_EPS <= settled <= line.quantity + _EPS, line.id

    @invariant()
    def the_order_stamps_follow_the_status(self) -> None:
        for order_id in _ORDER_IDS:
            order = self.order(order_id)
            if order.status == OrderStatus.ORDERED.value:
                assert order.ordered_date is not None, order_id
            delivered = order.status == OrderStatus.DELIVERED.value
            assert (order.delivery_date is not None) == delivered, order_id


OrderModel.TestCase.settings = model_settings(steps=30)
TestOrderModel = OrderModel.TestCase
