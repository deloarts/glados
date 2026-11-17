"""
Quote requests under the lifecycle reconciler, on the fake world: an awarded
line stays awarded only while an order line its award created is live, so a
change to such a line derives the request again. The request is locked last
and gets its status with a changelog line and an event. An award the run
finds voided, which the lock step saw live, is noted on the request even
when its status stays, as on a closed request.
"""

from src.modules.fulfillment.application.services.lifecycle_drift import LifecycleDriftReport
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequest
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequestSupplier
from src.modules.fulfillment.domain.events.quote_request_events import QuoteRequestStatusChanged
from src.modules.fulfillment.domain.value_objects.lifecycle_aggregate import LifecycleAggregate
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.quote_request_status import QuoteRequestLineState
from src.modules.fulfillment.domain.value_objects.quote_request_status import QuoteRequestStatus
from tests.unit.fakes import FakeEventBus
from tests.unit.lifecycle.fake_world import NOW
from tests.unit.lifecycle.fake_world import FakeWorld
from tests.unit.lifecycle.fake_world import actor

_A = LifecycleAggregate
ACTOR = actor()


def _awarded(world: FakeWorld) -> tuple[QuoteRequest, Order, int]:
    """A request whose only line was awarded onto an ordered order line;
    returns the request, the order and the order line's id."""
    request = world.quote_request(status=QuoteRequestStatus.AWARDED)
    line = request.lines[0]
    line.awarded_at = NOW
    line.awarded_supplier_id = 1
    order = world.order(status=OrderStatus.ORDERED, ordered_date=NOW)
    item = world.line(
        order, status=OrderItemStatus.ORDERED, ordered_date=NOW, quote_request_line_id=line.id
    )
    return request, order, item.id


async def test_a_canceled_award_line_opens_the_request_line_again() -> None:
    world = FakeWorld()
    request, _order, item_id = _awarded(world)
    world.order_items[item_id].canceled_at = NOW
    bus = FakeEventBus()
    reconciler = LifecycleReconciler(world.repositories, bus)
    reconciler.touch_order_items([item_id])

    result = await reconciler.run(ACTOR, NOW, reason="order item canceled")

    stored = world.quote_requests[request.id]
    assert stored.status == QuoteRequestStatus.DRAFT.value
    assert result.new_status(_A.QUOTE_REQUESTS, request.id) == QuoteRequestStatus.DRAFT.value
    assert stored.changes[-1].endswith("Status: awarded → draft (order item canceled).")
    view = world.quote_request_view(stored)
    assert view.lines[0].state is QuoteRequestLineState.OPEN
    assert view.lines[0].award_voided
    assert view.lines[0].awarded_supplier_id == 1
    events = [e for e in bus.published if isinstance(e, QuoteRequestStatusChanged)]
    assert [(e.old_status, e.new_status) for e in events] == [
        (QuoteRequestStatus.AWARDED, QuoteRequestStatus.DRAFT)
    ]
    assert world.lock_log[-1] == (_A.QUOTE_REQUESTS, (request.id,))


async def test_a_line_closed_short_or_delivered_keeps_the_award() -> None:
    world = FakeWorld()
    request, _order, item_id = _awarded(world)
    item = world.order_items[item_id]
    item.quantity_delivered = 6.0
    item.closed_short_at = NOW
    reconciler = LifecycleReconciler(world.repositories, FakeEventBus())
    reconciler.touch_order_items([item_id])

    result = await reconciler.run(ACTOR, NOW)

    assert result.new_status(_A.QUOTE_REQUESTS, request.id) is None
    assert world.quote_requests[request.id].status == QuoteRequestStatus.AWARDED.value


async def test_the_request_is_locked_after_every_other_lifecycle_row() -> None:
    world = FakeWorld()
    request, order, item_id = _awarded(world)
    reconciler = LifecycleReconciler(world.repositories, FakeEventBus())
    reconciler.touch_order_items([item_id])

    await reconciler.lock_touched()

    locked = [aggregate for aggregate, _ in world.lock_log]
    assert locked[-1] is _A.QUOTE_REQUESTS
    assert world.locked(_A.QUOTE_REQUESTS) == {request.id}
    assert world.locked(_A.ORDERS) == {order.id}


async def test_the_drift_report_lists_a_request_whose_award_was_voided() -> None:
    world = FakeWorld()
    request, _order, item_id = _awarded(world)
    world.order_items[item_id].canceled_at = NOW

    report = await LifecycleDriftReport(world.repositories).run([_A.QUOTE_REQUESTS])

    assert [(r.table, r.id, r.stored, r.derived) for r in report.rows] == [
        ("quote_requests", request.id, "awarded", "draft")
    ]


def _closed_with_a_live_award(world: FakeWorld) -> tuple[QuoteRequest, Order, int]:
    """A request someone closed with its only line awarded to Acme, the
    award still live; returns the request, the order and the award's order
    line id."""
    request, order, item_id = _awarded(world)
    request.status = QuoteRequestStatus.CLOSED
    request.closed_at = NOW
    request.suppliers = [
        QuoteRequestSupplier(
            id=1, quote_request_id=request.id, supplier_id=9, position=1, supplier_name="Acme"
        )
    ]
    return request, order, item_id


async def test_a_void_on_a_closed_request_is_noted_and_keeps_it_closed() -> None:
    world = FakeWorld()
    request, order, item_id = _closed_with_a_live_award(world)
    bus = FakeEventBus()
    reconciler = LifecycleReconciler(world.repositories, bus)
    reconciler.touch_order_items([item_id])
    await reconciler.lock_touched()
    world.order_items[item_id].canceled_at = NOW

    result = await reconciler.run(ACTOR, NOW, reason="order item canceled")

    stored = world.quote_requests[request.id]
    assert stored.status == QuoteRequestStatus.CLOSED.value
    assert result.new_status(_A.QUOTE_REQUESTS, request.id) is None
    assert stored.changes[-1].endswith(
        f"Award of line 1 to Acme voided: its line on order {order.order_number} was canceled."
    )
    assert stored.changed == NOW
    assert not [e for e in bus.published if isinstance(e, QuoteRequestStatusChanged)]


async def test_an_award_voided_before_the_lock_is_not_noted_again() -> None:
    world = FakeWorld()
    request, _order, item_id = _closed_with_a_live_award(world)
    world.order_items[item_id].canceled_at = NOW
    reconciler = LifecycleReconciler(world.repositories, FakeEventBus())
    reconciler.touch_order_items([item_id])
    await reconciler.lock_touched()

    await reconciler.run(ACTOR, NOW)

    assert world.quote_requests[request.id].changes == []
