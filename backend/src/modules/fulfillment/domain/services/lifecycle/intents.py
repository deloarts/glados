"""Which user actions a lifecycle aggregate accepts, as one intent table per
aggregate: order item, order, production order, lot position, lot and demand.
The rule and table types are the generic ones of
domain/services/intent_table.py.

The actor guards here are the rules an action adds on top of its base
permission: cancelling or force-completing a lot needs manage:lots, since
both cascade into other users' orders, and cancelling an order or changing
its lines (marking, cancelling, closing short, editing the quantity, moving
or removing one) past REQUESTED needs manage:orders, since the supplier
already holds the order. The base permission of each action, such as
write:orders or receive:deliveries, is checked by the use case.

Each rule carries its condition, permission and effect as text next to the
guards that enforce them, so a listing of the rules shows what the code runs.
Quantity checks that depend on the request, such as a new quantity or a
delivery amount, belong to the use case and appear only in the effect text.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.fulfillment.domain.value_objects.interruption_reason import InterruptionReason
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.source_approval_status import SourceApprovalStatus
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.intent_table import Check
from src.modules.platform.domain.services.intent_table import HasStatus
from src.modules.platform.domain.services.intent_table import IntentRule
from src.modules.platform.domain.services.intent_table import IntentTable
from src.modules.platform.domain.services.quantities import is_zero_quantity
from src.modules.platform.domain.services.quantities import quantity_gt
from src.modules.platform.domain.value_objects.permission import Permission
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction

# ── Subjects ─────────────────────────────────────────────────────────────


class OrderSubject(HasStatus, Protocol):
    """An order: its status and whether someone canceled it, which an order
    that reads canceled only because every line is canceled was not."""

    @property
    def canceled_at(self) -> datetime | None: ...


class OrderItemSubject(HasStatus, Protocol):
    @property
    def line_type(self) -> str: ...

    @property
    def closed_short_at(self) -> datetime | None: ...

    @property
    def quantity_delivered(self) -> float: ...

    @property
    def quantity_rejected(self) -> float: ...

    @property
    def quantity_rejected_lost(self) -> float: ...


class LotPositionSubject(HasStatus, Protocol):
    @property
    def kind(self) -> str: ...


class LotSubject(HasStatus, Protocol):
    @property
    def creator_id(self) -> int: ...


def _values(*members: Enum) -> tuple[str, ...]:
    return tuple(str(m.value) for m in members)


# ── Order item ───────────────────────────────────────────────────────────


@dataclass(frozen=True, kw_only=True)
class OrderItemContext:
    """`order_status` is the status of the line's order. `lot_canceled` says
    whether a MADE line's lot is canceled and is False for other lines.
    `target_order_canceled` says whether someone canceled the order a move
    would take the line to, which records its canceled_at; an order that
    reads canceled only because every line is canceled takes the line, as
    it takes a new one. It is False when no move is being checked."""

    order_status: OrderStatus
    lot_canceled: bool = False
    target_order_canceled: bool = False


_ORDER_OPEN_FOR_EDITS = (OrderStatus.DRAFT, OrderStatus.REQUESTED)
_LINE_NOT_WITH_THE_SUPPLIER = (OrderItemStatus.PENDING, OrderItemStatus.REQUESTED)


def may_change_order(actor: User, order_status: str) -> bool:
    """Whether the actor may change an order itself: anyone with the base
    permission while the order is DRAFT or REQUESTED, and once any of it was
    ordered only a manager of orders, since the supplier already holds it.
    OrderRules.assert_can_update and the order intent table decide by this."""
    return order_status in _ORDER_OPEN_FOR_EDITS or actor.has_permission(Permission.MANAGE_ORDERS)


def may_change_line(actor: User, order_status: str, line_status: str) -> bool:
    """Whether the actor may change one line of an order. A partially ordered
    order keeps the lines the supplier does not hold yet open to the base
    permission, so the buyer can finish ordering it, while its ordered lines
    need a manager of orders like any line of a submitted order. A new line
    counts as PENDING. OrderRules.assert_can_update_line and the order item
    intent table decide by this."""
    if may_change_order(actor, order_status):
        return True
    return (
        order_status == OrderStatus.PARTIALLY_ORDERED and line_status in _LINE_NOT_WITH_THE_SUPPLIER
    )


_ORDER_CHANGE_PERMISSION = "manage:orders once past REQUESTED"
_LINE_CHANGE_PERMISSION = "manage:orders once the order or the line is past REQUESTED"


def _may_change_lines(actor: User, item: OrderItemSubject, context: OrderItemContext) -> bool:
    return may_change_line(actor, context.order_status.value, item.status)


def _on_a_live_order(_item: OrderItemSubject, context: OrderItemContext) -> bool:
    return context.order_status != OrderStatus.CANCELED


def _lot_live_for_made(item: OrderItemSubject, context: OrderItemContext) -> bool:
    return not (item.line_type == OrderLineType.MADE and context.lot_canceled)


def _not_made(item: OrderItemSubject, _context: OrderItemContext) -> bool:
    return item.line_type != OrderLineType.MADE


def _not_closed_short(item: OrderItemSubject, _context: OrderItemContext) -> bool:
    return item.closed_short_at is None


def _closed_short(item: OrderItemSubject, _context: OrderItemContext) -> bool:
    return item.closed_short_at is not None


_ON_A_LIVE_ORDER = Check[OrderItemSubject, OrderItemContext]("order not CANCELED", _on_a_live_order)
_NOT_MADE = Check[OrderItemSubject, OrderItemContext]("not a MADE line", _not_made)


def _anything_settled(item: OrderItemSubject, _context: OrderItemContext) -> bool:
    return quantity_gt(item.quantity_delivered + item.quantity_rejected_lost, 0.0)


def _nothing_settled(item: OrderItemSubject, _context: OrderItemContext) -> bool:
    return is_zero_quantity(item.quantity_delivered) and is_zero_quantity(
        item.quantity_rejected_lost
    )


def _untouched(item: OrderItemSubject, _context: OrderItemContext) -> bool:
    return is_zero_quantity(item.quantity_delivered) and is_zero_quantity(item.quantity_rejected)


def _target_live(_item: OrderItemSubject, context: OrderItemContext) -> bool:
    return not context.target_order_canceled


_ITEM_OPEN = _values(OrderItemStatus.PENDING, OrderItemStatus.REQUESTED, OrderItemStatus.ORDERED)

ORDER_ITEM_INTENTS = IntentTable[OrderItemSubject, OrderItemContext](
    key="order_item",
    rules=(
        IntentRule(
            action=LifecycleAction.MARK_REQUESTED,
            allowed_from=_values(OrderItemStatus.PENDING),
            permission=_LINE_CHANGE_PERMISSION,
            needs=Permission.MANAGE_ORDERS,
            permitted=_may_change_lines,
            effect="requested_at",
        ),
        IntentRule(
            action=LifecycleAction.MARK_ORDERED,
            allowed_from=_values(OrderItemStatus.PENDING, OrderItemStatus.REQUESTED),
            permission=_LINE_CHANGE_PERMISSION,
            needs=Permission.MANAGE_ORDERS,
            permitted=_may_change_lines,
            effect="ordered_date",
        ),
        IntentRule(
            action=LifecycleAction.MARK_READY_FOR_PICKUP,
            allowed_from=_values(OrderItemStatus.ORDERED, OrderItemStatus.PARTIALLY_DELIVERED),
            condition="order not CANCELED",
            guard=_on_a_live_order,
            # A ready line is always ordered, so changing it is a change of a
            # submitted line, which needs manage:orders like every other one.
            permission=_LINE_CHANGE_PERMISSION,
            needs=Permission.MANAGE_ORDERS,
            permitted=_may_change_lines,
            effect="ready_for_pickup_date, never in the future",
        ),
        IntentRule(
            action=LifecycleAction.DELIVER,
            allowed_from=_values(OrderItemStatus.ORDERED, OrderItemStatus.PARTIALLY_DELIVERED),
            checks=(_ON_A_LIVE_ORDER, Check("lot not canceled for MADE lines", _lot_live_for_made)),
            effect="delivery row, totals",
        ),
        IntentRule(
            action=LifecycleAction.CORRECT_DELIVERY,
            allowed_from=_values(OrderItemStatus.PARTIALLY_DELIVERED, OrderItemStatus.DELIVERED),
            # A MADE line's pieces belong to its lot, whose own side a
            # correction cannot reach. A line of a canceled order, or one
            # closed short, waits for nothing more, so a correction would
            # leave it open for good.
            checks=(_NOT_MADE, Check("not closed short", _not_closed_short), _ON_A_LIVE_ORDER),
            effect=(
                "negative delivery row with reason, or with the pieces rejected after receipt, "
                "totals never below zero or below what demands have consumed from stock"
            ),
        ),
        IntentRule(
            action=LifecycleAction.CLOSE_SHORT,
            allowed_from=_values(OrderItemStatus.ORDERED, OrderItemStatus.PARTIALLY_DELIVERED),
            condition="delivered + lost > 0",
            guard=_anything_settled,
            permission=_LINE_CHANGE_PERMISSION,
            needs=Permission.MANAGE_ORDERS,
            permitted=_may_change_lines,
            effect="quantity := delivered + lost, closed_short_at",
        ),
        IntentRule(
            action=LifecycleAction.REOPEN,
            allowed_from=_values(OrderItemStatus.DELIVERED),
            # A MADE line was closed by its lot and is not reopened here.
            checks=(Check("closed short", _closed_short), _NOT_MADE, _ON_A_LIVE_ORDER),
            permission=_LINE_CHANGE_PERMISSION,
            needs=Permission.MANAGE_ORDERS,
            permitted=_may_change_lines,
            effect="quantity := quantity before the close, closed_short_at cleared",
        ),
        IntentRule(
            action=LifecycleAction.CANCEL,
            allowed_from=_ITEM_OPEN,
            condition="no delivery and no lost pieces",
            guard=_nothing_settled,
            permission=_LINE_CHANGE_PERMISSION,
            needs=Permission.MANAGE_ORDERS,
            permitted=_may_change_lines,
            effect="canceled_at, allocations deleted",
        ),
        IntentRule(
            action=LifecycleAction.EDIT_QUANTITY,
            allowed_from=_ITEM_OPEN,
            permission=_LINE_CHANGE_PERMISSION,
            needs=Permission.MANAGE_ORDERS,
            permitted=_may_change_lines,
            effect="refused below delivered + lost or below the allocated sum of both families",
        ),
        IntentRule(
            action=LifecycleAction.EDIT,
            allowed_from=_values(*(s for s in OrderItemStatus if s != OrderItemStatus.CANCELED)),
            permission=_LINE_CHANGE_PERMISSION,
            needs=Permission.MANAGE_ORDERS,
            permitted=_may_change_lines,
            effect=(
                "note, dates, price and storage place; quantity by edit_quantity, and the "
                "unit, item and project only until goods arrived"
            ),
        ),
        IntentRule(
            action=LifecycleAction.MOVE,
            allowed_from=_ITEM_OPEN,
            checks=(
                Check("no deliveries or rejections", _untouched),
                Check("target order without canceled_at", _target_live),
            ),
            permission=_LINE_CHANGE_PERMISSION,
            needs=Permission.MANAGE_ORDERS,
            permitted=_may_change_lines,
            effect="order id",
        ),
        IntentRule(
            action=LifecycleAction.REMOVE,
            allowed_from=_values(OrderItemStatus.PENDING, OrderItemStatus.REQUESTED),
            permission=_LINE_CHANGE_PERMISSION,
            needs=Permission.MANAGE_ORDERS,
            permitted=_may_change_lines,
            effect="row deleted, allocations deleted",
        ),
    ),
)


# ── Order ────────────────────────────────────────────────────────────────


def _may_change_order(actor: User, order: OrderSubject, _context: None) -> bool:
    return may_change_order(actor, order.status)


def _may_add_line(actor: User, order: OrderSubject, _context: None) -> bool:
    # A new line counts as PENDING (may_change_line).
    return may_change_line(actor, order.status, OrderItemStatus.PENDING.value)


def _not_canceled_by_a_user(order: OrderSubject, _context: None) -> bool:
    return order.canceled_at is None


_NOT_CANCELED_BY_A_USER = Check[OrderSubject, None](
    "nobody canceled the order", _not_canceled_by_a_user
)


ORDER_INTENTS = IntentTable[OrderSubject, None](
    key="order",
    rules=(
        IntentRule(
            action=LifecycleAction.MARK_REQUESTED,
            allowed_from=_values(OrderStatus.DRAFT),
            effect="stamps requested_at and requests PENDING lines",
        ),
        IntentRule(
            action=LifecycleAction.MARK_ORDERED,
            allowed_from=_values(
                OrderStatus.DRAFT, OrderStatus.REQUESTED, OrderStatus.PARTIALLY_ORDERED
            ),
            effect="stamps ordered_date and marks PENDING and REQUESTED lines ordered",
        ),
        IntentRule(
            action=LifecycleAction.CANCEL,
            allowed_from=_values(
                OrderStatus.DRAFT,
                OrderStatus.REQUESTED,
                OrderStatus.PARTIALLY_ORDERED,
                OrderStatus.ORDERED,
                OrderStatus.PARTIALLY_DELIVERED,
            ),
            permission=_ORDER_CHANGE_PERMISSION,
            needs=Permission.MANAGE_ORDERS,
            permitted=_may_change_order,
            effect=(
                "canceled_at; delivered lines keep their status and allocations, partially "
                "delivered lines are closed short, undelivered lines are canceled and their "
                "allocations released"
            ),
        ),
        IntentRule(
            action=LifecycleAction.DELIVER,
            allowed_from=_values(
                OrderStatus.PARTIALLY_ORDERED,
                OrderStatus.ORDERED,
                OrderStatus.PARTIALLY_DELIVERED,
            ),
            effect="one transaction over the deliverable lines",
        ),
        IntentRule(
            action=LifecycleAction.EDIT,
            allowed_from=None,
            checks=(_NOT_CANCELED_BY_A_USER,),
            permission=_ORDER_CHANGE_PERMISSION,
            needs=Permission.MANAGE_ORDERS,
            permitted=_may_change_order,
            effect="supplier, dates, notes and the order's other header fields",
        ),
        IntentRule(
            action=LifecycleAction.ADD_ITEM,
            allowed_from=None,
            # An order that reads canceled only because every line is
            # canceled takes a new line and derives from it again.
            checks=(_NOT_CANCELED_BY_A_USER,),
            permission=_LINE_CHANGE_PERMISSION,
            needs=Permission.MANAGE_ORDERS,
            permitted=_may_add_line,
            effect="a new PENDING line",
        ),
    ),
)


# ── Production order ─────────────────────────────────────────────────────


@dataclass(frozen=True, kw_only=True)
class ProductionOrderContext:
    """`lot_held` and `lot_terminal` describe the order's lot.
    `machine_resolvable` says whether start can settle on a machine, and
    `input_available` whether the predecessor or the raw material made
    pieces available. `open_interruption` is the reason of the order's open
    interruption, None when there is none."""

    lot_held: bool
    lot_terminal: bool
    machine_resolvable: bool
    input_available: bool
    open_interruption: InterruptionReason | None


_ProductionOrderCheck = Check[HasStatus, ProductionOrderContext]

LOT_NOT_HELD = _ProductionOrderCheck("lot not held", lambda _o, c: not c.lot_held)
_LOT_NOT_TERMINAL_FOR_ORDER = _ProductionOrderCheck(
    "lot not terminal", lambda _o, c: not c.lot_terminal
)
_INPUT_AVAILABLE = _ProductionOrderCheck(
    "upstream input available", lambda _o, c: c.input_available
)


PRODUCTION_ORDER_INTENTS = IntentTable[HasStatus, ProductionOrderContext](
    key="production_order",
    rules=(
        IntentRule(
            action=LifecycleAction.START,
            allowed_from=_values(ProductionOrderStatus.QUEUED),
            checks=(
                LOT_NOT_HELD,
                _LOT_NOT_TERMINAL_FOR_ORDER,
                Check("machine resolvable", lambda _o, c: c.machine_resolvable),
                _INPUT_AVAILABLE,
            ),
            effect="actual_start, operator",
        ),
        IntentRule(
            action=LifecycleAction.RESUME,
            allowed_from=_values(ProductionOrderStatus.PAUSED),
            # Only the operator's own pause is resumed here; an interruption of
            # a lot hold ends when the lot resumes. Like a start, a resume
            # needs input from upstream, or the machine would only sit idle.
            checks=(
                Check(
                    "an open manual interruption",
                    lambda _o, c: c.open_interruption == InterruptionReason.MANUAL,
                ),
                LOT_NOT_HELD,
                _INPUT_AVAILABLE,
            ),
            effect="closes the manual interruption",
        ),
        IntentRule(
            action=LifecycleAction.PAUSE,
            allowed_from=_values(ProductionOrderStatus.IN_PROGRESS),
            effect="opens a manual interruption",
        ),
        IntentRule(
            action=LifecycleAction.CANCEL,
            allowed_from=_values(
                ProductionOrderStatus.QUEUED,
                ProductionOrderStatus.IN_PROGRESS,
                ProductionOrderStatus.PAUSED,
            ),
            effect="canceled_at, closes any open interruption, keeps planned_end_at_start",
        ),
        IntentRule(
            action=LifecycleAction.RECORD_COMPLETION,
            allowed_from=_values(ProductionOrderStatus.IN_PROGRESS),
            checks=(LOT_NOT_HELD,),
            effect=(
                "completion row, processed + quantity <= order quantity; rejects only on an "
                "inspection position"
            ),
        ),
        # manage:production_orders is the reversal's base permission, which the use
        # case checks, so a user without it is offered the action and sees it
        # disabled.
        IntentRule(
            action=LifecycleAction.REVERSE_COMPLETION,
            allowed_from=_values(
                ProductionOrderStatus.IN_PROGRESS,
                ProductionOrderStatus.PAUSED,
                ProductionOrderStatus.COMPLETED,
            ),
            checks=(LOT_NOT_HELD, _LOT_NOT_TERMINAL_FOR_ORDER),
            condition=(
                "the completion rejected nothing, is not reversed yet and the next position "
                "has not used its pieces"
            ),
            effect="reversal row of the completion's pieces, a reason; completed count lowered",
        ),
        IntentRule(
            action=LifecycleAction.SCRAP,
            allowed_from=_values(ProductionOrderStatus.IN_PROGRESS),
            checks=(LOT_NOT_HELD,),
            effect="completion row with scrap, disposition",
        ),
        IntentRule(
            action=LifecycleAction.SPLIT,
            allowed_from=_values(ProductionOrderStatus.QUEUED),
            effect=(
                "new rows on the same machine copy machine_pool_id; lock scope "
                "(machine_id, machine_pool_id)"
            ),
        ),
        IntentRule(
            action=LifecycleAction.MERGE,
            allowed_from=_values(ProductionOrderStatus.QUEUED),
            effect="orders on the same machine and the same pool become one",
        ),
    ),
)


# ── Lot position ─────────────────────────────────────────────────────────


@dataclass(frozen=True, kw_only=True)
class LotPositionContext:
    """`live_line_status` is the status of the position's newest live order
    line, None without one, and `live_line_closed_short` says whether that
    line was closed short, which leaves the rest of the position to a new
    line. `remaining` is the position quantity still free for an assignment
    (lot_position.position_remaining). `lot_terminal` says whether the lot
    is COMPLETED, CANCELED or SCRAPPED."""

    live_line_status: OrderItemStatus | None
    remaining: float
    lot_terminal: bool
    live_line_closed_short: bool = False


_PositionCheck = Check[LotPositionSubject, LotPositionContext]

_EXTERNAL_KINDS = _values(LotPositionKind.EXTERNAL, LotPositionKind.MIXED)
_LOT_LIVE = _PositionCheck("lot not terminal", lambda _p, c: not c.lot_terminal)
_REMAINING = _PositionCheck("remaining > 0", lambda _p, c: quantity_gt(c.remaining, 0.0))


def _provisionable(position: LotPositionSubject, _context: LotPositionContext) -> bool:
    return position.kind in _EXTERNAL_KINDS


def _no_open_line(_position: LotPositionSubject, context: LotPositionContext) -> bool:
    """No live line, or only lines closed short, whose rest a new line may
    take."""
    return context.live_line_status is None or context.live_line_closed_short


def _external_assignable_kind(position: LotPositionSubject, context: LotPositionContext) -> bool:
    return (
        position.kind in _values(LotPositionKind.UNASSIGNED, LotPositionKind.INTERNAL)
        or context.live_line_closed_short
    )


LOT_POSITION_INTENTS = IntentTable[LotPositionSubject, LotPositionContext](
    key="lot_position",
    rules=(
        IntentRule(
            action=LifecycleAction.ASSIGN_EXTERNAL,
            allowed_from=None,
            checks=(
                _LOT_LIVE,
                Check("no live line, or only lines closed short", _no_open_line),
                Check(
                    "kind UNASSIGNED or INTERNAL, or its line closed short",
                    _external_assignable_kind,
                ),
                _REMAINING,
            ),
            effect=(
                "a line for at most the remaining quantity; a line closed short stays beside "
                "the new one"
            ),
        ),
        IntentRule(
            action=LifecycleAction.UNASSIGN_EXTERNAL,
            allowed_from=None,
            checks=(
                Check("kind EXTERNAL or MIXED", lambda p, _c: p.kind in _EXTERNAL_KINDS),
                Check(
                    "live line PENDING or REQUESTED",
                    lambda _p, c: (
                        c.live_line_status in (OrderItemStatus.PENDING, OrderItemStatus.REQUESTED)
                    ),
                ),
            ),
            effect="deletes the line",
        ),
        IntentRule(
            action=LifecycleAction.ASSIGN_INTERNAL,
            allowed_from=None,
            checks=(_LOT_LIVE, _REMAINING),
            effect=(
                "production orders for at most the remaining quantity; the line side of an "
                "EXTERNAL position stays"
            ),
        ),
        IntentRule(
            action=LifecycleAction.RECORD_PROVISION,
            allowed_from=None,
            checks=(
                _LOT_LIVE,
                Check("kind EXTERNAL or MIXED", _provisionable),
            ),
            effect="provision row within the available input",
        ),
    ),
)


# ── Lot ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True, kw_only=True)
class LotContext:
    """`produced` is the lot's completed count, its last position's.
    `has_good_pieces` says whether any position completed a good piece,
    finished or still in progress. `source_approval_status` is the lot's
    stored SourceApprovalStatus, which the source decisions start from."""

    produced: float
    has_good_pieces: bool = False
    source_approval_status: str = SourceApprovalStatus.NOT_REQUIRED


def _may_force_lot(actor: User, _lot: LotSubject, _context: LotContext) -> bool:
    return actor.has_permission(Permission.MANAGE_LOTS)


def _nothing_good_yet(_lot: LotSubject, context: LotContext) -> bool:
    """A cancel would throw away good pieces, which force-complete keeps."""
    return not context.has_good_pieces


def _made_good_pieces(_lot: LotSubject, context: LotContext) -> bool:
    """Force-complete keeps what the lot made: the last position's pieces as
    the lot's quantity, and good pieces upstream are recorded as dropped. A
    lot whose last step cannot be done ends that way too, rather than only
    through a cancel that would throw the good pieces away."""
    return context.has_good_pieces or quantity_gt(context.produced, 0.0)


_LOT_NOT_TERMINAL = _values(
    LotStatus.DRAFT,
    LotStatus.PARTIALLY_PLANNED,
    LotStatus.PLANNED,
    LotStatus.IN_PROGRESS,
    LotStatus.ON_HOLD,
)

_SOURCE_DECIDABLE = Check[LotSubject, LotContext](
    "material source pending or rejected",
    lambda _lot, c: (
        c.source_approval_status in (SourceApprovalStatus.PENDING, SourceApprovalStatus.REJECTED)
    ),
)
_SOURCE_PENDING = Check[LotSubject, LotContext](
    "material source pending",
    lambda _lot, c: c.source_approval_status == SourceApprovalStatus.PENDING,
)

LOT_INTENTS = IntentTable[LotSubject, LotContext](
    key="lot",
    rules=(
        IntentRule(
            action=LifecycleAction.HOLD,
            allowed_from=_values(
                LotStatus.PARTIALLY_PLANNED, LotStatus.PLANNED, LotStatus.IN_PROGRESS
            ),
            effect="held_at; opens lot_hold interruptions on IN_PROGRESS orders",
        ),
        IntentRule(
            action=LifecycleAction.RESUME,
            allowed_from=_values(LotStatus.ON_HOLD),
            effect="clears held_at; closes lot_hold interruptions only",
        ),
        IntentRule(
            action=LifecycleAction.CANCEL,
            allowed_from=_LOT_NOT_TERMINAL,
            condition="no position completed a good piece",
            guard=_nothing_good_yet,
            permission="manage:lots",
            needs=Permission.MANAGE_LOTS,
            permitted=_may_force_lot,
            effect=(
                "canceled_at; cancels live orders; cancels unordered lines, keeps ordered "
                "ones open, short-closes partially delivered MADE lines; deletes made "
                "allocations; settles the input demand"
            ),
        ),
        IntentRule(
            action=LifecycleAction.FORCE_COMPLETE,
            allowed_from=_LOT_NOT_TERMINAL,
            condition="a position completed a good piece",
            guard=_made_good_pieces,
            permission="manage:lots",
            needs=Permission.MANAGE_LOTS,
            permitted=_may_force_lot,
            effect=(
                "closes the lot short at its produced quantity and its live work with it, "
                "settles the input demand, force_completed_at"
            ),
        ),
        IntentRule(
            action=LifecycleAction.SCRAP,
            # A held lot is resumed before pieces are scrapped from it, as its
            # production orders refuse a scrap until then.
            allowed_from=_values(
                LotStatus.DRAFT,
                LotStatus.PARTIALLY_PLANNED,
                LotStatus.PLANNED,
                LotStatus.IN_PROGRESS,
            ),
            effect=(
                "disposition: shrinks the position, later positions and their live work; a "
                "zero lot cancels its live children and its input demand. A goods-receipt LOST "
                "disposition records what arrived, is not this action and stays allowed on a "
                "held lot"
            ),
        ),
        IntentRule(
            action=LifecycleAction.EDIT_STRUCTURE,
            allowed_from=_LOT_NOT_TERMINAL,
            effect=(
                "append, add or delete a step, regroup or replace, on positions that are "
                "UNASSIGNED with no progress"
            ),
        ),
        IntentRule(
            action=LifecycleAction.REORDER_POSITIONS,
            allowed_from=_LOT_NOT_TERMINAL,
            effect="sequences, when every moved position is UNASSIGNED with completed = 0",
        ),
        IntentRule(
            action=LifecycleAction.EDIT_QUANTITY,
            allowed_from=_values(LotStatus.DRAFT),
            effect=(
                "positions and an open raw material demand follow; new quantity >= allocated sum"
            ),
        ),
        # The source decisions need manage:lots and the switch write:lots,
        # their base permissions, which the use cases check.
        IntentRule(
            action=LifecycleAction.APPROVE_SOURCE,
            allowed_from=_LOT_NOT_TERMINAL,
            checks=(_SOURCE_DECIDABLE,),
            condition="the project is active and the source item demandable",
            effect="source_approval_status approved; creates the raw material demand",
        ),
        IntentRule(
            action=LifecycleAction.REJECT_SOURCE,
            allowed_from=_LOT_NOT_TERMINAL,
            checks=(_SOURCE_PENDING,),
            effect="source_approval_status rejected with a reason; no demand",
        ),
        IntentRule(
            action=LifecycleAction.SWITCH_SOURCE,
            allowed_from=_LOT_NOT_TERMINAL,
            condition="the raw material demand, if any, is not fulfilled",
            effect=(
                "replaces the raw material demand, keeping what already arrived; the new source "
                "is pending approval or gets a demand for what is missing"
            ),
        ),
    ),
)


# ── Demand (bought, made and source share the status values) ─────────────


@dataclass(frozen=True, kw_only=True)
class DemandContext:
    """`has_allocations` says whether any allocation of either source
    exists. `lot_started` says whether the lot a raw material demand feeds
    has started production; it is False for bought and made demands."""

    has_allocations: bool
    lot_started: bool = False


def _without_allocations(_demand: HasStatus, context: DemandContext) -> bool:
    return not context.has_allocations


# A started lot holds or consumes its material, so canceling its raw
# material demand would strand it waiting on material and drop what it
# already holds; its source is switched or the lot force-completed instead.
_LOT_NOT_STARTED = Check[HasStatus, DemandContext](
    "lot not started", lambda _demand, c: not c.lot_started
)


_DEMAND_LIVE = _values(
    BoughtItemDemandStatus.OPEN,
    BoughtItemDemandStatus.ALLOCATED,
    BoughtItemDemandStatus.ORDERED,
)

DEMAND_INTENTS = IntentTable[HasStatus, DemandContext](
    key="demand",
    rules=(
        IntentRule(
            action=LifecycleAction.CANCEL,
            allowed_from=_DEMAND_LIVE,
            checks=(_LOT_NOT_STARTED,),
            effect=(
                "canceled_at; allocations deleted; made: lots released or canceled through "
                "the cancel impact flow; source: its lot canceled too or left unlinked, as the "
                "caller chooses"
            ),
        ),
        IntentRule(
            action=LifecycleAction.FULFIL,
            allowed_from=_DEMAND_LIVE,
            effect="fulfilled_manually_at",
        ),
        IntentRule(
            action=LifecycleAction.ALLOCATE,
            allowed_from=_DEMAND_LIVE,
            effect=(
                "create, update or delete an allocation, fulfil from stock, auto-allocate; "
                "demand quantity >= allocated + stock; line capacity across both families"
            ),
        ),
        IntentRule(
            action=LifecycleAction.EDIT_QUANTITY,
            allowed_from=_DEMAND_LIVE,
            effect="quantity, never below allocated + stock",
        ),
        IntentRule(
            action=LifecycleAction.REMOVE,
            allowed_from=None,
            condition="no allocations",
            guard=_without_allocations,
            effect="row deleted",
        ),
    ),
)
