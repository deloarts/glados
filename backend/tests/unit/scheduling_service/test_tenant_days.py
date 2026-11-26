"""
The scheduling package reads every calendar day in the tenant's timezone.
These tests run the walk, the conflict flags, the earliest-start explanation
and the readiness resolvers in Europe/Vienna around local midnight and both
daylight saving switches, against UTC where the two disagree. Pure
functions only.
"""

from dataclasses import replace
from datetime import UTC
from datetime import date
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from src.modules.fulfillment.domain.services.scheduling import EarliestStartExplanation
from src.modules.fulfillment.domain.services.scheduling import ScheduledOrder
from src.modules.fulfillment.domain.services.scheduling import ScheduleWalkResult
from src.modules.fulfillment.domain.services.scheduling import WorkInterval
from src.modules.fulfillment.domain.services.scheduling import advance_machine_queue
from src.modules.fulfillment.domain.services.scheduling import build_machine_calendar
from src.modules.fulfillment.domain.services.scheduling import compute_order_conflicts
from src.modules.fulfillment.domain.services.scheduling import explain_earliest_start
from src.modules.fulfillment.domain.services.scheduling import placed_ends_by_position
from src.modules.fulfillment.domain.services.scheduling import resolve_external_predecessor_ready_at
from src.modules.fulfillment.domain.services.scheduling import resolve_input_material_ready_at
from src.modules.fulfillment.domain.services.scheduling import resolve_internal_predecessor_ready_at
from src.modules.fulfillment.domain.value_objects.schedule_conflict import ScheduleConflictReason
from tests.unit.scheduling_service._helpers import make_context

VIENNA = ZoneInfo("Europe/Vienna")
PAST_TARGET_DATE = ScheduleConflictReason.PAST_TARGET_DATE.value
WAITING_ON_PREDECESSOR = ScheduleConflictReason.WAITING_ON_PREDECESSOR.value

# Every local day works from midnight to midnight, so a placement starts
# exactly at its floor.
ROUND_THE_CLOCK = {day: (WorkInterval(0, 1440),) for day in range(7)}

# 23:30 UTC on 27 July is 01:30 on 28 July in Vienna (summer time, UTC+2).
LATE_EVENING_UTC = datetime(2026, 7, 27, 23, 30, tzinfo=UTC)
EARLIER_NOW = datetime(2026, 7, 20, 8, 0, tzinfo=UTC)


def test_an_order_ending_after_vienna_midnight_is_past_its_target_date():
    vienna = make_context(target_date=date(2026, 7, 27), zone=VIENNA)

    assert PAST_TARGET_DATE in compute_order_conflicts(vienna, LATE_EVENING_UTC, EARLIER_NOW)
    assert PAST_TARGET_DATE not in compute_order_conflicts(
        replace(vienna, zone=UTC), LATE_EVENING_UTC, EARLIER_NOW
    )


def test_an_order_ending_before_vienna_midnight_meets_its_target_date():
    # 21:30 UTC is 23:30 in Vienna, still on the target date.
    end = datetime(2026, 7, 27, 21, 30, tzinfo=UTC)
    ctx = make_context(target_date=date(2026, 7, 27), zone=VIENNA)

    assert PAST_TARGET_DATE not in compute_order_conflicts(ctx, end, EARLIER_NOW)


def test_waiting_on_a_predecessor_compares_with_the_vienna_today():
    # 22:30 UTC on 27 July is already 00:30 on 28 July in Vienna.
    now = datetime(2026, 7, 27, 22, 30, tzinfo=UTC)
    ctx = make_context(predecessor_ready_at=date(2026, 7, 28), position_sequence=2, zone=VIENNA)

    assert WAITING_ON_PREDECESSOR not in compute_order_conflicts(ctx, None, now)
    assert WAITING_ON_PREDECESSOR in compute_order_conflicts(replace(ctx, zone=UTC), None, now)


@pytest.mark.parametrize(
    ("not_before", "local_midnight"),
    [
        (date(2026, 1, 13), datetime(2026, 1, 12, 23, 0, tzinfo=UTC)),
        (date(2026, 7, 28), datetime(2026, 7, 27, 22, 0, tzinfo=UTC)),
        # Summer time begins at 02:00 on 29 March, so that day starts in
        # winter time and the next one in summer time.
        (date(2026, 3, 29), datetime(2026, 3, 28, 23, 0, tzinfo=UTC)),
        (date(2026, 3, 30), datetime(2026, 3, 29, 22, 0, tzinfo=UTC)),
        # Summer time ends at 03:00 on 25 October, so that day starts in
        # summer time and the next one in winter time.
        (date(2026, 10, 25), datetime(2026, 10, 24, 22, 0, tzinfo=UTC)),
        (date(2026, 10, 26), datetime(2026, 10, 25, 23, 0, tzinfo=UTC)),
    ],
)
def test_a_not_before_floor_starts_at_vienna_midnight(not_before, local_midnight):
    calendar = build_machine_calendar(ROUND_THE_CLOCK, None, {}, zone=VIENNA)
    ctx = make_context(not_before=not_before, zone=VIENNA)
    now = datetime(2026, 1, 1, tzinfo=UTC)

    planned_start, planned_end, _cursor = advance_machine_queue(ctx, None, calendar, now)

    assert planned_start == local_midnight
    assert planned_end is not None
    assert planned_end.astimezone(VIENNA).date() == not_before


def test_a_predecessor_ready_day_floors_at_vienna_midnight():
    calendar = build_machine_calendar(ROUND_THE_CLOCK, None, {}, zone=VIENNA)
    ctx = make_context(predecessor_ready_at=date(2026, 7, 28), position_sequence=2, zone=VIENNA)

    planned_start, _end, _cursor = advance_machine_queue(ctx, None, calendar, EARLIER_NOW)

    assert planned_start == datetime(2026, 7, 27, 22, 0, tzinfo=UTC)


def test_a_running_order_is_explained_on_its_vienna_start_day():
    ctx = make_context(
        status="in_progress", actual_start=datetime(2026, 7, 27, 22, 30, tzinfo=UTC), zone=VIENNA
    )

    assert explain_earliest_start(ctx) == EarliestStartExplanation("in_progress", date(2026, 7, 28))


def test_a_queue_push_is_judged_on_the_vienna_day_of_the_planned_start():
    """A planned start at 22:30 UTC on 28 July lies on 29 July in Vienna,
    after the not_before day, so the queue pushed it. In UTC it is the
    not_before day itself."""
    ctx = make_context(
        not_before=date(2026, 7, 28),
        existing_planned_start=datetime(2026, 7, 28, 22, 30, tzinfo=UTC),
        zone=VIENNA,
    )

    assert explain_earliest_start(ctx) == EarliestStartExplanation("queue", date(2026, 7, 28))
    assert explain_earliest_start(replace(ctx, zone=UTC)) == EarliestStartExplanation(
        "not_before", date(2026, 7, 28)
    )


def test_readiness_moments_count_on_their_vienna_day():
    assert resolve_internal_predecessor_ready_at([LATE_EVENING_UTC], zone=VIENNA) == date(
        2026, 7, 28
    )
    assert resolve_internal_predecessor_ready_at([LATE_EVENING_UTC], zone=UTC) == date(2026, 7, 27)
    before_the_fixtures = date(2026, 7, 1)
    assert resolve_external_predecessor_ready_at(
        LATE_EVENING_UTC, None, date(2026, 7, 20), zone=VIENNA, today=before_the_fixtures
    ) == date(2026, 7, 28)
    assert resolve_input_material_ready_at(
        [(LATE_EVENING_UTC, None), (None, date(2026, 7, 27))],
        zone=VIENNA,
        today=before_the_fixtures,
    ) == date(2026, 7, 28)


def test_the_propagated_walk_reads_a_position_ready_day_in_vienna():
    ctx = replace(make_context(order_id=1, zone=VIENNA), lot_position_id=10)
    result = ScheduleWalkResult(
        by_machine={
            1: [ScheduledOrder(1, datetime(2026, 7, 27, 20, 0, tzinfo=UTC), LATE_EVENING_UTC, [])]
        },
        by_pool={},
        manual=[],
        unassigned=[],
        machine_cursors={},
    )

    assert placed_ends_by_position([ctx], result) == {10: date(2026, 7, 28)}
