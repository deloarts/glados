"""
Unit tests for how the forward walk places manual orders without a machine.
Each one is placed on its own against the admin default calendar, so manual
orders take no capacity from each other, queue_sequence changes no date, and
a manual order never takes part in a wait cycle through a shared queue.
"""

from dataclasses import replace
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta

from src.modules.fulfillment.domain.services.scheduling import EarliestStartExplanation
from src.modules.fulfillment.domain.services.scheduling import PredecessorPosition
from src.modules.fulfillment.domain.services.scheduling import build_machine_calendar
from src.modules.fulfillment.domain.services.scheduling import explain_earliest_start
from src.modules.fulfillment.domain.services.scheduling import schedule_all
from src.modules.fulfillment.domain.services.scheduling import schedule_all_propagated
from src.modules.fulfillment.domain.services.scheduling._shared import day_start
from src.modules.fulfillment.domain.services.scheduling.machine_calendar import place
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.schedule_conflict import ScheduleConflictReason
from tests.unit.scheduling_service._helpers import MONDAY
from tests.unit.scheduling_service._helpers import WEEKDAY_HOURS
from tests.unit.scheduling_service._helpers import make_context

# 2026-11-25 is a Wednesday.
NOW = datetime(2026, 11, 25, 8, 28, tzinfo=UTC)


def _calendar():
    return build_machine_calendar(WEEKDAY_HOURS, None, {})


def _walk_manual(orders, now=NOW):
    calendar = _calendar()
    result = schedule_all(
        machine_queues={},
        machine_calendars={},
        pool_queues={},
        pool_members={},
        manual_queue=orders,
        manual_calendar=calendar,
        unassigned=[],
        now=now,
    )
    return {s.order_id: s for s in result.manual}, calendar


def test_manual_orders_without_constraints_all_start_now():
    """Two manual orders with nothing holding them back both start now,
    instead of the second one waiting for the first one's end."""
    orders = [
        make_context(order_id=1, queue_sequence=1, is_manual_step=True),
        make_context(order_id=2, queue_sequence=2, is_manual_step=True),
    ]
    placed, calendar = _walk_manual(orders)
    expected_start, _ = place(NOW, 60, calendar)
    assert placed[1].planned_start == expected_start
    assert placed[2].planned_start == expected_start


def test_a_blocked_manual_order_delays_only_its_own_lot():
    """Three inspections in queue order: two wait for deliveries (ready on
    Friday 2026-12-11 and Monday 2026-12-07), the third has nothing open
    before it. The third is dated now, and the one ready on Monday is no
    longer held behind the one ready on Friday."""
    friday = date(2026, 12, 11)
    monday = date(2026, 12, 7)
    orders = [
        make_context(
            order_id=2,
            queue_sequence=1,
            is_manual_step=True,
            position_sequence=2,
            estimated_duration_minutes=15,
            predecessor_ready_at=friday,
        ),
        make_context(
            order_id=4,
            queue_sequence=2,
            is_manual_step=True,
            position_sequence=2,
            estimated_duration_minutes=15,
            predecessor_ready_at=monday,
        ),
        make_context(
            order_id=6,
            queue_sequence=3,
            is_manual_step=True,
            position_sequence=2,
            estimated_duration_minutes=15,
        ),
    ]
    placed, calendar = _walk_manual(orders)

    assert placed[6].planned_start == place(NOW, 15, calendar)[0]
    assert placed[4].planned_start == place(day_start(monday, UTC), 15, calendar)[0]
    assert placed[2].planned_start == place(day_start(friday, UTC), 15, calendar)[0]


def test_a_pinned_manual_window_pushes_no_other_manual_order():
    """A pinned manual order keeps its window, and the manual order queued
    after it starts now rather than after that window. Neither is flagged
    as an overlap, since manual orders share no queue."""
    pinned_start = NOW + timedelta(hours=1)
    pinned_end = NOW + timedelta(hours=3)
    orders = [
        make_context(
            order_id=1,
            queue_sequence=1,
            is_manual_step=True,
            pinned=True,
            existing_planned_start=pinned_start,
            existing_planned_end=pinned_end,
        ),
        make_context(order_id=2, queue_sequence=2, is_manual_step=True),
    ]
    placed, calendar = _walk_manual(orders)

    assert placed[1].planned_start == pinned_start
    assert placed[1].planned_end == pinned_end
    assert placed[2].planned_start == place(NOW, 60, calendar)[0]
    for order_id in (1, 2):
        assert ScheduleConflictReason.WINDOW_OVERLAP.value not in placed[order_id].conflicts


def test_a_manual_step_queued_ahead_of_its_predecessor_is_no_cycle():
    """Position 2 of a lot sits ahead of position 1 in the manual queue.
    On a shared line this was a wait cycle that left both undated; now
    position 1 is placed now and position 2 after it."""
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time(), tzinfo=UTC)
    position_1 = replace(
        make_context(order_id=1, queue_sequence=2, is_manual_step=True),
        lot_id=1,
        lot_position_id=10,
    )
    position_2 = replace(
        make_context(
            order_id=2,
            queue_sequence=1,
            is_manual_step=True,
            position_sequence=2,
            predecessor_ready_at=MONDAY,
        ),
        lot_id=1,
        lot_position_id=20,
        predecessor_positions=(
            PredecessorPosition(
                position_id=10,
                sequence=1,
                kind=LotPositionKind.INTERNAL.value,
                external_ready_at=None,
                stored_internal_ready_at=MONDAY,
            ),
        ),
    )

    result, _ = schedule_all_propagated(
        machine_queues={},
        machine_calendars={},
        pool_queues={},
        pool_members={},
        manual_queue=[position_2, position_1],
        manual_calendar=calendar,
        unassigned=[],
        now=now,
    )
    placed = {s.order_id: s for s in result.manual}

    assert placed[1].planned_start == place(now, 60, calendar)[0]
    assert placed[1].planned_end is not None
    assert placed[2].planned_start is not None
    assert placed[2].planned_start >= placed[1].planned_end
    for order_id in (1, 2):
        assert ScheduleConflictReason.CHAIN_CYCLE.value not in placed[order_id].conflicts


def test_a_manual_order_off_any_queue_is_never_explained_by_the_queue():
    """A manual order dated after its constraint day is explained by that
    constraint when it waits behind no other order, while an order on a
    machine queue keeps the `queue` reason."""
    ready = MONDAY - timedelta(days=3)
    ctx = make_context(
        is_manual_step=True,
        position_sequence=2,
        predecessor_ready_at=ready,
        existing_planned_start=datetime.combine(MONDAY, datetime.min.time(), tzinfo=UTC),
    )
    assert explain_earliest_start(ctx, on_queue=False) == EarliestStartExplanation(
        "predecessor", ready
    )
    assert explain_earliest_start(ctx) == EarliestStartExplanation("queue", ready)
