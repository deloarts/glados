"""Table tests for the order status derivation
(src/modules/fulfillment/domain/services/lifecycle/order.py): one or more cases per row, then
every fact combination of a small domain against a transcription of the
target table."""

from dataclasses import replace

import pytest

from src.modules.fulfillment.domain.services.lifecycle.facts import OrderFacts
from src.modules.fulfillment.domain.services.lifecycle.order import ORDER_STATUS
from src.modules.fulfillment.domain.services.lifecycle.order import derive_order_status
from src.modules.fulfillment.domain.services.lifecycle.order import live_line_statuses
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from tests.unit.lifecycle.small_domains import T0
from tests.unit.lifecycle.small_domains import order_facts

PENDING = OrderItemStatus.PENDING
REQUESTED = OrderItemStatus.REQUESTED
ORDERED = OrderItemStatus.ORDERED
PARTIAL = OrderItemStatus.PARTIALLY_DELIVERED
DELIVERED = OrderItemStatus.DELIVERED
CANCELED = OrderItemStatus.CANCELED

_DRAFT_ORDER = OrderFacts(requested_at=None, ordered_date=None, canceled_at=None, line_statuses=())


def _facts(*lines: OrderItemStatus, **changes: object) -> OrderFacts:
    return replace(_DRAFT_ORDER, line_statuses=lines, **changes)


@pytest.mark.parametrize(
    ("facts", "status", "row"),
    [
        (_facts(DELIVERED, DELIVERED, canceled_at=T0), OrderStatus.CANCELED, 1),
        (_facts(canceled_at=T0), OrderStatus.CANCELED, 1),
        (_facts(ordered_date=T0, requested_at=T0), OrderStatus.ORDERED, 2),
        (_facts(requested_at=T0), OrderStatus.REQUESTED, 2),
        (_facts(), OrderStatus.DRAFT, 2),
        (_facts(CANCELED, CANCELED, ordered_date=T0), OrderStatus.CANCELED, 3),
        (_facts(DELIVERED, CANCELED), OrderStatus.DELIVERED, 4),
        (_facts(DELIVERED, DELIVERED, ordered_date=T0), OrderStatus.DELIVERED, 4),
        (_facts(DELIVERED, PENDING), OrderStatus.PARTIALLY_DELIVERED, 5),
        (_facts(PARTIAL, ORDERED, CANCELED), OrderStatus.PARTIALLY_DELIVERED, 5),
        (_facts(ORDERED, ORDERED), OrderStatus.ORDERED, 6),
        (_facts(ORDERED, CANCELED), OrderStatus.ORDERED, 6),
        (_facts(PENDING, ordered_date=T0), OrderStatus.ORDERED, 6),
        (_facts(REQUESTED, ORDERED), OrderStatus.PARTIALLY_ORDERED, 7),
        (_facts(ORDERED, PENDING), OrderStatus.PARTIALLY_ORDERED, 7),
        (_facts(ORDERED, PENDING, requested_at=T0), OrderStatus.PARTIALLY_ORDERED, 7),
        (_facts(PENDING, requested_at=T0), OrderStatus.REQUESTED, 8),
        (_facts(REQUESTED, REQUESTED), OrderStatus.REQUESTED, 8),
        (_facts(PENDING, CANCELED), OrderStatus.DRAFT, 9),
    ],
)
def test_derive_order_status_rows(facts, status, row):
    derivation = derive_order_status(facts)
    assert (derivation.value, derivation.rule) == (status, row)


def test_live_line_statuses_leave_out_canceled_lines():
    assert live_line_statuses(_facts(CANCELED, ORDERED, CANCELED, PENDING)) == (ORDERED, PENDING)


def _transcribed(f: OrderFacts) -> tuple[OrderStatus, int]:
    """The target table, written out independently of the module."""
    live = [s for s in f.line_statuses if s != CANCELED]
    if f.canceled_at is not None:
        return OrderStatus.CANCELED, 1
    if not f.line_statuses:
        if f.ordered_date is not None:
            return OrderStatus.ORDERED, 2
        if f.requested_at is not None:
            return OrderStatus.REQUESTED, 2
        return OrderStatus.DRAFT, 2
    if not live:
        return OrderStatus.CANCELED, 3
    if all(s == DELIVERED for s in live):
        return OrderStatus.DELIVERED, 4
    if any(s in (DELIVERED, PARTIAL) for s in live):
        return OrderStatus.PARTIALLY_DELIVERED, 5
    if f.ordered_date is not None or all(s == ORDERED for s in live):
        return OrderStatus.ORDERED, 6
    if any(s == ORDERED for s in live):
        return OrderStatus.PARTIALLY_ORDERED, 7
    if f.requested_at is not None or all(s == REQUESTED for s in live):
        return OrderStatus.REQUESTED, 8
    return OrderStatus.DRAFT, 9


def test_derive_order_status_matches_the_table_on_every_small_case():
    reached = set()
    for facts in order_facts():
        derivation = derive_order_status(facts)
        assert isinstance(derivation.value, OrderStatus)
        assert (derivation.value, derivation.rule) == _transcribed(facts), facts
        reached.add(derivation.rule)
    assert reached == {row.number for row in ORDER_STATUS.rows}
