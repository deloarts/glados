"""
How far a delivery on a bought, source or virtual order line may differ
from the ordered quantity, in percent of the line's quantity. The order
settings hold the global tolerances, and a bought or source line's
catalogue item may hold its own, which replace them; a virtual line has no
item and takes the global ones.

Within the over tolerance a line takes pieces beyond its quantity, and the
surplus is free capacity on the line that further demands can be allocated
to. Within the under tolerance the booking that settles the line close
enough to its quantity closes it short, as an explicit close short does.
A MADE line carries the counted pieces of its lot and has no tolerance. In
a unit that counts whole things the over allowance is rounded down to whole
pieces, so a tolerance never admits a fraction of a piece.
"""

import math
from dataclasses import dataclass

from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.platform.domain.services.quantities import QUANTITY_EPSILON
from src.modules.platform.domain.services.quantities import counts_whole_units
from src.modules.platform.domain.services.quantities import quantity_ge
from src.modules.platform.domain.services.quantities import quantity_gt

# The line types a tolerance applies to.
_TOLERANCED_LINES = frozenset({OrderLineType.BOUGHT, OrderLineType.SOURCE, OrderLineType.VIRTUAL})


@dataclass(frozen=True)
class DeliveryTolerance:
    """The tolerances in percent that apply to one line."""

    over_percent: float = 0.0
    under_percent: float = 0.0

    @classmethod
    def resolve(
        cls,
        *,
        over_percent: float,
        under_percent: float,
        item_over_percent: float | None,
        item_under_percent: float | None,
    ) -> "DeliveryTolerance":
        """The item's own tolerances where it has them, else the global ones."""
        return cls(
            over_percent=item_over_percent if item_over_percent is not None else over_percent,
            under_percent=item_under_percent if item_under_percent is not None else under_percent,
        )


NO_TOLERANCE = DeliveryTolerance()


def takes_tolerance(line: OrderItem) -> bool:
    return line.line_type in _TOLERANCED_LINES


def over_delivery_allowance(line: OrderItem, tolerance: DeliveryTolerance) -> float:
    """The pieces the line may take beyond its quantity."""
    if not takes_tolerance(line) or tolerance.over_percent <= 0:
        return 0.0
    allowance = max(line.quantity, 0.0) * tolerance.over_percent / 100.0
    if counts_whole_units(line.unit):
        return float(math.floor(allowance + QUANTITY_EPSILON))
    return allowance


def under_delivery_floor(line: OrderItem, tolerance: DeliveryTolerance) -> float:
    """The settled pieces from which the line counts as complete."""
    return line.quantity * (1.0 - tolerance.under_percent / 100.0)


def closes_within_under_tolerance(line: OrderItem, tolerance: DeliveryTolerance) -> bool:
    """Whether the line, as booked now, is short of its quantity by no more
    than the under tolerance, with pieces delivered or lost on it, so it
    closes short. A line that is settled in full or closed already does
    not."""
    if not takes_tolerance(line) or tolerance.under_percent <= 0:
        return False
    if line.canceled_at is not None or line.closed_short_at is not None:
        return False
    settled = line.quantity_settled
    return (
        quantity_gt(settled, 0.0)
        and quantity_gt(line.quantity, settled)
        and quantity_ge(settled, under_delivery_floor(line, tolerance))
    )
