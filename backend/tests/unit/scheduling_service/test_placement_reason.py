"""
The walk names what set each order's start: the order ahead on its queue,
an in-house predecessor and its wait, the order line of an external step and
whether it is late, not_before, or nothing beyond now; and for a running,
pinned or undated order a reason of its own.
"""

from dataclasses import replace
from datetime import UTC
from datetime import datetime
from datetime import time
from datetime import timedelta

from src.modules.fulfillment.domain.services.scheduling import PredecessorPosition
from src.modules.fulfillment.domain.services.scheduling import build_machine_calendar
from src.modules.fulfillment.domain.services.scheduling import schedule_all_propagated
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from tests.unit.scheduling_service._helpers import MONDAY
from tests.unit.scheduling_service._helpers import TUESDAY
from tests.unit.scheduling_service._helpers import WEEKDAY_HOURS
from tests.unit.scheduling_service._helpers import make_context

CALENDAR = build_machine_calendar(WEEKDAY_HOURS, None, {})
NOW = datetime.combine(MONDAY, time(8), tzinfo=UTC)


def _reasons(machine_queues=None, manual_queue=()):
    machine_queues = machine_queues or {}
    result, _ = schedule_all_propagated(
        machine_queues=machine_queues,
        machine_calendars={m: CALENDAR for m in machine_queues},
        pool_queues={},
        pool_members={},
        manual_queue=list(manual_queue),
        manual_calendar=CALENDAR,
        unassigned=[],
        now=NOW,
    )
    return {s.order_id: s.reason for s in result.all_orders()}


def _successor(*predecessors, **values):
    return replace(
        make_context(order_id=2, position_sequence=2, is_manual_step=True),
        lot_id=1,
        lot_position_id=20,
        predecessor_positions=predecessors,
        **values,
    )


def test_an_order_behind_another_on_its_queue_names_it():
    first = make_context(order_id=1, queue_sequence=1, estimated_duration_minutes=120)
    second = make_context(order_id=2, queue_sequence=2, estimated_duration_minutes=60)
    reasons = _reasons({1: [first, second]})

    assert reasons[1].kind == "ready_now"
    assert reasons[2].kind == "queue"
    assert reasons[2].previous_order_id == 1


def test_an_order_after_an_in_house_step_names_it_and_its_wait():
    curing = replace(
        make_context(order_id=1, estimated_duration_minutes=60),
        lot_id=1,
        lot_position_id=10,
        wait_after_minutes=180,
    )
    predecessor = PredecessorPosition(
        position_id=10,
        sequence=1,
        kind=LotPositionKind.INTERNAL.value,
        external_ready_at=None,
        stored_internal_ready_at=None,
        wait_after_minutes=180,
    )
    reasons = _reasons({1: [curing]}, [_successor(predecessor)])

    assert reasons[2].kind == "predecessor"
    assert reasons[2].position_id == 10
    assert reasons[2].wait_after_minutes == 180


def test_an_order_after_a_late_order_line_names_the_line_and_that_it_is_late():
    line = PredecessorPosition(
        position_id=10,
        sequence=1,
        kind=LotPositionKind.EXTERNAL.value,
        external_ready_at=TUESDAY,
        stored_internal_ready_at=None,
        typed_external_date=MONDAY - timedelta(days=5),
        order_item_id=46,
        arrival_late=True,
    )
    reasons = _reasons(manual_queue=[_successor(line, predecessor_ready_at=TUESDAY)])

    assert reasons[2].kind == "order_line"
    assert reasons[2].order_item_id == 46
    assert reasons[2].late is True
    assert reasons[2].expected_date == MONDAY - timedelta(days=5)


def test_a_not_before_day_names_itself():
    later = MONDAY + timedelta(days=3)
    reasons = _reasons({1: [make_context(order_id=1, not_before=later)]})
    assert reasons[1].kind == "not_before"
    assert reasons[1].day == later


def test_a_running_order_that_overruns_says_so():
    running = replace(
        make_context(
            order_id=1,
            status="in_progress",
            actual_start=datetime.combine(MONDAY - timedelta(days=3), time(8), tzinfo=UTC),
            estimated_duration_minutes=60,
        ),
        quantity=10.0,
        pieces_processed=6.0,
        minutes_per_piece=30.0,
    )
    reason = _reasons({1: [running]})[1]
    assert reason.kind == "in_progress"
    assert reason.overrun is True
    assert (reason.pieces_processed, reason.quantity) == (6.0, 10.0)


def test_a_pinned_and_an_undated_order_get_their_own_reasons():
    start = datetime.combine(TUESDAY, time(9), tzinfo=UTC)
    pinned = make_context(
        order_id=1,
        pinned=True,
        existing_planned_start=start,
        existing_planned_end=start + timedelta(hours=1),
    )
    waiting = make_context(
        order_id=2, queue_sequence=2, upstream_input_available=False, material_ready_at=None
    )
    reasons = _reasons({1: [pinned, waiting]})
    assert reasons[1].kind == "pinned"
    assert reasons[2].kind == "undated"
