"""Guards for editing the quantity of an order item, a production lot or a
demand.

A quantity never drops below what is already committed against it: the
pieces delivered or lost on a line, the allocations of both families that
cover a line, the made allocations on a lot, or the allocations and stock
that cover a demand. A MADE line, which supplies a lot position, never
grows past what the position leaves it. Every edit form sends the whole
row, so each guard acts only when the quantity actually moves. A row that
already breaks a rule therefore still accepts an unrelated edit such as a
new note, while any new quantity has to be valid. Comparisons use the one
lifecycle tolerance (domain/services/quantities.py). The status a line takes
after its quantity changed is derived by the lifecycle reconciler. No I/O.
"""

from typing import Protocol

from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.errors import AllocationOverflowError
from src.modules.fulfillment.domain.errors import LotPositionQuantityExceedsRemainingError
from src.modules.fulfillment.domain.errors import OrderItemQuantityBelowDeliveredError
from src.modules.platform.domain.services.quantities import assert_whole_pieces
from src.modules.platform.domain.services.quantities import quantity_eq
from src.modules.platform.domain.services.quantities import quantity_gt


class _DemandLike(Protocol):
    id: int
    quantity: float
    unit: str


def quantity_changed(current: float, new: float) -> bool:
    """Whether an edit moves a quantity by more than float noise."""
    return not quantity_eq(new, current)


def assert_order_item_quantity_allowed(
    item: OrderItem, new_quantity: float, allocated: float
) -> None:
    """Raises when a line's new quantity is below the pieces delivered or
    lost on it, or below `allocated`, the sum that demands of both
    allocation families have allocated to it. Call it before the new
    quantity is assigned."""
    if not quantity_changed(item.quantity, new_quantity):
        return
    settled = item.quantity_settled
    if quantity_gt(settled, new_quantity):
        raise OrderItemQuantityBelowDeliveredError(
            f"Order item #{item.id} has {settled:.3f} {item.unit} delivered or lost; its "
            f"quantity cannot drop to {new_quantity:.3f}."
        )
    if quantity_gt(allocated, new_quantity):
        raise AllocationOverflowError(
            f"Order item #{item.id} has {allocated:.3f} {item.unit} allocated to demands; its "
            f"quantity cannot drop to {new_quantity:.3f}. Reduce the allocations first."
        )


def assert_made_line_within_position(
    item: OrderItem, new_quantity: float, available: float
) -> None:
    """Raises when a MADE line's new quantity exceeds `available`, the part
    of its position that the position's production orders leave the line
    (lot_rules.compute_position_remaining without the line). Call it before
    the new quantity is assigned."""
    if not quantity_changed(item.quantity, new_quantity):
        return
    if quantity_gt(new_quantity, available):
        raise LotPositionQuantityExceedsRemainingError(
            f"Position #{item.lot_position_id} leaves {max(available, 0.0):.3f} {item.unit} to "
            f"order item #{item.id}; its quantity cannot be set to {new_quantity:.3f}."
        )


def assert_lot_quantity_allowed(lot: ProductionLot, new_quantity: float, allocated: float) -> None:
    """Raises when a lot's new quantity is below `allocated`, the sum that
    made demands have allocated to the lot. Call it before the new quantity
    is assigned."""
    if not quantity_changed(lot.quantity, new_quantity):
        return
    assert_whole_pieces(new_quantity, what="The lot quantity")
    if quantity_gt(allocated, new_quantity):
        raise AllocationOverflowError(
            f"Lot #{lot.id} has {allocated:.3f} piece(s) allocated to demands; its quantity "
            f"cannot drop to {new_quantity:.3f}."
        )


def assert_demand_quantity_allowed(
    demand: _DemandLike, new_quantity: float, covered: float, *, noun: str
) -> None:
    """Raises when a demand's new quantity is below `covered`, what its
    allocations and stock already cover. Call it before the new quantity is
    assigned."""
    if not quantity_changed(demand.quantity, new_quantity):
        return
    if quantity_gt(covered, new_quantity):
        raise AllocationOverflowError(
            f"{noun} #{demand.id} has {covered:.3f} {demand.unit} allocated or covered from "
            f"stock; its quantity cannot drop to {new_quantity:.3f}."
        )
