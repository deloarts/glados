"""The totals an order line keeps beside its delivery rows, and how they
compare with the rows.

A line stores three running totals: the accepted pieces
(`quantity_delivered`), the rejected pieces (`quantity_rejected`) and the
rejected pieces written off as lost (`quantity_rejected_lost`). Each is the
sum of the matching amount over the line's delivery rows, so a total that
differs from its sum means a booking without its row or a row without its
booking. The derivation of the line reads the totals, so the lifecycle drift
report lists such a line as a fact anomaly, which only the facts can settle.
Comparisons use the one lifecycle tolerance.
"""

from dataclasses import dataclass

from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.platform.domain.services.quantities import quantity_eq

DELIVERY_TOTALS_RULE = "fact anomaly: the line's total differs from the sum over its delivery rows"


@dataclass(frozen=True, kw_only=True)
class DeliveryTotals:
    """Accepted, rejected and lost pieces, either as a line stores them or
    summed over its delivery rows."""

    accepted: float = 0.0
    rejected: float = 0.0
    lost: float = 0.0


def stored_totals(item: OrderItem) -> DeliveryTotals:
    """The totals the line stores beside its delivery rows."""
    return DeliveryTotals(
        accepted=item.quantity_delivered,
        rejected=item.quantity_rejected,
        lost=item.quantity_rejected_lost,
    )


@dataclass(frozen=True)
class TotalsDifference:
    """One stored total that differs from the sum of the rows. `field` is
    the order line's column."""

    field: str
    stored: float
    from_rows: float


def delivery_totals_differences(
    stored: DeliveryTotals, from_rows: DeliveryTotals
) -> tuple[TotalsDifference, ...]:
    """The totals of `stored` that differ from `from_rows` beyond the
    tolerance, in the order the line's columns are named."""
    pairs = (
        ("quantity_delivered", stored.accepted, from_rows.accepted),
        ("quantity_rejected", stored.rejected, from_rows.rejected),
        ("quantity_rejected_lost", stored.lost, from_rows.lost),
    )
    return tuple(
        TotalsDifference(field=field, stored=kept, from_rows=summed)
        for field, kept, summed in pairs
        if not quantity_eq(kept, summed)
    )
