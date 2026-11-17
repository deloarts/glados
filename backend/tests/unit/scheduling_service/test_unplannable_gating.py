"""
Unit tests for the unknowable-predecessor-chain and missing-raw-material
placement gates. No database, no HTTP, pure functions only.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta

from src.modules.fulfillment.domain.services.scheduling import advance_machine_queue
from src.modules.fulfillment.domain.services.scheduling import build_machine_calendar
from src.modules.fulfillment.domain.services.scheduling import compute_order_conflicts
from src.modules.fulfillment.domain.services.scheduling import is_unplannable_for_missing_material
from src.modules.fulfillment.domain.services.scheduling import schedule_all
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.schedule_conflict import ScheduleConflictReason
from tests.unit.scheduling_service._helpers import MONDAY
from tests.unit.scheduling_service._helpers import TUESDAY
from tests.unit.scheduling_service._helpers import WEEKDAY_HOURS
from tests.unit.scheduling_service._helpers import make_context


def test_unknowable_chain_without_upstream_input_yields_no_dates_and_frees_the_cursor():
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    incoming_cursor = datetime.combine(MONDAY, datetime.min.time(), tzinfo=UTC) + timedelta(
        hours=10
    )

    ctx = make_context(
        predecessor_chain_unknown=True,
        upstream_input_available=False,
        position_sequence=2,
        estimated_duration_minutes=60,
    )
    planned_start, planned_end, next_cursor = advance_machine_queue(
        ctx, incoming_cursor, calendar, now
    )

    assert planned_start is None
    assert planned_end is None
    assert next_cursor == incoming_cursor  # not consumed, same as PAUSED


def test_unknowable_chain_still_flags_waiting_on_predecessor():
    """No dates does not mean no signal. The badge that would have
    explained the 422 on Start/Resume must still show."""
    now = datetime.combine(MONDAY, datetime.min.time(), tzinfo=UTC)
    ctx = make_context(
        predecessor_chain_unknown=True, upstream_input_available=False, position_sequence=2
    )
    conflicts = compute_order_conflicts(ctx, planned_end=None, now=now)
    assert ScheduleConflictReason.WAITING_ON_PREDECESSOR.value in conflicts


def test_unknowable_chain_with_upstream_input_available_still_gets_floored_dates():
    """Parts are already sitting at this step (a partial delivery, say):
    the chain's overall finish time is still unknowable, but this step can
    genuinely start now, so the usual now/cursor floor applies."""
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())

    ctx = make_context(
        predecessor_chain_unknown=True,
        upstream_input_available=True,
        position_sequence=2,
        estimated_duration_minutes=60,
    )
    planned_start, planned_end, next_cursor = advance_machine_queue(ctx, None, calendar, now)

    assert planned_start is not None
    assert planned_end is not None
    assert next_cursor == planned_end


def test_unknowable_chain_is_out_of_scope_for_sequence_one_orders():
    """Sequence 1's upstream is raw material, gated separately. The
    unknowable-chain branch must never suppress its dates even if it were
    somehow flagged. upstream_input_available=True here (material already
    available) isolates this from the newer missing-material branch
    (is_unplannable_for_missing_material, see its own test section below):
    both branches independently exempt sequence 1 for their own reason,
    and mixing them into one ctx would prove neither claim cleanly."""
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())

    ctx = make_context(
        predecessor_chain_unknown=True,
        upstream_input_available=True,
        position_sequence=1,
        estimated_duration_minutes=60,
    )
    planned_start, planned_end, _ = advance_machine_queue(ctx, None, calendar, now)

    assert planned_start is not None
    assert planned_end is not None


def test_pinned_order_keeps_its_window_even_when_chain_unknown():
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    manual_start = datetime(2026, 8, 5, 13, 0, tzinfo=UTC)
    manual_end = datetime(2026, 8, 5, 15, 0, tzinfo=UTC)

    ctx = make_context(
        pinned=True,
        existing_planned_start=manual_start,
        existing_planned_end=manual_end,
        predecessor_chain_unknown=True,
        upstream_input_available=False,
        position_sequence=2,
    )
    planned_start, planned_end, next_cursor = advance_machine_queue(ctx, None, calendar, now)

    assert planned_start == manual_start
    assert planned_end == manual_end
    assert next_cursor == manual_end


def test_in_progress_order_keeps_its_actual_start_anchor_even_when_chain_unknown():
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    actual_start = datetime.combine(MONDAY, datetime.min.time(), tzinfo=UTC) + timedelta(hours=9)

    ctx = make_context(
        status=ProductionOrderStatus.IN_PROGRESS.value,
        actual_start=actual_start,
        estimated_duration_minutes=60,
        predecessor_chain_unknown=True,
        upstream_input_available=False,
        position_sequence=2,
    )
    planned_start, planned_end, next_cursor = advance_machine_queue(ctx, None, calendar, now)

    assert planned_start == actual_start
    assert planned_end == actual_start + timedelta(hours=1)
    assert next_cursor == planned_end


def test_is_unplannable_for_missing_material_predicate():
    unplannable = make_context(
        position_sequence=1, upstream_input_available=False, material_ready_at=None
    )
    assert is_unplannable_for_missing_material(unplannable) is True

    has_forecast = make_context(
        position_sequence=1, upstream_input_available=False, material_ready_at=TUESDAY
    )
    assert is_unplannable_for_missing_material(has_forecast) is False

    material_available = make_context(
        position_sequence=1, upstream_input_available=True, material_ready_at=None
    )
    assert is_unplannable_for_missing_material(material_available) is False

    sequence_two = make_context(
        position_sequence=2, upstream_input_available=False, material_ready_at=None
    )
    assert is_unplannable_for_missing_material(sequence_two) is False

    for status in ("completed", "canceled"):
        terminal = make_context(
            status=status,
            position_sequence=1,
            upstream_input_available=False,
            material_ready_at=None,
        )
        assert is_unplannable_for_missing_material(terminal) is False, status


def test_missing_material_without_forecast_yields_no_dates_and_frees_the_cursor():
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    incoming_cursor = datetime.combine(MONDAY, datetime.min.time(), tzinfo=UTC) + timedelta(
        hours=10
    )

    ctx = make_context(
        position_sequence=1,
        upstream_input_available=False,
        material_ready_at=None,
        estimated_duration_minutes=60,
    )
    planned_start, planned_end, next_cursor = advance_machine_queue(
        ctx, incoming_cursor, calendar, now
    )

    assert planned_start is None
    assert planned_end is None
    assert next_cursor == incoming_cursor  # not consumed, same as PAUSED


def test_missing_material_still_flags_waiting_on_material():
    now = datetime.combine(MONDAY, datetime.min.time(), tzinfo=UTC)
    ctx = make_context(position_sequence=1, upstream_input_available=False, material_ready_at=None)

    conflicts = compute_order_conflicts(ctx, planned_end=None, now=now)

    assert ScheduleConflictReason.WAITING_ON_MATERIAL.value in conflicts


def test_material_with_a_delivery_forecast_is_placed_and_floored_at_it():
    """material_ready_at set (an expected_delivery_date exists) is the
    escape from the branch above: the forecast is a real, honest
    constraint, not a fabricated one, so the order is placed normally,
    floored at that date via compute_earliest_start."""
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    forecast = TUESDAY

    ctx = make_context(
        position_sequence=1,
        upstream_input_available=False,
        material_ready_at=forecast,
        estimated_duration_minutes=60,
    )
    planned_start, planned_end, next_cursor = advance_machine_queue(ctx, None, calendar, now)

    assert planned_start is not None
    assert planned_start.date() == forecast
    assert planned_end is not None
    assert next_cursor == planned_end


def test_missing_material_check_does_not_affect_sequence_two_orders():
    """position_sequence <= 1 is part of the predicate. A sequence-2+
    order with upstream_input_available=False and material_ready_at=None
    (fields that mean something else entirely past sequence 1, see
    OrderSchedulingContext.position_sequence's own docstring) must still
    fall through to the ordinary placement branch, not this one."""
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())

    ctx = make_context(
        position_sequence=2,
        upstream_input_available=False,
        material_ready_at=None,
        predecessor_chain_unknown=False,
        estimated_duration_minutes=60,
    )
    planned_start, planned_end, next_cursor = advance_machine_queue(ctx, None, calendar, now)

    assert planned_start is not None
    assert planned_end is not None
    assert next_cursor == planned_end


def test_pinned_order_keeps_its_window_even_with_missing_material():
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    manual_start = datetime(2026, 8, 5, 13, 0, tzinfo=UTC)
    manual_end = datetime(2026, 8, 5, 15, 0, tzinfo=UTC)

    ctx = make_context(
        pinned=True,
        existing_planned_start=manual_start,
        existing_planned_end=manual_end,
        position_sequence=1,
        upstream_input_available=False,
        material_ready_at=None,
    )
    planned_start, planned_end, next_cursor = advance_machine_queue(ctx, None, calendar, now)

    assert planned_start == manual_start
    assert planned_end == manual_end
    assert next_cursor == manual_end


def test_paused_precedence_holds_over_missing_material():
    """PAUSED is checked first regardless. This only proves the branch
    order doesn't accidentally invert; PAUSED already yields the same
    (None, None, cursor) shape either way."""
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    incoming_cursor = datetime.combine(MONDAY, datetime.min.time(), tzinfo=UTC) + timedelta(hours=3)

    ctx = make_context(
        status=ProductionOrderStatus.PAUSED.value,
        position_sequence=1,
        upstream_input_available=False,
        material_ready_at=None,
    )
    planned_start, planned_end, next_cursor = advance_machine_queue(
        ctx, incoming_cursor, calendar, now
    )

    assert planned_start is None
    assert planned_end is None
    assert next_cursor == incoming_cursor


def test_schedule_all_dateless_missing_material_head_does_not_block_its_own_pool_or_the_other_one():
    """Mirrors test_schedule_all_dateless_pool_head_does_not_block_its_own_
    pool_or_the_other_one, using the missing-material branch instead of
    PAUSED as the dateless head. schedule_all's pool merge must commit a
    dateless head immediately, for whatever reason it's dateless, without
    stalling its own pool's next order or an unrelated pool's order."""
    calendar_1 = build_machine_calendar(WEEKDAY_HOURS, None, {})
    calendar_2 = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    missing_material_head = make_context(
        order_id=1,
        queue_sequence=1,
        position_sequence=1,
        upstream_input_available=False,
        material_ready_at=None,
        estimated_duration_minutes=60,
    )
    next_in_pool_1 = make_context(order_id=2, queue_sequence=2, estimated_duration_minutes=60)
    pool_2_order = make_context(order_id=3, queue_sequence=1, estimated_duration_minutes=30)

    result = schedule_all(
        machine_queues={},
        machine_calendars={1: calendar_1, 2: calendar_2},
        pool_queues={1: [missing_material_head, next_in_pool_1], 2: [pool_2_order]},
        pool_members={1: [1], 2: [2]},
        manual_queue=[],
        manual_calendar=calendar_1,
        unassigned=[],
        now=now,
    )

    head_result = {r.order_id: r for r in result.by_pool[1]}[1]
    assert head_result.planned_start is None
    assert head_result.trial_machine_id is None
    next_result = {r.order_id: r for r in result.by_pool[1]}[2]
    assert next_result.planned_start.hour == 8  # not pushed by the dateless order ahead of it
    pool_2_result = result.by_pool[2][0]
    assert pool_2_result.planned_start.hour == 8  # unaffected by pool 1 entirely
