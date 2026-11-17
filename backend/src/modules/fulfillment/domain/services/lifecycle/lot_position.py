"""Kind, completed count, remaining quantity and status of a lot position,
derived from the order line linked to it and its production orders.

The live line is the linked line unless it is CANCELED, and a live order is
a production order that is not CANCELED. A line closed short leaves the rest
of its position to a later line, so a position can hold several live lines:
the earlier ones are closed short and count with what they hold, and at most
one is still open. A canceled order still counts with
the pieces it completed, because those pieces exist: they stay in the
position's completed count, keep the internal side of its kind, and are not
offered again when the position is planned anew. A canceled lot cancels each
of its positions, whatever they completed.
"""

from src.modules.fulfillment.domain.services.lifecycle.facts import LotPositionFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import PositionLineFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import PositionOrderFacts
from src.modules.fulfillment.domain.services.lifecycle.rules import Derivation
from src.modules.fulfillment.domain.services.lifecycle.rules import DerivationTable
from src.modules.fulfillment.domain.services.lifecycle.rules import otherwise
from src.modules.fulfillment.domain.services.lifecycle.rules import rule
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.platform.domain.services.quantities import quantity_ge
from src.modules.platform.domain.services.quantities import quantity_gt

_RUNNING = (ProductionOrderStatus.IN_PROGRESS, ProductionOrderStatus.PAUSED)
_PLACED_LINE = (OrderItemStatus.ORDERED, OrderItemStatus.PARTIALLY_DELIVERED)


def live_line(facts: LotPositionFacts) -> PositionLineFacts | None:
    """The linked order line, or None when there is none or it is CANCELED."""
    line = facts.line
    if line is None or line.status == OrderItemStatus.CANCELED:
        return None
    return line


def live_lines(facts: LotPositionFacts) -> tuple[PositionLineFacts, ...]:
    """Every live line of the position: the earlier lines closed short and
    the newest one unless it is CANCELED."""
    line = live_line(facts)
    return (*facts.closed_lines, line) if line is not None else facts.closed_lines


def live_orders(facts: LotPositionFacts) -> tuple[PositionOrderFacts, ...]:
    """The production orders of the position that are not CANCELED."""
    return tuple(o for o in facts.orders if o.status != ProductionOrderStatus.CANCELED)


def internal_progress(facts: LotPositionFacts) -> float:
    """Pieces the position's production orders completed, canceled ones
    included."""
    return sum((o.quantity_completed for o in facts.orders), 0.0)


def derive_position_quantity_completed(facts: LotPositionFacts) -> float:
    """The live lines' accepted pieces plus the internal progress."""
    delivered = sum((line.delivered for line in live_lines(facts)), 0.0)
    return delivered + internal_progress(facts)


def position_remaining(facts: LotPositionFacts) -> float:
    """The quantity still free for a new assignment: the position quantity
    minus the live lines' quantities, the live orders' quantities and the
    pieces canceled orders completed, never below zero. A line closed short
    holds what arrived, so the pieces it never brought are free again. A
    disposition can shrink a position below what its orders hold until they
    are cut, and nothing is free then."""
    on_line = sum((line.quantity for line in live_lines(facts)), 0.0)
    on_live_orders = sum((o.quantity for o in live_orders(facts)), 0.0)
    done_by_canceled = sum(
        (o.quantity_completed for o in facts.orders if o.status == ProductionOrderStatus.CANCELED),
        0.0,
    )
    return max(facts.quantity - on_line - on_live_orders - done_by_canceled, 0.0)


def _has_internal_side(facts: LotPositionFacts) -> bool:
    return bool(live_orders(facts)) or quantity_gt(internal_progress(facts), 0.0)


POSITION_KIND = DerivationTable[LotPositionFacts, LotPositionKind](
    key="lot_position_kind",
    rules=(
        rule(
            1,
            "live line, and (a live order or internal progress > 0)",
            LotPositionKind.MIXED,
            lambda f: bool(live_lines(f)) and _has_internal_side(f),
        ),
        rule(2, "live line", LotPositionKind.EXTERNAL, lambda f: bool(live_lines(f))),
        rule(
            3,
            "a live order (not CANCELED) or internal progress > 0",
            LotPositionKind.INTERNAL,
            _has_internal_side,
        ),
    ),
    fallback=otherwise(4, LotPositionKind.UNASSIGNED),
)


def _line_placed_or_order_queued(facts: LotPositionFacts) -> bool:
    line = live_line(facts)
    if line is not None and line.status in _PLACED_LINE:
        return True
    return any(o.status == ProductionOrderStatus.QUEUED for o in live_orders(facts))


POSITION_STATUS = DerivationTable[LotPositionFacts, LotPositionStatus](
    key="lot_position_status",
    rules=(
        rule(1, "the lot has canceled_at", LotPositionStatus.CANCELED, lambda f: f.lot_canceled),
        rule(
            2,
            "quantity > 0 and completed >= quantity",
            LotPositionStatus.COMPLETED,
            lambda f: (
                quantity_gt(f.quantity, 0.0)
                and quantity_ge(derive_position_quantity_completed(f), f.quantity)
            ),
        ),
        rule(
            3,
            "completed > 0",
            LotPositionStatus.PARTIALLY_COMPLETED,
            lambda f: quantity_gt(derive_position_quantity_completed(f), 0.0),
        ),
        rule(
            4,
            "a live order IN_PROGRESS or PAUSED",
            LotPositionStatus.IN_PROGRESS,
            lambda f: any(o.status in _RUNNING for o in live_orders(f)),
        ),
        rule(
            5,
            "live line ORDERED or PARTIALLY_DELIVERED, or a live order QUEUED",
            LotPositionStatus.ORDERED_OR_QUEUED,
            _line_placed_or_order_queued,
        ),
    ),
    fallback=otherwise(6, LotPositionStatus.PENDING),
)


def derive_position_kind(facts: LotPositionFacts) -> Derivation[LotPositionKind]:
    return POSITION_KIND.derive(facts)


def derive_position_status(facts: LotPositionFacts) -> Derivation[LotPositionStatus]:
    return POSITION_STATUS.derive(facts)
