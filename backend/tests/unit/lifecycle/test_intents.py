"""Unit tests for src/modules/fulfillment/domain/services/lifecycle/intents.py: which actions
each aggregate accepts per status, the guards on context and actor, the order
in which `check` reports a refusal, and that every intent rule is reachable."""

import typing
from dataclasses import dataclass
from dataclasses import fields
from dataclasses import replace
from datetime import UTC
from datetime import datetime
from itertools import product

import pytest

from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemDemandStatus
from src.modules.fulfillment.domain.entities.bought_item_demand_item import BoughtItemDemandItem
from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.made_item_demand_item import MadeItemDemandItem
from src.modules.fulfillment.domain.entities.order import Order
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.entities.production_lot import ProductionLot
from src.modules.fulfillment.domain.entities.production_order import ProductionOrder
from src.modules.fulfillment.domain.entities.source_item_demand_item import SourceItemDemandItem
from src.modules.fulfillment.domain.services.lifecycle.intents import DEMAND_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import LOT_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import LOT_POSITION_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import ORDER_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import ORDER_ITEM_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import PRODUCTION_ORDER_INTENTS
from src.modules.fulfillment.domain.services.lifecycle.intents import DemandContext
from src.modules.fulfillment.domain.services.lifecycle.intents import LotContext
from src.modules.fulfillment.domain.services.lifecycle.intents import LotPositionContext
from src.modules.fulfillment.domain.services.lifecycle.intents import LotPositionSubject
from src.modules.fulfillment.domain.services.lifecycle.intents import LotSubject
from src.modules.fulfillment.domain.services.lifecycle.intents import OrderItemContext
from src.modules.fulfillment.domain.services.lifecycle.intents import OrderItemSubject
from src.modules.fulfillment.domain.services.lifecycle.intents import ProductionOrderContext
from src.modules.fulfillment.domain.services.lifecycle.quote_request import QUOTE_REQUEST_INTENTS
from src.modules.fulfillment.domain.value_objects.interruption_reason import InterruptionReason
from src.modules.fulfillment.domain.value_objects.lot_status import TERMINAL_LOT_STATUSES
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.source_approval_status import SourceApprovalStatus
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.intent_table import HasStatus
from src.modules.platform.domain.services.intent_table import IntentRefusal
from src.modules.platform.domain.services.intent_table import IntentRule
from src.modules.platform.domain.services.intent_table import IntentTable
from src.modules.platform.domain.services.intent_table import RefusalKind
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.permission import Permission
from src.modules.platform.domain.value_objects.start_page import StartPage
from src.modules.platform.domain.value_objects.theme import ThemePreset
from src.modules.platform.domain.value_objects.theme import ThemePrimary
from src.modules.platform.domain.value_objects.theme import ThemeSurface
from src.modules.workspace.domain.services.lifecycle.project import PROJECT_INTENTS
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction as A

ALL_TABLES = [
    ORDER_ITEM_INTENTS,
    ORDER_INTENTS,
    PRODUCTION_ORDER_INTENTS,
    LOT_POSITION_INTENTS,
    LOT_INTENTS,
    DEMAND_INTENTS,
    QUOTE_REQUEST_INTENTS,
    PROJECT_INTENTS,
]


def _user(user_id: int, *permissions: str) -> User:
    return User(
        id=user_id,
        username=f"user{user_id}",
        full_name=f"User {user_id}",
        email=f"user{user_id}@example.com",
        created=datetime(2026, 1, 1, tzinfo=UTC),
        hashed_password="x",
        is_active=True,
        is_systemuser=False,
        permissions=list(permissions),
        language=Language.enGB,
        date_format=DateFormat.ISO,
        start_page=StartPage.DASHBOARD,
        theme_preset=ThemePreset.Aura,
        theme_surface=ThemeSurface.glados,
        theme_primary=ThemePrimary.glados,
        theme_dark_mode=False,
        button_flat_style=False,
        table_gridlines=False,
        table_striped_rows=False,
    )


MANAGER = _user(
    9, Permission.MANAGE_ORDERS, Permission.MANAGE_LOTS, Permission.MANAGE_PRODUCTION_ORDERS
)
CREATOR = _user(1)
OTHER = _user(2)


@dataclass(frozen=True)
class _Item:
    status: str
    line_type: str = OrderLineType.BOUGHT.value
    quantity_delivered: float = 0.0
    quantity_rejected: float = 0.0
    quantity_rejected_lost: float = 0.0
    closed_short_at: datetime | None = None


@dataclass(frozen=True)
class _Status:
    status: str
    # Read by the order table only: whether someone canceled the order.
    canceled_at: datetime | None = None


@dataclass(frozen=True)
class _Position:
    kind: str
    status: str = LotPositionStatus.PENDING.value


@dataclass(frozen=True)
class _Lot:
    status: str
    creator_id: int = CREATOR.id


def _set(*actions: A) -> set[A]:
    return set(actions)


# ── Tables and subjects ─────────────────────────────────────────────────


def test_every_lifecycle_action_belongs_to_an_intent_table():
    used = {rule.action for table in ALL_TABLES for rule in table.rules}
    assert used == set(A)


@pytest.mark.parametrize(
    ("protocol", "entity"),
    [
        (OrderItemSubject, OrderItem),
        (HasStatus, Order),
        (HasStatus, ProductionOrder),
        (LotPositionSubject, LotPosition),
        (LotSubject, ProductionLot),
        (HasStatus, BoughtItemDemandItem),
        (HasStatus, MadeItemDemandItem),
        (HasStatus, SourceItemDemandItem),
    ],
)
def test_entities_carry_what_the_intent_subjects_read(protocol, entity):
    assert typing.get_protocol_members(protocol) <= {f.name for f in fields(entity)}


def test_table_rejects_an_action_listed_twice():
    rule = IntentRule[HasStatus, None](action=A.CANCEL, allowed_from=None, effect="x")
    with pytest.raises(ValueError, match="may appear once"):
        IntentTable(key="twice", rules=(rule, rule))


def test_allowed_actions_follow_the_table_order():
    actions = ORDER_ITEM_INTENTS.allowed_actions(
        _Item(OrderItemStatus.PENDING.value),
        OrderItemContext(order_status=OrderStatus.DRAFT),
        MANAGER,
    )
    table_order = [r.action for r in ORDER_ITEM_INTENTS.rules if r.action in actions]
    assert list(actions) == table_order


# ── Order item ──────────────────────────────────────────────────────────

_ORDERED_ORDER = OrderItemContext(order_status=OrderStatus.ORDERED)


@pytest.mark.parametrize(
    ("item", "expected"),
    [
        (
            _Item(OrderItemStatus.PENDING.value),
            _set(
                A.MARK_REQUESTED,
                A.MARK_ORDERED,
                A.CANCEL,
                A.EDIT_QUANTITY,
                A.EDIT,
                A.MOVE,
                A.REMOVE,
            ),
        ),
        (
            _Item(OrderItemStatus.REQUESTED.value),
            _set(A.MARK_ORDERED, A.CANCEL, A.EDIT_QUANTITY, A.EDIT, A.MOVE, A.REMOVE),
        ),
        (
            _Item(OrderItemStatus.ORDERED.value),
            _set(A.MARK_READY_FOR_PICKUP, A.DELIVER, A.CANCEL, A.EDIT_QUANTITY, A.EDIT, A.MOVE),
        ),
        (
            _Item(OrderItemStatus.PARTIALLY_DELIVERED.value, quantity_delivered=4.0),
            _set(A.MARK_READY_FOR_PICKUP, A.DELIVER, A.CORRECT_DELIVERY, A.CLOSE_SHORT, A.EDIT),
        ),
        (
            _Item(OrderItemStatus.DELIVERED.value, quantity_delivered=10.0),
            _set(A.CORRECT_DELIVERY, A.EDIT),
        ),
        (_Item(OrderItemStatus.CANCELED.value), set()),
    ],
)
def test_order_item_actions_per_status(item, expected):
    # A manager of orders: past REQUESTED the line changes need manage:orders,
    # which the next test covers.
    assert set(ORDER_ITEM_INTENTS.allowed_actions(item, _ORDERED_ORDER, MANAGER)) == expected


_PARTIALLY_ORDERED_ORDER = OrderItemContext(order_status=OrderStatus.PARTIALLY_ORDERED)


@pytest.mark.parametrize("status", [OrderItemStatus.PENDING, OrderItemStatus.REQUESTED])
def test_a_partially_ordered_order_keeps_its_unordered_lines_open_to_the_buyer(status):
    actions = set(
        ORDER_ITEM_INTENTS.allowed_actions(_Item(status.value), _PARTIALLY_ORDERED_ORDER, OTHER)
    )
    assert {A.MARK_ORDERED, A.CANCEL, A.EDIT_QUANTITY, A.MOVE, A.REMOVE} <= actions


def test_an_ordered_line_of_a_partially_ordered_order_needs_manage_orders():
    ordered = _Item(OrderItemStatus.ORDERED.value)
    for action in (A.CANCEL, A.EDIT_QUANTITY, A.MOVE):
        refusal = ORDER_ITEM_INTENTS.check(action, ordered, _PARTIALLY_ORDERED_ORDER, OTHER)
        assert refusal is not None and refusal.kind == RefusalKind.PERMISSION, action
        assert ORDER_ITEM_INTENTS.check(action, ordered, _PARTIALLY_ORDERED_ORDER, MANAGER) is None
    partial = _Item(OrderItemStatus.PARTIALLY_DELIVERED.value, quantity_delivered=4.0)
    refusal = ORDER_ITEM_INTENTS.check(A.CLOSE_SHORT, partial, _PARTIALLY_ORDERED_ORDER, OTHER)
    assert refusal is not None and refusal.kind == RefusalKind.PERMISSION


def test_a_partially_ordered_order_is_submitted_for_its_own_actions():
    order = _Status(OrderStatus.PARTIALLY_ORDERED.value)
    assert set(ORDER_INTENTS.allowed_actions(order, None, MANAGER)) == _set(
        A.MARK_ORDERED, A.CANCEL, A.DELIVER, A.EDIT, A.ADD_ITEM
    )
    # Its header is submitted, but a new line is pending and stays open.
    assert set(ORDER_INTENTS.allowed_actions(order, None, OTHER)) == _set(
        A.MARK_ORDERED, A.DELIVER, A.ADD_ITEM
    )


_LINE_CHANGES = _set(
    A.MARK_REQUESTED, A.MARK_ORDERED, A.CANCEL, A.EDIT_QUANTITY, A.EDIT, A.MOVE, A.REMOVE
)


@pytest.mark.parametrize(
    ("order_status", "actor", "changes_offered"),
    [
        (OrderStatus.DRAFT, OTHER, True),
        (OrderStatus.REQUESTED, OTHER, True),
        (OrderStatus.ORDERED, OTHER, False),
        (OrderStatus.PARTIALLY_DELIVERED, OTHER, False),
        (OrderStatus.DRAFT, MANAGER, True),
        (OrderStatus.ORDERED, MANAGER, True),
    ],
)
def test_line_changes_past_requested_need_manage_orders(order_status, actor, changes_offered):
    context = OrderItemContext(order_status=order_status)
    actions = set(
        ORDER_ITEM_INTENTS.allowed_actions(_Item(OrderItemStatus.PENDING.value), context, actor)
    )
    assert (actions == _LINE_CHANGES) is changes_offered
    if not changes_offered:
        assert actions == set()
        refusal = ORDER_ITEM_INTENTS.check(
            A.CANCEL, _Item(OrderItemStatus.PENDING.value), context, actor
        )
        assert refusal is not None and refusal.kind == RefusalKind.PERMISSION
    partial = _Item(OrderItemStatus.PARTIALLY_DELIVERED.value, quantity_delivered=4.0)
    close_short = A.CLOSE_SHORT in ORDER_ITEM_INTENTS.allowed_actions(partial, context, actor)
    assert close_short is changes_offered


def test_a_made_line_takes_no_delivery_correction():
    made = _Item(
        OrderItemStatus.PARTIALLY_DELIVERED.value,
        line_type=OrderLineType.MADE.value,
        quantity_delivered=4.0,
    )
    actions = ORDER_ITEM_INTENTS.allowed_actions(made, _ORDERED_ORDER, MANAGER)
    assert A.CORRECT_DELIVERY not in actions
    assert A.DELIVER in actions


def test_a_line_closed_short_is_reopened_instead_of_corrected():
    closed = _Item(
        OrderItemStatus.DELIVERED.value,
        quantity_delivered=8.0,
        closed_short_at=datetime(2026, 10, 1, tzinfo=UTC),
    )

    actions = ORDER_ITEM_INTENTS.allowed_actions(closed, _ORDERED_ORDER, MANAGER)

    assert A.REOPEN in actions
    assert A.CORRECT_DELIVERY not in actions


def test_a_line_of_a_canceled_order_takes_neither_a_correction_nor_a_reopen():
    context = OrderItemContext(order_status=OrderStatus.CANCELED)
    delivered = _Item(OrderItemStatus.DELIVERED.value, quantity_delivered=10.0)
    closed = _Item(
        OrderItemStatus.DELIVERED.value,
        quantity_delivered=8.0,
        closed_short_at=datetime(2026, 10, 1, tzinfo=UTC),
    )

    assert A.CORRECT_DELIVERY not in ORDER_ITEM_INTENTS.allowed_actions(delivered, context, MANAGER)
    assert A.REOPEN not in ORDER_ITEM_INTENTS.allowed_actions(closed, context, MANAGER)


def test_a_made_line_closed_by_its_lot_is_not_reopened():
    made = _Item(
        OrderItemStatus.DELIVERED.value,
        line_type=OrderLineType.MADE.value,
        quantity_delivered=3.0,
        closed_short_at=datetime(2026, 10, 1, tzinfo=UTC),
    )

    assert A.REOPEN not in ORDER_ITEM_INTENTS.allowed_actions(made, _ORDERED_ORDER, MANAGER)


def test_order_item_is_not_deliverable_on_a_canceled_order():
    context = OrderItemContext(order_status=OrderStatus.CANCELED)
    refusal = ORDER_ITEM_INTENTS.check(
        A.DELIVER, _Item(OrderItemStatus.ORDERED.value), context, OTHER
    )
    assert refusal is not None and refusal.kind == RefusalKind.STATE


def test_made_line_is_not_deliverable_once_its_lot_is_canceled():
    context = OrderItemContext(order_status=OrderStatus.ORDERED, lot_canceled=True)
    made = _Item(OrderItemStatus.ORDERED.value, line_type=OrderLineType.MADE.value)
    bought = _Item(OrderItemStatus.ORDERED.value)
    assert ORDER_ITEM_INTENTS.check(A.DELIVER, made, context, OTHER) is not None
    assert ORDER_ITEM_INTENTS.check(A.DELIVER, bought, context, OTHER) is None


def test_order_item_with_lost_pieces_cannot_be_canceled():
    item = _Item(OrderItemStatus.ORDERED.value, quantity_rejected=2.0, quantity_rejected_lost=2.0)
    assert ORDER_ITEM_INTENTS.check(A.CANCEL, item, _ORDERED_ORDER, OTHER) is not None


def test_order_item_awaiting_redelivery_can_be_canceled_but_not_moved():
    item = _Item(OrderItemStatus.ORDERED.value, quantity_rejected=2.0)
    assert ORDER_ITEM_INTENTS.check(A.CANCEL, item, _ORDERED_ORDER, MANAGER) is None
    assert ORDER_ITEM_INTENTS.check(A.MOVE, item, _ORDERED_ORDER, MANAGER) is not None


def test_order_item_cannot_move_to_an_order_someone_canceled():
    item = _Item(OrderItemStatus.PENDING.value)
    to_canceled = OrderItemContext(order_status=OrderStatus.DRAFT, target_order_canceled=True)
    to_live = OrderItemContext(order_status=OrderStatus.DRAFT, target_order_canceled=False)
    assert ORDER_ITEM_INTENTS.check(A.MOVE, item, to_canceled, OTHER) is not None
    assert ORDER_ITEM_INTENTS.check(A.MOVE, item, to_live, OTHER) is None


def test_order_item_close_short_needs_something_settled():
    nothing = _Item(OrderItemStatus.ORDERED.value)
    only_lost = _Item(OrderItemStatus.PARTIALLY_DELIVERED.value, quantity_rejected_lost=1.0)
    assert ORDER_ITEM_INTENTS.check(A.CLOSE_SHORT, nothing, _ORDERED_ORDER, MANAGER) is not None
    assert ORDER_ITEM_INTENTS.check(A.CLOSE_SHORT, only_lost, _ORDERED_ORDER, MANAGER) is None


# ── Order ───────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (OrderStatus.DRAFT, _set(A.MARK_REQUESTED, A.MARK_ORDERED, A.CANCEL, A.EDIT, A.ADD_ITEM)),
        (OrderStatus.REQUESTED, _set(A.MARK_ORDERED, A.CANCEL, A.EDIT, A.ADD_ITEM)),
        (OrderStatus.ORDERED, _set(A.CANCEL, A.DELIVER, A.EDIT, A.ADD_ITEM)),
        (OrderStatus.PARTIALLY_DELIVERED, _set(A.CANCEL, A.DELIVER, A.EDIT, A.ADD_ITEM)),
        (OrderStatus.DELIVERED, _set(A.EDIT, A.ADD_ITEM)),
        # Every line canceled, but nobody canceled the order itself.
        (OrderStatus.CANCELED, _set(A.EDIT, A.ADD_ITEM)),
    ],
)
def test_order_actions_per_status_for_a_manager(status, expected):
    assert set(ORDER_INTENTS.allowed_actions(_Status(status.value), None, MANAGER)) == expected


def test_an_order_someone_canceled_takes_no_edit_and_no_new_line():
    canceled = _Status(OrderStatus.CANCELED.value, canceled_at=datetime(2026, 11, 1, tzinfo=UTC))
    assert set(ORDER_INTENTS.allowed_actions(canceled, None, MANAGER)) == set()


def test_ready_for_pickup_on_a_submitted_line_needs_manage_orders():
    ordered = _Item(OrderItemStatus.ORDERED.value)
    refusal = ORDER_ITEM_INTENTS.check(A.MARK_READY_FOR_PICKUP, ordered, _ORDERED_ORDER, OTHER)
    assert refusal is not None and refusal.kind == RefusalKind.PERMISSION
    assert (
        ORDER_ITEM_INTENTS.check(A.MARK_READY_FOR_PICKUP, ordered, _ORDERED_ORDER, MANAGER) is None
    )


def test_order_cancel_past_requested_needs_manage_orders():
    ordered = _Status(OrderStatus.ORDERED.value)
    refusal = ORDER_INTENTS.check(A.CANCEL, ordered, None, OTHER)
    assert refusal == IntentRefusal(
        A.CANCEL, RefusalKind.PERMISSION, "manage:orders once past REQUESTED"
    )
    assert ORDER_INTENTS.check(A.CANCEL, _Status(OrderStatus.DRAFT.value), None, OTHER) is None
    # REQUESTED is the last status a user without manage:orders may cancel
    # from; ORDERED above is the first that needs it.
    requested = _Status(OrderStatus.REQUESTED.value)
    assert ORDER_INTENTS.check(A.CANCEL, requested, None, OTHER) is None
    assert ORDER_INTENTS.check(A.CANCEL, ordered, None, MANAGER) is None


def test_check_reports_a_missing_permission_before_a_wrong_state():
    delivered = _Status(OrderStatus.DELIVERED.value)
    worker = ORDER_INTENTS.check(A.CANCEL, delivered, None, OTHER)
    manager = ORDER_INTENTS.check(A.CANCEL, delivered, None, MANAGER)
    assert worker is not None and worker.kind == RefusalKind.PERMISSION
    assert manager is not None and manager.kind == RefusalKind.STATE


# ── Production order ────────────────────────────────────────────────────


_STARTABLE = ProductionOrderContext(
    lot_held=False,
    lot_terminal=False,
    machine_resolvable=True,
    input_available=True,
    open_interruption=None,
)


def _po_context(**changes: object) -> ProductionOrderContext:
    return replace(_STARTABLE, **changes)


@pytest.mark.parametrize(
    ("status", "open_interruption", "expected"),
    [
        (ProductionOrderStatus.QUEUED, None, _set(A.START, A.CANCEL, A.SPLIT, A.MERGE)),
        (
            ProductionOrderStatus.IN_PROGRESS,
            None,
            _set(A.PAUSE, A.CANCEL, A.RECORD_COMPLETION, A.REVERSE_COMPLETION, A.SCRAP),
        ),
        (
            ProductionOrderStatus.PAUSED,
            InterruptionReason.MANUAL,
            _set(A.RESUME, A.CANCEL, A.REVERSE_COMPLETION),
        ),
        (
            ProductionOrderStatus.PAUSED,
            InterruptionReason.LOT_HOLD,
            _set(A.CANCEL, A.REVERSE_COMPLETION),
        ),
        (ProductionOrderStatus.COMPLETED, None, _set(A.REVERSE_COMPLETION)),
        (ProductionOrderStatus.CANCELED, None, set()),
    ],
)
def test_production_order_actions_per_status(status, open_interruption, expected):
    context = _po_context(open_interruption=open_interruption)
    actions = PRODUCTION_ORDER_INTENTS.allowed_actions(_Status(status.value), context, OTHER)
    assert set(actions) == expected


@pytest.mark.parametrize(
    "blocker",
    [
        {"lot_held": True},
        {"lot_terminal": True},
        {"machine_resolvable": False},
        {"input_available": False},
    ],
)
def test_production_order_start_needs_an_open_lot_a_machine_and_input(blocker):
    queued = _Status(ProductionOrderStatus.QUEUED.value)
    refusal = PRODUCTION_ORDER_INTENTS.check(A.START, queued, _po_context(**blocker), OTHER)
    assert refusal is not None and refusal.kind == RefusalKind.STATE


def test_production_order_resume_is_refused_while_the_lot_is_held():
    paused = _Status(ProductionOrderStatus.PAUSED.value)
    context = _po_context(open_interruption=InterruptionReason.MANUAL, lot_held=True)
    assert PRODUCTION_ORDER_INTENTS.check(A.RESUME, paused, context, OTHER) is not None


@pytest.mark.parametrize(
    ("action", "status"),
    [
        (A.RECORD_COMPLETION, ProductionOrderStatus.IN_PROGRESS),
        (A.SCRAP, ProductionOrderStatus.IN_PROGRESS),
        (A.REVERSE_COMPLETION, ProductionOrderStatus.IN_PROGRESS),
        (A.REVERSE_COMPLETION, ProductionOrderStatus.COMPLETED),
    ],
)
def test_production_order_work_on_a_held_lot_is_refused_until_it_resumes(action, status):
    order = _Status(status.value)
    held = PRODUCTION_ORDER_INTENTS.check(action, order, _po_context(lot_held=True), MANAGER)
    running = PRODUCTION_ORDER_INTENTS.check(action, order, _po_context(), MANAGER)
    assert held is not None and (held.kind, held.failed) == (RefusalKind.STATE, "lot not held")
    assert running is None


@pytest.mark.parametrize(
    "status",
    [
        ProductionOrderStatus.IN_PROGRESS,
        ProductionOrderStatus.PAUSED,
        ProductionOrderStatus.COMPLETED,
    ],
)
def test_production_order_reverse_completion_is_refused_on_a_finished_lot(status):
    order = _Status(status.value)
    context = _po_context(lot_terminal=True)

    refusal = PRODUCTION_ORDER_INTENTS.check(A.REVERSE_COMPLETION, order, context, MANAGER)

    assert refusal is not None
    assert (refusal.kind, refusal.failed) == (RefusalKind.STATE, "lot not terminal")
    assert A.REVERSE_COMPLETION not in PRODUCTION_ORDER_INTENTS.allowed_actions(
        order, context, MANAGER
    )


def test_production_order_reverse_completion_is_offered_on_state_alone():
    """manage:production_orders is the reversal's base permission, which the use
    case checks, so a user without it is offered the action and the client
    shows it disabled instead of hiding it."""
    completed = _Status(ProductionOrderStatus.COMPLETED.value)

    assert (
        PRODUCTION_ORDER_INTENTS.check(A.REVERSE_COMPLETION, completed, _po_context(), OTHER)
        is None
    )


def test_production_order_reverse_completion_keeps_the_use_case_conditions_in_its_text():
    rule = PRODUCTION_ORDER_INTENTS.rule_for(A.REVERSE_COMPLETION)
    assert rule is not None
    assert rule.condition.startswith(
        "lot not held; lot not terminal; the completion rejected nothing"
    )


# ── Lot position ────────────────────────────────────────────────────────


def _position_context(
    line: OrderItemStatus | None = None, remaining: float = 10.0, lot_terminal: bool = False
) -> LotPositionContext:
    return LotPositionContext(live_line_status=line, remaining=remaining, lot_terminal=lot_terminal)


@pytest.mark.parametrize(
    ("kind", "context", "expected"),
    [
        (
            LotPositionKind.UNASSIGNED,
            _position_context(),
            _set(A.ASSIGN_EXTERNAL, A.ASSIGN_INTERNAL),
        ),
        (
            LotPositionKind.INTERNAL,
            _position_context(remaining=4.0),
            _set(A.ASSIGN_EXTERNAL, A.ASSIGN_INTERNAL),
        ),
        (LotPositionKind.INTERNAL, _position_context(remaining=0.0), set()),
        (
            LotPositionKind.EXTERNAL,
            _position_context(OrderItemStatus.PENDING, remaining=0.0),
            _set(A.UNASSIGN_EXTERNAL, A.RECORD_PROVISION),
        ),
        (
            LotPositionKind.EXTERNAL,
            _position_context(OrderItemStatus.ORDERED, remaining=0.0),
            _set(A.RECORD_PROVISION),
        ),
        (
            LotPositionKind.MIXED,
            _position_context(OrderItemStatus.REQUESTED, remaining=2.0),
            _set(A.UNASSIGN_EXTERNAL, A.ASSIGN_INTERNAL, A.RECORD_PROVISION),
        ),
        (LotPositionKind.UNASSIGNED, _position_context(lot_terminal=True), set()),
    ],
)
def test_lot_position_actions(kind, context, expected):
    actions = LOT_POSITION_INTENTS.allowed_actions(_Position(kind.value), context, OTHER)
    assert set(actions) == expected


def test_assign_external_is_refused_while_a_live_line_exists():
    # Kind INTERNAL and remaining > 0 pass the other assign-external guards,
    # so only the live line refuses it. Unassign needs an EXTERNAL or MIXED
    # kind, so it is not offered either.
    position = _Position(LotPositionKind.INTERNAL.value)
    context = _position_context(OrderItemStatus.PENDING, remaining=4.0)
    actions = LOT_POSITION_INTENTS.allowed_actions(position, context, OTHER)
    assert set(actions) == _set(A.ASSIGN_INTERNAL)
    refusal = LOT_POSITION_INTENTS.check(A.ASSIGN_EXTERNAL, position, context, OTHER)
    assert refusal is not None and refusal.kind == RefusalKind.STATE


@pytest.mark.parametrize("kind", [LotPositionKind.EXTERNAL, LotPositionKind.MIXED])
def test_assign_external_takes_the_rest_of_a_line_closed_short(kind):
    position = _Position(kind.value)
    closed = LotPositionContext(
        live_line_status=OrderItemStatus.DELIVERED,
        live_line_closed_short=True,
        remaining=4.0,
        lot_terminal=False,
    )
    actions = set(LOT_POSITION_INTENTS.allowed_actions(position, closed, OTHER))
    assert _set(A.ASSIGN_EXTERNAL, A.ASSIGN_INTERNAL) <= actions
    assert A.UNASSIGN_EXTERNAL not in actions

    delivered = _position_context(OrderItemStatus.DELIVERED, remaining=4.0)
    assert A.ASSIGN_EXTERNAL not in set(
        LOT_POSITION_INTENTS.allowed_actions(position, delivered, OTHER)
    )


# ── Lot ─────────────────────────────────────────────────────────────────

_PRODUCED = LotContext(produced=4.0)


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (
            LotStatus.DRAFT,
            _set(
                A.CANCEL,
                A.FORCE_COMPLETE,
                A.SCRAP,
                A.EDIT_STRUCTURE,
                A.REORDER_POSITIONS,
                A.EDIT_QUANTITY,
                A.SWITCH_SOURCE,
            ),
        ),
        (
            LotStatus.IN_PROGRESS,
            _set(
                A.HOLD,
                A.CANCEL,
                A.FORCE_COMPLETE,
                A.SCRAP,
                A.EDIT_STRUCTURE,
                A.REORDER_POSITIONS,
                A.SWITCH_SOURCE,
            ),
        ),
        (
            LotStatus.ON_HOLD,
            _set(
                A.RESUME,
                A.CANCEL,
                A.FORCE_COMPLETE,
                A.EDIT_STRUCTURE,
                A.REORDER_POSITIONS,
                A.SWITCH_SOURCE,
            ),
        ),
        (LotStatus.COMPLETED, set()),
        (LotStatus.CANCELED, set()),
        (LotStatus.SCRAPPED, set()),
    ],
)
def test_lot_actions_per_status_for_a_manager(status, expected):
    actions = LOT_INTENTS.allowed_actions(_Lot(status.value), _PRODUCED, MANAGER)
    assert set(actions) == expected


@pytest.mark.parametrize(
    ("actor", "allowed"),
    [(CREATOR, False), (OTHER, False), (MANAGER, True)],
    ids=["creator", "other", "manager"],
)
def test_lot_cancel_needs_manage_lots(actor, allowed):
    refusal = LOT_INTENTS.check(A.CANCEL, _Lot(LotStatus.PLANNED.value), _PRODUCED, actor)
    if allowed:
        assert refusal is None
    else:
        assert refusal == IntentRefusal(A.CANCEL, RefusalKind.PERMISSION, "manage:lots")


def test_lot_force_complete_needs_manage_lots_and_produced_pieces():
    planned = _Lot(LotStatus.IN_PROGRESS.value)
    creator = LOT_INTENTS.check(A.FORCE_COMPLETE, planned, _PRODUCED, CREATOR)
    nothing_made = LOT_INTENTS.check(A.FORCE_COMPLETE, planned, LotContext(produced=0.0), MANAGER)
    assert creator is not None and creator.kind == RefusalKind.PERMISSION
    assert nothing_made is not None and nothing_made.kind == RefusalKind.STATE
    assert LOT_INTENTS.check(A.FORCE_COMPLETE, planned, _PRODUCED, MANAGER) is None


def test_lot_cancel_of_a_terminal_lot_by_another_user_is_a_permission_refusal():
    refusal = LOT_INTENTS.check(A.CANCEL, _Lot(LotStatus.COMPLETED.value), _PRODUCED, OTHER)
    assert refusal is not None and refusal.kind == RefusalKind.PERMISSION


@pytest.mark.parametrize(
    ("approval", "expected"),
    [
        (SourceApprovalStatus.NOT_REQUIRED, set()),
        (SourceApprovalStatus.PENDING, {A.APPROVE_SOURCE, A.REJECT_SOURCE}),
        (SourceApprovalStatus.APPROVED, set()),
        (SourceApprovalStatus.REJECTED, {A.APPROVE_SOURCE}),
    ],
)
def test_lot_source_decisions_follow_the_approval_status(approval, expected):
    context = LotContext(produced=0.0, source_approval_status=approval.value)
    actions = LOT_INTENTS.allowed_actions(_Lot(LotStatus.PLANNED.value), context, OTHER)
    assert set(actions) & {A.APPROVE_SOURCE, A.REJECT_SOURCE} == expected


@pytest.mark.parametrize("status", sorted(TERMINAL_LOT_STATUSES))
@pytest.mark.parametrize("action", [A.APPROVE_SOURCE, A.REJECT_SOURCE, A.SWITCH_SOURCE])
def test_lot_source_actions_are_refused_on_a_terminal_lot_by_status(status, action):
    context = LotContext(produced=0.0, source_approval_status=SourceApprovalStatus.PENDING.value)
    refusal = LOT_INTENTS.check(action, _Lot(status), context, MANAGER)
    assert refusal is not None and refusal.kind == RefusalKind.STATE and refusal.by_status


# ── Demand ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("status", "has_allocations", "expected"),
    [
        (
            BoughtItemDemandStatus.OPEN,
            False,
            _set(A.CANCEL, A.FULFIL, A.ALLOCATE, A.EDIT_QUANTITY, A.REMOVE),
        ),
        (
            BoughtItemDemandStatus.ALLOCATED,
            True,
            _set(A.CANCEL, A.FULFIL, A.ALLOCATE, A.EDIT_QUANTITY),
        ),
        (
            BoughtItemDemandStatus.ORDERED,
            True,
            _set(A.CANCEL, A.FULFIL, A.ALLOCATE, A.EDIT_QUANTITY),
        ),
        (BoughtItemDemandStatus.FULFILLED, True, set()),
        (BoughtItemDemandStatus.FULFILLED, False, _set(A.REMOVE)),
        (BoughtItemDemandStatus.CANCELED, False, _set(A.REMOVE)),
    ],
)
def test_demand_actions_per_status(status, has_allocations, expected):
    context = DemandContext(has_allocations=has_allocations)
    actions = DEMAND_INTENTS.allowed_actions(_Status(status.value), context, OTHER)
    assert set(actions) == expected


@pytest.mark.parametrize(
    "status",
    [
        BoughtItemDemandStatus.OPEN,
        BoughtItemDemandStatus.ALLOCATED,
        BoughtItemDemandStatus.ORDERED,
    ],
)
def test_a_demand_whose_lot_started_is_not_canceled(status):
    context = DemandContext(has_allocations=True, lot_started=True)
    demand = _Status(status.value)
    assert A.CANCEL not in DEMAND_INTENTS.allowed_actions(demand, context, OTHER)
    refusal = DEMAND_INTENTS.check(A.CANCEL, demand, context, OTHER)
    assert refusal is not None
    assert (refusal.kind, refusal.failed, refusal.by_status) == (
        RefusalKind.STATE,
        "lot not started",
        False,
    )


# ── check() ─────────────────────────────────────────────────────────────


def test_check_refuses_an_action_the_aggregate_does_not_have():
    refusal = ORDER_INTENTS.check(A.HOLD, _Status(OrderStatus.DRAFT.value), None, MANAGER)
    assert refusal == IntentRefusal(A.HOLD, RefusalKind.STATE, "hold is not an action of order")


def test_check_states_the_requirement_of_a_state_refusal():
    item = _Item(OrderItemStatus.DELIVERED.value, quantity_delivered=10.0)
    refusal = ORDER_ITEM_INTENTS.check(A.CANCEL, item, _ORDERED_ORDER, MANAGER)
    assert refusal == IntentRefusal(
        A.CANCEL,
        RefusalKind.STATE,
        "status pending or requested or ordered; no delivery and no lost pieces",
        failed="status pending or requested or ordered",
        by_status=True,
    )


def test_a_state_refusal_names_the_condition_that_fails():
    item = _Item(OrderItemStatus.ORDERED.value, quantity_delivered=2.0)
    refusal = ORDER_ITEM_INTENTS.check(A.CANCEL, item, _ORDERED_ORDER, MANAGER)
    assert refusal is not None
    assert (refusal.failed, refusal.by_status) == ("no delivery and no lost pieces", False)
    assert refusal.message("Order item #1", "ordered", "cancel") == (
        "Order item #1 is ordered, but to cancel it needs no delivery and no lost pieces."
    )


def test_a_rule_of_several_checks_names_the_first_that_fails():
    line = _Item(OrderItemStatus.DELIVERED.value, quantity_delivered=10.0)
    canceled_order = OrderItemContext(order_status=OrderStatus.CANCELED)
    refusal = ORDER_ITEM_INTENTS.check(A.CORRECT_DELIVERY, line, canceled_order, MANAGER)
    assert refusal is not None
    assert refusal.failed == "order not CANCELED"
    rule = ORDER_ITEM_INTENTS.rule_for(A.CORRECT_DELIVERY)
    assert rule is not None
    assert rule.condition == "not a MADE line; not closed short; order not CANCELED"


# ── Every rule is reachable ─────────────────────────────────────────────

_ACTORS = (CREATOR, OTHER, MANAGER)
_CLOSED_AT = datetime(2026, 10, 1, tzinfo=UTC)


def _order_item_cases():
    items = [
        _Item(
            status.value,
            line_type=line_type.value,
            quantity_delivered=delivered,
            quantity_rejected_lost=lost,
            closed_short_at=closed_at,
        )
        for status, line_type, delivered, lost, closed_at in product(
            OrderItemStatus,
            (OrderLineType.BOUGHT, OrderLineType.MADE),
            (0.0, 4.0),
            (0.0, 1.0),
            (None, _CLOSED_AT),
        )
    ]
    contexts = [
        OrderItemContext(
            order_status=order_status,
            lot_canceled=lot_canceled,
            target_order_canceled=target_canceled,
        )
        for order_status, lot_canceled, target_canceled in product(
            OrderStatus, (False, True), (False, True)
        )
    ]
    return ORDER_ITEM_INTENTS, product(items, contexts, _ACTORS)


def _order_cases():
    return ORDER_INTENTS, product([_Status(s.value) for s in OrderStatus], [None], _ACTORS)


def _production_order_cases():
    contexts = [
        ProductionOrderContext(
            lot_held=held,
            lot_terminal=terminal,
            machine_resolvable=machine,
            input_available=available,
            open_interruption=interruption,
        )
        for held, terminal, machine, available, interruption in product(
            (False, True), (False, True), (False, True), (False, True), (None, *InterruptionReason)
        )
    ]
    subjects = [_Status(s.value) for s in ProductionOrderStatus]
    return PRODUCTION_ORDER_INTENTS, product(subjects, contexts, _ACTORS)


def _lot_position_cases():
    contexts = [
        LotPositionContext(live_line_status=line, remaining=remaining, lot_terminal=terminal)
        for line, remaining, terminal in product(
            (None, *OrderItemStatus), (0.0, 4.0), (False, True)
        )
    ]
    subjects = [_Position(kind.value) for kind in LotPositionKind]
    return LOT_POSITION_INTENTS, product(subjects, contexts, _ACTORS)


def _lot_cases():
    subjects = [_Lot(s.value) for s in LotStatus]
    contexts = [
        LotContext(produced=produced, source_approval_status=approval.value)
        for produced, approval in product((0.0, 4.0), SourceApprovalStatus)
    ]
    return LOT_INTENTS, product(subjects, contexts, _ACTORS)


def _demand_cases():
    subjects = [_Status(s.value) for s in BoughtItemDemandStatus]
    contexts = [
        DemandContext(has_allocations=allocated, lot_started=started)
        for allocated, started in product((False, True), (False, True))
    ]
    return DEMAND_INTENTS, product(subjects, contexts, _ACTORS)


@pytest.mark.parametrize(
    "cases",
    [
        _order_item_cases,
        _order_cases,
        _production_order_cases,
        _lot_position_cases,
        _lot_cases,
        _demand_cases,
    ],
    ids=lambda fn: fn.__name__.strip("_").removesuffix("_cases"),
)
def test_every_intent_rule_is_reachable_and_check_agrees(cases):
    table, combinations = cases()
    reached = set()
    for subject, context, actor in combinations:
        allowed = table.allowed_actions(subject, context, actor)
        reached.update(allowed)
        for rule in table.rules:
            refusal = table.check(rule.action, subject, context, actor)
            assert (refusal is None) == (rule.action in allowed)
    assert reached == {rule.action for rule in table.rules}


@pytest.mark.parametrize(
    "cases",
    [_order_item_cases, _order_cases, _lot_cases],
    ids=lambda fn: fn.__name__.strip("_").removesuffix("_cases"),
)
def test_an_action_is_blocked_exactly_when_only_the_actor_guard_refuses_it(cases):
    """A blocked action is one the state allows but the actor may not take,
    so it is never also allowed, and it names the permission the rule needs."""
    table, combinations = cases()
    blocked_somewhere = set()
    for subject, context, actor in combinations:
        allowed = table.allowed_actions(subject, context, actor)
        blocked = table.blocked_actions(subject, context, actor)
        blocked_somewhere.update(blocked)
        assert set(blocked).isdisjoint(allowed)
        for rule in table.rules:
            refusal = table.check(rule.action, subject, context, actor)
            expected = (
                refusal is not None
                and refusal.kind is RefusalKind.PERMISSION
                and rule.state_allows(subject, context)
            )
            assert (rule.action in blocked) == expected
            if expected:
                assert blocked[rule.action] == rule.needs
    assert blocked_somewhere == {rule.action for rule in table.rules if rule.needs}


def test_a_rule_with_an_actor_guard_must_name_the_permission_it_needs():
    with pytest.raises(ValueError, match="needs"):
        IntentRule[HasStatus, None](
            action=A.CANCEL,
            allowed_from=None,
            effect="",
            permission="manage:orders",
            permitted=lambda actor, _subject, _context: actor.has_permission("manage:orders"),
        )
