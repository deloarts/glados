"""
Unit tests for schedule_all, the unified walk. No database, no HTTP, pure
functions only.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta

import pytest

from src.modules.fulfillment.domain.services.scheduling import ScheduledOrder
from src.modules.fulfillment.domain.services.scheduling import ScheduleWalkResult
from src.modules.fulfillment.domain.services.scheduling import build_machine_calendar
from src.modules.fulfillment.domain.services.scheduling import schedule_all
from src.modules.fulfillment.domain.services.scheduling import schedule_unassigned_orders
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.schedule_conflict import ScheduleConflictReason
from tests.unit.scheduling_service._helpers import MONDAY
from tests.unit.scheduling_service._helpers import WEEKDAY_HOURS
from tests.unit.scheduling_service._helpers import make_context
from tests.unit.scheduling_service._helpers import walk_machine_queue


def test_schedule_all_machine_assigned_running_and_pinned_orders_push_the_pool_floater_later():
    """A pool floater sharing a member with that member's own
    machine-assigned queue must never be placed as if that queue didn't
    exist. It has to queue behind both the running order (anchored to
    actual_start) and the pinned order's manual window."""
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    actual_start = datetime.combine(MONDAY, datetime.min.time(), tzinfo=UTC) + timedelta(hours=8)
    pinned_start = datetime.combine(MONDAY, datetime.min.time(), tzinfo=UTC) + timedelta(hours=10)
    pinned_end = datetime.combine(MONDAY, datetime.min.time(), tzinfo=UTC) + timedelta(hours=11)
    running_order = make_context(
        order_id=1,
        queue_sequence=1,
        status=ProductionOrderStatus.IN_PROGRESS.value,
        actual_start=actual_start,
        estimated_duration_minutes=60,
    )
    pinned_order = make_context(
        order_id=2,
        queue_sequence=2,
        pinned=True,
        existing_planned_start=pinned_start,
        existing_planned_end=pinned_end,
    )
    floating_order = make_context(order_id=3, queue_sequence=1, estimated_duration_minutes=60)

    result = schedule_all(
        machine_queues={1: [running_order, pinned_order]},
        machine_calendars={1: calendar},
        pool_queues={10: [floating_order]},
        pool_members={10: [1]},
        manual_queue=[],
        manual_calendar=calendar,
        unassigned=[],
        now=now,
    )

    floated = result.by_pool[10][0]
    assert floated.planned_start == pinned_end  # queues behind both machine-assigned orders
    assert floated.planned_end == pinned_end + timedelta(hours=1)
    assert floated.trial_machine_id == 1
    assert result.machine_cursors[1] == floated.planned_end


def test_schedule_all_paused_machine_order_leaves_the_cursor_free_for_the_pool_floater():
    """A PAUSED machine-assigned order consumes no capacity. A pool
    floater sharing that member must still land at the top of the day, not
    behind a phantom reservation."""
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    paused_order = make_context(
        order_id=1,
        queue_sequence=1,
        status=ProductionOrderStatus.PAUSED.value,
        estimated_duration_minutes=120,
    )
    floating_order = make_context(order_id=2, queue_sequence=1, estimated_duration_minutes=60)

    result = schedule_all(
        machine_queues={1: [paused_order]},
        machine_calendars={1: calendar},
        pool_queues={10: [floating_order]},
        pool_members={10: [1]},
        manual_queue=[],
        manual_calendar=calendar,
        unassigned=[],
        now=now,
    )

    assert result.by_machine[1][0].planned_start is None  # the paused order itself stays dateless
    floated = result.by_pool[10][0]
    assert floated.planned_start.hour == 8  # not pushed by the paused order


def test_schedule_all_two_pools_sharing_a_member_never_overlap_and_earliest_finish_goes_first():
    """Pool 2's head (30 minutes) finishes strictly earlier than pool 1's
    head (120 minutes) would, so the merge must commit pool 2 first and
    then place pool 1's order after it, never overlapping on their shared
    member."""
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    pool_1_order = make_context(order_id=1, queue_sequence=1, estimated_duration_minutes=120)
    pool_2_order = make_context(order_id=2, queue_sequence=1, estimated_duration_minutes=30)

    result = schedule_all(
        machine_queues={},
        machine_calendars={1: calendar},
        pool_queues={1: [pool_1_order], 2: [pool_2_order]},
        pool_members={1: [1], 2: [1]},
        manual_queue=[],
        manual_calendar=calendar,
        unassigned=[],
        now=now,
    )

    pool_2_result = result.by_pool[2][0]
    pool_1_result = result.by_pool[1][0]
    assert pool_2_result.planned_start.hour == 8
    assert pool_2_result.planned_end == pool_2_result.planned_start + timedelta(minutes=30)
    # Pool 1's order queues in behind pool 2's, not overlapping it.
    assert pool_1_result.planned_start == pool_2_result.planned_end
    assert pool_1_result.planned_end == pool_1_result.planned_start + timedelta(hours=2)
    assert result.machine_cursors[1] == pool_1_result.planned_end


def test_schedule_all_dateless_pool_head_does_not_block_its_own_pool_or_the_other_one():
    """A PAUSED head at the front of pool 1's queue must be committed
    immediately (dateless) without stalling pool 1's own next order, and
    without stalling pool 2's unrelated order either."""
    calendar_1 = build_machine_calendar(WEEKDAY_HOURS, None, {})
    calendar_2 = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    paused_head = make_context(
        order_id=1,
        queue_sequence=1,
        status=ProductionOrderStatus.PAUSED.value,
        estimated_duration_minutes=60,
    )
    next_in_pool_1 = make_context(order_id=2, queue_sequence=2, estimated_duration_minutes=60)
    pool_2_order = make_context(order_id=3, queue_sequence=1, estimated_duration_minutes=30)

    result = schedule_all(
        machine_queues={},
        machine_calendars={1: calendar_1, 2: calendar_2},
        pool_queues={1: [paused_head, next_in_pool_1], 2: [pool_2_order]},
        pool_members={1: [1], 2: [2]},
        manual_queue=[],
        manual_calendar=calendar_1,
        unassigned=[],
        now=now,
    )

    paused_result = {r.order_id: r for r in result.by_pool[1]}[1]
    assert paused_result.planned_start is None
    assert paused_result.trial_machine_id is None
    next_result = {r.order_id: r for r in result.by_pool[1]}[2]
    assert next_result.planned_start.hour == 8  # not pushed by the dateless order ahead of it
    pool_2_result = result.by_pool[2][0]
    assert pool_2_result.planned_start.hour == 8  # unaffected by pool 1 entirely


def test_schedule_all_pool_with_no_members_degrades_to_unassigned_flags():
    order = make_context(order_id=1, machine_pool_id=5)
    result = schedule_all(
        machine_queues={},
        machine_calendars={},
        pool_queues={5: [order]},
        pool_members={},
        manual_queue=[],
        manual_calendar=build_machine_calendar(WEEKDAY_HOURS, None, {}),
        unassigned=[],
        now=datetime.now(UTC),
    )
    expected = schedule_unassigned_orders([order])
    assert result.by_pool[5][0].planned_start is None
    assert result.by_pool[5][0].conflicts == expected[0].conflicts
    assert ScheduleConflictReason.NO_MACHINE_ASSIGNED.value not in result.by_pool[5][0].conflicts


def test_schedule_all_machine_cursor_equals_the_last_committed_planned_end():
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    orders = [
        make_context(order_id=1, queue_sequence=1, estimated_duration_minutes=120),
        make_context(order_id=2, queue_sequence=2, estimated_duration_minutes=60),
    ]
    result = schedule_all(
        machine_queues={1: orders},
        machine_calendars={1: calendar},
        pool_queues={},
        pool_members={},
        manual_queue=[],
        manual_calendar=calendar,
        unassigned=[],
        now=now,
    )
    assert result.machine_cursors[1] == result.by_machine[1][-1].planned_end


def test_schedule_all_tie_break_by_order_id_when_queue_sequence_matches():
    """Two machine-assigned orders sharing a queue_sequence must still
    place deterministically by order_id, regardless of input list order,
    the determinism guard, exercised through schedule_all."""
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    orders = [
        make_context(order_id=5, queue_sequence=1, estimated_duration_minutes=60),
        make_context(order_id=3, queue_sequence=1, estimated_duration_minutes=60),
    ]
    result = schedule_all(
        machine_queues={1: orders},
        machine_calendars={1: calendar},
        pool_queues={},
        pool_members={},
        manual_queue=[],
        manual_calendar=calendar,
        unassigned=[],
        now=now,
    )
    results = {r.order_id: r for r in result.by_machine[1]}
    assert results[3].planned_start.hour == 8  # lower order_id wins the tie, goes first
    assert results[5].planned_start == results[3].planned_end


def test_schedule_all_raises_value_error_for_a_machine_queue_with_no_calendar():
    order = make_context(order_id=1)
    with pytest.raises(ValueError, match="99"):
        schedule_all(
            machine_queues={99: [order]},
            machine_calendars={},
            pool_queues={},
            pool_members={},
            manual_queue=[],
            manual_calendar=build_machine_calendar(WEEKDAY_HOURS, None, {}),
            unassigned=[],
            now=datetime.now(UTC),
        )


def test_schedule_all_manual_and_unassigned_match_their_standalone_functions():
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    manual_order = make_context(
        order_id=1, estimated_duration_minutes=0, time_estimate_source="not_applicable"
    )
    unassigned_order = make_context(order_id=2)

    result = schedule_all(
        machine_queues={},
        machine_calendars={},
        pool_queues={},
        pool_members={},
        manual_queue=[manual_order],
        manual_calendar=calendar,
        unassigned=[unassigned_order],
        now=now,
    )

    expected_manual = walk_machine_queue([manual_order], calendar, now)
    expected_unassigned = schedule_unassigned_orders([unassigned_order])
    assert result.manual == expected_manual
    assert result.unassigned == expected_unassigned


def test_schedule_walk_result_all_orders_flattens_every_group():
    order = ScheduledOrder(order_id=1, planned_start=None, planned_end=None, conflicts=[])
    result = ScheduleWalkResult(
        by_machine={1: [order]},
        by_pool={2: [order]},
        manual=[order],
        unassigned=[order],
        machine_cursors={1: None},
    )
    assert result.all_orders() == [order, order, order, order]
