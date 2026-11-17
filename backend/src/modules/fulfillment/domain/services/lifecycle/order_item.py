"""Status of a supplier order line, derived from its delivery totals and its
intents.

Lost pieces count like delivered ones, because the supplier sends nothing
more for them on this line. Cancellation wins over everything, and the
delivery totals win over the ordering intents, so a line that received goods
is never shown as merely ordered.
"""

from src.modules.fulfillment.domain.services.lifecycle.facts import OrderItemFacts
from src.modules.fulfillment.domain.services.lifecycle.rules import Derivation
from src.modules.fulfillment.domain.services.lifecycle.rules import DerivationTable
from src.modules.fulfillment.domain.services.lifecycle.rules import otherwise
from src.modules.fulfillment.domain.services.lifecycle.rules import rule
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.platform.domain.services.quantities import quantity_ge
from src.modules.platform.domain.services.quantities import quantity_gt


def settled_quantity(facts: OrderItemFacts) -> float:
    """Pieces the line will not receive again: accepted plus lost."""
    return facts.delivered + facts.lost


ORDER_ITEM_STATUS = DerivationTable[OrderItemFacts, OrderItemStatus](
    key="order_item_status",
    rules=(
        rule(1, "canceled_at set", OrderItemStatus.CANCELED, lambda f: f.canceled_at is not None),
        rule(
            2,
            "quantity > 0 and delivered + lost >= quantity",
            OrderItemStatus.DELIVERED,
            lambda f: quantity_gt(f.quantity, 0.0) and quantity_ge(settled_quantity(f), f.quantity),
        ),
        rule(
            3,
            "delivered + lost > 0",
            OrderItemStatus.PARTIALLY_DELIVERED,
            lambda f: quantity_gt(settled_quantity(f), 0.0),
        ),
        rule(4, "ordered_date set", OrderItemStatus.ORDERED, lambda f: f.ordered_date is not None),
        rule(
            5, "requested_at set", OrderItemStatus.REQUESTED, lambda f: f.requested_at is not None
        ),
    ),
    fallback=otherwise(6, OrderItemStatus.PENDING),
)


def derive_order_item_status(facts: OrderItemFacts) -> Derivation[OrderItemStatus]:
    return ORDER_ITEM_STATUS.derive(facts)
