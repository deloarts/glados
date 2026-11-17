"""
Drops a production order's planned window when a user moves the order to
another place in a queue or to another queue. The walk keeps the window of a
pinned order and of a queued one inside the frozen window, so a moved order
would otherwise stay where it was planned. A pinned order is never moved, so
its window is never dropped here.
"""

from src.modules.fulfillment.domain.entities.production_order import ProductionOrder


def drop_planned_window(order: ProductionOrder) -> None:
    """Clears the planned window of an order that is not pinned, for the
    next walk to place it again."""
    if order.pinned:
        return
    order.planned_start = None
    order.planned_end = None
