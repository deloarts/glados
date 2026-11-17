"""
The walk's floors and its idle calendars: a queued order whose readiness
lies in the past starts no earlier than now, while a running order keeps its
anchor in the past; a pinned window that starts before the previous order
ends keeps its place, never moves the cursor backwards and is flagged as an
overlap, and one that starts before its predecessor is ready is kept and
flagged too; a machine whose calendar holds no working time leaves only its own
queue undated and flagged, and a pool places its orders on a member that
works.
"""

import dataclasses
from datetime import UTC
from datetime import datetime
from datetime import timedelta

from src.modules.fulfillment.domain.entities.machine_downtime import MachineDowntime
from src.modules.fulfillment.domain.services.scheduling import build_machine_calendar
from src.modules.fulfillment.domain.services.scheduling import schedule_all
from src.modules.fulfillment.domain.services.scheduling.machine_calendar import apply_downtimes
from src.modules.fulfillment.domain.value_objects.machine_downtime_reason import (
    MachineDowntimeReason,
)
from src.modules.fulfillment.domain.value_objects.schedule_conflict import ScheduleConflictReason
from tests.unit.scheduling_service._helpers import MONDAY
from tests.unit.scheduling_service._helpers import WEEKDAY_HOURS
from tests.unit.scheduling_service._helpers import make_context
from tests.unit.scheduling_service._helpers import walk_machine_queue
from tests.unit.scheduling_service._helpers import walk_pool_queue

# Wednesday of the week of MONDAY, mid-morning.
_NOW = datetime.combine(MONDAY, datetime.min.time(), tzinfo=UTC) + timedelta(days=2, hours=10)
_IDLE_WEEK = dict.fromkeys(range(7), 0)
_OVERLAP = ScheduleConflictReason.WINDOW_OVERLAP.value
_NO_WORKING_TIME = ScheduleConflictReason.NO_WORKING_TIME.value
_BEFORE_PREDECESSOR = ScheduleConflictReason.WINDOW_BEFORE_PREDECESSOR.value


def _calendar():
    return build_machine_calendar(WEEKDAY_HOURS, None, {})


def test_walk_floors_a_queued_order_with_a_past_readiness_at_now() -> None:
    order = make_context(not_before=MONDAY)

    [placed] = walk_machine_queue([order], _calendar(), _NOW)

    assert placed.planned_start is not None
    assert placed.planned_start >= _NOW


def test_walk_keeps_a_running_order_anchored_at_its_start_in_the_past() -> None:
    started = _NOW - timedelta(days=1)
    order = make_context(status="in_progress", actual_start=started)

    [placed] = walk_machine_queue([order], _calendar(), _NOW)

    assert placed.planned_start is not None
    assert placed.planned_start < _NOW


def test_walk_keeps_a_pinned_window_that_overlaps_and_flags_it() -> None:
    long_order = make_context(order_id=1, queue_sequence=1, estimated_duration_minutes=240)
    pinned_start = _NOW + timedelta(hours=1)
    pinned = make_context(
        order_id=2,
        queue_sequence=2,
        pinned=True,
        existing_planned_start=pinned_start,
        existing_planned_end=pinned_start + timedelta(minutes=30),
    )
    after = make_context(order_id=3, queue_sequence=3)

    first, kept, third = walk_machine_queue([long_order, pinned, after], _calendar(), _NOW)

    assert (kept.planned_start, kept.planned_end) == (
        pinned.existing_planned_start,
        pinned.existing_planned_end,
    )
    assert _OVERLAP in kept.conflicts
    assert _OVERLAP not in first.conflicts
    # The pin ends before the first order does, so the next one follows the
    # first order rather than the pin.
    assert first.planned_end is not None and third.planned_start is not None
    assert third.planned_start >= first.planned_end


def test_walk_flags_a_frozen_window_that_overlaps_too() -> None:
    long_order = make_context(order_id=1, queue_sequence=1, estimated_duration_minutes=240)
    start = _NOW + timedelta(hours=1)
    frozen = dataclasses.replace(
        make_context(
            order_id=2,
            queue_sequence=2,
            existing_planned_start=start,
            existing_planned_end=start + timedelta(minutes=30),
        ),
        frozen=True,
    )

    _, kept = walk_machine_queue([long_order, frozen], _calendar(), _NOW)

    assert kept.planned_start == start
    assert _OVERLAP in kept.conflicts


def test_walk_leaves_only_the_idle_machine_undated() -> None:
    idle = build_machine_calendar(_IDLE_WEEK, None, {})
    result = schedule_all(
        machine_queues={1: [make_context(order_id=1)], 2: [make_context(order_id=2)]},
        machine_calendars={1: idle, 2: _calendar()},
        pool_queues={},
        pool_members={},
        manual_queue=[],
        manual_calendar=_calendar(),
        unassigned=[],
        now=_NOW,
    )

    [undated] = result.by_machine[1]
    [dated] = result.by_machine[2]
    assert (undated.planned_start, undated.planned_end) == (None, None)
    assert _NO_WORKING_TIME in undated.conflicts
    assert dated.planned_start is not None
    assert _NO_WORKING_TIME not in dated.conflicts


def test_walk_leaves_a_machine_down_for_good_undated() -> None:
    down = MachineDowntime(
        id=1,
        created=_NOW,
        changed=None,
        changes=[],
        machine_id=1,
        started_at=_NOW - timedelta(days=1),
        ended_at=_NOW + timedelta(days=3700),
        reason=MachineDowntimeReason.BREAKDOWN,
        note=None,
        reported_by_id=1,
        ended_by_id=None,
    )
    calendar = apply_downtimes(_calendar(), [down], _NOW)

    [placed] = walk_machine_queue([make_context()], calendar, _NOW)

    assert placed.planned_start is None
    assert _NO_WORKING_TIME in placed.conflicts


def test_walk_places_a_pool_order_on_the_member_that_works() -> None:
    idle = build_machine_calendar(_IDLE_WEEK, None, {})

    [placed] = walk_pool_queue([make_context(machine_pool_id=1)], {1: idle, 2: _calendar()}, _NOW)

    assert placed.planned_start is not None
    assert placed.trial_machine_id == 2


def test_walk_flags_a_pool_order_when_no_member_works() -> None:
    idle = build_machine_calendar(_IDLE_WEEK, None, {})

    [placed] = walk_pool_queue([make_context(machine_pool_id=1)], {1: idle, 2: idle}, _NOW)

    assert placed.planned_start is None
    assert _NO_WORKING_TIME in placed.conflicts


def test_walk_places_a_running_order_first_even_behind_queued_ones() -> None:
    """A pool start appends the started order to its member's queue, and an
    operator may start an order that is not at the head: the machine is busy
    with it now, so the queued orders follow it instead of overlapping it."""
    queued = make_context(order_id=1, queue_sequence=1, estimated_duration_minutes=240)
    running = make_context(
        order_id=2,
        queue_sequence=2,
        status="in_progress",
        actual_start=_NOW - timedelta(minutes=30),
        estimated_duration_minutes=60,
    )

    placed = {p.order_id: p for p in walk_machine_queue([queued, running], _calendar(), _NOW)}

    assert placed[2].planned_start == _NOW - timedelta(minutes=30)
    assert placed[1].planned_start is not None and placed[2].planned_end is not None
    assert placed[1].planned_start >= placed[2].planned_end
    assert _OVERLAP not in placed[1].conflicts + placed[2].conflicts


def test_walk_flags_a_second_running_order_on_one_machine_and_keeps_the_cursor() -> None:
    first = make_context(
        order_id=1,
        queue_sequence=1,
        status="in_progress",
        actual_start=_NOW - timedelta(hours=1),
        estimated_duration_minutes=240,
    )
    second = make_context(
        order_id=2,
        queue_sequence=2,
        status="in_progress",
        actual_start=_NOW - timedelta(minutes=30),
        estimated_duration_minutes=30,
    )
    queued = make_context(order_id=3, queue_sequence=3)

    placed = {p.order_id: p for p in walk_machine_queue([first, second, queued], _calendar(), _NOW)}

    assert _OVERLAP in placed[2].conflicts
    assert _OVERLAP not in placed[1].conflicts
    assert placed[3].planned_start is not None and placed[1].planned_end is not None
    assert placed[3].planned_start >= placed[1].planned_end


def test_walk_keeps_a_pinned_window_before_its_predecessor_and_flags_it() -> None:
    start = _NOW + timedelta(hours=1)
    pinned = make_context(
        pinned=True,
        existing_planned_start=start,
        existing_planned_end=start + timedelta(minutes=30),
    )
    early = dataclasses.replace(pinned, predecessor_ready_moment=start + timedelta(hours=2))
    in_time = dataclasses.replace(pinned, predecessor_ready_moment=start)

    [kept] = walk_machine_queue([early], _calendar(), _NOW)
    [ready] = walk_machine_queue([in_time], _calendar(), _NOW)

    assert kept.planned_start == start
    assert _BEFORE_PREDECESSOR in kept.conflicts
    assert _BEFORE_PREDECESSOR not in ready.conflicts


def test_walk_flags_a_frozen_window_before_its_predecessor_ready_day() -> None:
    start = _NOW + timedelta(hours=1)
    frozen = dataclasses.replace(
        make_context(
            existing_planned_start=start,
            existing_planned_end=start + timedelta(minutes=30),
            predecessor_ready_at=(_NOW + timedelta(days=1)).date(),
        ),
        frozen=True,
    )

    [kept] = walk_machine_queue([frozen], _calendar(), _NOW)

    assert kept.planned_start == start
    assert _BEFORE_PREDECESSOR in kept.conflicts
