"""Pure domain logic for the ProductionLot aggregate: quantity propagation
across positions, position grouping, closing a lot short and the cuts that
follow, lot-backed demand coverage, and permission and lifecycle guards. The
lot's and its positions' statuses are derived in src/domain/services/lifecycle/.
No I/O."""

import math
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from itertools import pairwise
from typing import Literal

from src.modules.catalogue.domain.policies.material_source_rules import (
    assert_at_most_one_material_source as _assert_at_most_one_material_source,
)
from src.modules.catalogue.domain.policies.step_role_rules import assert_role_matches_methods
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.errors import AllocationOverflowError
from src.modules.fulfillment.domain.errors import LotDemandMadeItemMismatchError
from src.modules.fulfillment.domain.errors import LotDemandProjectMismatchError
from src.modules.fulfillment.domain.errors import LotInvalidStatusTransitionError
from src.modules.fulfillment.domain.errors import LotNotScrappableError
from src.modules.fulfillment.domain.errors import LotPositionAlreadyAssignedError
from src.modules.fulfillment.domain.errors import LotPositionGroupingInvalidError
from src.modules.fulfillment.domain.errors import LotPositionOverflowError
from src.modules.fulfillment.domain.errors import LotStructureLockedError
from src.modules.fulfillment.domain.errors import ScrapQuantityExceedsAvailableError
from src.modules.fulfillment.domain.errors import SourceApprovalNotPendingError
from src.modules.fulfillment.domain.services.allocation_coverage import CoverageInfo
from src.modules.fulfillment.domain.services.lifecycle.demand import arrived_pieces
from src.modules.fulfillment.domain.services.lifecycle.demand import is_placed
from src.modules.fulfillment.domain.services.lifecycle.facts import AllocationFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import CoveringLotFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import LotPositionFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import PositionLineFacts
from src.modules.fulfillment.domain.services.lifecycle.facts import PositionOrderFacts
from src.modules.fulfillment.domain.services.lifecycle.intents import LOT_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import LOT_POSITION_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import ORDER_ITEM_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import LotContext
from src.modules.fulfillment.domain.services.lifecycle.intents import LotPositionContext
from src.modules.fulfillment.domain.services.lifecycle.intents import OrderItemContext
from src.modules.fulfillment.domain.services.lifecycle.lot_position import position_remaining
from src.modules.fulfillment.domain.value_objects.lot_status import TERMINAL_LOT_STATUSES
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import DomainError
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.services.grouping_rules import validate_contiguous_grouping
from src.modules.platform.domain.services.intent_table import RefusalKind
from src.modules.platform.domain.services.quantities import assert_whole_pieces
from src.modules.platform.domain.services.quantities import counts_whole_units
from src.modules.platform.domain.services.quantities import is_zero_quantity
from src.modules.platform.domain.services.quantities import quantity_eq
from src.modules.platform.domain.services.quantities import quantity_gt
from src.modules.platform.domain.value_objects.permission import Permission
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction

# Decimal places of split_quantity_by_largest_remainder.
_SPLIT_DP = 6
_SPLIT_SLACK = 1e-6

# ── Quantity propagation ────────────────────────────────────────────────


def available_input(
    positions: list[LotPosition],
    lot_quantity: float,
    target_sequence: int,
    raw_material_arrived: float | None = None,
) -> float:
    """Position 1's input is its own quantity, capped by raw_material_arrived
    when that is given, so the raw-material demand acts as a virtual
    predecessor. Its quantity is the lot's until pieces are removed further
    down the chain: the lot then shrinks while position 1 keeps its
    quantity, because its output also fed the removed pieces. lot_quantity
    stands in when position 1 is not among `positions`. None means
    unconstrained and is only right for rework lots and EXTERNAL position 1,
    where the supplier sources the material; a sourced lot passes 0.0 before
    any demand is linked. Later positions get the predecessor's
    quantity_completed."""
    if target_sequence <= 1:
        first = next((p for p in positions if p.sequence == target_sequence), None)
        own_quantity = first.quantity if first is not None else lot_quantity
        if raw_material_arrived is not None:
            return min(own_quantity, raw_material_arrived)
        return own_quantity
    predecessor = next((p for p in positions if p.sequence == target_sequence - 1), None)
    return predecessor.quantity_completed if predecessor else 0.0


def pieces_processed_at(position: LotPosition) -> float:
    """The pieces a position has processed: everything its production orders
    booked, accepted, rejected and scrapped alike, with reversals netted,
    and the supplier's share, the pieces handed to it or, when more, those
    its live lines delivered, never less than its stored completed count,
    whose accepted pieces are among them. A rejected or scrapped piece used
    up its input as much as an accepted one, and so did a piece handed to
    the supplier, so a MIXED position's two shares never draw on the same
    input."""
    booked = sum((order.pieces_processed for order in position.production_orders), 0.0)
    delivered = (position.order_item_quantity_delivered or 0.0) + position.closed_lines_delivered
    supplier = max(delivered, position.provisioned_quantity)
    return max(booked + supplier, position.quantity_completed)


def open_input(
    position: LotPosition,
    positions: list[LotPosition],
    lot_quantity: float,
    raw_material_arrived: float | None = None,
) -> float:
    """The pieces that reached the position and it has not processed yet,
    never below zero. A later position draws on its predecessor's completed
    count. Position 1 draws on its own quantity, which a disposition there
    already shrank, less what it completed; with raw_material_arrived, also
    on the arrived material less everything it processed (available_input
    says when that is given)."""
    processed = pieces_processed_at(position)
    if position.sequence <= 1:
        own = available_input(positions, lot_quantity, position.sequence) - (
            position.quantity_completed
        )
        if raw_material_arrived is not None:
            own = min(own, raw_material_arrived - processed)
        return max(own, 0.0)
    return max(available_input(positions, lot_quantity, position.sequence) - processed, 0.0)


def assert_completion_within_available(
    position: LotPosition,
    positions: list[LotPosition],
    lot_quantity: float,
    delta: float,
    raw_material_arrived: float | None = None,
) -> None:
    """A position cannot process more pieces than reached it: `delta`, the
    pieces a booking processes, accepted and rejected together, must fit
    its open input."""
    available = open_input(position, positions, lot_quantity, raw_material_arrived)
    if quantity_gt(delta, available):
        source = "its source material" if position.sequence == 1 else "its predecessor"
        raise LotPositionOverflowError(
            f"Position #{position.id} (sequence {position.sequence}) has "
            f"{available:.3f} piece(s) from {source} left to process; cannot record "
            f"{delta:.3f} (already processed {pieces_processed_at(position):.3f})."
        )


def assert_position_has_available_input(
    position: LotPosition,
    positions: list[LotPosition],
    lot_quantity: float,
    raw_material_arrived: float | None = None,
) -> None:
    """Blocks starting or resuming work when the upstream has made nothing
    available that this position has not processed yet, since the machine
    would only sit idle."""
    available = open_input(position, positions, lot_quantity, raw_material_arrived)
    if not quantity_gt(available, 0.0):
        upstream = (
            "its source material hasn't arrived yet"
            if position.sequence == 1
            else "its predecessor step hasn't made anything available yet"
        )
        raise LotPositionOverflowError(
            f"Position #{position.id} (sequence {position.sequence}) has no available "
            f"input left: {upstream}, and this position has already processed "
            f"{pieces_processed_at(position):.3f}."
        )


def warn_out_of_sequence_ordering(position: LotPosition, positions: list[LotPosition]) -> bool:
    """True when the predecessor has not finished yet. Only a warning,
    because purchasing pre-books capacity ahead of time."""
    if position.sequence <= 1:
        return False
    predecessor = next((p for p in positions if p.sequence == position.sequence - 1), None)
    if predecessor is None:
        return False
    return predecessor.quantity_completed < predecessor.quantity


# ── Step role ────────────────────────────────────────────────────────────


def assert_valid_step_role(
    role: str, fabrication_method_id: int | None, inspection_method_id: int | None
) -> None:
    """A fabrication step has only a fabrication method and an inspection
    step only an inspection method, mirroring the database checks."""
    assert_role_matches_methods(
        role,
        fabrication_method_id,
        inspection_method_id,
        error=LotPositionGroupingInvalidError,
        noun="step",
    )


# ── Position grouping ────────────────────────────────────────────────────


def validate_position_grouping(steps: list[LotStep], groups: list[list[int]]) -> None:
    """Each group of step ids becomes one position. The groups must form
    contiguous, ordered slices covering every step once, and an inspection
    step is always a position of its own."""
    validate_contiguous_grouping(
        steps,
        groups,
        item_id=lambda s: s.id,
        item_order=lambda s: s.sequence,
        is_inspection=lambda s: s.role == StepRole.INSPECTION,
        error_factory=LotPositionGroupingInvalidError,
        item_noun="step",
        group_noun="position group",
        owner_noun="this lot",
        order_noun="sequence",
    )


# ── Position quantities ────────────────────────────────────────────────


def compute_position_remaining(
    quantity: float,
    order_item_quantity: float | None,
    production_orders: list[ProductionOrder],
    closed_lines_quantity: float = 0.0,
) -> float:
    """The position quantity still free for an assignment: the quantity less
    the live order lines', the live production orders' and the pieces
    canceled orders completed, which exist and are not made again
    (lifecycle/lot_position.py, position_remaining). `order_item_quantity`
    is the newest live line's, None without one, and `closed_lines_quantity`
    what the earlier lines closed short hold. Both assignments validate
    against this."""
    line = (
        PositionLineFacts(
            status=OrderItemStatus.ORDERED, quantity=order_item_quantity, delivered=0.0
        )
        if order_item_quantity is not None
        else None
    )
    closed = PositionLineFacts(
        status=OrderItemStatus.DELIVERED,
        quantity=closed_lines_quantity,
        delivered=closed_lines_quantity,
    )
    facts = LotPositionFacts(
        quantity=quantity,
        line=line,
        closed_lines=(closed,) if quantity_gt(closed_lines_quantity, 0.0) else (),
        orders=tuple(
            PositionOrderFacts(
                status=ProductionOrderStatus(o.status),
                quantity=o.quantity,
                quantity_completed=o.quantity_completed,
            )
            for o in production_orders
        ),
        lot_canceled=False,
    )
    return position_remaining(facts)


def lot_position_remaining(position: LotPosition) -> float:
    """compute_position_remaining of a position as the repository read it."""
    return compute_position_remaining(
        position.quantity,
        position.order_item_quantity,
        position.production_orders,
        position.closed_lines_quantity,
    )


def sync_position_quantities(
    positions: list[LotPosition], new_lot_quantity: float
) -> list[LotPosition]:
    """Copies a DRAFT lot's quantity onto every position, in place."""
    for position in positions:
        position.quantity = new_lot_quantity
    return positions


# ── Closing a lot short: dispositions and force-complete ───────────────


def _snapped(value: float, *anchors: float) -> float:
    """`value`, or the first anchor it equals within the quantity
    tolerance, so the float residue of a subtraction does not leave a
    quantity a hair below the count it must hold."""
    return next((anchor for anchor in anchors if quantity_eq(value, anchor)), value)


def shrink_lot_for_scrap(
    lot: ProductionLot, position: LotPosition, quantity: float
) -> list[LotPosition]:
    """Closes a lot short for scrap, inspection rejects and pieces lost at
    receipt: removing pieces at `position` shrinks the lot permanently, and
    `position` and every later position lose the removed pieces from their
    own quantity. Earlier positions keep theirs, since their output also fed
    the removed pieces. A stored completed count is never left above its
    lowered quantity, as the database requires;
    assert_disposition_keeps_completed refuses a removal that would need
    that. Mutates in place and returns the touched positions for the caller
    to persist."""
    touched: list[LotPosition] = []
    for lot_position in lot.positions:
        if lot_position.sequence < position.sequence:
            continue
        lot_position.quantity = _snapped(
            max(lot_position.quantity - quantity, 0.0), 0.0, lot_position.quantity_completed
        )
        lot_position.quantity_completed = min(
            lot_position.quantity_completed, lot_position.quantity
        )
        touched.append(lot_position)
    # The lot's quantity follows its last position's, so a float residue
    # next to that position's quantity or completed count is that value.
    last = max(lot.positions, key=lambda p: p.sequence, default=None)
    anchors = (0.0,) if last is None else (0.0, last.quantity, last.quantity_completed)
    lot.quantity = _snapped(max(lot.quantity - quantity, 0.0), *anchors)
    return touched


def assert_disposition_keeps_completed(
    lot: ProductionLot, position: LotPosition, removed: float, accepted_now: float = 0.0
) -> None:
    """A disposition removes only pieces still to come: after the shrink,
    every shrunk position, the lot's last one included, must still hold its
    completed count, with the pieces this operation accepts at `position`
    added. Removing more would take the lot below what it already completed,
    which LotNotScrappableError refuses."""
    for lot_position in lot.positions:
        if lot_position.sequence < position.sequence:
            continue
        completed = lot_position.quantity_completed
        if lot_position.id == position.id:
            completed += accepted_now
        left = lot_position.quantity - removed
        if quantity_gt(completed, left):
            raise LotNotScrappableError(
                f"Position #{lot_position.id} of lot #{lot.id} has completed {completed:.3f}; "
                f"removing {removed:.3f} would leave it {left:.3f}, below what it already "
                "completed."
            )


def dropped_wip(lot: ProductionLot) -> list[tuple[LotPosition, float]]:
    """The pieces a force-complete drops: for each position but the last,
    the good pieces it finished that the next position has not, which sit
    between the two and go nowhere once the lot closes at what its last
    position produced. Positions with nothing dropped are left out."""
    positions = sorted(lot.positions, key=lambda p: p.sequence)
    dropped: list[tuple[LotPosition, float]] = []
    for position, following in pairwise(positions):
        pieces = position.quantity_completed - following.quantity_completed
        if quantity_gt(pieces, 0.0):
            dropped.append((position, pieces))
    return dropped


def unused_raw_material(lot: ProductionLot, arrived: float, unit: str) -> float:
    """The raw material that arrived for the lot and its first position did
    not use, in pieces; zero when the material's unit measures rather than
    counts, since its use cannot be compared with pieces."""
    if not counts_whole_units(unit) or not lot.positions:
        return 0.0
    first = min(lot.positions, key=lambda p: p.sequence)
    return max(arrived - pieces_processed_at(first), 0.0)


def close_lot_short(lot: ProductionLot) -> list[LotPosition]:
    """Force-complete: the lot closes at what it produced, its last
    position's completed count, and each position at the larger of that and
    its own completed count, never above its quantity, so no completed count
    exceeds its position. Mutates in place and returns the positions whose
    quantity changed."""
    produced = lot.quantity_completed
    lot.quantity = produced
    touched: list[LotPosition] = []
    for position in lot.positions:
        closed = min(position.quantity, max(produced, position.quantity_completed))
        if not quantity_eq(closed, position.quantity):
            position.quantity = closed
            touched.append(position)
    return touched


def line_end_action(line: OrderItem, order_status: str) -> LifecycleAction | None:
    """How a cascade over a lot's live work ends one of its lines, by the
    order item intent table: CANCEL when the line takes a cancel, with
    nothing delivered or lost on it, CLOSE_SHORT when it can be closed short
    at the pieces delivered or lost, and None when it takes neither, as a
    DELIVERED line does. `order_status` is the status of the line's order."""
    try:
        context = OrderItemContext(order_status=OrderStatus(order_status))
    except ValueError:
        context = OrderItemContext(order_status=OrderStatus.DRAFT)
    for action in (LifecycleAction.CANCEL, LifecycleAction.CLOSE_SHORT):
        rule = ORDER_ITEM_INTENTS.rule_for(action)
        if rule is None:
            continue
        if rule.allowed_from is not None and line.status not in rule.allowed_from:
            continue
        if rule.guard(line, context):
            return action
    return None


@dataclass(frozen=True)
class Commitment:
    """One live commitment of a position: one of its production orders or
    its supplier line. `done` is what it has already taken care of, the
    processed pieces of an order or the delivered and lost pieces of a
    line. `cuttable` is False for a line the supplier was asked to deliver,
    which a disposition leaves to the buyer. `queued` marks an order that
    has not started."""

    id: int
    is_line: bool
    quantity: float
    done: float
    cuttable: bool = True
    queued: bool = False


@dataclass(frozen=True)
class CommitmentCut:
    """A commitment a disposition lowers to `quantity`."""

    commitment: Commitment
    quantity: float

    @property
    def cancels(self) -> bool:
        """True when nothing of the commitment was done and nothing is left,
        so it is canceled rather than kept at zero."""
        return is_zero_quantity(self.commitment.done) and is_zero_quantity(self.quantity)


def plan_commitment_cuts(
    position: LotPosition, commitments: Iterable[Commitment], *, accepted_now: float = 0.0
) -> list[CommitmentCut]:
    """The cuts that bring a shrunk position's live commitments back to what
    it still needs, its quantity less its completed count and the
    `accepted_now` pieces the caller's own operation accepted there, which
    the stored count does not hold yet. Production orders that have not
    started go first, then running ones, newest first, each never below what
    it processed, then a line not yet ordered. A cut that leaves nothing
    done and nothing open cancels the commitment. The excess counts only
    what may be cut, the orders and a line not yet ordered: an ordered line
    is left to the buyer and neither cut nor counted, so a position may stay
    over-committed to a supplier."""
    need = max(position.quantity - position.quantity_completed - accepted_now, 0.0)
    live = [c for c in commitments if c.cuttable]
    excess = sum(max(c.quantity - c.done, 0.0) for c in live) - need
    cuts: list[CommitmentCut] = []
    for commitment in sorted(live, key=lambda c: (c.is_line, not c.queued, -c.id)):
        if not quantity_gt(excess, 0.0):
            break
        cut = min(max(commitment.quantity - commitment.done, 0.0), excess)
        if quantity_gt(cut, 0.0):
            # Never below what it processed, and a float residue next to
            # that count is that count.
            kept = _snapped(max(commitment.quantity - cut, commitment.done), commitment.done)
            cuts.append(CommitmentCut(commitment, kept))
            excess -= cut
    return cuts


def scrap_capacity(
    lot: ProductionLot, position: LotPosition, raw_material_arrived: float | None = None
) -> float:
    """Pieces at `position` that can still be scrapped: its open input, what
    reached it and it has not processed yet. Scrapping processes pieces like
    a completion does."""
    return open_input(position, lot.positions, lot.quantity, raw_material_arrived)


def assert_scrap_allowed(
    lot: ProductionLot,
    position: LotPosition,
    quantity: float,
    actor: User,
    raw_material_arrived: float | None = None,
) -> None:
    """Scrap needs a lot the intent table lets scrap (not terminal and not
    held), a position with internal work (an EXTERNAL position's pieces are
    the supplier's), whole pieces and enough capacity."""
    assert_whole_pieces(quantity, what="The scrapped quantity")
    assert_lot_action(LifecycleAction.SCRAP, lot, actor)
    if position.kind == LotPositionKind.EXTERNAL:
        raise LotNotScrappableError(
            f"Position #{position.id} is external; pieces there cannot be scrapped through "
            "the production-order scrap flow."
        )
    capacity = scrap_capacity(lot, position, raw_material_arrived)
    if quantity_gt(quantity, capacity):
        raise ScrapQuantityExceedsAvailableError(
            f"Position #{position.id} has {capacity:.3f} piece(s) available to scrap; "
            f"cannot scrap {quantity:.3f}."
        )


def assert_delivery_disposition_allowed(lot: ProductionLot, position: LotPosition) -> None:
    """A goods-receipt "lost" disposition needs a non-terminal lot and an
    EXTERNAL or MIXED position."""
    if lot.status in TERMINAL_LOT_STATUSES:
        raise LotNotScrappableError(
            f"Lot #{lot.id} is {lot.status.value} and cannot have pieces lost at receipt "
            "disposed against it."
        )
    if position.kind == LotPositionKind.INTERNAL:
        raise LotNotScrappableError(
            f"Position #{position.id} is internal; a goods-receipt disposition only "
            "applies to an external or mixed position."
        )


def split_quantity_by_largest_remainder(
    total: float, weights: list[float], favoured: list[bool] | None = None
) -> list[float]:
    """Splits `total` proportionally to `weights` with the largest-remainder
    method, so the shares sum exactly. Used to divide removed pieces across
    a lot's demand allocations. `total` is clamped to the weight sum,
    because a demand can give up no more than it was allocated. A share
    marked in `favoured` is rounded down, so it gives up no more than its
    exact proportion: the unmarked shares take the rounding remainder, and
    the marked ones only what the unmarked cannot hold."""
    n = len(weights)
    if n == 0 or total <= 0:
        return [0.0] * n
    weight_total = sum(weights)
    if weight_total <= 0:
        return [0.0] * n
    total = min(total, weight_total)
    scale = 10**_SPLIT_DP
    raw = [total * w / weight_total for w in weights]
    floored = [math.floor(r * scale) for r in raw]
    remainders = [r * scale - f for r, f in zip(raw, floored, strict=True)]
    shortfall = int(round(total * scale) - sum(floored))
    # Floored, so no share can exceed its weight and leave an allocation
    # below zero; the small slack keeps a float such as 0.3 * 1e6 on its
    # whole unit.
    caps = [math.floor(w * scale + _SPLIT_SLACK) for w in weights]
    marked = favoured or [False] * n
    by_remainder = sorted(range(n), key=lambda i: remainders[i], reverse=True)
    for group in (
        [i for i in by_remainder if not marked[i]],
        [i for i in by_remainder if marked[i]],
    ):
        shortfall = _hand_out_units(floored, caps, group, shortfall)
    return [f / scale for f in floored]


def _hand_out_units(floored: list[int], caps: list[int], group: list[int], shortfall: int) -> int:
    """Adds one unit at a time to the shares in `group`, in its order and
    round after round, until the shortfall is gone or every share is at its
    cap. Returns the shortfall left."""
    while shortfall > 0 and any(floored[i] < caps[i] for i in group):
        for i in group:
            if shortfall > 0 and floored[i] < caps[i]:
                floored[i] += 1
                shortfall -= 1
    return shortfall


# ── Structure edits ─────────────────────────────────────────────────────


def has_progress(position: LotPosition) -> bool:
    """True when the position has completed pieces or any of its production
    orders left a record of work: a completion row, accepted, rejected or
    scrapped pieces alike, a start, an interruption or an assessment, also
    on an order canceled since. A structure edit would delete such a
    position with the rows, evidence and assessments of its work."""
    if quantity_gt(position.quantity_completed, 0.0):
        return True
    return any(
        order.completions
        or order.actual_start is not None
        or order.interruptions
        or order.assessment is not None
        for order in position.production_orders
    )


def moved_position_ids(before: list[int], after: list[int]) -> set[int]:
    """The positions present before and after a structure edit whose rank
    among those positions changed. Renumbering for a removed or an added
    position moves nothing."""
    common = set(before) & set(after)
    kept_before = [p for p in before if p in common]
    kept_after = [p for p in after if p in common]
    return {p for p in common if kept_before.index(p) != kept_after.index(p)}


def assert_moved_positions_free(positions: Iterable[LotPosition], moved: set[int]) -> None:
    """A position committed to a supplier or a machine, or with pieces made,
    keeps its place in the sequence, since its input comes from the position
    before it and its commitment was planned for that place."""
    blocked = sorted(
        (
            p
            for p in positions
            if p.id in moved and (p.kind != LotPositionKind.UNASSIGNED or has_progress(p))
        ),
        key=lambda p: p.sequence,
    )
    if blocked:
        ids = ", ".join(f"#{p.id}" for p in blocked)
        raise LotPositionAlreadyAssignedError(
            f"Position(s) {ids} are assigned or have progress and keep their place in the sequence."
        )


def assert_no_new_position_before_progress(submitted: list[LotPosition | None]) -> None:
    """`submitted` is the new sequence of positions, None for a new one. A
    new position may not come before a position with progress, whose input
    would then be what the new position makes."""
    new_before = False
    for position in submitted:
        if position is None:
            new_before = True
        elif new_before and has_progress(position):
            raise LotPositionAlreadyAssignedError(
                f"Position #{position.id} has progress; no new position can be placed before it."
            )


# ── Lot intents ─────────────────────────────────────────────────────────

# The error each action has always answered a refused state with, so its
# HTTP status stays.
_REFUSED_WITH: dict[LifecycleAction, type[DomainError]] = {
    LifecycleAction.EDIT_STRUCTURE: LotStructureLockedError,
    LifecycleAction.REORDER_POSITIONS: LotStructureLockedError,
    LifecycleAction.EDIT_QUANTITY: LotStructureLockedError,
    LifecycleAction.SCRAP: LotNotScrappableError,
    LifecycleAction.SWITCH_SOURCE: LotStructureLockedError,
}


def lot_context(lot: ProductionLot) -> LotContext:
    """The context the lot intent table judges an action in: what the lot
    produced, its last position's completed count, whether any position
    completed a good piece, and where its material source approval stands."""
    return LotContext(
        produced=lot.quantity_completed,
        has_good_pieces=any(quantity_gt(p.quantity_completed, 0.0) for p in lot.positions),
        source_approval_status=lot.source_approval_status,
    )


def assert_lot_action(action: LifecycleAction, lot: ProductionLot, actor: User) -> None:
    """Raises unless the lot intent table allows the action on the lot now.
    A missing permission raises InsufficientPermissionsError; a state that
    does not allow the action raises the error the action has always
    answered with: LotStructureLockedError for structure, reorder and
    quantity edits, LotNotScrappableError for scrap, and
    LotInvalidStatusTransitionError for the others."""
    refusal = LOT_INTENTS.check(action, lot, lot_context(lot), actor)
    if refusal is None:
        return
    verb = action.value.replace("_", " ")
    if refusal.kind is RefusalKind.PERMISSION:
        raise InsufficientPermissionsError(
            f"User #{actor.id} ({actor.full_name}) cannot {verb} lot #{lot.id}; "
            f"{refusal.requirement} is required."
        )
    refused = _REFUSED_WITH.get(action, LotInvalidStatusTransitionError)
    if action is LifecycleAction.CANCEL and lot.status not in TERMINAL_LOT_STATUSES:
        raise refused(
            f"Lot #{lot.id} has good pieces at a position, which a cancel would throw away; "
            "force-complete it to keep them."
        )
    raise refused(refusal.message(f"Lot #{lot.id}", lot.status.value, verb))


# ── Lot position intents ───────────────────────────────────────────────


class PositionRefusal(Enum):
    """Which state requirement of a lot position action failed, so a use
    case can answer with the error it has always raised for it."""

    LIVE_LINE = "live_line"
    KIND = "kind"
    LOT_TERMINAL = "lot_terminal"
    NOTHING_REMAINING = "nothing_remaining"
    LINE_PLACED = "line_placed"


def parse_live_line_status(value: str | None) -> OrderItemStatus | None:
    """The live order line's status as the intent tables read it, or None
    when there is no line or its stored value is not a known status."""
    if not value:
        return None
    try:
        return OrderItemStatus(value)
    except ValueError:
        return None


def lot_position_context(
    position: LotPosition,
    lot_status: str,
    live_line: OrderItem | Literal[False] | None = False,
) -> LotPositionContext:
    """The context the lot position intent table judges an action in. The
    newest live line is the position's own unless `live_line` passes a
    fresher one, read under the lot's lock (None when there is none); the
    remaining quantity is compute_position_remaining's."""
    if live_line is False:
        status: str | None = position.order_item_status
        closed_short = position.order_item_closed_short
    elif live_line is None:
        status, closed_short = None, False
    else:
        status, closed_short = live_line.status, live_line.closed_short_at is not None
    return LotPositionContext(
        live_line_status=parse_live_line_status(status),
        live_line_closed_short=closed_short,
        remaining=lot_position_remaining(position),
        lot_terminal=lot_status in TERMINAL_LOT_STATUSES,
    )


# The order in which each action names a failed requirement, the order in
# which its use case has always checked them.
_POSITION_REFUSAL_ORDER: dict[LifecycleAction, tuple[PositionRefusal, ...]] = {
    LifecycleAction.ASSIGN_EXTERNAL: (
        PositionRefusal.KIND,
        PositionRefusal.LOT_TERMINAL,
        PositionRefusal.LIVE_LINE,
        PositionRefusal.NOTHING_REMAINING,
    ),
    LifecycleAction.UNASSIGN_EXTERNAL: (PositionRefusal.KIND, PositionRefusal.LINE_PLACED),
    LifecycleAction.ASSIGN_INTERNAL: (
        PositionRefusal.LOT_TERMINAL,
        PositionRefusal.NOTHING_REMAINING,
    ),
    LifecycleAction.RECORD_PROVISION: (PositionRefusal.LOT_TERMINAL, PositionRefusal.KIND),
}

_KINDS_FOR: dict[LifecycleAction, tuple[str, ...]] = {
    LifecycleAction.ASSIGN_EXTERNAL: (
        LotPositionKind.UNASSIGNED,
        LotPositionKind.INTERNAL,
    ),
    LifecycleAction.UNASSIGN_EXTERNAL: (
        LotPositionKind.EXTERNAL,
        LotPositionKind.MIXED,
    ),
    LifecycleAction.RECORD_PROVISION: (
        LotPositionKind.EXTERNAL,
        LotPositionKind.MIXED,
    ),
}


def _fails(
    requirement: PositionRefusal,
    action: LifecycleAction,
    position: LotPosition,
    context: LotPositionContext,
) -> bool:
    if requirement is PositionRefusal.LIVE_LINE:
        return context.live_line_status is not None and not context.live_line_closed_short
    if requirement is PositionRefusal.KIND:
        if action is LifecycleAction.ASSIGN_EXTERNAL and context.live_line_closed_short:
            return False
        return position.kind not in _KINDS_FOR[action]
    if requirement is PositionRefusal.LOT_TERMINAL:
        return context.lot_terminal
    if requirement is PositionRefusal.NOTHING_REMAINING:
        return not quantity_gt(context.remaining, 0.0)
    return context.live_line_status not in (OrderItemStatus.PENDING, OrderItemStatus.REQUESTED)


def lot_position_refusal(
    action: LifecycleAction, position: LotPosition, context: LotPositionContext, actor: User
) -> PositionRefusal | None:
    """None when the lot position intent table allows the action now, else
    the first requirement it fails, in the order the action's use case
    reports them. The table decides; this only names the reason."""
    if LOT_POSITION_INTENTS.check(action, position, context, actor) is None:
        return None
    for requirement in _POSITION_REFUSAL_ORDER.get(action, ()):
        if _fails(requirement, action, position, context):
            return requirement
    # Every guard of the table is one of the requirements above, so a
    # refusal always names one; an action outside the table is refused as a
    # changed position.
    return PositionRefusal.KIND


# ── Lot-backed coverage adapter (for allocation_coverage.py) ───────────


def build_lot_coverage(lots: list[ProductionLot]) -> dict[int, CoverageInfo]:
    """Whether each lot is placed for the made demands allocated to it and
    how many of its pieces are complete, as the demand derivation reads them
    (lifecycle/demand.py): a lot counts as placed once it is past DRAFT and
    neither canceled nor scrapped, and a canceled lot covers nothing."""
    coverage: dict[int, CoverageInfo] = {}
    for lot in lots:
        facts = AllocationFacts.on_lot(
            1.0,
            CoveringLotFacts(
                status=LotStatus(lot.status),
                quantity=lot.quantity,
                quantity_completed=lot.quantity_completed,
            ),
        )
        coverage[lot.id] = CoverageInfo(is_placed=is_placed(facts), arrived=arrived_pieces(facts))
    return coverage


# ── Permission / lifecycle guards ───────────────────────────────────────


class LotRules:
    """Permission and validity guards for ProductionLot operations."""

    @staticmethod
    def assert_can_create(actor: User) -> None:
        assert_has_permission(actor, Permission.WRITE_LOTS, "create", "production lots")

    @staticmethod
    def assert_can_update(actor: User, lot: ProductionLot) -> None:
        assert_has_permission(actor, Permission.WRITE_LOTS, "update", "production lots")
        if not actor.has_permission(Permission.MANAGE_LOTS) and lot.status in TERMINAL_LOT_STATUSES:
            raise LotStructureLockedError(
                f"Lot #{lot.id} is {lot.status.value} and cannot be modified."
            )

    @staticmethod
    def assert_can_edit_structure(
        actor: User,
        lot: ProductionLot,
        action: LifecycleAction = LifecycleAction.EDIT_STRUCTURE,
    ) -> None:
        """A structure edit, or with REORDER_POSITIONS a reorder, is decided
        by the lot intent table, the rule the lot's actions are offered by;
        assigned positions are protected separately. The permission check
        runs first so a 409 never leaks the status to an unauthorized caller."""
        assert_has_permission(actor, Permission.WRITE_LOTS, "edit", "production lot structure")
        assert_lot_action(action, lot, actor)

    @staticmethod
    def assert_can_append_position(actor: User, lot: ProductionLot) -> None:
        """Appending a position is a structure edit, decided by the lot
        intent table (403 before 409)."""
        assert_has_permission(actor, Permission.WRITE_LOTS, "append", "production lot positions")
        assert_lot_action(LifecycleAction.EDIT_STRUCTURE, lot, actor)

    @staticmethod
    def assert_positions_unassigned(positions: list[LotPosition]) -> None:
        """Regrouping never touches a position already committed to a
        supplier order or machine, or with pieces made, whose steps are a
        physical fact by then."""
        assigned = [p for p in positions if p.kind != LotPositionKind.UNASSIGNED or has_progress(p)]
        if assigned:
            ids = ", ".join(f"#{p.id}" for p in assigned)
            raise LotPositionAlreadyAssignedError(
                f"Position(s) {ids} are already assigned and cannot be restructured."
            )

    @staticmethod
    def assert_demand_project_matches(
        lot_project_id: int, demand_project_id: int, demand_id: int
    ) -> None:
        """A lot runs for one project, so it only takes that project's demands."""
        if demand_project_id != lot_project_id:
            raise LotDemandProjectMismatchError(
                f"Demand item #{demand_id} belongs to project #{demand_project_id}, "
                f"not lot project #{lot_project_id}."
            )

    @staticmethod
    def assert_demand_made_item_matches(
        lot_made_item_id: int, demand_made_item_id: int, demand_id: int
    ) -> None:
        """A lot builds one made item, so it only takes demands for that
        item; a demand for another item, an older revision's for example,
        is refused rather than covered by pieces it did not ask for."""
        if demand_made_item_id != lot_made_item_id:
            raise LotDemandMadeItemMismatchError(
                f"Demand item #{demand_id} is for made item #{demand_made_item_id}, "
                f"not the lot's made item #{lot_made_item_id}."
            )

    @staticmethod
    def assert_whole_lot_quantities(lot_quantity: float, allocations: list[float]) -> None:
        """A lot builds whole pieces, so its quantity and every demand's share
        of it are whole numbers. A follow-up lot takes its quantity from
        pieces already counted and skips the check."""
        assert_whole_pieces(lot_quantity, what="The lot quantity")
        for allocated in allocations:
            assert_whole_pieces(allocated, what="A demand allocation of the lot")

    @staticmethod
    def assert_allocations_within_quantity(lot_quantity: float, allocated_total: float) -> None:
        """Allocations cannot exceed the lot quantity, or a demand would count
        as covered by pieces nobody is building. Both are independent user
        inputs, so nothing else keeps them consistent."""
        if quantity_gt(allocated_total, lot_quantity):
            raise AllocationOverflowError(
                f"Demand allocations total {allocated_total:.3f}, which exceeds the "
                f"lot quantity {lot_quantity:.3f}. A lot cannot allocate more than "
                f"it produces."
            )

    @staticmethod
    def assert_at_most_one_material_source(
        bought_item_id: int | None, source_item_id: int | None, made_item_id: int | None
    ) -> None:
        _assert_at_most_one_material_source(bought_item_id, source_item_id, made_item_id)

    @staticmethod
    def assert_can_approve_source(actor: User, lot: ProductionLot, action: LifecycleAction) -> None:
        """Guards approving (APPROVE_SOURCE) or rejecting (REJECT_SOURCE) a
        lot's material source. manage:lots comes first, so a 403 comes
        before any 409; then the lot intent table decides: the lot is not
        terminal and its source is pending, or also rejected for an
        approval."""
        assert_has_permission(
            actor, Permission.MANAGE_LOTS, "approve or reject", "a lot's material source"
        )
        refusal = LOT_INTENTS.check(action, lot, lot_context(lot), actor)
        if refusal is None:
            return
        if refusal.by_status:
            raise LotStructureLockedError(
                f"Lot #{lot.id} is {lot.status.value} and its material source can no longer be "
                "approved or rejected."
            )
        approving = action is LifecycleAction.APPROVE_SOURCE
        raise SourceApprovalNotPendingError(
            f"Lot #{lot.id}'s material source is {lot.source_approval_status.value!r}; only a "
            f"{'pending or rejected' if approving else 'pending'} source can be "
            f"{'approved' if approving else 'rejected'}."
        )
