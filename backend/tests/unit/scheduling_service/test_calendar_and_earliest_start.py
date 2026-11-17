"""
Unit tests for calendar resolution and earliest-start resolution. No database, no HTTP, pure
functions only.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta

import pytest

from src.modules.fulfillment.domain.services.scheduling import build_machine_calendar
from src.modules.fulfillment.domain.services.scheduling import compute_earliest_start
from src.modules.fulfillment.domain.services.scheduling import compute_order_conflicts
from src.modules.fulfillment.domain.services.scheduling import place
from src.modules.fulfillment.domain.services.scheduling import resolve_external_predecessor_ready_at
from src.modules.fulfillment.domain.services.scheduling import resolve_input_material_ready_at
from src.modules.fulfillment.domain.services.scheduling import resolve_internal_predecessor_ready_at
from src.modules.fulfillment.domain.services.scheduling import resolve_mixed_predecessor_ready_at
from src.modules.fulfillment.domain.services.scheduling import resolve_weekly_minutes
from src.modules.fulfillment.domain.services.scheduling import schedule_unassigned_orders
from src.modules.fulfillment.domain.services.scheduling import snap_to_working_start
from src.modules.fulfillment.domain.services.scheduling import validate_weekly_hours
from src.modules.fulfillment.domain.value_objects.schedule_conflict import ScheduleConflictReason
from src.modules.platform.domain.exceptions import InvalidScheduleCalendarError
from tests.unit.scheduling_service._helpers import MONDAY
from tests.unit.scheduling_service._helpers import SATURDAY
from tests.unit.scheduling_service._helpers import TUESDAY
from tests.unit.scheduling_service._helpers import WEEKDAY_HOURS
from tests.unit.scheduling_service._helpers import make_context
from tests.unit.scheduling_service._helpers import walk_machine_queue
from tests.unit.scheduling_service._helpers import walk_pool_queue


def test_resolve_weekly_minutes_uses_machine_override_when_present():
    default = WEEKDAY_HOURS
    override = {0: 600, 1: 600, 2: 600, 3: 600, 4: 600, 5: 0, 6: 0}
    assert resolve_weekly_minutes(default, override) == override
    assert resolve_weekly_minutes(default, None) == default


def test_machine_calendar_exception_overrides_weekly_template():
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {MONDAY: 0})
    assert calendar.minutes_available_on(MONDAY) == 0  # holiday exception
    assert calendar.minutes_available_on(TUESDAY) == 480  # falls through to weekly template
    assert calendar.minutes_available_on(SATURDAY) == 0  # weekend, no exception


def test_validate_weekly_hours_rejects_missing_weekday_or_negative_minutes():
    with pytest.raises(InvalidScheduleCalendarError):
        validate_weekly_hours({0: 480})  # missing weekdays 1-6
    with pytest.raises(InvalidScheduleCalendarError):
        validate_weekly_hours({**WEEKDAY_HOURS, 0: -10})


def test_snap_to_working_start_rolls_forward_over_weekend():
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    friday_evening = datetime.combine(date(2026, 7, 31), datetime.min.time()) + timedelta(hours=20)
    snapped = snap_to_working_start(friday_evening, calendar)
    assert snapped.date() == date(2026, 8, 3)  # next Monday, skips Sat/Sun (0 minutes)
    assert snapped.hour == 8


def test_place_splits_duration_across_multiple_working_days():
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    start = datetime.combine(MONDAY, datetime.min.time(), tzinfo=UTC) + timedelta(hours=8)
    # 600 minutes > one 480-minute workday, so it must spill into Tuesday.
    planned_start, planned_end = place(start, 600, calendar)
    assert planned_start == start
    assert planned_end.date() == TUESDAY
    assert planned_end.hour == 10  # 8:00 + 120 leftover minutes


def test_place_zero_duration_still_snaps_start_to_working_time():
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    off_hours = datetime.combine(SATURDAY, datetime.min.time())
    start, end = place(off_hours, 0, calendar)
    assert start == end
    assert start.date() == date(2026, 8, 3)  # next Monday after the Saturday


def test_resolve_internal_predecessor_ready_at_ignores_unknown_orders():
    d1 = datetime(2026, 7, 27, 10, 0)
    d2 = datetime(2026, 7, 28, 10, 0)
    assert resolve_internal_predecessor_ready_at([d1, d2], zone=UTC) == d2.date()
    # An unassigned sibling (planned_end=None) is ignored, not blocking.
    assert resolve_internal_predecessor_ready_at([d1, None], zone=UTC) == d1.date()
    # All unknown -> no constraint at all.
    assert resolve_internal_predecessor_ready_at([None, None], zone=UTC) is None


def test_resolve_external_predecessor_ready_at_prefers_pickup_over_expected_delivery():
    pickup = date(2026, 7, 20)
    expected = date(2026, 7, 25)
    assert resolve_external_predecessor_ready_at(None, pickup, expected, zone=UTC) == pickup
    assert resolve_external_predecessor_ready_at(None, None, expected, zone=UTC) == expected
    assert resolve_external_predecessor_ready_at(None, None, None, zone=UTC) is None


def test_resolve_external_predecessor_ready_at_prefers_actual_delivery_over_estimates():
    # Regression: an order item that has actually arrived must be treated
    # as ready now, even when its expected_delivery_date/ready_for_pickup_date
    # estimate points to a later (or earlier) date that's now stale.
    actual = date(2026, 8, 3)
    pickup = date(2026, 7, 20)
    expected = date(2026, 8, 17)
    assert resolve_external_predecessor_ready_at(actual, pickup, expected, zone=UTC) == actual
    assert resolve_external_predecessor_ready_at(actual, None, expected, zone=UTC) == actual
    assert resolve_external_predecessor_ready_at(actual, None, None, zone=UTC) == actual


def test_resolve_external_predecessor_ready_at_collapses_event_timestamps_to_a_day():
    """delivery_date/ready_for_pickup_date are full timestamps, while
    expected_delivery_date is a plain date. The scheduler plans in whole
    days, so all three must come back as `date`: leaking a datetime here
    crashes _with_waiting_and_target_flags on `predecessor_ready_at > now.date()`
    (datetime subclasses date, so nothing caught it at type-check time).
    """
    delivered_at = datetime(2026, 8, 3, 16, 45, tzinfo=UTC)
    pickup_at = datetime(2026, 7, 20, 9, 0, tzinfo=UTC)
    expected = date(2026, 8, 17)

    from_delivery = resolve_external_predecessor_ready_at(
        delivered_at, pickup_at, expected, zone=UTC
    )
    assert from_delivery == date(2026, 8, 3)
    assert type(from_delivery) is date

    from_pickup = resolve_external_predecessor_ready_at(None, pickup_at, expected, zone=UTC)
    assert from_pickup == date(2026, 7, 20)
    assert type(from_pickup) is date

    # The result must be directly comparable against a plain date.
    assert from_delivery > date(2026, 8, 2)


def test_waiting_on_predecessor_flag_survives_a_timestamped_delivery():
    """End-to-end shape of the crash: a context built from a timestamped
    delivery must flow through conflict computation without a TypeError."""
    ready_at = resolve_external_predecessor_ready_at(
        datetime(2026, 9, 1, 13, 30, tzinfo=UTC), None, None, zone=UTC
    )
    ctx = make_context(order_id=1, predecessor_ready_at=ready_at)
    now = datetime(2026, 8, 6, 8, 0, tzinfo=UTC)

    conflicts = compute_order_conflicts(ctx, planned_end=None, now=now)

    assert ScheduleConflictReason.WAITING_ON_PREDECESSOR.value in conflicts


class TestAwaitingPredecessorOutput:
    """An unassigned predecessor has no planned date, so
    predecessor_ready_at stays None and the date-based check below can
    never fire, yet lot_rules.assert_position_has_available_input still
    hard-blocks Start/Resume with a 422. awaiting_predecessor_output
    closes that gap so the card warns before the click."""

    def test_exhausted_upstream_is_flagged_without_any_predecessor_date(self):
        ctx = make_context(
            predecessor_ready_at=None, upstream_input_available=False, position_sequence=2
        )
        now = datetime(2026, 8, 6, 8, 0, tzinfo=UTC)

        conflicts = compute_order_conflicts(ctx, planned_end=None, now=now)

        assert ScheduleConflictReason.WAITING_ON_PREDECESSOR.value in conflicts

    def test_available_upstream_is_not_flagged(self):
        ctx = make_context(
            predecessor_ready_at=None, upstream_input_available=True, position_sequence=2
        )
        now = datetime(2026, 8, 6, 8, 0, tzinfo=UTC)

        assert compute_order_conflicts(ctx, planned_end=None, now=now) == []

    def test_the_reason_is_not_duplicated_when_both_conditions_hold(self):
        """A future predecessor date AND an exhausted upstream are one
        blockage, not two: the badge must appear exactly once."""
        ctx = make_context(
            predecessor_ready_at=date(2026, 9, 1),
            upstream_input_available=False,
            position_sequence=2,
        )
        now = datetime(2026, 8, 6, 8, 0, tzinfo=UTC)

        conflicts = compute_order_conflicts(ctx, planned_end=None, now=now)

        assert conflicts.count(ScheduleConflictReason.WAITING_ON_PREDECESSOR.value) == 1

    def test_a_terminal_order_is_never_flagged(self):
        """A completed/canceled order has no Start/Resume left to block, so
        the warning would be pure noise on the read model."""
        now = datetime(2026, 8, 6, 8, 0, tzinfo=UTC)
        for status in ("completed", "canceled"):
            ctx = make_context(status=status, upstream_input_available=False, position_sequence=2)
            conflicts = compute_order_conflicts(ctx, planned_end=None, now=now)
            assert ScheduleConflictReason.WAITING_ON_PREDECESSOR.value not in conflicts, status

    def test_an_in_progress_order_is_still_flagged(self):
        """Started, but the predecessor hasn't fed it any more units, so it
        can't record further completions or resume after a pause, so the
        warning is accurate, not noise."""
        ctx = make_context(
            status="in_progress", upstream_input_available=False, position_sequence=2
        )
        now = datetime(2026, 8, 6, 8, 0, tzinfo=UTC)

        conflicts = compute_order_conflicts(ctx, planned_end=None, now=now)

        assert ScheduleConflictReason.WAITING_ON_PREDECESSOR.value in conflicts

    def test_machine_less_unassigned_orders_are_flagged_too(self):
        """schedule_unassigned_orders only runs _static_conflicts, which is
        why the check lives there rather than beside the date comparison."""
        ctx = make_context(upstream_input_available=False, position_sequence=2)

        results = schedule_unassigned_orders([ctx])

        assert ScheduleConflictReason.WAITING_ON_PREDECESSOR.value in results[0].conflicts
        assert ScheduleConflictReason.NO_MACHINE_ASSIGNED.value in results[0].conflicts


class TestWaitingOnMaterial:
    """WAITING_ON_MATERIAL, the sequence-1 twin of WAITING_ON_PREDECESSOR:
    sequence 1's upstream is raw material rather than an earlier position,
    so it never gets WAITING_ON_PREDECESSOR (see position_sequence's own
    docstring), but StartProductionOrder still refuses it under the same
    upstream_input_available=False condition, and this is that gate's badge."""

    def test_sequence_one_without_material_is_flagged_and_not_waiting_on_predecessor(self):
        ctx = make_context(upstream_input_available=False, position_sequence=1)
        now = datetime(2026, 8, 6, 8, 0, tzinfo=UTC)

        conflicts = compute_order_conflicts(ctx, planned_end=None, now=now)

        assert ScheduleConflictReason.WAITING_ON_MATERIAL.value in conflicts
        assert ScheduleConflictReason.WAITING_ON_PREDECESSOR.value not in conflicts

    def test_sequence_one_with_material_available_is_not_flagged(self):
        ctx = make_context(upstream_input_available=True, position_sequence=1)
        now = datetime(2026, 8, 6, 8, 0, tzinfo=UTC)

        conflicts = compute_order_conflicts(ctx, planned_end=None, now=now)

        assert ScheduleConflictReason.WAITING_ON_MATERIAL.value not in conflicts

    def test_sequence_two_without_upstream_gets_predecessor_flag_only(self):
        ctx = make_context(upstream_input_available=False, position_sequence=2)
        now = datetime(2026, 8, 6, 8, 0, tzinfo=UTC)

        conflicts = compute_order_conflicts(ctx, planned_end=None, now=now)

        assert ScheduleConflictReason.WAITING_ON_PREDECESSOR.value in conflicts
        assert ScheduleConflictReason.WAITING_ON_MATERIAL.value not in conflicts

    def test_a_terminal_sequence_one_order_is_never_flagged(self):
        now = datetime(2026, 8, 6, 8, 0, tzinfo=UTC)
        for status in ("completed", "canceled"):
            ctx = make_context(status=status, upstream_input_available=False, position_sequence=1)
            conflicts = compute_order_conflicts(ctx, planned_end=None, now=now)
            assert ScheduleConflictReason.WAITING_ON_MATERIAL.value not in conflicts, status

    def test_flag_survives_walk_machine_queue(self):
        calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
        now = datetime.combine(MONDAY, datetime.min.time())
        ctx = make_context(order_id=1, upstream_input_available=False, position_sequence=1)

        results = walk_machine_queue([ctx], calendar, now)

        assert ScheduleConflictReason.WAITING_ON_MATERIAL.value in results[0].conflicts

    def test_flag_survives_walk_pool_queue(self):
        calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
        now = datetime.combine(MONDAY, datetime.min.time())
        ctx = make_context(order_id=1, upstream_input_available=False, position_sequence=1)

        results = walk_pool_queue([ctx], {1: calendar}, now)

        assert ScheduleConflictReason.WAITING_ON_MATERIAL.value in results[0].conflicts

    def test_flag_survives_schedule_unassigned_orders(self):
        ctx = make_context(order_id=1, upstream_input_available=False, position_sequence=1)

        results = schedule_unassigned_orders([ctx])

        assert ScheduleConflictReason.WAITING_ON_MATERIAL.value in results[0].conflicts
        assert ScheduleConflictReason.NO_MACHINE_ASSIGNED.value in results[0].conflicts


def test_resolve_mixed_predecessor_ready_at_takes_the_later_known_date():
    early = date(2026, 7, 20)
    late = date(2026, 7, 25)
    assert resolve_mixed_predecessor_ready_at(early, late) == late
    assert resolve_mixed_predecessor_ready_at(None, late) == late
    assert resolve_mixed_predecessor_ready_at(None, None) is None


def test_resolve_input_material_ready_at_takes_latest_allocation_date():
    d1 = date(2026, 7, 20)
    d2 = date(2026, 7, 22)
    assert resolve_input_material_ready_at([d1, d2, None], zone=UTC) == d2
    assert resolve_input_material_ready_at([None, None], zone=UTC) is None


def test_compute_earliest_start_takes_max_of_known_constraints():
    not_before = date(2026, 7, 20)
    predecessor = date(2026, 7, 25)
    material = date(2026, 7, 18)
    assert compute_earliest_start(not_before, predecessor, material) == predecessor
    assert compute_earliest_start(None, None, None) is None
