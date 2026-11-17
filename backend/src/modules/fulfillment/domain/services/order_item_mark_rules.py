"""Status guards for marking an order item requested or ordered. No I/O.

A line is marked requested only while it is PENDING, and ordered only while it
is PENDING or REQUESTED. Every later status and CANCELED are refused, so a
mark can neither move a delivered line back to ORDERED nor make a canceled
line live again, which would also make it eligible for allocations again. The
status sets are the start statuses of the two marks in the order item intent
table (lifecycle/intents.py), and the bulk marks select their lines by the
same sets, so one definition decides which lines a mark may touch.
"""

from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.errors import OrderItemCannotBeMarkedError
from src.modules.fulfillment.domain.services.lifecycle.intents import ORDER_ITEM_INTENTS
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction


def _start_statuses(action: LifecycleAction) -> frozenset[str]:
    rule = ORDER_ITEM_INTENTS.rule_for(action)
    if rule is None or rule.allowed_from is None:
        raise ValueError(f"The order item intent table names no start status for {action.value}.")
    return frozenset(rule.allowed_from)


MARK_REQUESTED_SOURCES: frozenset[str] = _start_statuses(LifecycleAction.MARK_REQUESTED)
MARK_ORDERED_SOURCES: frozenset[str] = _start_statuses(LifecycleAction.MARK_ORDERED)


def assert_mark_requested_allowed(item: OrderItem) -> None:
    """Refuses marking a line requested unless it is PENDING."""
    _assert_markable(item, MARK_REQUESTED_SOURCES, "requested", "a pending line")


def assert_mark_ordered_allowed(item: OrderItem) -> None:
    """Refuses marking a line ordered unless it is PENDING or REQUESTED."""
    _assert_markable(item, MARK_ORDERED_SOURCES, "ordered", "a pending or requested line")


def _assert_markable(
    item: OrderItem, sources: frozenset[str], target: str, allowed_description: str
) -> None:
    if item.status not in sources:
        raise OrderItemCannotBeMarkedError(
            f"Order item #{item.id} is {item.status.value} and cannot be marked as {target}; "
            f"only {allowed_description} can."
        )
