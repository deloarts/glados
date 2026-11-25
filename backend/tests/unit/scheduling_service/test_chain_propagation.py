"""
Unit tests for schedule_all_propagated, the multi-pass wrapper around
schedule_all that lets an entire lot chain move within one recompute
instead of lagging a pass behind. Builds OrderSchedulingContext values
directly (via dataclasses.replace on top of the shared make_context
factory) rather than through the application layer, so these tests stay
pure-domain, no database, no HTTP.
"""

from dataclasses import replace
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from itertools import pairwise

from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.domain.entities.lot_step import LotStep
from src.modules.fulfillment.domain.services.scheduling import PredecessorPosition
from src.modules.fulfillment.domain.services.scheduling import build_machine_calendar
from src.modules.fulfillment.domain.services.scheduling import resolve_position_lead_days
from src.modules.fulfillment.domain.services.scheduling import schedule_all
from src.modules.fulfillment.domain.services.scheduling import schedule_all_propagated
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.schedule_conflict import ScheduleConflictReason
from tests.unit.scheduling_service._helpers import MONDAY
from tests.unit.scheduling_service._helpers import WEEKDAY_HOURS
from tests.unit.scheduling_service._helpers import make_context

NOW = datetime.combine(MONDAY, datetime.min.time())
STALE = MONDAY - timedelta(days=30)


def _step(
    role: StepRole = StepRole.FABRICATION,
    fabrication_method_lead_time_days: int | None = None,
) -> LotStep:
    """A minimal LotStep for resolve_position_lead_days tests. Only role
    and fabrication_method_lead_time_days matter to that function, every
    other field is a placeholder."""
    return LotStep(
        id=0,
        created=date(2026, 1, 1),
        note=None,
        estimated_setup_minutes=None,
        estimated_minutes_per_piece=None,
        sequence=1,
        creator_id=1,
        fabrication_method_id=1 if role == StepRole.FABRICATION.value else None,
        lot_id=1,
        position_id=1,
        source_process_id=None,
        role=role,
        inspection_method_id=2 if role == StepRole.INSPECTION.value else None,
        fabrication_method_lead_time_days=fabrication_method_lead_time_days,
    )


def _calendar():
    return build_machine_calendar(WEEKDAY_HOURS, None, {})


def test_manual_successor_uses_the_in_run_predecessor_end_not_a_stale_stored_date():
    """Position 2, in the manual queue, must start from position 1's own
    in-run placement (plus the response-time buffer) even though its
    context was built with a badly stale predecessor_ready_at. This is the exact
    bug schedule_all_propagated exists to fix (a successor lagging one
    recompute behind its predecessor's real end)."""
    calendar = _calendar()

    position_1 = replace(
        make_context(order_id=1, queue_sequence=1, estimated_duration_minutes=200),
        lot_id=1,
        lot_position_id=10,
    )
    position_2 = replace(
        make_context(
            order_id=2,
            queue_sequence=1,
            position_sequence=2,
            is_manual_step=True,
            estimated_duration_minutes=20,
            predecessor_ready_at=STALE,
        ),
        lot_id=1,
        lot_position_id=20,
        response_time_days=1,
        predecessor_positions=(
            PredecessorPosition(
                position_id=10,
                sequence=1,
                kind=LotPositionKind.INTERNAL.value,
                external_ready_at=None,
                stored_internal_ready_at=STALE,
            ),
        ),
    )

    result, passes = schedule_all_propagated(
        machine_queues={1: [position_1]},
        machine_calendars={1: calendar},
        pool_queues={},
        pool_members={},
        manual_queue=[position_2],
        manual_calendar=calendar,
        unassigned=[],
        now=NOW,
    )

    predecessor_end = result.by_machine[1][0].planned_end
    assert predecessor_end is not None
    assert predecessor_end.date() == MONDAY  # 200 minutes fits inside Monday's 8h window

    successor = result.manual[0]
    assert successor.planned_start is not None
    # The successor starts right at the predecessor's in-run end, not from
    # the 30-day-stale value the context started with. An in-house
    # predecessor adds no response time.
    assert successor.planned_start == predecessor_end
    assert passes > 1  # the stale value only self-heals once a refresh pass ran


def test_undated_predecessor_leaves_the_successor_undated_despite_a_stale_stored_date():
    """When the walk itself cannot date position 1 (it's PAUSED, so it
    consumes no capacity and stays dateless), position 2 must become
    chain-unknown and stay undated too, even though its context started
    out with a stale-but-present predecessor_ready_at that would have let
    it schedule on a naive single pass."""
    calendar = _calendar()

    position_1 = replace(
        make_context(
            order_id=1,
            queue_sequence=1,
            status=ProductionOrderStatus.PAUSED.value,
            estimated_duration_minutes=200,
        ),
        lot_id=1,
        lot_position_id=10,
    )
    position_2 = replace(
        make_context(
            order_id=2,
            queue_sequence=1,
            position_sequence=2,
            estimated_duration_minutes=30,
            upstream_input_available=False,
            predecessor_ready_at=MONDAY,
            predecessor_chain_unknown=False,
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

    result, _passes = schedule_all_propagated(
        machine_queues={1: [position_1], 2: [position_2]},
        machine_calendars={1: calendar, 2: calendar},
        pool_queues={},
        pool_members={},
        manual_queue=[],
        manual_calendar=calendar,
        unassigned=[],
        now=NOW,
    )

    assert result.by_machine[1][0].planned_start is None
    assert result.by_machine[2][0].planned_start is None
    assert result.by_machine[2][0].planned_end is None


def test_three_position_chain_converges_within_three_passes():
    """A 3-position chain, each context built with a badly stale
    predecessor_ready_at (a different stale value per link so each one
    genuinely needs its own refresh), must settle onto the real in-run
    dates and report the number of passes it took to get there."""
    calendar = _calendar()
    stale_1 = MONDAY + timedelta(days=7)
    stale_2 = MONDAY + timedelta(days=14)

    position_1 = replace(
        make_context(order_id=1, queue_sequence=1, estimated_duration_minutes=480),
        lot_id=1,
        lot_position_id=10,
    )
    position_2 = replace(
        make_context(
            order_id=2,
            queue_sequence=1,
            position_sequence=2,
            estimated_duration_minutes=480,
            predecessor_ready_at=stale_1,
        ),
        lot_id=1,
        lot_position_id=20,
        predecessor_positions=(
            PredecessorPosition(
                position_id=10,
                sequence=1,
                kind=LotPositionKind.INTERNAL.value,
                external_ready_at=None,
                stored_internal_ready_at=stale_1,
            ),
        ),
    )
    position_3 = replace(
        make_context(
            order_id=3,
            queue_sequence=1,
            position_sequence=3,
            estimated_duration_minutes=60,
            predecessor_ready_at=stale_2,
        ),
        lot_id=1,
        lot_position_id=30,
        predecessor_positions=(
            PredecessorPosition(
                position_id=20,
                sequence=2,
                kind=LotPositionKind.INTERNAL.value,
                external_ready_at=None,
                stored_internal_ready_at=stale_2,
            ),
        ),
    )

    result, passes = schedule_all_propagated(
        machine_queues={1: [position_1], 2: [position_2], 3: [position_3]},
        machine_calendars={1: calendar, 2: calendar, 3: calendar},
        pool_queues={},
        pool_members={},
        manual_queue=[],
        manual_calendar=calendar,
        unassigned=[],
        now=NOW,
    )

    assert passes <= 3
    end_1 = result.by_machine[1][0].planned_end
    end_2 = result.by_machine[2][0].planned_end
    start_3 = result.by_machine[3][0].planned_start
    assert end_1 is not None and end_1.date() == MONDAY
    # Each step starts when the one before it ends, not on the stale dates.
    assert end_2 is not None and end_2.date() == MONDAY + timedelta(days=1)
    start_2 = result.by_machine[2][0].planned_start
    assert start_2 is not None and start_2 >= end_1
    assert start_3 is not None and start_3 >= end_2
    assert start_3.date() < stale_2


def test_max_passes_one_reproduces_the_old_single_pass_behaviour():
    """max_passes=1 must produce exactly one schedule_all call and never
    refresh anything: the pre-propagation behaviour, kept reachable as a
    literal regression guard against the wrapper's own convergence loop."""
    calendar = _calendar()

    position_1 = replace(
        make_context(order_id=1, queue_sequence=1, estimated_duration_minutes=200),
        lot_id=1,
        lot_position_id=10,
    )
    position_2 = replace(
        make_context(
            order_id=2,
            queue_sequence=1,
            position_sequence=2,
            is_manual_step=True,
            estimated_duration_minutes=20,
            predecessor_ready_at=STALE,
        ),
        lot_id=1,
        lot_position_id=20,
        response_time_days=1,
        predecessor_positions=(
            PredecessorPosition(
                position_id=10,
                sequence=1,
                kind=LotPositionKind.INTERNAL.value,
                external_ready_at=None,
                stored_internal_ready_at=STALE,
            ),
        ),
    )

    kwargs = dict(
        machine_queues={1: [position_1]},
        machine_calendars={1: calendar},
        pool_queues={},
        pool_members={},
        manual_queue=[position_2],
        manual_calendar=calendar,
        unassigned=[],
        now=NOW,
    )
    expected = schedule_all(**kwargs)  # type: ignore[arg-type]
    result, passes = schedule_all_propagated(max_passes=1, **kwargs)  # type: ignore[arg-type]

    assert passes == 1
    assert result.manual == expected.manual
    assert result.by_machine == expected.by_machine


def test_pinned_and_in_progress_successors_are_unaffected_by_propagation():
    """A pinned window or an actual_start anchor is a fixed fact the walk
    never recomputes (advance_machine_queue's own pinned/IN_PROGRESS
    branches ignore predecessor_ready_at entirely), so refreshing the
    underlying predecessor chain across passes must not perturb either,
    even though the chain itself does genuinely change and drives more
    than one pass."""
    calendar = _calendar()

    position_1 = replace(
        make_context(order_id=1, queue_sequence=1, estimated_duration_minutes=200),
        lot_id=1,
        lot_position_id=10,
    )
    pinned_start = datetime(MONDAY.year, MONDAY.month, MONDAY.day, 10, tzinfo=UTC)
    pinned_end = datetime(MONDAY.year, MONDAY.month, MONDAY.day, 11, tzinfo=UTC)
    pinned_successor = replace(
        make_context(
            order_id=2,
            queue_sequence=1,
            position_sequence=2,
            pinned=True,
            existing_planned_start=pinned_start,
            existing_planned_end=pinned_end,
            estimated_duration_minutes=20,
            predecessor_ready_at=STALE,
        ),
        lot_id=1,
        lot_position_id=21,
        predecessor_positions=(
            PredecessorPosition(
                position_id=10,
                sequence=1,
                kind=LotPositionKind.INTERNAL.value,
                external_ready_at=None,
                stored_internal_ready_at=STALE,
            ),
        ),
    )
    actual_start = datetime(MONDAY.year, MONDAY.month, MONDAY.day, 9, tzinfo=UTC)
    in_progress_successor = replace(
        make_context(
            order_id=3,
            queue_sequence=1,
            position_sequence=2,
            status=ProductionOrderStatus.IN_PROGRESS.value,
            actual_start=actual_start,
            estimated_duration_minutes=30,
            predecessor_ready_at=STALE,
        ),
        lot_id=1,
        lot_position_id=22,
        predecessor_positions=(
            PredecessorPosition(
                position_id=10,
                sequence=1,
                kind=LotPositionKind.INTERNAL.value,
                external_ready_at=None,
                stored_internal_ready_at=STALE,
            ),
        ),
    )

    result, passes = schedule_all_propagated(
        machine_queues={1: [position_1], 2: [pinned_successor], 3: [in_progress_successor]},
        machine_calendars={1: calendar, 2: calendar, 3: calendar},
        pool_queues={},
        pool_members={},
        manual_queue=[],
        manual_calendar=calendar,
        unassigned=[],
        now=NOW,
    )

    assert passes >= 2  # the predecessor chain itself did change across passes
    pinned_result = result.by_machine[2][0]
    assert pinned_result.planned_start == pinned_start
    assert pinned_result.planned_end == pinned_end
    in_progress_result = result.by_machine[3][0]
    assert in_progress_result.planned_start == actual_start
    assert in_progress_result.planned_end == actual_start + timedelta(minutes=30)


def test_typed_date_earlier_than_predecessor_flags_the_successor():
    """An EXTERNAL predecessor's typed_external_date earlier than the
    in-run end of the INTERNAL chain feeding it raises
    EXTERNAL_DATE_BEFORE_PREDECESSOR on the first INTERNAL/MIXED position
    after it. The typed date itself is never rewritten or cleared, this
    is purely an added conflict flag."""
    calendar = _calendar()
    stale_typed_date = MONDAY - timedelta(days=10)

    position_1 = replace(
        make_context(order_id=1, queue_sequence=1, estimated_duration_minutes=200),
        lot_id=1,
        lot_position_id=10,
    )
    successor = replace(
        make_context(
            order_id=2,
            queue_sequence=1,
            position_sequence=3,
            is_manual_step=True,
            estimated_duration_minutes=20,
        ),
        lot_id=1,
        lot_position_id=30,
        predecessor_positions=(
            PredecessorPosition(
                position_id=10,
                sequence=1,
                kind=LotPositionKind.INTERNAL.value,
                external_ready_at=None,
                stored_internal_ready_at=MONDAY,
            ),
            PredecessorPosition(
                position_id=20,
                sequence=2,
                kind=LotPositionKind.EXTERNAL.value,
                external_ready_at=stale_typed_date,
                stored_internal_ready_at=None,
                typed_external_date=stale_typed_date,
            ),
        ),
    )

    result, _passes = schedule_all_propagated(
        machine_queues={1: [position_1]},
        machine_calendars={1: calendar},
        pool_queues={},
        pool_members={},
        manual_queue=[successor],
        manual_calendar=calendar,
        unassigned=[],
        now=NOW,
    )

    successor_result = result.manual[0]
    assert (
        ScheduleConflictReason.EXTERNAL_DATE_BEFORE_PREDECESSOR.value in successor_result.conflicts
    )


def test_typed_date_later_than_predecessor_does_not_flag_the_successor():
    """A typed date that is comfortably after the chain feeding it is
    perfectly consistent, no conflict is raised."""
    calendar = _calendar()
    later_typed_date = MONDAY + timedelta(days=10)

    position_1 = replace(
        make_context(order_id=1, queue_sequence=1, estimated_duration_minutes=200),
        lot_id=1,
        lot_position_id=10,
    )
    successor = replace(
        make_context(
            order_id=2,
            queue_sequence=1,
            position_sequence=3,
            is_manual_step=True,
            estimated_duration_minutes=20,
        ),
        lot_id=1,
        lot_position_id=30,
        predecessor_positions=(
            PredecessorPosition(
                position_id=10,
                sequence=1,
                kind=LotPositionKind.INTERNAL.value,
                external_ready_at=None,
                stored_internal_ready_at=MONDAY,
            ),
            PredecessorPosition(
                position_id=20,
                sequence=2,
                kind=LotPositionKind.EXTERNAL.value,
                external_ready_at=later_typed_date,
                stored_internal_ready_at=None,
                typed_external_date=later_typed_date,
            ),
        ),
    )

    result, _passes = schedule_all_propagated(
        machine_queues={1: [position_1]},
        machine_calendars={1: calendar},
        pool_queues={},
        pool_members={},
        manual_queue=[successor],
        manual_calendar=calendar,
        unassigned=[],
        now=NOW,
    )

    successor_result = result.manual[0]
    assert (
        ScheduleConflictReason.EXTERNAL_DATE_BEFORE_PREDECESSOR.value
        not in successor_result.conflicts
    )


def test_actual_delivery_present_is_never_flagged_even_if_early():
    """Once an EXTERNAL predecessor has an actual delivery (or
    ready-for-pickup) event, typed_external_date is None. A recorded fact
    is never second-guessed against the chain, no matter how early it
    happened to land."""
    calendar = _calendar()
    early_actual_date = MONDAY - timedelta(days=10)

    position_1 = replace(
        make_context(order_id=1, queue_sequence=1, estimated_duration_minutes=200),
        lot_id=1,
        lot_position_id=10,
    )
    successor = replace(
        make_context(
            order_id=2,
            queue_sequence=1,
            position_sequence=3,
            is_manual_step=True,
            estimated_duration_minutes=20,
        ),
        lot_id=1,
        lot_position_id=30,
        predecessor_positions=(
            PredecessorPosition(
                position_id=10,
                sequence=1,
                kind=LotPositionKind.INTERNAL.value,
                external_ready_at=None,
                stored_internal_ready_at=MONDAY,
            ),
            PredecessorPosition(
                position_id=20,
                sequence=2,
                kind=LotPositionKind.EXTERNAL.value,
                external_ready_at=early_actual_date,
                stored_internal_ready_at=None,
                typed_external_date=None,
            ),
        ),
    )

    result, _passes = schedule_all_propagated(
        machine_queues={1: [position_1]},
        machine_calendars={1: calendar},
        pool_queues={},
        pool_members={},
        manual_queue=[successor],
        manual_calendar=calendar,
        unassigned=[],
        now=NOW,
    )

    successor_result = result.manual[0]
    assert (
        ScheduleConflictReason.EXTERNAL_DATE_BEFORE_PREDECESSOR.value
        not in successor_result.conflicts
    )


def test_only_the_first_internal_position_after_the_stale_external_one_is_flagged():
    """A four-position chain (INTERNAL, stale EXTERNAL, INTERNAL,
    INTERNAL) only raises the conflict on the third position, the first
    INTERNAL/MIXED position after the stale one. The fourth position's own
    predecessor tuple still carries the stale EXTERNAL entry (it's an
    earlier, still-open position of the same lot), but the third position
    already absorbed it, so the fourth is not re-flagged for the same
    contradiction."""
    calendar = _calendar()
    stale_typed_date = MONDAY - timedelta(days=10)

    position_1 = replace(
        make_context(order_id=1, queue_sequence=1, estimated_duration_minutes=200),
        lot_id=1,
        lot_position_id=10,
    )
    internal_pred_1 = PredecessorPosition(
        position_id=10,
        sequence=1,
        kind=LotPositionKind.INTERNAL.value,
        external_ready_at=None,
        stored_internal_ready_at=MONDAY,
    )
    external_pred = PredecessorPosition(
        position_id=20,
        sequence=2,
        kind=LotPositionKind.EXTERNAL.value,
        external_ready_at=stale_typed_date,
        stored_internal_ready_at=None,
        typed_external_date=stale_typed_date,
    )
    position_3 = replace(
        make_context(
            order_id=3, queue_sequence=1, position_sequence=3, estimated_duration_minutes=60
        ),
        lot_id=1,
        lot_position_id=30,
        predecessor_positions=(internal_pred_1, external_pred),
    )
    internal_pred_3 = PredecessorPosition(
        position_id=30,
        sequence=3,
        kind=LotPositionKind.INTERNAL.value,
        external_ready_at=None,
        stored_internal_ready_at=MONDAY,
    )
    position_4 = replace(
        make_context(
            order_id=4, queue_sequence=1, position_sequence=4, estimated_duration_minutes=60
        ),
        lot_id=1,
        lot_position_id=40,
        predecessor_positions=(internal_pred_1, external_pred, internal_pred_3),
    )

    result, _passes = schedule_all_propagated(
        machine_queues={1: [position_1], 3: [position_3], 4: [position_4]},
        machine_calendars={1: calendar, 3: calendar, 4: calendar},
        pool_queues={},
        pool_members={},
        manual_queue=[],
        manual_calendar=calendar,
        unassigned=[],
        now=NOW,
    )

    assert (
        ScheduleConflictReason.EXTERNAL_DATE_BEFORE_PREDECESSOR.value
        in result.by_machine[3][0].conflicts
    )
    assert (
        ScheduleConflictReason.EXTERNAL_DATE_BEFORE_PREDECESSOR.value
        not in result.by_machine[4][0].conflicts
    )


# ══════════════════════════════════════════════════════════════════════
# resolve_position_lead_days
# ══════════════════════════════════════════════════════════════════════


def test_resolve_position_lead_days_supplier_override_wins():
    """A supplier's own external_lead_time_days wins outright, the
    position's steps are never even summed."""
    steps = [_step(fabrication_method_lead_time_days=10)]
    assert resolve_position_lead_days(steps, 3, default_external_lead_days=7) == 3


def test_resolve_position_lead_days_sums_over_steps():
    """No supplier override: the sum of each fabrication step's own lead
    time."""
    steps = [
        _step(fabrication_method_lead_time_days=2),
        _step(fabrication_method_lead_time_days=4),
    ]
    assert resolve_position_lead_days(steps, None, default_external_lead_days=7) == 6


def test_resolve_position_lead_days_inspection_step_contributes_zero():
    """An inspection step has no fabrication method and no lead time of
    its own, so it's skipped outright, never falls back to the admin
    default either."""
    steps = [
        _step(fabrication_method_lead_time_days=2),
        _step(role=StepRole.INSPECTION),
    ]
    assert resolve_position_lead_days(steps, None, default_external_lead_days=7) == 2


def test_resolve_position_lead_days_falls_back_to_admin_default_per_step():
    """A fabrication step with no lead_time_days of its own falls back to
    the admin default, per step, summed alongside any step that does have
    its own value."""
    steps = [
        _step(fabrication_method_lead_time_days=2),
        _step(fabrication_method_lead_time_days=None),
    ]
    assert resolve_position_lead_days(steps, None, default_external_lead_days=7) == 2 + 7


# ══════════════════════════════════════════════════════════════════════
# External forecast
# ══════════════════════════════════════════════════════════════════════


def test_external_predecessor_with_no_typed_date_falls_back_to_its_own_forecast():
    """An EXTERNAL predecessor with neither an actual/typed date still
    feeds the successor's readiness, via its own forecast (pickup = the
    chain before it plus response_time_days, delivery = pickup plus
    lead_days) instead of leaving the chain unknown. The same forecast is
    exposed on the walk result, keyed by the EXTERNAL position's id."""
    calendar = _calendar()

    position_1 = replace(
        make_context(order_id=1, queue_sequence=1, estimated_duration_minutes=200),
        lot_id=1,
        lot_position_id=10,
    )
    successor = replace(
        make_context(
            order_id=2,
            queue_sequence=1,
            position_sequence=3,
            is_manual_step=True,
            estimated_duration_minutes=20,
        ),
        lot_id=1,
        lot_position_id=30,
        response_time_days=1,
        predecessor_positions=(
            PredecessorPosition(
                position_id=10,
                sequence=1,
                kind=LotPositionKind.INTERNAL.value,
                external_ready_at=None,
                stored_internal_ready_at=None,
            ),
            PredecessorPosition(
                position_id=20,
                sequence=2,
                kind=LotPositionKind.EXTERNAL.value,
                external_ready_at=None,
                stored_internal_ready_at=None,
                lead_days=5,
                typed_external_date=None,
            ),
        ),
    )

    result, _passes = schedule_all_propagated(
        machine_queues={1: [position_1]},
        machine_calendars={1: calendar},
        pool_queues={},
        pool_members={},
        manual_queue=[successor],
        manual_calendar=calendar,
        unassigned=[],
        now=NOW,
    )

    predecessor_end = result.by_machine[1][0].planned_end
    assert predecessor_end is not None
    predecessor_end_date = predecessor_end.date()

    expected_pickup = predecessor_end_date + timedelta(days=1)  # response_time_days=1
    expected_delivery = expected_pickup + timedelta(days=5)  # lead_days=5

    forecast = result.external_forecasts[20]
    assert forecast.planned_pickup_date == expected_pickup
    assert forecast.planned_delivery_date == expected_delivery

    successor_result = result.manual[0]
    assert successor_result.planned_start is not None
    # The successor's own readiness buffers the forecast delivery by
    # response_time_days again, the same top-level buffer every other
    # predecessor kind already gets, applied once more here since handing
    # goods back from the external step to the next internal step is its
    # own handover, separate from the handover into the external step.
    assert successor_result.planned_start.date() == expected_delivery + timedelta(days=1)


def test_external_predecessor_typed_date_still_wins_over_its_own_forecast():
    """A typed/actual date on the EXTERNAL predecessor always wins for
    readiness even though a forecast is still computed and exposed. The
    forecast is persisted independent of which date the successor
    actually used."""
    calendar = _calendar()
    typed_date = MONDAY - timedelta(days=20)  # far earlier than any forecast would be

    position_1 = replace(
        make_context(order_id=1, queue_sequence=1, estimated_duration_minutes=200),
        lot_id=1,
        lot_position_id=10,
    )
    successor = replace(
        make_context(
            order_id=2,
            queue_sequence=1,
            position_sequence=3,
            is_manual_step=True,
            estimated_duration_minutes=20,
        ),
        lot_id=1,
        lot_position_id=30,
        response_time_days=1,
        predecessor_positions=(
            PredecessorPosition(
                position_id=10,
                sequence=1,
                kind=LotPositionKind.INTERNAL.value,
                external_ready_at=None,
                stored_internal_ready_at=None,
            ),
            PredecessorPosition(
                position_id=20,
                sequence=2,
                kind=LotPositionKind.EXTERNAL.value,
                external_ready_at=typed_date,
                stored_internal_ready_at=None,
                lead_days=5,
                typed_external_date=typed_date,
            ),
        ),
    )

    result, _passes = schedule_all_propagated(
        machine_queues={1: [position_1]},
        machine_calendars={1: calendar},
        pool_queues={},
        pool_members={},
        manual_queue=[successor],
        manual_calendar=calendar,
        unassigned=[],
        now=NOW,
    )

    # The forecast is still computed and exposed, even though it loses to
    # the typed date for readiness below.
    forecast = result.external_forecasts[20]
    assert forecast.planned_delivery_date is not None

    successor_result = result.manual[0]
    assert successor_result.planned_start is not None
    # Governed by position 1's own fresh end (the max over both
    # predecessors), not by the much-earlier typed date and not by the
    # forecast. An in-house predecessor adds no response time, so the
    # successor starts right when position 1 ends.
    assert successor_result.planned_start == result.by_machine[1][0].planned_end


def test_external_predecessor_unknown_chain_gives_no_forecast():
    """When the position feeding the EXTERNAL predecessor is itself
    unresolvable (PAUSED, no capacity consumed), the EXTERNAL
    predecessor's own forecast has no basis to compute from and comes back
    fully None, exposed that way on the walk result too, not just
    silently omitted."""
    calendar = _calendar()

    position_1 = replace(
        make_context(
            order_id=1,
            queue_sequence=1,
            status=ProductionOrderStatus.PAUSED.value,
            estimated_duration_minutes=200,
        ),
        lot_id=1,
        lot_position_id=10,
    )
    successor = replace(
        make_context(
            order_id=2,
            queue_sequence=1,
            position_sequence=3,
            estimated_duration_minutes=20,
            upstream_input_available=False,
        ),
        lot_id=1,
        lot_position_id=30,
        response_time_days=1,
        predecessor_positions=(
            PredecessorPosition(
                position_id=10,
                sequence=1,
                kind=LotPositionKind.INTERNAL.value,
                external_ready_at=None,
                stored_internal_ready_at=None,
            ),
            PredecessorPosition(
                position_id=20,
                sequence=2,
                kind=LotPositionKind.EXTERNAL.value,
                external_ready_at=None,
                stored_internal_ready_at=None,
                lead_days=5,
                typed_external_date=None,
            ),
        ),
    )

    result, _passes = schedule_all_propagated(
        machine_queues={1: [position_1], 2: [successor]},
        machine_calendars={1: calendar, 2: calendar},
        pool_queues={},
        pool_members={},
        manual_queue=[],
        manual_calendar=calendar,
        unassigned=[],
        now=NOW,
    )

    forecast = result.external_forecasts[20]
    assert forecast.planned_pickup_date is None
    assert forecast.planned_delivery_date is None

    assert result.by_machine[2][0].planned_start is None
    assert result.by_machine[2][0].planned_end is None


def _chain_step(order_id: int, sequence: int, queue_sequence: int = 1, **overrides):
    """Position `sequence` of lot 1, one order on it, listing every earlier
    position as an internal predecessor with a stale stored end."""
    return replace(
        make_context(
            order_id=order_id,
            queue_sequence=queue_sequence,
            position_sequence=sequence,
            estimated_duration_minutes=60,
            predecessor_ready_at=STALE if sequence > 1 else None,
            **overrides,
        ),
        lot_id=1,
        lot_position_id=sequence * 10,
        response_time_days=1,
        predecessor_positions=tuple(
            PredecessorPosition(
                position_id=earlier * 10,
                sequence=earlier,
                kind=LotPositionKind.INTERNAL.value,
                external_ready_at=None,
                stored_internal_ready_at=STALE,
            )
            for earlier in range(1, sequence)
        ),
    )


def test_a_chain_longer_than_any_fixed_pass_count_settles_completely():
    """Nine positions on nine machines: every pass settles one more link,
    so the walk needs more passes than a small fixed cap would allow, and
    still ends with each step starting no earlier than the one before it
    ends."""
    calendar = _calendar()
    steps = [_chain_step(order_id=n, sequence=n) for n in range(1, 10)]

    result, passes = schedule_all_propagated(
        machine_queues={n: [step] for n, step in enumerate(steps, start=1)},
        machine_calendars={n: calendar for n in range(1, 10)},
        pool_queues={},
        pool_members={},
        manual_queue=[],
        manual_calendar=calendar,
        unassigned=[],
        now=NOW,
    )

    assert passes > 6
    assert result.unsettled_order_ids == frozenset()
    placed = [result.by_machine[n][0] for n in range(1, 10)]
    assert all(p.planned_start is not None and p.planned_end is not None for p in placed)
    assert all(
        later.planned_start >= earlier.planned_end  # type: ignore[operator]
        for earlier, later in pairwise(placed)
    )


def _walk(machine_queues, **queues):
    calendar = _calendar()
    return schedule_all_propagated(
        machine_queues=machine_queues,
        machine_calendars=dict.fromkeys(machine_queues, calendar),
        pool_queues=queues.get("pool_queues", {}),
        pool_members={},
        manual_queue=[],
        manual_calendar=calendar,
        unassigned=queues.get("unassigned", []),
        now=NOW,
    )


def test_a_successor_queued_ahead_of_its_predecessor_stays_undated_as_a_cycle():
    """Step 2 sits ahead of step 1 on one queue, so each pass would push
    step 2 behind step 1's new end and step 1 behind step 2: a cycle. Both
    stay undated and flagged instead of running away to the pass limit."""
    first = _chain_step(order_id=1, sequence=1, queue_sequence=2)
    second = _chain_step(order_id=2, sequence=2, queue_sequence=1)

    result, passes = _walk({1: [second, first]})

    placed = {s.order_id: s for s in result.all_orders()}
    assert passes <= 2
    assert result.unsettled_order_ids == frozenset()
    for order_id in (1, 2):
        assert (placed[order_id].planned_start, placed[order_id].planned_end) == (None, None)
        assert ScheduleConflictReason.CHAIN_CYCLE.value in placed[order_id].conflicts


def test_a_cycle_takes_no_capacity_and_its_later_steps_wait_for_it():
    """The cycle's orders take no capacity, so the order behind them on
    their machine is placed; the lot's next step has an undated predecessor
    and stays undated by the walk's own rule."""
    first = _chain_step(order_id=1, sequence=1, queue_sequence=2)
    second = _chain_step(order_id=2, sequence=2, queue_sequence=1)
    behind = make_context(order_id=4, queue_sequence=3)
    third = _chain_step(order_id=3, sequence=3, queue_sequence=1, upstream_input_available=False)

    result, _ = _walk({1: [second, first, behind], 2: [third]})

    placed = {s.order_id: s for s in result.all_orders()}
    assert placed[4].planned_start is not None
    assert placed[4].planned_start.date() <= NOW.date() + timedelta(days=1)
    assert ScheduleConflictReason.CHAIN_CYCLE.value not in placed[4].conflicts
    assert placed[3].planned_start is None


def test_a_pinned_predecessor_behind_its_successor_is_no_cycle():
    """A pinned window does not wait on the order ahead of it, so the
    successor simply follows the pin."""
    start = NOW + timedelta(days=2)
    first = _chain_step(
        order_id=1,
        sequence=1,
        queue_sequence=2,
        pinned=True,
        existing_planned_start=start,
        existing_planned_end=start + timedelta(hours=1),
    )
    second = _chain_step(order_id=2, sequence=2, queue_sequence=1)

    result, _ = _walk({1: [second, first]})

    placed = {s.order_id: s for s in result.all_orders()}
    assert ScheduleConflictReason.CHAIN_CYCLE.value not in placed[2].conflicts
    assert placed[2].planned_start is not None


def test_a_successor_on_another_machine_starts_when_its_predecessor_ends():
    """Readiness used to be the predecessor's end day, so without a
    response buffer a successor on another machine started at that day's
    first window, while its predecessor was still running."""
    first = replace(
        make_context(order_id=1, queue_sequence=1, estimated_duration_minutes=200),
        lot_id=1,
        lot_position_id=10,
    )
    second = replace(
        _chain_step(order_id=2, sequence=2, queue_sequence=1),
        response_time_days=0,
        predecessor_ready_at=None,
    )

    result, _ = _walk({1: [first], 2: [second]})

    end_1 = result.by_machine[1][0].planned_end
    start_2 = result.by_machine[2][0].planned_start
    assert end_1 is not None and start_2 is not None
    assert start_2 == end_1


def test_a_cycle_through_a_pool_keeps_no_runaway_date():
    """Step 2 sits on the machine, step 1 floats in a pool whose only member
    is that machine: the pool places step 1 behind step 2, which waits for
    step 1. The cycle graph does not model pools, so the walk runs to its
    pass limit; the orders still moving there come back undated."""
    first = replace(
        make_context(order_id=1, queue_sequence=1, machine_pool_id=7),
        lot_id=1,
        lot_position_id=10,
    )
    second = replace(
        _chain_step(order_id=2, sequence=2, queue_sequence=1),
        response_time_days=0,
        predecessor_ready_at=None,
        upstream_input_available=False,
    )
    calendar = _calendar()

    result, _ = schedule_all_propagated(
        machine_queues={1: [second]},
        machine_calendars={1: calendar},
        pool_queues={7: [first]},
        pool_members={7: [1]},
        manual_queue=[],
        manual_calendar=calendar,
        unassigned=[],
        now=NOW,
    )

    placed = {s.order_id: s for s in result.all_orders()}
    assert placed[2].planned_start is None
    assert ScheduleConflictReason.CHAIN_CYCLE.value in placed[2].conflicts
    assert placed[1].planned_start is not None
    assert placed[1].planned_start.date() <= NOW.date() + timedelta(days=1)
    assert result.unsettled_order_ids == frozenset({2})
