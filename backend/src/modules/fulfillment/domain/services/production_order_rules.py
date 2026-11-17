"""Pure domain logic for the ProductionOrder aggregate: quantity split
validation, capability checks, the order-level completion cap, and
permission and lifecycle guards. No I/O.

Which action an order's state allows comes from the production order intent
table (lifecycle/intents.py), through assert_production_order_action; the
order's status itself is derived from its facts by the lifecycle reconciler.

This module and lot_rules.py never import each other; use cases combine
them for position-level caps.
"""

from datetime import date

from src.modules.catalogue.domain.errors import MachineCapabilityMismatchError
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.entities.machine_pool import MachinePool
from src.modules.fulfillment.domain.entities.production_machine import ProductionMachine
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)
from src.modules.fulfillment.domain.errors import CompletionAlreadyReversedError
from src.modules.fulfillment.domain.errors import CompletionDateInvalidError
from src.modules.fulfillment.domain.errors import CompletionNotReversibleError
from src.modules.fulfillment.domain.errors import LotOnHoldError
from src.modules.fulfillment.domain.errors import OperatorNotAssignedError
from src.modules.fulfillment.domain.errors import OperatorSelectionRequiredError
from src.modules.fulfillment.domain.errors import ProductionMachineArchivedError
from src.modules.fulfillment.domain.errors import ProductionOrderCannotMergeError
from src.modules.fulfillment.domain.errors import ProductionOrderCompletionSplitInvalidError
from src.modules.fulfillment.domain.errors import ProductionOrderInvalidScheduleError
from src.modules.fulfillment.domain.errors import ProductionOrderInvalidStatusTransitionError
from src.modules.fulfillment.domain.errors import ProductionOrderNoMachineAssignedError
from src.modules.fulfillment.domain.errors import ProductionOrderQuantityOverflowError
from src.modules.fulfillment.domain.errors import ProductionOrderSplitMismatchError
from src.modules.fulfillment.domain.services.lifecycle.intents import LOT_NOT_HELD
from src.modules.fulfillment.domain.services.lifecycle.intents import PRODUCTION_ORDER_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import ProductionOrderContext
from src.modules.fulfillment.domain.services.lifecycle.snapshot import production_order_facts
from src.modules.fulfillment.domain.value_objects.production_status import (
    TERMINAL_PRODUCTION_ORDER_STATUSES,
)
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.exceptions import DomainError
from src.modules.platform.domain.exceptions import InsufficientPermissionsError
from src.modules.platform.domain.services.crud_permission_rules import assert_has_permission
from src.modules.platform.domain.services.intent_table import RefusalKind
from src.modules.platform.domain.services.quantities import assert_whole_pieces
from src.modules.platform.domain.services.quantities import quantity_eq
from src.modules.platform.domain.services.quantities import quantity_gt
from src.modules.platform.domain.value_objects.permission import Permission
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction


def resolve_effective_per_piece_minutes(step: LotStep) -> tuple[float, str]:
    """A step's per-piece minutes and their source: "measured", "budget"
    (the time-budget apportionment) or "missing" (0)."""
    if step.estimated_minutes_per_piece is not None:
        return step.estimated_minutes_per_piece, "measured"
    if step.time_budget_per_piece is not None:
        return step.time_budget_per_piece, "budget"
    return 0.0, "missing"


def compute_estimated_duration_minutes(steps: list[LotStep], quantity: float) -> int:
    """Total setup plus quantity times per-piece minutes. Each order pays
    its own setup because it is a separate machine run, so a merge
    recomputes rather than summing its parts."""
    setup_total = sum(s.estimated_setup_minutes or 0 for s in steps)
    per_piece_total = sum(resolve_effective_per_piece_minutes(s)[0] for s in steps)
    return round(setup_total + quantity * per_piece_total)


def estimate_time_source(steps: list[LotStep]) -> str:
    """The estimate source for a whole order, which picks the time-estimate
    conflict flag. One missing step dominates. Inspection steps without an
    estimate are ignored, because QA gets no time budget and flagging them
    would be permanent noise; an order of only such steps reports
    "not_applicable"."""
    if not steps:
        return "missing"
    counted = []
    for step in steps:
        _minutes, source = resolve_effective_per_piece_minutes(step)
        if step.role == StepRole.INSPECTION and source == "missing":
            continue
        counted.append(source)
    if not counted:
        return "not_applicable"
    if "missing" in counted:
        return "missing"
    if "budget" in counted:
        return "budget"
    return "measured"


# ── Split-assignment quantity ────────────────────────────────────────────


def assert_quantity_within_position(
    existing_total: float, new_quantity: float, position_quantity: float
) -> None:
    """A position's production orders may not exceed its quantity, and a new
    order builds whole pieces."""
    assert_whole_pieces(new_quantity, what="The production order quantity")
    total = existing_total + new_quantity
    if quantity_gt(total, position_quantity):
        raise ProductionOrderQuantityOverflowError(
            f"Assigning {new_quantity:.3f} would bring the position's queued "
            f"total to {total:.3f}, exceeding its quantity of {position_quantity:.3f}."
        )


def is_position_fully_queued(orders: list[ProductionOrder], position_quantity: float) -> bool:
    """True once the non-canceled orders cover the position quantity exactly."""
    total = sum(o.quantity for o in orders if o.status != ProductionOrderStatus.CANCELED)
    return quantity_eq(total, position_quantity)


# ── Split / merge (QUEUED only, by the intent table) ────────────────────


def assert_split_sums_correctly(parts: list[float], original_quantity: float) -> None:
    if len(parts) < 2:
        raise ProductionOrderSplitMismatchError("A split must produce at least two parts.")
    if any(p <= 0 for p in parts):
        raise ProductionOrderSplitMismatchError("Split quantities must all be positive.")
    for part in parts:
        assert_whole_pieces(part, what="A split quantity")
    total = sum(parts)
    if not quantity_eq(total, original_quantity):
        raise ProductionOrderSplitMismatchError(
            f"Split quantities sum to {total:.3f}, expected {original_quantity:.3f}."
        )


def assert_can_merge(orders: list[ProductionOrder]) -> None:
    """The orders become one run, so they share a machine, a machine pool
    and a lot position. Whether each order's state allows a merge is the
    intent table's MERGE rule."""
    if len(orders) < 2:
        raise ProductionOrderCannotMergeError("A merge needs at least two orders.")
    machine_ids = {o.machine_id for o in orders}
    pool_ids = {o.machine_pool_id for o in orders}
    position_ids = {o.lot_position_id for o in orders}
    if len(machine_ids) > 1:
        raise ProductionOrderCannotMergeError("Orders on different machines cannot be merged.")
    if len(pool_ids) > 1:
        raise ProductionOrderCannotMergeError("Orders of different machine pools cannot be merged.")
    if len(position_ids) > 1:
        raise ProductionOrderCannotMergeError(
            "Orders belonging to different lot positions cannot be merged."
        )


# ── Capability match ────────────────────────────────────────────────────


def _machine_requiring_method_ids(steps: list[LotStep]) -> set[int]:
    """Methods of the steps that need a machine. Manual steps never have a
    capable machine and would otherwise make every machine ineligible."""
    return {
        s.fabrication_method_id
        for s in steps
        if s.fabrication_method_requires_machine and s.fabrication_method_id is not None
    }


def position_requires_qa_machine(steps: list[LotStep]) -> bool:
    """An inspection step is always its own position, so one is enough."""
    return any(s.role == StepRole.INSPECTION for s in steps)


def position_is_manual(steps: list[LotStep]) -> bool:
    """True when no step needs a machine. Such a position never gets a
    machine or pool and is scheduled against the admin default calendar.
    Inspection steps count as manual. An empty list is not manual."""
    return bool(steps) and all(not s.fabrication_method_requires_machine for s in steps)


def assert_machine_takes_work(machine: ProductionMachine) -> None:
    """An archived machine is off the planning and queue boards, so an order
    queued on it would vanish. The writers that queue an order on a machine
    read it under the machine's queue lock, which an archive takes before it
    counts the machine's orders, so the two cannot interleave."""
    if machine.archived:
        raise ProductionMachineArchivedError(
            f"Machine #{machine.id} ({machine.internal_name}) is archived and takes no "
            "production orders. Pick another machine, or restore this one first."
        )


def assert_capability_match(machine: ProductionMachine, steps: list[LotStep]) -> None:
    """The machine must cover the fabrication method of every
    machine-requiring step. Inspection positions only go to QA machines and
    QA machines never take fabrication work. A manual position is rejected,
    because its empty requirement would match every machine vacuously."""
    if position_requires_qa_machine(steps):
        if not machine.is_qa_machine:
            raise MachineCapabilityMismatchError(
                f"Machine #{machine.id} ({machine.internal_name}) is not a QA/measuring "
                f"machine and cannot take an inspection position."
            )
        return
    if machine.is_qa_machine:
        raise MachineCapabilityMismatchError(
            f"Machine #{machine.id} ({machine.internal_name}) is a dedicated QA/measuring "
            f"machine and cannot take fabrication work."
        )
    if position_is_manual(steps):
        raise MachineCapabilityMismatchError(
            f"This position has no machine-requiring step and must be queued without a "
            f"machine, not assigned to machine #{machine.id} ({machine.internal_name})."
        )
    required = _machine_requiring_method_ids(steps)
    available = set(machine.fabrication_method_ids)
    missing = required - available
    if missing:
        raise MachineCapabilityMismatchError(
            f"Machine #{machine.id} ({machine.internal_name}) does not cover fabrication "
            f"method(s) {sorted(missing)} required by this position."
        )


def assert_pool_capability_match(pool: MachinePool, steps: list[LotStep]) -> None:
    """A pool's capability is the intersection of its members' methods, so
    any machine later picked from it is capable. Inspection and manual
    positions never go to a pool."""
    if position_requires_qa_machine(steps):
        raise MachineCapabilityMismatchError(
            f"Machine pool #{pool.id} ({pool.name}) cannot take an inspection position - "
            f"QA work goes to a specific QA/measuring machine, never a pool."
        )
    if position_is_manual(steps):
        raise MachineCapabilityMismatchError(
            f"This position has no machine-requiring step and must be queued without a "
            f"machine, not assigned to machine pool #{pool.id} ({pool.name})."
        )
    required = _machine_requiring_method_ids(steps)
    if not pool.machines:
        available: set[int] = set()
    else:
        available = set.intersection(*(set(m.fabrication_method_ids) for m in pool.machines))
    missing = required - available
    if missing:
        raise MachineCapabilityMismatchError(
            f"Machine pool #{pool.id} ({pool.name}) does not cover fabrication "
            f"method(s) {sorted(missing)} required by this position."
        )


def assert_machine_or_pool_assigned(
    steps: list[LotStep], machine_id: int | None, machine_pool_id: int | None
) -> None:
    """Fabrication work cannot be queued without a machine or pool. Manual
    and inspection positions are exempt through position_is_manual."""
    if position_is_manual(steps):
        return
    if machine_id is None and machine_pool_id is None:
        raise ProductionOrderNoMachineAssignedError(
            "This position has at least one machine-requiring step and must be "
            "assigned a machine or a machine pool."
        )


# ── Completion cap (order-level; position-level reuses lot_rules) ──────


def assert_whole_completion(*quantities: float) -> None:
    """A completion books whole pieces: processed, accepted, rejected,
    rework and scrap alike."""
    for quantity in quantities:
        assert_whole_pieces(quantity, what="A completion quantity")


def assert_order_completion_within_order_quantity(
    order: ProductionOrder, processed_total: float, delta: float
) -> None:
    """An order cannot process more than its quantity. The cap counts
    accepted plus rejected pieces, because rejects consume capacity too and
    would otherwise leave the order unable to finish."""
    if quantity_gt(processed_total + delta, order.quantity):
        raise ProductionOrderQuantityOverflowError(
            f"Production order #{order.id} has {order.quantity:.3f} queued; cannot record "
            f"{delta:.3f} more (already processed {processed_total:.3f})."
        )


# ── Completion accepted/rejected split ──────────────────────────────────


def resolve_completion_split(
    quantity: float, quantity_accepted: float | None, quantity_rejected: float | None
) -> tuple[float, float]:
    """Both omitted means everything was accepted; otherwise both must be
    given and sum to quantity. Mirrors the request schema's validator for
    callers that bypass HTTP."""
    if quantity_accepted is None and quantity_rejected is None:
        return quantity, 0.0
    accepted = quantity_accepted if quantity_accepted is not None else 0.0
    rejected = quantity_rejected if quantity_rejected is not None else 0.0
    if not quantity_eq(accepted + rejected, quantity):
        raise ProductionOrderCompletionSplitInvalidError(
            f"quantity_accepted + quantity_rejected must equal quantity "
            f"({accepted:.3f} + {rejected:.3f} != {quantity:.3f})."
        )
    return accepted, rejected


def assert_valid_disposition(
    is_inspection: bool, quantity_rejected: float, quantity_rework: float, quantity_scrap: float
) -> None:
    """Rejected pieces leave the lot short, which only the disposition of an
    inspection completion accounts for: there rework plus scrap must equal
    the rejected pieces. An ordinary completion records accepted pieces
    only; pieces lost during production are scrapped through the scrap
    action, which runs the same disposition."""
    if is_inspection:
        if not quantity_eq(quantity_rework + quantity_scrap, quantity_rejected):
            raise ProductionOrderCompletionSplitInvalidError(
                f"quantity_rework + quantity_scrap must equal quantity_rejected on an "
                f"inspection completion ({quantity_rework:.3f} + {quantity_scrap:.3f} != "
                f"{quantity_rejected:.3f})."
            )
        return
    if quantity_gt(quantity_rejected, 0.0):
        raise ProductionOrderCompletionSplitInvalidError(
            "quantity_rejected is only allowed on an inspection completion; scrap pieces "
            "lost during production through the scrap action instead."
        )
    if quantity_rework != 0 or quantity_scrap != 0:
        raise ProductionOrderCompletionSplitInvalidError(
            "quantity_rework/quantity_scrap are only allowed on an inspection completion."
        )


def assert_completion_date_allowed(
    completion_date: date, today: date, started_on: date | None
) -> None:
    """A completion is reported for a day that has begun in the tenant's
    timezone and not before the order was first started (`started_on`, its
    local date), which bounds how far back it can be dated."""
    if completion_date > today:
        raise CompletionDateInvalidError(
            f"A completion cannot be reported for {completion_date.isoformat()}, a day that "
            "has not begun yet."
        )
    if started_on is not None and completion_date < started_on:
        raise CompletionDateInvalidError(
            f"A completion cannot be reported for {completion_date.isoformat()}, before the "
            f"order was started on {started_on.isoformat()}."
        )


# ── Operator resolution ──────────────────────────────────────────────────


def assert_completion_reversible(
    completion: ProductionOrderCompletion,
    *,
    reversed_already: bool,
    completed_after: float,
    used_downstream: float,
) -> None:
    """Raises unless a reversal may take the completion back. Only pieces
    that are still at the position can be taken back: a reversal of a
    reversal, a second reversal, a completion that rejected pieces, whose
    disposition already shrank the lot or spawned lots, and one whose pieces
    the next position already used (`used_downstream` above
    `completed_after`, the position's completed count without it) are
    refused. A finished lot is the production order intent table's
    refusal."""
    noun = f"Completion #{completion.id}"
    if completion.reverses_completion_id is not None:
        raise CompletionNotReversibleError(f"{noun} is a reversal itself.")
    if reversed_already:
        raise CompletionAlreadyReversedError(f"{noun} is already reversed.")
    if quantity_gt(completion.quantity_rejected, 0.0):
        raise CompletionNotReversibleError(
            f"{noun} rejected pieces, and their disposition already changed the lot; "
            "it cannot be reversed."
        )
    if quantity_gt(used_downstream, completed_after):
        raise CompletionNotReversibleError(
            f"The next position already used {used_downstream:.3f} piece(s); without "
            f"{noun} this position has only {completed_after:.3f}."
        )


def resolve_operator_id(actor: User, operator_id: int | None) -> int:
    """A shared account must name one of its members as operator, so a
    shared account without members can never act. A personal account is
    its own operator: it may leave the operator out or name itself, and any
    other id is refused before anything is written."""
    if actor.is_shared_account:
        if operator_id is None:
            raise OperatorSelectionRequiredError(
                f"User {actor.username!r} is a shared account; an operator must be selected."
            )
        if operator_id not in actor.member_ids:
            raise OperatorNotAssignedError(
                f"Operator #{operator_id} is not assigned to shared account {actor.username!r}."
            )
        return operator_id
    if operator_id is not None and operator_id != actor.id:
        raise OperatorNotAssignedError(
            f"User {actor.username!r} is a personal account and records its own work; "
            f"operator #{operator_id} cannot be named."
        )
    return actor.id


# ── Permission / lifecycle guards ───────────────────────────────────────


def production_order_context(
    order: ProductionOrder,
    *,
    lot_held: bool = False,
    lot_terminal: bool = False,
    machine_resolvable: bool = True,
    input_available: bool = True,
) -> ProductionOrderContext:
    """The context the intent table judges an action on the order in. The
    open interruption comes from the order's own rows. The lot, machine and
    input conditions default to satisfied, for a caller that checks them
    itself and names what is missing."""
    return ProductionOrderContext(
        lot_held=lot_held,
        lot_terminal=lot_terminal,
        machine_resolvable=machine_resolvable,
        input_available=input_available,
        open_interruption=production_order_facts(order).open_interruption,
    )


def assert_production_order_action(
    action: LifecycleAction,
    order: ProductionOrder,
    actor: User,
    context: ProductionOrderContext | None = None,
    *,
    refused: type[DomainError] = ProductionOrderInvalidStatusTransitionError,
) -> None:
    """Raises unless the production order intent table allows the action on
    the order now. A missing permission raises InsufficientPermissionsError;
    a lot on hold raises LotOnHoldError, and any other state that does not
    allow the action `refused`, the error the action has always answered
    with, so its HTTP status stays."""
    refusal = PRODUCTION_ORDER_INTENTS.check(
        action, order, context or production_order_context(order), actor
    )
    if refusal is None:
        return
    verb = action.value.replace("_", " ")
    if refusal.kind is RefusalKind.PERMISSION:
        raise InsufficientPermissionsError(
            f"User #{actor.id} ({actor.full_name}) cannot {verb} production order #{order.id}; "
            f"{refusal.requirement} is required."
        )
    if refusal.failed == LOT_NOT_HELD.text:
        raise LotOnHoldError(
            f"Production order #{order.id} belongs to a lot that is on hold; resume the lot "
            f"before you {verb} it."
        )
    raise refused(refusal.message(f"Production order #{order.id}", order.status.value, verb))


class ProductionOrderRules:
    """Permission and validity guards for ProductionOrder operations."""

    @staticmethod
    def assert_can_assign(actor: User) -> None:
        assert_has_permission(
            actor, Permission.WRITE_PRODUCTION_ORDERS, "assign", "production orders"
        )

    @staticmethod
    def assert_can_update(actor: User, order: ProductionOrder) -> None:
        assert_has_permission(
            actor, Permission.WRITE_PRODUCTION_ORDERS, "update", "production orders"
        )
        if not actor.has_permission(Permission.MANAGE_PRODUCTION_ORDERS) and order.pinned:
            raise InsufficientPermissionsError(
                f"Production order #{order.id} is pinned; only MANAGE_PRODUCTION_ORDERS "
                "can modify it."
            )

    @staticmethod
    def assert_can_manage(actor: User) -> None:
        """Pin/unpin, priority override, canceling another user's order."""
        assert_has_permission(
            actor, Permission.MANAGE_PRODUCTION_ORDERS, "manage", "production orders"
        )

    @staticmethod
    def assert_can_set_schedule(order: ProductionOrder) -> None:
        """A manual schedule override is only allowed before the order runs."""
        if order.status not in (
            ProductionOrderStatus.QUEUED,
            ProductionOrderStatus.PAUSED,
        ):
            raise ProductionOrderInvalidScheduleError(
                f"Production order #{order.id} is {order.status.value} and cannot have its "
                "schedule manually set."
            )

    @staticmethod
    def assert_can_cancel(actor: User, order: ProductionOrder) -> None:
        if order.status in TERMINAL_PRODUCTION_ORDER_STATUSES:
            raise ProductionOrderInvalidStatusTransitionError(
                f"Production order #{order.id} is already {order.status.value}."
            )
        if (
            not actor.has_permission(Permission.MANAGE_PRODUCTION_ORDERS)
            and order.creator_id != actor.id
        ):
            raise InsufficientPermissionsError(
                f"User #{actor.id} ({actor.full_name}) cannot cancel production order #{order.id} "
                f",  it belongs to another user."
            )
