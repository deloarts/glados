"""
The wait after a position: which step's wait a position takes, how the walk
lets it hold the next step back, also after the step is booked complete,
and how the backward passes and the late check count it.
"""

from dataclasses import replace
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta

from src.modules.fulfillment.domain.policies.wait_after import StepWait
from src.modules.fulfillment.domain.policies.wait_after import latest_ready_moment
from src.modules.fulfillment.domain.policies.wait_after import position_wait_after_minutes
from src.modules.fulfillment.domain.policies.wait_after import wait_days
from src.modules.fulfillment.domain.services.scheduling import PredecessorPosition
from src.modules.fulfillment.domain.services.scheduling import build_machine_calendar
from src.modules.fulfillment.domain.services.scheduling import compute_order_conflicts
from src.modules.fulfillment.domain.services.scheduling import compute_position_due_dates
from src.modules.fulfillment.domain.services.scheduling import schedule_all_propagated
from src.modules.fulfillment.domain.services.scheduling import stored_predecessor_readiness
from src.modules.fulfillment.domain.services.scheduling.external_work import ExternalWorkChain
from src.modules.fulfillment.domain.services.scheduling.external_work import latest_pickup_dates
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.schedule_conflict import ScheduleConflictReason
from tests.unit.scheduling_service._helpers import MONDAY
from tests.unit.scheduling_service._helpers import WEEKDAY_HOURS
from tests.unit.scheduling_service._helpers import make_context

NOW = datetime.combine(MONDAY, time(), tzinfo=UTC)
TUESDAY = MONDAY + timedelta(days=1)


# ── Which wait a position takes ──────────────────────────────────────


def test_an_internal_position_waits_as_long_as_its_last_step():
    steps = [StepWait(1, False, 30), StepWait(2, False, 720)]
    assert position_wait_after_minutes(LotPositionKind.INTERNAL, steps) == 720
    # The order of the steps given does not matter, their sequence does.
    assert position_wait_after_minutes(LotPositionKind.INTERNAL, list(reversed(steps))) == 720


def test_a_mixed_position_waits_as_long_as_its_last_in_house_step():
    steps = [StepWait(1, False, 240), StepWait(2, True, 999)]
    assert position_wait_after_minutes(LotPositionKind.MIXED, steps) == 240


def test_an_external_position_waits_nothing():
    steps = [StepWait(1, True, 999)]
    assert position_wait_after_minutes(LotPositionKind.EXTERNAL, steps) == 0
    assert position_wait_after_minutes(LotPositionKind.INTERNAL, []) == 0


def test_a_wait_counts_in_whole_days_rounded_up():
    assert [wait_days(m) for m in (0, 1, 1440, 1441)] == [0, 1, 1, 2]


def test_the_latest_ready_moment_adds_each_wait():
    early = datetime(2026, 7, 27, 10, tzinfo=UTC)
    late = datetime(2026, 7, 27, 12, tzinfo=UTC)
    assert latest_ready_moment([(early, 300), (late, 0), (None, 999)]) == early + timedelta(
        minutes=300
    )
    assert latest_ready_moment([(None, 60)]) is None


# ── The walk ─────────────────────────────────────────────────────────


def _internal(position_id: int, sequence: int, **values) -> PredecessorPosition:
    return PredecessorPosition(
        **{
            "position_id": position_id,
            "sequence": sequence,
            "kind": LotPositionKind.INTERNAL.value,
            "external_ready_at": None,
            "stored_internal_ready_at": None,
            **values,
        }
    )


def _walk(machine_queues, manual_queue):
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    result, _ = schedule_all_propagated(
        machine_queues=machine_queues,
        machine_calendars={m: calendar for m in machine_queues},
        pool_queues={},
        pool_members={},
        manual_queue=manual_queue,
        manual_calendar=calendar,
        unassigned=[],
        now=NOW,
    )
    return result


def _successor(*predecessors: PredecessorPosition, **values):
    return replace(
        make_context(order_id=2, position_sequence=2, is_manual_step=True),
        lot_id=1,
        lot_position_id=20,
        predecessor_positions=predecessors,
        **values,
    )


def test_the_next_step_waits_on_clock_time_after_the_step_before():
    """Curing of 12 hours after a machine step: the manual step after it
    starts 12 clock hours after the machine step ends, the next morning,
    not 12 working hours later."""
    curing = replace(
        make_context(order_id=1, estimated_duration_minutes=60, not_before=MONDAY),
        lot_id=1,
        lot_position_id=10,
        wait_after_minutes=720,
    )
    result = _walk({1: [curing]}, [_successor(_internal(10, 1))])

    end = result.by_machine[1][0].planned_end
    start = result.manual[0].planned_start
    assert end is not None and start is not None
    # Ready at 21:00 Monday, outside working time, so it starts Tuesday 08:00.
    assert start >= end + timedelta(minutes=720)
    assert start == datetime.combine(TUESDAY, time(8), tzinfo=UTC)


def test_a_completed_step_holds_the_next_one_until_its_wait_is_over():
    """The step before was booked complete, but its lab result is not in
    yet: the next step is dated when the wait is over, and the chain is
    not unknown."""
    ready = datetime.combine(TUESDAY, time(14), tzinfo=UTC)
    completed = _internal(
        10,
        1,
        wait_after_minutes=240,
        completed=True,
        completed_ready_at=TUESDAY,
        completed_ready_moment=ready,
    )
    result = _walk({}, [_successor(completed)])

    assert result.manual[0].planned_start == ready
    assert ScheduleConflictReason.WAITING_ON_PREDECESSOR.value in result.manual[0].conflicts


def test_a_split_position_keeps_the_wait_of_its_completed_order():
    """One order of the step before is complete and still waits until
    Tuesday 14:00, another one still runs and ends earlier: the next step
    waits for the later of both."""
    ready = datetime.combine(TUESDAY, time(14), tzinfo=UTC)
    running = replace(
        make_context(order_id=1, estimated_duration_minutes=60, not_before=MONDAY),
        lot_id=1,
        lot_position_id=10,
    )
    split = _internal(10, 1, completed_ready_at=TUESDAY, completed_ready_moment=ready)
    result = _walk({1: [running]}, [_successor(split)])

    assert result.by_machine[1][0].planned_end is not None
    assert result.by_machine[1][0].planned_end < ready
    assert result.manual[0].planned_start == ready


def test_the_read_path_counts_the_stored_wait():
    stored = _internal(
        10,
        1,
        stored_internal_ready_at=TUESDAY,
        stored_internal_ready_moment=datetime.combine(TUESDAY, time(9), tzinfo=UTC),
        wait_after_minutes=600,
    )
    assert stored_predecessor_readiness((stored,), 3) == (TUESDAY, False)
    completed = _internal(10, 1, completed=True, completed_ready_at=TUESDAY)
    assert stored_predecessor_readiness((completed,), 3) == (TUESDAY, False)


# ── Backward passes and the late check ──────────────────────────────


def test_a_wait_on_the_last_position_moves_every_due_date_earlier():
    due = compute_position_due_dates(
        [1, 2], {1: 1, 2: 1}, date(2026, 8, 20), wait_days_by_sequence={2: 2}
    )
    # Position 2 must be done two days before the target, since its pieces
    # wait two days, and position 1 a day before position 2 starts.
    assert due == {2: date(2026, 8, 18), 1: date(2026, 8, 17)}


def test_a_wait_in_the_middle_moves_only_the_positions_up_to_it():
    due = compute_position_due_dates(
        [1, 2, 3], {1: 1, 2: 1, 3: 1}, date(2026, 8, 20), wait_days_by_sequence={2: 3}
    )
    assert due == {3: date(2026, 8, 20), 2: date(2026, 8, 16), 1: date(2026, 8, 15)}


def test_the_latest_pickup_leaves_the_wait_of_a_later_step_and_skips_a_completed_one():
    hardening = PredecessorPosition(
        position_id=20,
        sequence=2,
        kind=LotPositionKind.EXTERNAL.value,
        external_ready_at=None,
        stored_internal_ready_at=None,
        lead_days=4,
    )
    painting = _internal(30, 3, wait_after_minutes=1440)
    done = _internal(10, 1, completed=True, completed_ready_at=MONDAY)
    chain = ExternalWorkChain(
        lot_id=1,
        positions=(done, hardening, painting),
        external_position_ids=frozenset({20}),
        target_date=date(2026, 8, 20),
        remaining_minutes_by_position={30: 30},
    )
    # Painting: 1 day of work and 1 day of waiting before the target, so the
    # hardening is back by 08-18 and leaves 4 days before.
    assert latest_pickup_dates(chain, 0) == {20: date(2026, 8, 14)}


def test_an_order_is_late_when_its_wait_ends_after_the_target_date():
    ctx = replace(make_context(target_date=MONDAY), wait_after_minutes=600)
    end = datetime.combine(MONDAY, time(16), tzinfo=UTC)
    assert ScheduleConflictReason.PAST_TARGET_DATE.value in compute_order_conflicts(ctx, end, NOW)
    on_time = replace(ctx, wait_after_minutes=0)
    assert ScheduleConflictReason.PAST_TARGET_DATE.value not in compute_order_conflicts(
        on_time, end, NOW
    )
