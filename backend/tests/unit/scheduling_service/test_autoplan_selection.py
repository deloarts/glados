"""
Unit tests for AutoPlan machine/pool selection and dispatch strategies.
No database, no HTTP, pure functions only.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta

from src.modules.fulfillment.domain.services.scheduling import build_machine_calendar
from src.modules.fulfillment.domain.services.scheduling import resolve_algorithm_strategies
from src.modules.fulfillment.domain.services.scheduling import resolve_best_machine
from src.modules.fulfillment.domain.services.scheduling import resolve_best_pool
from src.modules.fulfillment.domain.services.scheduling import resolve_least_loaded_machine
from src.modules.fulfillment.domain.services.scheduling import resolve_least_loaded_pool
from src.modules.fulfillment.domain.services.scheduling import resolve_machine_for_candidate
from src.modules.fulfillment.domain.services.scheduling import resolve_pool_for_candidate
from src.modules.fulfillment.domain.value_objects.auto_plan_algorithm import AutoPlanAlgorithm
from tests.unit.scheduling_service._helpers import MONDAY
from tests.unit.scheduling_service._helpers import WEEKDAY_HOURS
from tests.unit.scheduling_service._helpers import make_context


def test_resolve_best_machine_returns_none_when_no_eligible_machines():
    ctx = make_context(estimated_duration_minutes=60)
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    result = resolve_best_machine(ctx, [], {}, {1: calendar}, now)
    assert result is None


def test_resolve_best_machine_picks_the_earliest_finishing_machine():
    ctx = make_context(estimated_duration_minutes=60)
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    # Machine 1's cursor is already at 10:00 (within the working day), so it
    # finishes at 11:00; machine 2 is free from the top of the day and
    # snaps to the 08:00 day-start, finishing at 09:00, sooner, despite
    # being tried second.
    machine_cursors = {
        1: datetime.combine(MONDAY, datetime.min.time()) + timedelta(hours=10),
        2: None,
    }
    calendars = {1: calendar, 2: calendar}
    result = resolve_best_machine(ctx, [1, 2], machine_cursors, calendars, now)
    assert result is not None
    best_machine_id, _ = result
    assert best_machine_id == 2


def test_resolve_best_machine_returns_the_chosen_machines_next_cursor():
    ctx = make_context(estimated_duration_minutes=60)
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    result = resolve_best_machine(ctx, [1], {1: None}, {1: calendar}, now)
    assert result is not None
    best_machine_id, next_cursor = result
    assert best_machine_id == 1
    assert next_cursor == datetime.combine(MONDAY, datetime.min.time(), tzinfo=UTC).replace(hour=9)


def test_resolve_best_machine_ignores_queue_lengths_when_a_real_date_exists():
    """A plannable candidate (at least one trial produces a real
    planned_end) must keep picking by earliest finish. The least-loaded
    fallback below only fires when EVERY trial ties at the datetime.max
    sentinel. Machine 2 finishes soonest but is deliberately given a much
    longer queue than machine 1, proving machine_queue_lengths never
    overrides a real date."""
    ctx = make_context(estimated_duration_minutes=60)
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    machine_cursors = {
        1: datetime.combine(MONDAY, datetime.min.time()) + timedelta(hours=10),
        2: None,
    }
    calendars = {1: calendar, 2: calendar}
    machine_queue_lengths = {1: 0, 2: 100}  # machine 2 heavily loaded already

    result = resolve_best_machine(
        ctx, [1, 2], machine_cursors, calendars, now, machine_queue_lengths
    )

    assert result is not None
    best_machine_id, _ = result
    assert best_machine_id == 2  # still the earliest-finishing machine


def test_resolve_best_machine_spreads_unplannable_candidates_by_load():
    """An unplannable candidate (chain-unknown, nothing physically
    available yet) returns planned_end=None on EVERY machine, because the
    unknowable state is machine-independent, so every trial ties at the
    datetime.max sentinel and there is no real earliest-finish signal to
    choose by. Without the least-loaded fallback, the strict `<` tie-break
    always keeps whichever machine iterates first, backlogging it with
    every chain-blocked candidate in the run (empirically confirmed: 5
    unplannable candidates x machines [1,2,3] all landed on machine 1).
    Simulates AutoPlan's own loop: each pick's machine_queue_lengths entry
    is bumped before the next candidate is resolved, same as AutoPlan.
    execute() does after every placement."""
    ctx = make_context(
        predecessor_chain_unknown=True,
        upstream_input_available=False,
        position_sequence=2,
    )
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    machine_cursors: dict[int, datetime | None] = {1: None, 2: None, 3: None}
    calendars = {1: calendar, 2: calendar, 3: calendar}
    machine_queue_lengths = {1: 0, 2: 0, 3: 0}

    assignments = []
    for _ in range(5):
        result = resolve_best_machine(
            ctx, [1, 2, 3], machine_cursors, calendars, now, machine_queue_lengths
        )
        assert result is not None
        chosen, _ = result
        assignments.append(chosen)
        machine_queue_lengths[chosen] += 1

    assert assignments != [1, 1, 1, 1, 1]
    assert set(assignments) == {1, 2, 3}  # every machine absorbs at least one
    counts = {mid: assignments.count(mid) for mid in (1, 2, 3)}
    assert max(counts.values()) <= 2  # ceil(5/3), never all 5 on one machine


def test_resolve_best_machine_breaks_unplannable_ties_by_ascending_machine_id():
    """Every machine starts at queue length 0 (an equal tie), so the
    fallback's secondary tie-break must be deterministic, ascending
    machine id, same convention as resolve_least_loaded_machine."""
    ctx = make_context(
        predecessor_chain_unknown=True,
        upstream_input_available=False,
        position_sequence=2,
    )
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    calendars = {1: calendar, 2: calendar, 3: calendar}

    result = resolve_best_machine(
        ctx, [3, 2, 1], {1: None, 2: None, 3: None}, calendars, now, {1: 0, 2: 0, 3: 0}
    )

    assert result is not None
    best_machine_id, _ = result
    assert best_machine_id == 1


def test_resolve_best_pool_returns_none_when_no_eligible_pools():
    ctx = make_context(estimated_duration_minutes=60)
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    result = resolve_best_pool(ctx, [], {}, {}, {1: calendar}, now)
    assert result is None


def test_resolve_best_pool_picks_the_earliest_finishing_pool():
    """Pool analog of resolve_best_machine_picks_the_earliest_finishing_
    machine, one level up: pool 10's only member (machine 1) is already
    busy until 10:00, pool 20's only member (machine 2) is free from the
    top of the day and finishes sooner despite being tried second."""
    ctx = make_context(estimated_duration_minutes=60)
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    machine_cursors = {
        1: datetime.combine(MONDAY, datetime.min.time()) + timedelta(hours=10),
        2: None,
    }
    calendars = {1: calendar, 2: calendar}
    pool_machine_ids = {10: [1], 20: [2]}

    result = resolve_best_pool(ctx, [10, 20], pool_machine_ids, machine_cursors, calendars, now)

    assert result is not None
    best_pool_id, best_member_id, _ = result
    assert best_pool_id == 20
    assert best_member_id == 2


def test_resolve_best_pool_picks_the_earliest_finishing_member_within_a_pool():
    """A pool's own result is whichever of its OWN members finishes this
    candidate earliest, not just whichever member is tried first."""
    ctx = make_context(estimated_duration_minutes=60)
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    machine_cursors = {
        1: datetime.combine(MONDAY, datetime.min.time()) + timedelta(hours=10),
        2: None,
    }
    calendars = {1: calendar, 2: calendar}

    result = resolve_best_pool(ctx, [10], {10: [1, 2]}, machine_cursors, calendars, now)

    assert result is not None
    best_pool_id, best_member_id, _ = result
    assert best_pool_id == 10
    assert best_member_id == 2


def test_resolve_best_pool_skips_members_outside_the_run_scope():
    """A member not present in `calendars` (out of this run's cmd.
    machine_ids scope) is simply skipped, not a KeyError."""
    ctx = make_context(estimated_duration_minutes=60)
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())

    result = resolve_best_pool(ctx, [10], {10: [1, 2]}, {1: None}, {1: calendar}, now)

    assert result is not None
    best_pool_id, best_member_id, _ = result
    assert best_pool_id == 10
    assert best_member_id == 1


def test_resolve_best_pool_falls_back_to_least_loaded_when_every_trial_is_unplannable():
    """Mirrors resolve_best_machine's own chain-unknown fallback (see its
    docstring) one level up: every member of every pool returns
    planned_end=None (chain-unknown, nothing physically available yet),
    so there's no real earliest-finish signal to choose by, and it falls back
    to ascending pool_queue_lengths instead of always keeping whichever
    pool was tried first."""
    ctx = make_context(
        predecessor_chain_unknown=True,
        upstream_input_available=False,
        position_sequence=2,
    )
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    calendars = {1: calendar, 2: calendar}
    pool_machine_ids = {10: [1], 20: [2]}
    pool_queue_lengths = {10: 5, 20: 0}

    result = resolve_best_pool(
        ctx, [10, 20], pool_machine_ids, {1: None, 2: None}, calendars, now, pool_queue_lengths
    )

    assert result is not None
    best_pool_id, _, _ = result
    assert best_pool_id == 20


def test_resolve_least_loaded_machine_returns_none_when_no_eligible_machines():
    ctx = make_context(estimated_duration_minutes=60)
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    result = resolve_least_loaded_machine(ctx, [], {}, {}, {1: calendar}, now)
    assert result is None


def test_resolve_least_loaded_machine_ignores_finish_time_picks_least_booked():
    """Machine 2 would finish this order soonest (like resolve_best_machine
    would pick), but machine 1 has far fewer total booked minutes, so least-
    loaded selection must pick machine 1 anyway."""
    ctx = make_context(estimated_duration_minutes=60)
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    machine_cursors = {
        1: datetime.combine(MONDAY, datetime.min.time()) + timedelta(hours=10),
        2: None,
    }
    machine_booked_minutes = {1: 60, 2: 2000}
    calendars = {1: calendar, 2: calendar}

    result = resolve_least_loaded_machine(
        ctx, [1, 2], machine_cursors, machine_booked_minutes, calendars, now
    )

    assert result is not None
    best_machine_id, _ = result
    assert best_machine_id == 1


def test_resolve_least_loaded_machine_breaks_ties_by_machine_id():
    ctx = make_context(estimated_duration_minutes=60)
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    calendars = {1: calendar, 2: calendar}

    result = resolve_least_loaded_machine(
        ctx, [2, 1], {1: None, 2: None}, {1: 100, 2: 100}, calendars, now
    )

    assert result is not None
    best_machine_id, _ = result
    assert best_machine_id == 1


def test_resolve_least_loaded_pool_returns_none_when_no_eligible_pools():
    ctx = make_context(estimated_duration_minutes=60)
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    result = resolve_least_loaded_pool(ctx, [], {}, {}, {}, {1: calendar}, now)
    assert result is None


def test_resolve_least_loaded_pool_ignores_finish_time_picks_least_aggregated_booked():
    """Pool 20 (member 2) would finish this candidate soonest, but pool
    10's member carries far fewer total booked minutes, so least-loaded
    selection must pick pool 10 anyway, same load-over-finish-time
    judgment resolve_least_loaded_machine already makes one level down."""
    ctx = make_context(estimated_duration_minutes=60)
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    machine_cursors = {
        1: datetime.combine(MONDAY, datetime.min.time()) + timedelta(hours=10),
        2: None,
    }
    machine_booked_minutes = {1: 60, 2: 2000}
    calendars = {1: calendar, 2: calendar}
    pool_machine_ids = {10: [1], 20: [2]}

    result = resolve_least_loaded_pool(
        ctx, [10, 20], pool_machine_ids, machine_cursors, machine_booked_minutes, calendars, now
    )

    assert result is not None
    best_pool_id, best_member_id, _ = result
    assert best_pool_id == 10
    assert best_member_id == 1


def test_resolve_least_loaded_pool_aggregates_booked_minutes_across_members():
    """The load signal is the SUM across a pool's own members, not just
    one of them: pool 10 (members 1+2, 1000+1000=2000 total) must lose
    to pool 20 (member 3 alone, 500 total) even though neither single
    member of pool 10 individually out-loads member 3."""
    ctx = make_context(estimated_duration_minutes=60)
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    machine_cursors = {1: None, 2: None, 3: None}
    machine_booked_minutes = {1: 1000, 2: 1000, 3: 500}
    calendars = {1: calendar, 2: calendar, 3: calendar}
    pool_machine_ids = {10: [1, 2], 20: [3]}

    result = resolve_least_loaded_pool(
        ctx, [10, 20], pool_machine_ids, machine_cursors, machine_booked_minutes, calendars, now
    )

    assert result is not None
    best_pool_id, _, _ = result
    assert best_pool_id == 20


def test_resolve_machine_for_candidate_dispatch_routes_to_each_strategy():
    ctx = make_context(estimated_duration_minutes=60)
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    machine_cursors = {
        1: datetime.combine(MONDAY, datetime.min.time()) + timedelta(hours=10),
        2: None,
    }
    machine_booked_minutes = {1: 60, 2: 2000}
    calendars = {1: calendar, 2: calendar}

    earliest_finish_default = resolve_machine_for_candidate(
        "unknown-strategy", ctx, [1, 2], machine_cursors, machine_booked_minutes, calendars, now
    )
    least_loaded = resolve_machine_for_candidate(
        "least_loaded", ctx, [1, 2], machine_cursors, machine_booked_minutes, calendars, now
    )

    assert earliest_finish_default is not None and earliest_finish_default[0] == 2
    assert least_loaded is not None and least_loaded[0] == 1


def test_resolve_pool_for_candidate_dispatch_routes_to_each_strategy():
    ctx = make_context(estimated_duration_minutes=60)
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    now = datetime.combine(MONDAY, datetime.min.time())
    machine_cursors = {
        1: datetime.combine(MONDAY, datetime.min.time()) + timedelta(hours=10),
        2: None,
    }
    machine_booked_minutes = {1: 60, 2: 2000}
    calendars = {1: calendar, 2: calendar}
    pool_machine_ids = {10: [1], 20: [2]}

    earliest_finish_default = resolve_pool_for_candidate(
        "unknown-strategy",
        ctx,
        [10, 20],
        pool_machine_ids,
        machine_cursors,
        machine_booked_minutes,
        calendars,
        now,
    )
    least_loaded = resolve_pool_for_candidate(
        "least_loaded",
        ctx,
        [10, 20],
        pool_machine_ids,
        machine_cursors,
        machine_booked_minutes,
        calendars,
        now,
    )

    assert earliest_finish_default is not None and earliest_finish_default[0] == 20
    assert least_loaded is not None and least_loaded[0] == 10


def test_resolve_algorithm_strategies_maps_every_named_algorithm():
    for algorithm in AutoPlanAlgorithm:
        ordering, selection = resolve_algorithm_strategies(algorithm.value)
        assert ordering and selection  # every named algorithm resolves to a real pair


def test_resolve_algorithm_strategies_urgent_first_matches_todays_default_behavior():
    ordering, selection = resolve_algorithm_strategies(AutoPlanAlgorithm.URGENT_FIRST.value)
    assert ordering == "priority_edd"
    assert selection == "earliest_finish"


def test_resolve_algorithm_strategies_falls_back_to_default_for_unknown_value():
    assert resolve_algorithm_strategies("not-a-real-algorithm") == resolve_algorithm_strategies(
        AutoPlanAlgorithm.default().value
    )
