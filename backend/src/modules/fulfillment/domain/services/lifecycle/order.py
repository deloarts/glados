"""Status of a supplier order, derived from its intents and the derived
statuses of its lines.

A live line is one that is not CANCELED. Canceled lines do not count in the
rollup, so an order whose other lines are all delivered is DELIVERED and an
order whose lines are all canceled is CANCELED. An order with some lines
ordered and others still pending or requested is PARTIALLY_ORDERED, and a
correction that takes every delivered piece back leaves it there, never
DRAFT. The order's own
`canceled_at` wins over its lines, and an order without lines shows the
furthest intent it has recorded.
"""

from src.modules.fulfillment.domain.services.lifecycle.facts import OrderFacts
from src.modules.fulfillment.domain.services.lifecycle.rules import Derivation
from src.modules.fulfillment.domain.services.lifecycle.rules import DerivationRule
from src.modules.fulfillment.domain.services.lifecycle.rules import DerivationTable
from src.modules.fulfillment.domain.services.lifecycle.rules import otherwise
from src.modules.fulfillment.domain.services.lifecycle.rules import rule
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus

_DELIVERING = (OrderItemStatus.DELIVERED, OrderItemStatus.PARTIALLY_DELIVERED)


def live_line_statuses(facts: OrderFacts) -> tuple[OrderItemStatus, ...]:
    """The statuses of the lines that are not CANCELED."""
    return tuple(s for s in facts.line_statuses if s != OrderItemStatus.CANCELED)


def _status_by_intent(facts: OrderFacts) -> OrderStatus:
    if facts.ordered_date is not None:
        return OrderStatus.ORDERED
    if facts.requested_at is not None:
        return OrderStatus.REQUESTED
    return OrderStatus.DRAFT


_NO_LINES = DerivationRule[OrderFacts, OrderStatus](
    number=2,
    condition="no lines",
    result="ordered if ordered_date, requested if requested_at, else draft",
    results=(OrderStatus.ORDERED, OrderStatus.REQUESTED, OrderStatus.DRAFT),
    applies=lambda f: not f.line_statuses,
    outcome=_status_by_intent,
)

ORDER_STATUS = DerivationTable[OrderFacts, OrderStatus](
    key="order_status",
    rules=(
        rule(1, "canceled_at set", OrderStatus.CANCELED, lambda f: f.canceled_at is not None),
        _NO_LINES,
        rule(
            3,
            "every line CANCELED",
            OrderStatus.CANCELED,
            lambda f: all(s == OrderItemStatus.CANCELED for s in f.line_statuses),
        ),
        rule(
            4,
            "every live line DELIVERED",
            OrderStatus.DELIVERED,
            lambda f: all(s == OrderItemStatus.DELIVERED for s in live_line_statuses(f)),
        ),
        rule(
            5,
            "any live line DELIVERED or PARTIALLY_DELIVERED",
            OrderStatus.PARTIALLY_DELIVERED,
            lambda f: any(s in _DELIVERING for s in live_line_statuses(f)),
        ),
        rule(
            6,
            "ordered_date set, or every live line ORDERED",
            OrderStatus.ORDERED,
            lambda f: (
                f.ordered_date is not None
                or all(s == OrderItemStatus.ORDERED for s in live_line_statuses(f))
            ),
        ),
        # Some lines are with the supplier and others are not: the order is
        # placed in part, so its ordered lines are past the buyer's edits
        # while its other lines can still be ordered.
        rule(
            7,
            "any live line ORDERED",
            OrderStatus.PARTIALLY_ORDERED,
            lambda f: any(s == OrderItemStatus.ORDERED for s in live_line_statuses(f)),
        ),
        rule(
            8,
            "requested_at set, or every live line REQUESTED",
            OrderStatus.REQUESTED,
            lambda f: (
                f.requested_at is not None
                or all(s == OrderItemStatus.REQUESTED for s in live_line_statuses(f))
            ),
        ),
    ),
    fallback=otherwise(9, OrderStatus.DRAFT),
)


def derive_order_status(facts: OrderFacts) -> Derivation[OrderStatus]:
    return ORDER_STATUS.derive(facts)
