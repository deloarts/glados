"""Table tests for the order item status derivation
(src/modules/fulfillment/domain/services/lifecycle/order_item.py): one or more cases per row,
then every fact combination of a small domain against a transcription of the
target table."""

from dataclasses import replace

import pytest

from src.modules.fulfillment.domain.services.lifecycle.facts import OrderItemFacts
from src.modules.fulfillment.domain.services.lifecycle.order_item import ORDER_ITEM_STATUS
from src.modules.fulfillment.domain.services.lifecycle.order_item import derive_order_item_status
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from tests.unit.lifecycle.small_domains import T0
from tests.unit.lifecycle.small_domains import order_item_facts

EPS = 1e-6

_PENDING_LINE = OrderItemFacts(
    quantity=10.0, delivered=0.0, lost=0.0, requested_at=None, ordered_date=None, canceled_at=None
)


def _facts(**changes: object) -> OrderItemFacts:
    return replace(_PENDING_LINE, **changes)


@pytest.mark.parametrize(
    ("facts", "status", "row"),
    [
        (_facts(canceled_at=T0), OrderItemStatus.CANCELED, 1),
        (_facts(canceled_at=T0, delivered=10.0, ordered_date=T0), OrderItemStatus.CANCELED, 1),
        (_facts(delivered=10.0, ordered_date=T0), OrderItemStatus.DELIVERED, 2),
        (_facts(quantity=1.0, delivered=0.7 + 0.2 + 0.1), OrderItemStatus.DELIVERED, 2),
        (_facts(delivered=6.0, lost=4.0), OrderItemStatus.DELIVERED, 2),
        (_facts(lost=10.0), OrderItemStatus.DELIVERED, 2),
        (_facts(delivered=12.0), OrderItemStatus.DELIVERED, 2),
        (_facts(delivered=4.0, ordered_date=T0), OrderItemStatus.PARTIALLY_DELIVERED, 3),
        (_facts(lost=1.0), OrderItemStatus.PARTIALLY_DELIVERED, 3),
        (_facts(quantity=0.0, delivered=1.0), OrderItemStatus.PARTIALLY_DELIVERED, 3),
        (_facts(ordered_date=T0, requested_at=T0), OrderItemStatus.ORDERED, 4),
        (_facts(ordered_date=T0, delivered=1e-7), OrderItemStatus.ORDERED, 4),
        (_facts(requested_at=T0), OrderItemStatus.REQUESTED, 5),
        (_facts(), OrderItemStatus.PENDING, 6),
        (_facts(quantity=0.0), OrderItemStatus.PENDING, 6),
    ],
)
def test_derive_order_item_status_rows(facts, status, row):
    derivation = derive_order_item_status(facts)
    assert (derivation.value, derivation.rule) == (status, row)


def _transcribed(f: OrderItemFacts) -> tuple[OrderItemStatus, int]:
    """The target table, written out independently of the module."""
    settled = f.delivered + f.lost
    if f.canceled_at is not None:
        return OrderItemStatus.CANCELED, 1
    if f.quantity > EPS and settled >= f.quantity - EPS:
        return OrderItemStatus.DELIVERED, 2
    if settled > EPS:
        return OrderItemStatus.PARTIALLY_DELIVERED, 3
    if f.ordered_date is not None:
        return OrderItemStatus.ORDERED, 4
    if f.requested_at is not None:
        return OrderItemStatus.REQUESTED, 5
    return OrderItemStatus.PENDING, 6


def test_derive_order_item_status_matches_the_table_on_every_small_case():
    reached = set()
    for facts in order_item_facts():
        derivation = derive_order_item_status(facts)
        assert isinstance(derivation.value, OrderItemStatus)
        assert (derivation.value, derivation.rule) == _transcribed(facts), facts
        reached.add(derivation.rule)
    assert reached == {row.number for row in ORDER_ITEM_STATUS.rows}
