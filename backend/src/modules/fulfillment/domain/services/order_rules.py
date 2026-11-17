"""Business rules for orders and order items. No I/O.

Which status an order or a line must have for an action is decided by the
intent tables of the lifecycle package (lifecycle/intents.py), the same
tables the lifecycle catalogue and the actions offered to a client read. The
rules here add the base permission of each action and name the reason of a
refusal; a status they compare is the stored one, which the lifecycle
reconciler keeps equal to its derivation.
"""

from collections.abc import Sequence
from datetime import datetime
from datetime import timedelta

from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.order_item_delivery import OrderItemDelivery
from src.modules.fulfillment.domain.errors import DeliveryCannotBeCorrectedError
from src.modules.fulfillment.domain.errors import DeliveryRejectionInvalidError
from src.modules.fulfillment.domain.errors import InvalidDeliveryQuantityError
from src.modules.fulfillment.domain.errors import OrderAlreadyRequestedError
from src.modules.fulfillment.domain.errors import OrderAlreadySubmittedError
from src.modules.fulfillment.domain.errors import OrderCanceledError
from src.modules.fulfillment.domain.errors import OrderCannotBeCanceledError
from src.modules.fulfillment.domain.errors import OrderItemCanceledError
from src.modules.fulfillment.domain.errors import OrderItemCannotBeCanceledError
from src.modules.fulfillment.domain.errors import OrderItemCannotBeClosedShortError
from src.modules.fulfillment.domain.errors import OrderItemCannotBeMovedError
from src.modules.fulfillment.domain.errors import OrderItemCannotBeRemovedError
from src.modules.fulfillment.domain.errors import OrderItemCannotBeReopenedError
from src.modules.fulfillment.domain.errors import OrderItemLineTypeMismatchError
from src.modules.fulfillment.domain.errors import OrderItemNotDeliverableError
from src.modules.fulfillment.domain.errors import OrderItemNotReadyForPickupError
from src.modules.fulfillment.domain.errors import OrderItemQuantityNotEditableError
from src.modules.fulfillment.domain.errors import OrderItemReceivedLockedError
from src.modules.fulfillment.domain.errors import OrderSupplierLockedError
from src.modules.fulfillment.domain.errors import PickupInFutureError
from src.modules.fulfillment.domain.services.lifecycle.intents import ORDER_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import ORDER_ITEM_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import OrderItemContext
from src.modules.fulfillment.domain.services.lifecycle.intents import may_change_line
from src.modules.fulfillment.domain.services.lifecycle.intents import may_change_order
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.rejection_after_receipt import (
    RejectionAfterReceipt,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.services.intent_table import HasStatus
from src.modules.platform.domain.services.intent_table import IntentRule
from src.modules.platform.domain.services.intent_table import IntentTable
from src.modules.platform.domain.services.intent_table import RefusalKind
from src.modules.platform.domain.services.quantities import assert_finite
from src.modules.platform.domain.services.quantities import assert_whole_pieces
from src.modules.platform.domain.services.quantities import is_zero_quantity
from src.modules.platform.domain.services.quantities import quantity_eq
from src.modules.platform.domain.services.quantities import quantity_gt
from src.modules.platform.domain.value_objects.permission import Permission
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction

# assert_valid_line_type's field table: every order-item line-identity
# column, and which one each OrderLineType claims as its own. The other
# three must stay unset for that line.
_LINE_TYPE_FIELDS = ("bought_item_id", "source_item_id", "lot_position_id", "virtual_name")
_LINE_TYPE_IDENTITY_FIELD: dict[str, str] = {
    OrderLineType.BOUGHT: "bought_item_id",
    OrderLineType.SOURCE: "source_item_id",
    OrderLineType.MADE: "lot_position_id",
    OrderLineType.VIRTUAL: "virtual_name",
}


def _rule[S: HasStatus, C](table: IntentTable[S, C], action: LifecycleAction) -> IntentRule[S, C]:
    found = table.rule_for(action)
    if found is None:
        raise ValueError(f"{action.value} is not an action of {table.key}.")
    return found


def _state_allows[S: HasStatus, C](rule: IntentRule[S, C], subject: S, context: C) -> bool:
    """Whether the rule's start statuses and guard accept the subject. The
    rule's actor guard is left to the caller, for an action that has none."""
    if rule.allowed_from is not None and subject.status not in rule.allowed_from:
        return False
    return rule.guard(subject, context)


def _order_status(value: str) -> OrderStatus:
    """An order's stored status as the intent tables take it. A value that
    no writer of OrderStatus produces reads as DRAFT, the status of an order
    without any recorded intent."""
    try:
        return OrderStatus(value)
    except ValueError:
        return OrderStatus.DRAFT


def order_item_context(order: HasStatus, lot_status: str | None = None) -> OrderItemContext:
    """The context the order item intent table reads: the line's order and,
    for a MADE line, whether its lot is canceled. `lot_status` is that lot's
    status, None for every other line. `order` is the order or anything that
    carries its status, such as its result."""
    return OrderItemContext(
        order_status=_order_status(order.status),
        lot_canceled=lot_status == LotStatus.CANCELED,
    )


def _undeliverable_reason(
    order: Order, order_item: OrderItem, lot_status: str | None
) -> str | None:
    """Why the line cannot take a delivery, or None when it can. The deliver
    rule of the order item intent table decides; the reason names the
    condition it failed on."""
    rule = _rule(ORDER_ITEM_INTENTS, LifecycleAction.DELIVER)
    if _state_allows(rule, order_item, order_item_context(order, lot_status)):
        return None
    if order.status == OrderStatus.CANCELED:
        return f"Order #{order.id} is canceled, so its items cannot take deliveries."
    if rule.allowed_from is not None and order_item.status not in rule.allowed_from:
        return (
            f"Order item #{order_item.id} has status '{order_item.status.value}'; only ordered or "
            "partially delivered items can take a delivery."
        )
    return (
        f"Order item #{order_item.id} supplies a canceled production lot and cannot take "
        "a delivery."
    )


# ── Order rules ───────────────────────────────────────────────────────


# A browser clock a little ahead of the server's is not a future pickup.
_PICKUP_CLOCK_SLACK = timedelta(minutes=5)

_PLACED_LINE_STATUSES = frozenset(
    {
        OrderItemStatus.ORDERED,
        OrderItemStatus.PARTIALLY_DELIVERED,
        OrderItemStatus.DELIVERED,
    }
)
_AWAITING_LINE_STATUSES = frozenset(
    {
        OrderItemStatus.PENDING,
        OrderItemStatus.REQUESTED,
        OrderItemStatus.ORDERED,
        OrderItemStatus.PARTIALLY_DELIVERED,
    }
)


def counted_unit(item: OrderItem) -> str | None:
    """The unit the line's quantities are checked against for whole numbers:
    None for a MADE line, which always carries pieces of its lot."""
    return None if item.line_type == OrderLineType.MADE else item.unit


class OrderRules:
    @staticmethod
    def assert_can_create(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_ORDERS, "create", "orders")

    @staticmethod
    def assert_can_update(actor: User, order: Order) -> None:
        """write:orders, and manage:orders once the order is past REQUESTED,
        the rule the order intent table reports (lifecycle/intents.py
        may_change_order). A change to one line goes through
        assert_can_update_line instead."""
        assert_has_permission(actor, Permission.WRITE_ORDERS, "update", "orders")
        if not may_change_order(actor, order.status):
            raise OrderAlreadySubmittedError(
                f"Order #{order.id} has already been submitted (status={order.status.value}) "
                f"and cannot be modified without manage:orders permission."
            )

    @staticmethod
    def assert_can_update_line(
        actor: User, order: Order, line_status: OrderItemStatus, what: str
    ) -> None:
        """write:orders, and manage:orders for a line the supplier holds or a
        line of an order past REQUESTED, except that a partially ordered
        order keeps its pending and requested lines open to the base
        permission (lifecycle/intents.py may_change_line). `line_status` is
        PENDING for a line about to be added; `what` names the line in the
        refusal."""
        assert_has_permission(actor, Permission.WRITE_ORDERS, "update", "orders")
        if not may_change_line(actor, order.status, line_status):
            raise OrderAlreadySubmittedError(
                f"{what} ({line_status.value}) on order #{order.id} ({order.status.value}) cannot be "
                f"modified without manage:orders permission once it or its order is past "
                f"requested."
            )

    @staticmethod
    def assert_can_write_orders(actor: User) -> None:
        """The base permission of every order edit, checked before the order
        is read; the status-dependent rule of assert_can_update follows on
        the read."""
        assert_has_permission(actor, Permission.WRITE_ORDERS, "update", "orders")

    @staticmethod
    def assert_can_manage_files(actor: User) -> None:
        """Order documents need WRITE_ORDERS but no status gate, because
        delivery notes are often attached to submitted or delivered orders."""
        assert_has_permission(actor, Permission.WRITE_ORDERS, "manage", "order files")

    @staticmethod
    def assert_can_delete_order_file(actor: User, delivery_id: int | None) -> None:
        """Order documents need WRITE_ORDERS. A picture of a delivery row
        is the receiver's evidence, so RECEIVE_DELIVERIES deletes it too,
        for example a photo taken by mistake. `delivery_id` is the row the
        file documents, None for a file of the order itself."""
        if delivery_id is not None and actor.has_permission(Permission.RECEIVE_DELIVERIES):
            return
        OrderRules.assert_can_manage_files(actor)

    @staticmethod
    def assert_can_receive_delivery(actor: User) -> None:
        """Receiving goods is a warehouse action with its own permission, so
        it neither requires nor implies editing orders."""
        assert_has_permission(actor, Permission.RECEIVE_DELIVERIES, "record", "order deliveries")

    @staticmethod
    def can_deliver(order: Order, order_item: OrderItem, lot_status: str | None = None) -> bool:
        """Whether the line can take a delivery: it is ordered or partially
        delivered, its order is not canceled, and the lot behind a MADE line
        is not canceled. `lot_status` is that lot's status, None for every
        other line."""
        return _undeliverable_reason(order, order_item, lot_status) is None

    @staticmethod
    def assert_can_deliver(
        order: Order, order_item: OrderItem, lot_status: str | None = None
    ) -> None:
        """Refuses a delivery on a line that can_deliver rejects, naming the
        reason."""
        reason = _undeliverable_reason(order, order_item, lot_status)
        if reason is not None:
            raise OrderItemNotDeliverableError(reason)

    @staticmethod
    def assert_valid_delivery(
        order_item: OrderItem,
        delivered_now: float,
        quantity_rejected: float,
        remaining: float,
        rejection_reason: str | None,
        rejection_outcome: str | None,
        allowance: float = 0.0,
    ) -> None:
        """Guards one delivery booking. Every quantity must be a finite
        number, everything in the shipment, accepted or rejected, must fit
        in what the line still has open (pieces rejected for redelivery
        stay open) plus the `allowance` its over-delivery tolerance grants
        beyond its quantity, and a rejection needs a reason and an outcome,
        which in turn need rejected pieces.
        A line whose open quantity is not finite has broken delivery totals
        and takes no booking until they are repaired."""
        assert_finite(
            remaining,
            error=InvalidDeliveryQuantityError,
            what=f"The open quantity of order item #{order_item.id}",
        )
        assert_finite(
            delivered_now,
            error=InvalidDeliveryQuantityError,
            what=f"The delivered quantity of order item #{order_item.id}",
        )
        assert_finite(
            quantity_rejected,
            error=InvalidDeliveryQuantityError,
            what=f"The rejected quantity of order item #{order_item.id}",
        )
        if delivered_now < 0 or quantity_rejected < 0:
            raise InvalidDeliveryQuantityError(
                f"Order item #{order_item.id}: delivered and rejected quantities must not "
                "be negative."
            )
        for booked in (delivered_now, quantity_rejected):
            assert_whole_pieces(
                booked,
                what=f"A booking on order item #{order_item.id}",
                unit=counted_unit(order_item),
            )
        if not quantity_gt(delivered_now + quantity_rejected, 0.0):
            raise InvalidDeliveryQuantityError(
                f"Order item #{order_item.id}: a delivery booking must record at least one "
                "accepted or rejected piece."
            )
        if quantity_gt(delivered_now + quantity_rejected, remaining + allowance):
            beyond = (
                f" and its over-delivery tolerance allows {allowance:.3f} more"
                if quantity_gt(allowance, 0.0)
                else ""
            )
            raise InvalidDeliveryQuantityError(
                f"Order item #{order_item.id} has {remaining:.3f} {order_item.unit} remaining"
                f"{beyond}; cannot book {delivered_now:.3f} accepted + "
                f"{quantity_rejected:.3f} rejected."
            )
        if quantity_rejected > 0 and (rejection_reason is None or rejection_outcome is None):
            raise DeliveryRejectionInvalidError(
                f"Order item #{order_item.id}: rejecting {quantity_rejected:.3f} "
                f"{order_item.unit} requires both a rejection reason and an outcome."
            )
        # An outcome acts on the line, a redelivery clears its expected date,
        # so one without rejected pieces would act on nothing it names.
        if not quantity_gt(quantity_rejected, 0.0) and (
            rejection_reason is not None or rejection_outcome is not None
        ):
            raise DeliveryRejectionInvalidError(
                f"Order item #{order_item.id}: a rejection reason or outcome needs rejected pieces."
            )

    @staticmethod
    def assert_can_cancel(actor: User, order: Order) -> None:
        """Cancelling needs `write:orders`, and `manage:orders` once the
        order is past DRAFT/REQUESTED. Permission checks run before status
        checks, so an unauthorized caller learns nothing about the state."""
        assert_has_permission(actor, Permission.WRITE_ORDERS, "cancel", "orders")
        refusal = ORDER_INTENTS.check(LifecycleAction.CANCEL, order, None, actor)
        if refusal is None:
            return
        if refusal.kind is RefusalKind.PERMISSION:
            raise InsufficientPermissionsError(
                f"Order #{order.id} has already been submitted (status={order.status.value}) "
                f"and cannot be canceled without manage:orders permission."
            )
        if order.status == OrderStatus.DELIVERED:
            raise OrderCannotBeCanceledError(
                f"Order #{order.id} is fully delivered and cannot be canceled."
            )
        if order.status == OrderStatus.CANCELED:
            raise OrderCannotBeCanceledError(f"Order #{order.id} is already canceled.")
        raise OrderCannotBeCanceledError(
            f"Order #{order.id} has status '{order.status.value}' and cannot be canceled."
        )

    @staticmethod
    def assert_header_editable(order: Order) -> None:
        """An order someone canceled keeps its header as it was canceled,
        the edit rule of the order intent table."""
        if order.canceled_at is not None:
            raise OrderCanceledError(f"Order #{order.id} is canceled and is not edited any more.")

    @staticmethod
    def assert_line_editable(item: OrderItem) -> None:
        """A canceled line waits for nothing and is not edited, the edit rule
        of the order item intent table."""
        if item.status == OrderItemStatus.CANCELED:
            raise OrderItemCanceledError(f"Order item #{item.id} is canceled and is not edited.")

    @staticmethod
    def assert_can_add_line(order: Order) -> None:
        """An order someone canceled, which carries the cancel intent, takes
        no new line, because nothing on it can be ordered or delivered any
        more. An order that derives CANCELED only because every line is
        canceled, for example its only MADE line by a lot cancel, still takes
        one and then derives from that line again; so does a delivered
        order."""
        if order.canceled_at is not None:
            raise OrderCanceledError(f"Order #{order.id} is canceled and takes no new lines.")

    @staticmethod
    def assert_can_remove_item(actor: User, order: Order, item: OrderItem) -> None:
        """Removing a line needs the line's update permission (403 before
        409) and a PENDING or REQUESTED line, by the remove rule of the
        order item intent table. An ordered line is canceled instead, and a
        canceled, partially delivered or delivered line stays as the record
        of what happened to it."""
        OrderRules.assert_can_update_line(actor, order, item.status, f"Order item #{item.id}")
        rule = _rule(ORDER_ITEM_INTENTS, LifecycleAction.REMOVE)
        if _state_allows(rule, item, order_item_context(order)):
            return
        # A MADE line is its position's external assignment; removing it
        # past PENDING/REQUESTED would orphan a real purchase.
        if item.lot_position_id is not None:
            raise OrderItemCannotBeRemovedError(
                f"Order item #{item.id} is linked to a production lot position and has "
                f"status '{item.status.value}'; it can only be removed while pending/requested."
            )
        if item.status == OrderItemStatus.ORDERED:
            raise OrderItemCannotBeRemovedError(
                f"Order item #{item.id} is ordered and cannot be removed; cancel it instead."
            )
        raise OrderItemCannotBeRemovedError(
            f"Order item #{item.id} has status '{item.status.value}' and cannot be removed."
        )

    @staticmethod
    def assert_can_move_item(actor: User, source: Order, target: Order, item: OrderItem) -> None:
        """A line moves to another order nobody canceled while it is
        PENDING, REQUESTED or ORDERED and nothing was delivered or rejected
        on it, by the move rule of the order item intent table: received
        pieces stay on the order that received them. Like a new line
        (assert_can_add_line), a moved line is refused only by a target that
        carries the cancel intent; an order that reads canceled only because
        every line is canceled takes it and derives from it. Both orders need
        the update permission, checked before the line's state."""
        if source.id == target.id:
            raise OrderItemCannotBeMovedError(
                f"Order item #{item.id} is already on order #{source.id}."
            )
        if target.canceled_at is not None:
            raise OrderItemCannotBeMovedError(
                f"Order #{target.id} is canceled and cannot receive moved items."
            )
        what = f"Order item #{item.id}"
        OrderRules.assert_can_update_line(actor, source, item.status, what)
        OrderRules.assert_can_update_line(actor, target, item.status, what)
        rule = _rule(ORDER_ITEM_INTENTS, LifecycleAction.MOVE)
        context = OrderItemContext(
            order_status=_order_status(source.status),
            target_order_canceled=target.canceled_at is not None,
        )
        if _state_allows(rule, item, context):
            return
        untouched = is_zero_quantity(item.quantity_delivered) and is_zero_quantity(
            item.quantity_rejected
        )
        if not untouched:
            raise OrderItemCannotBeMovedError(
                f"Order item #{item.id} has delivered or rejected pieces and cannot be moved; "
                "they stay on the order that received them."
            )
        raise OrderItemCannotBeMovedError(
            f"Order item #{item.id} has status '{item.status.value}' and cannot be moved."
        )

    @staticmethod
    def assert_can_cancel_line(actor: User, order: Order, item: OrderItem) -> None:
        """Canceling a single line needs the line's update permission (403
        before 409) and the cancel rule of the order item intent table: the
        line is PENDING, REQUESTED or ORDERED and nothing was delivered or
        lost on it. A line that received pieces is closed short instead."""
        OrderRules.assert_can_update_line(actor, order, item.status, f"Order item #{item.id}")
        if OrderRules.can_cancel_line(order, item):
            return
        if item.status == OrderItemStatus.CANCELED:
            raise OrderItemCannotBeCanceledError(f"Order item #{item.id} is already canceled.")
        if item.status == OrderItemStatus.DELIVERED:
            raise OrderItemCannotBeCanceledError(
                f"Order item #{item.id} is delivered and cannot be canceled."
            )
        raise OrderItemCannotBeCanceledError(
            f"Order item #{item.id} has pieces delivered or lost and cannot be canceled; "
            "close it short instead."
        )

    @staticmethod
    def assert_supplier_changeable(order: Order, lines: Sequence[OrderItem]) -> None:
        """An order's supplier changes only while none of its lines was
        ordered: an ordered line is already with the old supplier."""
        placed = [
            line
            for line in lines
            if line.canceled_at is None and line.status in _PLACED_LINE_STATUSES
        ]
        if placed:
            raise OrderSupplierLockedError(
                f"Order #{order.id} has {len(placed)} line(s) already ordered from "
                f"{order.supplier_name or 'its supplier'}; its supplier cannot change."
            )

    @staticmethod
    def awaits_goods(line: OrderItem) -> bool:
        """Whether a line still waits for goods: not delivered, not
        canceled. Only such a line takes a new expected delivery date."""
        return line.canceled_at is None and line.status in _AWAITING_LINE_STATUSES

    @staticmethod
    def can_close_line_short(order: Order, item: OrderItem) -> bool:
        """Whether the line can be closed short: it is ORDERED or PARTIALLY
        DELIVERED and pieces were delivered or lost on it, by the close
        short rule of the order item intent table."""
        rule = _rule(ORDER_ITEM_INTENTS, LifecycleAction.CLOSE_SHORT)
        return _state_allows(rule, item, order_item_context(order))

    @staticmethod
    def assert_can_close_short(actor: User, order: Order, item: OrderItem) -> None:
        """Closing a line short needs the line's update permission (403
        before 409) and the close short rule. A line on which nothing was
        delivered or lost is canceled instead."""
        OrderRules.assert_can_update_line(actor, order, item.status, f"Order item #{item.id}")
        if OrderRules.can_close_line_short(order, item):
            return
        rule = _rule(ORDER_ITEM_INTENTS, LifecycleAction.CLOSE_SHORT)
        if rule.allowed_from is not None and item.status in rule.allowed_from:
            raise OrderItemCannotBeClosedShortError(
                f"Order item #{item.id} has nothing delivered or lost yet; cancel it instead."
            )
        raise OrderItemCannotBeClosedShortError(
            f"Order item #{item.id} has status '{item.status.value}' and cannot be closed short."
        )

    @staticmethod
    def assert_received_line_keeps_its_identity(
        item: OrderItem,
        *,
        unit: str,
        items_per_unit: float,
        project_id: int | None,
        bought_item_id: int | None,
    ) -> None:
        """Once a line received goods, accepted, rejected or lost, its unit,
        items per unit, project and bought item stay as they were: changing
        them would rewrite what was received and what the demands counted.
        Price, note, dates and storage place stay editable."""
        received = item.quantity_delivered + item.quantity_rejected + item.quantity_rejected_lost
        if not quantity_gt(received, 0.0):
            return
        changed = [
            name
            for name, differs in (
                ("unit", unit.strip().upper() != item.unit.strip().upper()),
                ("items per unit", not quantity_eq(items_per_unit, item.items_per_unit)),
                ("project", project_id is not None and project_id != item.project_id),
                (
                    "bought item",
                    bought_item_id is not None and bought_item_id != item.bought_item_id,
                ),
            )
            if differs
        ]
        if changed:
            raise OrderItemReceivedLockedError(
                f"Order item #{item.id} already received goods, so its "
                f"{', '.join(changed)} cannot change."
            )

    @staticmethod
    def assert_ready_for_pickup(
        order: Order, item: OrderItem, pickup_at: datetime, now: datetime
    ) -> None:
        """A line is ready for pickup only while it is ordered or partially
        delivered on an order that is not canceled, by the order item intent
        table, and never at a time still to come."""
        rule = _rule(ORDER_ITEM_INTENTS, LifecycleAction.MARK_READY_FOR_PICKUP)
        if not _state_allows(rule, item, order_item_context(order)):
            raise OrderItemNotReadyForPickupError(
                f"Order item #{item.id} has status '{item.status.value}' on an order that is "
                f"{order.status.value} and cannot be marked ready for pickup."
            )
        if pickup_at > now + _PICKUP_CLOCK_SLACK:
            raise PickupInFutureError(
                f"Order item #{item.id} cannot be ready for pickup at "
                f"{pickup_at.isoformat(timespec='minutes')}, which is still to come."
            )

    @staticmethod
    def assert_can_reopen(actor: User, order: Order, item: OrderItem) -> None:
        """Reopening a line closed short needs the line's update permission
        (403 before 409) and the reopen rule of the order item intent table:
        a delivered line closed short, not a MADE line, on an order that is
        not canceled."""
        OrderRules.assert_can_update_line(actor, order, item.status, f"Order item #{item.id}")
        rule = _rule(ORDER_ITEM_INTENTS, LifecycleAction.REOPEN)
        if _state_allows(rule, item, order_item_context(order)):
            return
        if item.closed_short_at is None:
            raise OrderItemCannotBeReopenedError(f"Order item #{item.id} is not closed short.")
        if item.line_type == OrderLineType.MADE:
            raise OrderItemCannotBeReopenedError(
                f"Order item #{item.id} is a MADE line, closed short by its lot; it cannot be "
                "reopened here."
            )
        raise OrderItemCannotBeReopenedError(
            f"Order item #{item.id} has status '{item.status.value}' on an order that is "
            f"{order.status.value} and cannot be reopened."
        )

    @staticmethod
    def assert_quantity_editable(order: Order, item: OrderItem) -> None:
        """A line's quantity changes only while it is PENDING, REQUESTED or
        ORDERED, by the edit rule of the order item intent table. A line
        that received pieces is closed short instead, and a canceled line
        keeps its quantity."""
        rule = _rule(ORDER_ITEM_INTENTS, LifecycleAction.EDIT_QUANTITY)
        if _state_allows(rule, item, order_item_context(order)):
            return
        hint = (
            "; close it short instead"
            if item.status in (OrderItemStatus.PARTIALLY_DELIVERED, OrderItemStatus.DELIVERED)
            else ""
        )
        raise OrderItemQuantityNotEditableError(
            f"Order item #{item.id} has status '{item.status.value}'; its quantity can no longer "
            f"be changed{hint}."
        )

    @staticmethod
    def assert_delivery_correctable(
        order: Order,
        item: OrderItem,
        row: OrderItemDelivery,
        already_corrected: float,
        quantity: float,
    ) -> None:
        """Guards a correction of the accepted pieces of one delivery row:
        the line is PARTIALLY_DELIVERED or DELIVERED, not a MADE line, whose
        delivered pieces its lot keeps, and not closed short, on an order
        that is not canceled, by the correction rule of the order item
        intent table; the row is a delivery, not a correction; and
        the pieces taken back are a finite positive number, at most what the
        row accepted less `already_corrected`, the pieces earlier
        corrections of the row took back, and at most the line's delivered
        total, which so never drops below zero."""
        assert_finite(
            quantity,
            error=InvalidDeliveryQuantityError,
            what=f"The corrected quantity of order item #{item.id}",
        )
        if not quantity_gt(quantity, 0.0):
            raise InvalidDeliveryQuantityError(
                f"Order item #{item.id}: a correction must take back at least one piece."
            )
        assert_whole_pieces(
            quantity, what=f"A correction on order item #{item.id}", unit=counted_unit(item)
        )
        rule = _rule(ORDER_ITEM_INTENTS, LifecycleAction.CORRECT_DELIVERY)
        if not _state_allows(rule, item, order_item_context(order)):
            if item.line_type == OrderLineType.MADE:
                raise DeliveryCannotBeCorrectedError(
                    f"Order item #{item.id} is a MADE line; its lot keeps the delivered pieces, "
                    "so its deliveries cannot be corrected here."
                )
            if order.status == OrderStatus.CANCELED:
                raise DeliveryCannotBeCorrectedError(
                    f"Order #{order.id} is canceled, so order item #{item.id} waits for nothing "
                    "more and its deliveries cannot be corrected."
                )
            if item.closed_short_at is not None:
                raise DeliveryCannotBeCorrectedError(
                    f"Order item #{item.id} is closed short; reopen it before correcting its "
                    "deliveries."
                )
            raise DeliveryCannotBeCorrectedError(
                f"Order item #{item.id} has status '{item.status.value}' and takes no correction."
            )
        if row.corrects_delivery_id is not None:
            raise DeliveryCannotBeCorrectedError(
                f"Delivery #{row.id} is itself a correction and cannot be corrected."
            )
        open_on_row = row.quantity - already_corrected
        if quantity_gt(quantity, open_on_row):
            raise DeliveryCannotBeCorrectedError(
                f"Delivery #{row.id} has {max(open_on_row, 0.0):.3f} {item.unit} accepted that "
                f"no correction took back yet; cannot take back {quantity:.3f}."
            )
        if quantity_gt(quantity, item.quantity_delivered):
            raise DeliveryCannotBeCorrectedError(
                f"Order item #{item.id} has {item.quantity_delivered:.3f} {item.unit} "
                f"delivered; cannot take back {quantity:.3f}."
            )

    @staticmethod
    def assert_correction_explained(
        order_item_id: int, reason: str | None, rejection: RejectionAfterReceipt | None
    ) -> None:
        """A correction says why it takes pieces back: a miscount names its
        reason, and a rejection after receipt its classified rejection
        reason, which stands in for one."""
        if rejection is not None:
            if not rejection.reason.strip():
                raise DeliveryRejectionInvalidError(
                    f"Order item #{order_item_id}: a rejection after receipt needs a reason."
                )
            return
        if reason is None or not reason.strip():
            raise DeliveryRejectionInvalidError(
                f"Order item #{order_item_id}: a correction needs a reason."
            )

    @staticmethod
    def assert_no_consumed_demand(item: OrderItem, consumed: Sequence[str]) -> None:
        """Refuses a delivery correction while a demand allocated to the
        line has consumed its pieces: one marked fulfilled by hand, or a raw
        material demand whose lot started. A demand the deliveries fulfil
        derives back from the corrected total. `consumed` names those
        demands."""
        if consumed:
            raise DeliveryCannotBeCorrectedError(
                f"Order item #{item.id} serves demands that consumed its pieces "
                f"({', '.join(consumed)}); its deliveries cannot be corrected."
            )

    @staticmethod
    def assert_can_submit(actor: User, order: Order) -> None:
        """Placing an order needs `write:orders` (403 before 409) and a
        DRAFT or REQUESTED order."""
        assert_has_permission(actor, Permission.WRITE_ORDERS, "submit", "orders")
        if ORDER_INTENTS.check(LifecycleAction.MARK_ORDERED, order, None, actor) is not None:
            raise OrderAlreadySubmittedError(
                f"Order #{order.id} cannot be submitted (status={order.status.value})."
            )

    @staticmethod
    def assert_can_request(actor: User, order: Order) -> None:
        """Sending a price request needs `write:orders` (403 before 409) and
        a DRAFT order."""
        assert_has_permission(actor, Permission.WRITE_ORDERS, "request", "orders")
        if ORDER_INTENTS.check(LifecycleAction.MARK_REQUESTED, order, None, actor) is not None:
            raise OrderAlreadyRequestedError(
                f"Order #{order.id} cannot be requested (status={order.status.value})."
            )

    @staticmethod
    def can_cancel_line(order: Order, item: OrderItem) -> bool:
        """Whether the line can be canceled, by itself or by a cascade over
        its order's lines: it is PENDING, REQUESTED or ORDERED and nothing
        was delivered or lost on it, by the cancel rule of the order item
        intent table."""
        rule = _rule(ORDER_ITEM_INTENTS, LifecycleAction.CANCEL)
        return _state_allows(rule, item, order_item_context(order))

    @staticmethod
    def assert_valid_line_type(item: OrderItem) -> None:
        """Exactly the identity column matching line_type is set, mirroring
        the database check. A MADE line is identified by lot_position_id;
        made_item_id is only a denormalized display field.
        """
        identity_field = _LINE_TYPE_IDENTITY_FIELD.get(item.line_type)
        if identity_field is None:
            raise OrderItemLineTypeMismatchError(
                # Only a value outside OrderLineType gets here, kept as stored.
                f"Order item #{item.id} has unknown line_type {item.line_type!r}."
            )
        if not getattr(item, identity_field):
            raise OrderItemLineTypeMismatchError(
                f"Order item #{item.id} is a {item.line_type.value} line but has no {identity_field}."
            )

        set_others = [
            field for field in _LINE_TYPE_FIELDS if field != identity_field and getattr(item, field)
        ]
        if set_others:
            raise OrderItemLineTypeMismatchError(
                f"Order item #{item.id} is a {item.line_type.value} line but also has "
                f"{', '.join(set_others)} set."
            )
