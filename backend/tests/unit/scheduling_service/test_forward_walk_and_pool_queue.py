"""
Unit tests for the forward walk over machine and pool queues and for
timezone-aware inputs. No database, no HTTP, pure functions only.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta

from src.modules.fulfillment.domain.services.scheduling import OrderSchedulingContext
from src.modules.fulfillment.domain.services.scheduling import advance_machine_queue
from src.modules.fulfillment.domain.services.scheduling import build_machine_calendar
from src.modules.fulfillment.domain.services.scheduling import compute_order_conflicts
from src.modules.fulfillment.domain.services.scheduling import place
from src.modules.fulfillment.domain.services.scheduling import schedule_unassigned_orders
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.schedule_conflict import ScheduleConflictReason
from tests.unit.scheduling_service._helpers import MONDAY
from tests.unit.scheduling_service._helpers import WEEKDAY_HOURS
from tests.unit.scheduling_service._helpers import make_context
from tests.unit.scheduling_service._helpers import walk_machine_queue
from tests.unit.scheduling_service._helpers import walk_pool_queue


def test_walk_machine_queue_places_orders_back_to_back():
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    orders = [
        make_context(order_id=1, queue_sequence=1, estimated_duration_minutes=120),
        make_context(order_id=2, queue_sequence=2, estimated_duration_minutes=60),
    ]
    results = {r.order_id: r for r in walk_machine_queue(orders, calendar, now)}
    assert results[1].planned_start.hour == 8
    assert results[1].planned_end.hour == 10
    assert results[2].planned_start == results[1].planned_end
    assert results[2].planned_end.hour == 11


def test_walk_machine_queue_paused_order_clears_dates_and_frees_capacity():
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    orders = [
        make_context(
            order_id=1,
            queue_sequence=1,
            status=ProductionOrderStatus.PAUSED.value,
            estimated_duration_minutes=120,
        ),
        make_context(order_id=2, queue_sequence=2, estimated_duration_minutes=60),
    ]
    results = {r.order_id: r for r in walk_machine_queue(orders, calendar, now)}
    assert results[1].planned_start is None
    assert results[1].planned_end is None
    # order 2 starts at the top of the day, unaffected by the paused order.
    assert results[2].planned_start.hour == 8


def test_walk_machine_queue_in_progress_anchors_to_actual_start():
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    actual_start = datetime.combine(MONDAY, datetime.min.time(), tzinfo=UTC) + timedelta(hours=9)
    orders = [
        make_context(
            order_id=1,
            queue_sequence=1,
            status=ProductionOrderStatus.IN_PROGRESS.value,
            actual_start=actual_start,
            estimated_duration_minutes=60,
        ),
    ]
    results = {r.order_id: r for r in walk_machine_queue(orders, calendar, now)}
    assert results[1].planned_start == actual_start
    assert results[1].planned_end == actual_start + timedelta(hours=1)


def test_walk_machine_queue_pinned_order_keeps_manual_override():
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    manual_start = datetime(2026, 8, 5, 13, 0, tzinfo=UTC)
    manual_end = datetime(2026, 8, 5, 15, 0, tzinfo=UTC)
    orders = [
        make_context(
            order_id=1,
            queue_sequence=1,
            pinned=True,
            existing_planned_start=manual_start,
            existing_planned_end=manual_end,
        ),
        make_context(order_id=2, queue_sequence=2, estimated_duration_minutes=60),
    ]
    results = {r.order_id: r for r in walk_machine_queue(orders, calendar, now)}
    assert results[1].planned_start == manual_start
    assert results[1].planned_end == manual_end
    # Order 2 queues after the pinned order's manual window, not from `now`.
    assert results[2].planned_start == manual_end


def test_walk_machine_queue_conflict_flags():
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())

    missing_estimate = make_context(order_id=1, time_estimate_source="missing")
    budget_estimate = make_context(order_id=2, time_estimate_source="budget")
    capability_mismatch = make_context(order_id=3, capability_mismatch=True)
    not_fully_queued = make_context(order_id=4, position_not_fully_queued=True)
    waiting_on_predecessor = make_context(
        order_id=5, predecessor_ready_at=now.date() + timedelta(days=10)
    )
    past_target = make_context(
        order_id=6, estimated_duration_minutes=60, target_date=now.date() - timedelta(days=1)
    )

    results = {
        r.order_id: r
        for r in walk_machine_queue(
            [
                missing_estimate,
                budget_estimate,
                capability_mismatch,
                not_fully_queued,
                waiting_on_predecessor,
                past_target,
            ],
            calendar,
            now,
        )
    }
    assert ScheduleConflictReason.MISSING_TIME_ESTIMATE.value in results[1].conflicts
    assert ScheduleConflictReason.ESTIMATE_FROM_TIME_BUDGET.value in results[2].conflicts
    assert ScheduleConflictReason.CAPABILITY_MISMATCH.value in results[3].conflicts
    assert ScheduleConflictReason.POSITION_NOT_FULLY_QUEUED.value in results[4].conflicts
    assert ScheduleConflictReason.WAITING_ON_PREDECESSOR.value in results[5].conflicts
    assert ScheduleConflictReason.PAST_TARGET_DATE.value in results[6].conflicts


def test_compute_order_conflicts_matches_walk_machine_queue_without_a_walk():
    """compute_order_conflicts (the lightweight, no-calendar-walk path used
    to attach conflicts to a plain ProductionOrder read) must agree with
    walk_machine_queue's own conflict computation for the same context
    plus the order's already-persisted planned_end."""
    now = datetime.combine(MONDAY, datetime.min.time())
    ctx = make_context(
        order_id=1,
        capability_mismatch=True,
        position_not_fully_queued=True,
        predecessor_ready_at=now.date() + timedelta(days=5),
        target_date=now.date() - timedelta(days=1),
        existing_planned_end=now + timedelta(hours=1),
    )
    conflicts = compute_order_conflicts(ctx, ctx.existing_planned_end, now)
    assert set(conflicts) == {
        ScheduleConflictReason.CAPABILITY_MISMATCH.value,
        ScheduleConflictReason.POSITION_NOT_FULLY_QUEUED.value,
        ScheduleConflictReason.WAITING_ON_PREDECESSOR.value,
        ScheduleConflictReason.PAST_TARGET_DATE.value,
    }


def test_compute_order_conflicts_clean_order_has_no_conflicts():
    now = datetime.combine(MONDAY, datetime.min.time())
    ctx = make_context(order_id=1, time_estimate_source="measured")
    assert compute_order_conflicts(ctx, now + timedelta(hours=1), now) == []


def test_schedule_unassigned_orders_always_flags_no_machine_assigned():
    orders = [make_context(order_id=1), make_context(order_id=2, capability_mismatch=True)]
    results = schedule_unassigned_orders(orders)
    assert all(r.planned_start is None and r.planned_end is None for r in results)
    assert all(ScheduleConflictReason.NO_MACHINE_ASSIGNED.value in r.conflicts for r in results)


def test_schedule_unassigned_orders_pool_assigned_context_is_not_flagged():
    """Pool-first planning: a pool-assigned order (machine_pool_id
    set) reflects a deliberate planner decision, not a bare absence of
    one. walk_pool_queue is the primary path for such orders, so
    this bare fallback must not flag it NO_MACHINE_ASSIGNED either, only
    a genuinely machine-and-pool-less order still gets it."""
    pool_order = make_context(order_id=1, machine_pool_id=7)
    legacy_order = make_context(order_id=2)
    results = {r.order_id: r for r in schedule_unassigned_orders([pool_order, legacy_order])}
    assert ScheduleConflictReason.NO_MACHINE_ASSIGNED.value not in results[1].conflicts
    assert ScheduleConflictReason.NO_MACHINE_ASSIGNED.value in results[2].conflicts


def test_machine_less_inspection_order_gets_real_dates_and_no_conflicts():
    """A born-internal QA inspection order is
    machine-less but manual (is_manual_step=True, see
    production_order_rules.position_is_manual: an inspection step always
    reports fabrication_method_requires_machine=False), so it walks
    through walk_machine_queue against the default calendar like any
    other manual order, not schedule_unassigned_orders. Real planned
    dates, no NO_MACHINE_ASSIGNED. And with no estimate at all its
    time_estimate_source is "not_applicable", not "missing", so
    it carries no MISSING_TIME_ESTIMATE conflict either."""
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    inspection_order = make_context(
        order_id=1,
        estimated_duration_minutes=0,
        time_estimate_source="not_applicable",
        is_manual_step=True,
    )
    results = {r.order_id: r for r in walk_machine_queue([inspection_order], calendar, now)}
    result = results[1]
    assert result.planned_start is not None
    assert result.planned_end is not None
    assert ScheduleConflictReason.MISSING_TIME_ESTIMATE.value not in result.conflicts
    assert ScheduleConflictReason.NO_MACHINE_ASSIGNED.value not in result.conflicts


def test_walk_pool_queue_single_member_matches_plain_machine_walk():
    """A one-member pool has nothing to choose between, so
    walk_pool_queue must place every order exactly where
    walk_machine_queue would against that same member's calendar;
    the earliest-available-member rule degenerates to the plain walk."""
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    orders = [
        make_context(order_id=1, queue_sequence=1, estimated_duration_minutes=120),
        make_context(order_id=2, queue_sequence=2, estimated_duration_minutes=60),
    ]
    pool_results = {r.order_id: r for r in walk_pool_queue(orders, {9: calendar}, now)}
    machine_results = {r.order_id: r for r in walk_machine_queue(orders, calendar, now)}
    assert pool_results[1].planned_start == machine_results[1].planned_start
    assert pool_results[1].planned_end == machine_results[1].planned_end
    assert pool_results[2].planned_start == machine_results[2].planned_start
    assert pool_results[2].planned_end == machine_results[2].planned_end


def test_walk_pool_queue_places_each_order_on_the_earliest_finishing_member():
    """Two members, one already partway booked (via a shorter calendar
    day), so the walk must pick whichever member actually finishes each
    order soonest, not just alternate/round-robin."""
    busy_calendar = build_machine_calendar({**WEEKDAY_HOURS, 0: 60}, None, {})  # Monday: 1h only
    free_calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})  # Monday: 8h
    now = datetime.combine(MONDAY, datetime.min.time())
    order = make_context(order_id=1, queue_sequence=1, estimated_duration_minutes=120)

    results = {
        r.order_id: r for r in walk_pool_queue([order], {1: busy_calendar, 2: free_calendar}, now)
    }
    # Member 1 only has 60 minutes on Monday, so a 120-minute order spills
    # into Tuesday there; member 2 has a full day and finishes same-day.
    assert results[1].planned_end.date() == MONDAY


def test_walk_pool_queue_parallelizes_across_members_instead_of_serializing_on_one():
    """Multi-member pool, multi-order queue: each order independently
    lands on whichever member's own running cursor+calendar finishes it
    earliest. Both members start empty, so order 1 (a tie) settles on
    member 1 (iteration order); order 2 must then prefer the still-empty
    member 2 over queueing behind order 1 on member 1, since both members work
    in parallel, so order 2 finishes at the same time as order 1 rather
    than after it."""
    calendar_a = build_machine_calendar(WEEKDAY_HOURS, None, {})
    calendar_b = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    orders = [
        make_context(order_id=1, queue_sequence=1, estimated_duration_minutes=30),
        make_context(order_id=2, queue_sequence=2, estimated_duration_minutes=30),
    ]
    results = {r.order_id: r for r in walk_pool_queue(orders, {1: calendar_a, 2: calendar_b}, now)}
    assert results[1].planned_start.hour == 8
    assert results[2].planned_start.hour == 8
    # Parallel members, not a serialized single-machine queue: both finish
    # at the same instant instead of order 2 stacking behind order 1.
    assert results[1].planned_end == results[2].planned_end


def test_walk_pool_queue_paused_order_frees_capacity_on_every_member():
    """A PAUSED order in the pool queue consumes no member's capacity,
    same PAUSED semantics as the plain machine walk (advance_machine_queue),
    just verified across every member instead of one."""
    calendar_a = build_machine_calendar(WEEKDAY_HOURS, None, {})
    calendar_b = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    orders = [
        make_context(
            order_id=1,
            queue_sequence=1,
            status=ProductionOrderStatus.PAUSED.value,
            estimated_duration_minutes=120,
        ),
        make_context(order_id=2, queue_sequence=2, estimated_duration_minutes=60),
    ]
    results = {r.order_id: r for r in walk_pool_queue(orders, {1: calendar_a, 2: calendar_b}, now)}
    assert results[1].planned_start is None
    assert results[1].planned_end is None
    # order 2 starts at the top of the day on whichever member it lands
    # on, unaffected by the paused order ahead of it.
    assert results[2].planned_start.hour == 8


def test_walk_pool_queue_pinned_order_keeps_manual_window():
    """A pinned order with an existing planned window is a fixed anchor
    regardless of which member it's trialed against. advance_machine_queue
    returns the same pinned window on every member, so this must hold
    across the whole pool exactly as it does for a single machine."""
    calendar_a = build_machine_calendar(WEEKDAY_HOURS, None, {})
    calendar_b = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    manual_start = datetime(2026, 8, 5, 13, 0, tzinfo=UTC)
    manual_end = datetime(2026, 8, 5, 15, 0, tzinfo=UTC)
    orders = [
        make_context(
            order_id=1,
            queue_sequence=1,
            pinned=True,
            existing_planned_start=manual_start,
            existing_planned_end=manual_end,
        ),
    ]
    results = {r.order_id: r for r in walk_pool_queue(orders, {1: calendar_a, 2: calendar_b}, now)}
    assert results[1].planned_start == manual_start
    assert results[1].planned_end == manual_end


def test_walk_pool_queue_in_progress_order_anchors_to_actual_start():
    """An IN_PROGRESS order (already running, e.g. a defensive/edge case:
    a real pool order only reaches IN_PROGRESS after Start resolves it to
    a concrete machine_id, taking it out of the pool bucket entirely, but
    the pure function must still honor the anchor correctly if ever
    handed one) places against whichever member finishes it soonest from
    actual_start, same as the single-machine walk."""
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    actual_start = datetime.combine(MONDAY, datetime.min.time(), tzinfo=UTC) + timedelta(hours=9)
    orders = [
        make_context(
            order_id=1,
            queue_sequence=1,
            status=ProductionOrderStatus.IN_PROGRESS.value,
            actual_start=actual_start,
            estimated_duration_minutes=60,
        ),
    ]
    results = {r.order_id: r for r in walk_pool_queue(orders, {1: calendar}, now)}
    assert results[1].planned_start == actual_start
    assert results[1].planned_end == actual_start + timedelta(hours=1)


def test_walk_pool_queue_empty_pool_leaves_orders_dateless_without_no_machine_assigned():
    """A pool with no members (member_calendars={}) can't place anything,
    but, unlike schedule_unassigned_orders, never flags
    NO_MACHINE_ASSIGNED either: this order still reflects a deliberate
    pool assignment, just an unplaceable one."""
    order = make_context(order_id=1, machine_pool_id=5)
    results = {r.order_id: r for r in walk_pool_queue([order], {}, datetime.now(UTC))}
    assert results[1].planned_start is None
    assert results[1].planned_end is None
    assert ScheduleConflictReason.NO_MACHINE_ASSIGNED.value not in results[1].conflicts


def test_walk_pool_queue_honors_queue_sequence_order_not_list_order():
    """Orders are walked in queue_sequence order regardless of the input
    list's order, mirroring walk_machine_queue's own sort."""
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    orders = [
        make_context(order_id=2, queue_sequence=2, estimated_duration_minutes=60),
        make_context(order_id=1, queue_sequence=1, estimated_duration_minutes=120),
    ]
    results = {r.order_id: r for r in walk_pool_queue(orders, {1: calendar}, now)}
    assert results[1].planned_start.hour == 8
    assert results[2].planned_start == results[1].planned_end


def _occupied_until(end: datetime) -> OrderSchedulingContext:
    """A pinned machine-assigned order that keeps its member busy until end."""
    return make_context(
        order_id=99,
        pinned=True,
        existing_planned_start=end - timedelta(hours=1),
        existing_planned_end=end,
    )


def test_walk_pool_queue_seeded_cursor_delays_placement_past_the_seed():
    """A member's own machine-assigned queue seeds its cursor for the pool
    merge. The pool order must not be placed any earlier than where that
    queue ended, exactly as if it had already advanced there via a prior
    walk."""
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    order = make_context(order_id=1, queue_sequence=1, estimated_duration_minutes=60)
    seed = datetime.combine(MONDAY, datetime.min.time(), tzinfo=UTC) + timedelta(hours=10)

    unseeded = {r.order_id: r for r in walk_pool_queue([order], {1: calendar}, now)}
    seeded = {
        r.order_id: r
        for r in walk_pool_queue(
            [order], {1: calendar}, now, machine_queues={1: [_occupied_until(seed)]}
        )
    }

    assert unseeded[1].planned_start.hour == 8  # unseeded: default behaviour, unchanged
    assert seeded[1].planned_start == seed  # seeded: floored at the seed cursor instead
    assert seeded[1].planned_end == seed + timedelta(hours=1)


def test_walk_pool_queue_a_member_missing_from_seed_cursors_starts_at_none():
    """A member without a machine-assigned queue of its own starts the pool
    merge with an empty cursor, independent of how far another member's
    queue already reaches."""
    calendar_seeded = build_machine_calendar(WEEKDAY_HOURS, None, {})
    calendar_unseeded = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    seed = datetime.combine(MONDAY, datetime.min.time(), tzinfo=UTC) + timedelta(hours=10)
    order = make_context(order_id=1, queue_sequence=1, estimated_duration_minutes=60)

    results = {
        r.order_id: r
        for r in walk_pool_queue(
            [order],
            {1: calendar_seeded, 2: calendar_unseeded},
            now,
            machine_queues={1: [_occupied_until(seed)]},
        )
    }
    # Member 2 starts at None (unseeded) and so finishes this order at 9:00,
    # strictly earlier than member 1's seeded 10:00 start, so earliest-finish
    # selection must prefer it.
    assert results[1].planned_start.hour == 8
    assert results[1].planned_end.hour == 9


def test_trial_machine_id_set_to_the_winning_member_on_a_dated_pool_placement():
    busy_calendar = build_machine_calendar({**WEEKDAY_HOURS, 0: 60}, None, {})  # Monday: 1h only
    free_calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})  # Monday: 8h
    now = datetime.combine(MONDAY, datetime.min.time())
    order = make_context(order_id=1, queue_sequence=1, estimated_duration_minutes=120)

    results = {
        r.order_id: r for r in walk_pool_queue([order], {1: busy_calendar, 2: free_calendar}, now)
    }
    assert results[1].trial_machine_id == 2  # only member 2 can finish it same-day


def test_trial_machine_id_is_none_when_the_best_trial_has_no_dates():
    """A PAUSED order still nominally 'wins' a member by iteration order
    (see _best_member_placement), but there's no real placement to
    attribute to that member, so trial_machine_id must stay None."""
    calendar_a = build_machine_calendar(WEEKDAY_HOURS, None, {})
    calendar_b = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    order = make_context(
        order_id=1,
        queue_sequence=1,
        status=ProductionOrderStatus.PAUSED.value,
        estimated_duration_minutes=60,
    )
    results = {r.order_id: r for r in walk_pool_queue([order], {1: calendar_a, 2: calendar_b}, now)}
    assert results[1].planned_start is None
    assert results[1].trial_machine_id is None


def test_trial_machine_id_is_none_on_machine_queue_results():
    """A plain machine-assigned order never floats. trial_machine_id has
    no meaning there and must stay None even for a normally-dated order."""
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    order = make_context(order_id=1, queue_sequence=1, estimated_duration_minutes=60)
    results = walk_machine_queue([order], calendar, now)
    assert results[0].planned_start is not None
    assert results[0].trial_machine_id is None


def test_place_accepts_a_timezone_aware_earliest():
    """Regression: actual_start/planned_* are `timestamptz`, so they read back
    from the database aware, while the calendar's day windows are built from a
    bare date. Comparing the two raised "can't compare offset-naive and
    offset-aware datetimes" inside snap_to_working_start."""
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    aware = datetime(2026, 7, 27, 9, 0, tzinfo=UTC)

    start, end = place(aware, 60, calendar)

    assert start.tzinfo is not None
    assert end.tzinfo is not None
    assert start == datetime(2026, 7, 27, 9, 0, tzinfo=UTC)


def test_place_reads_a_naive_earliest_as_utc():
    """Naive input stays supported and means UTC, the frame these columns
    were always written in."""
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})

    from_naive = place(datetime(2026, 7, 27, 9, 0), 60, calendar)
    from_aware = place(datetime(2026, 7, 27, 9, 0, tzinfo=UTC), 60, calendar)

    assert from_naive == from_aware


def test_running_order_with_aware_actual_start_walks_the_queue():
    """The exact path from the AutoPlan traceback: an IN_PROGRESS order
    anchors to actual_start, which goes straight into place()."""
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    ctx = make_context(
        order_id=1,
        status="in_progress",
        actual_start=datetime(2026, 7, 27, 9, 0, tzinfo=UTC),
        estimated_duration_minutes=60,
    )

    planned_start, planned_end, cursor = advance_machine_queue(
        ctx, None, calendar, datetime(2026, 7, 27, 8, 0, tzinfo=UTC)
    )

    assert planned_start == datetime(2026, 7, 27, 9, 0, tzinfo=UTC)
    assert planned_end == datetime(2026, 7, 27, 10, 0, tzinfo=UTC)
    assert cursor == planned_end


def test_queue_mixes_an_aware_running_order_with_a_naive_now():
    """A running order (aware, from the DB) followed by a queued one placed
    against `now`, the two must not meet as different shapes."""
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    running = make_context(
        order_id=1,
        queue_sequence=1,
        status="in_progress",
        actual_start=datetime(2026, 7, 27, 9, 0, tzinfo=UTC),
        estimated_duration_minutes=60,
    )
    queued = make_context(order_id=2, queue_sequence=2, estimated_duration_minutes=60)

    results = walk_machine_queue([running, queued], calendar, datetime(2026, 7, 27, 8, 0))

    assert [r.planned_start for r in results] == [
        datetime(2026, 7, 27, 9, 0, tzinfo=UTC),
        datetime(2026, 7, 27, 10, 0, tzinfo=UTC),
    ]


def test_pinned_order_with_aware_window_is_returned_aware():
    """A pinned order short-circuits placement and returns its stored window
    directly, that window is `timestamptz` too."""
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    ctx = make_context(
        order_id=1,
        pinned=True,
        existing_planned_start=datetime(2026, 7, 27, 9, 0, tzinfo=UTC),
        existing_planned_end=datetime(2026, 7, 27, 11, 0, tzinfo=UTC),
    )

    planned_start, planned_end, cursor = advance_machine_queue(
        ctx, None, calendar, datetime(2026, 7, 27, 8, 0, tzinfo=UTC)
    )

    assert planned_start.tzinfo is not None
    assert planned_end.tzinfo is not None
    assert cursor == planned_end
