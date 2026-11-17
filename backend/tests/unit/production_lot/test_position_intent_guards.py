"""
The lot position use cases decide through the lot position intent table
(lifecycle/intents.py LOT_POSITION_INTENTS): lot_position_refusal says
which requirement of an action failed, in the order its use case has
always reported them, and lot_position_context builds the table's context
from a position and its lot. The actions a position response offers are
therefore the ones its use cases accept.
"""

from datetime import UTC
from datetime import datetime
from types import SimpleNamespace
from typing import cast

import pytest

from src.modules.fulfillment.domain.entities.lot_position import LotPosition
from src.modules.fulfillment.domain.entities.order_item import OrderItem
from src.modules.fulfillment.domain.services.lifecycle.intents import LOT_POSITION_INTENTS
from src.modules.fulfillment.domain.services.lot_rules import PositionRefusal
from src.modules.fulfillment.domain.services.lot_rules import lot_position_context
from src.modules.fulfillment.domain.services.lot_rules import lot_position_refusal
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction
from tests.unit.lifecycle.test_intents import _user

ACTOR = _user(2)
A = LifecycleAction


def _position(
    kind: LotPositionKind, *, line: OrderItemStatus = "", line_quantity: float | None = None
) -> LotPosition:
    return LotPosition(
        id=1,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=None,
        changes=[],
        sequence=1,
        kind=kind,
        status=LotPositionStatus.PENDING,
        quantity=5.0,
        quantity_completed=0.0,
        note=None,
        creator_id=1,
        lot_id=1,
        order_item_status=line,
        order_item_quantity=line_quantity,
    )


def test_the_context_reads_the_live_line_the_remaining_quantity_and_the_lot():
    position = _position(LotPositionKind.EXTERNAL, line=OrderItemStatus.PENDING, line_quantity=3.0)

    context = lot_position_context(position, "planned")

    assert context.live_line_status == OrderItemStatus.PENDING
    assert context.remaining == pytest.approx(2.0)
    assert context.lot_terminal is False
    assert lot_position_context(position, "scrapped").lot_terminal is True


def _line(status: str, *, closed_short: bool = False) -> OrderItem:
    line = SimpleNamespace(
        status=status, closed_short_at=datetime(2026, 1, 2, tzinfo=UTC) if closed_short else None
    )
    return cast(OrderItem, line)


def test_a_fresher_live_line_read_under_the_lock_wins_over_the_stored_one():
    position = _position(LotPositionKind.EXTERNAL, line=OrderItemStatus.PENDING, line_quantity=3.0)

    ordered = lot_position_context(position, "planned", _line("ordered"))
    assert ordered.live_line_status == OrderItemStatus.ORDERED
    assert ordered.live_line_closed_short is False
    assert lot_position_context(position, "planned", None).live_line_status is None
    closed = lot_position_context(position, "planned", _line("delivered", closed_short=True))
    assert (closed.live_line_status, closed.live_line_closed_short) == (
        OrderItemStatus.DELIVERED,
        True,
    )


R = PositionRefusal
_FREE = _position(LotPositionKind.UNASSIGNED)
_FULL = _position(LotPositionKind.UNASSIGNED, line_quantity=5.0)
_PENDING_LINE = _position(LotPositionKind.EXTERNAL, line=OrderItemStatus.PENDING, line_quantity=5.0)
_ORDERED_LINE = _position(LotPositionKind.EXTERNAL, line=OrderItemStatus.ORDERED, line_quantity=5.0)


@pytest.mark.parametrize(
    ("action", "position", "lot_status", "expected"),
    [
        (A.ASSIGN_EXTERNAL, _FREE, "planned", None),
        (A.ASSIGN_EXTERNAL, _PENDING_LINE, "completed", R.KIND),
        (A.ASSIGN_EXTERNAL, _FREE, "canceled", R.LOT_TERMINAL),
        (
            A.ASSIGN_EXTERNAL,
            _position(LotPositionKind.INTERNAL, line=OrderItemStatus.PENDING, line_quantity=1.0),
            "planned",
            R.LIVE_LINE,
        ),
        (A.ASSIGN_EXTERNAL, _FULL, "planned", R.NOTHING_REMAINING),
        (
            A.ASSIGN_INTERNAL,
            _position(LotPositionKind.EXTERNAL, line=OrderItemStatus.ORDERED, line_quantity=2.0),
            "planned",
            None,
        ),
        (A.ASSIGN_INTERNAL, _FULL, "completed", R.LOT_TERMINAL),
        (A.ASSIGN_INTERNAL, _FULL, "planned", R.NOTHING_REMAINING),
        (
            A.UNASSIGN_EXTERNAL,
            _position(LotPositionKind.MIXED, line=OrderItemStatus.REQUESTED, line_quantity=2.0),
            "planned",
            None,
        ),
        (A.UNASSIGN_EXTERNAL, _position(LotPositionKind.INTERNAL), "planned", R.KIND),
        (A.UNASSIGN_EXTERNAL, _ORDERED_LINE, "planned", R.LINE_PLACED),
        (A.RECORD_PROVISION, _ORDERED_LINE, "planned", None),
        (A.RECORD_PROVISION, _position(LotPositionKind.INTERNAL), "planned", R.KIND),
    ],
)
def test_the_refusal_names_the_first_failed_requirement(action, position, lot_status, expected):
    context = lot_position_context(position, lot_status)

    refusal = lot_position_refusal(action, position, context, ACTOR)

    assert refusal is expected
    allowed = action in LOT_POSITION_INTENTS.allowed_actions(position, context, ACTOR)
    assert allowed is (expected is None)
