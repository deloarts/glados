"""
The two buffers between the positions of a lot. The response time, in whole
days, follows an arrival: an external position's delivery or pickup and the
raw material. The handoff, in minutes, follows the end of an in-house
position, so the next in-house order starts that many minutes later.
"""

from dataclasses import replace
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta

from src.modules.fulfillment.domain.services.scheduling import PredecessorPosition
from src.modules.fulfillment.domain.services.scheduling import buffered_ready_day
from src.modules.fulfillment.domain.services.scheduling import build_machine_calendar
from src.modules.fulfillment.domain.services.scheduling import predecessor_ready_moment
from src.modules.fulfillment.domain.services.scheduling import schedule_all_propagated
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from tests.unit.scheduling_service._helpers import MONDAY
from tests.unit.scheduling_service._helpers import WEEKDAY_HOURS
from tests.unit.scheduling_service._helpers import make_context

NOW = datetime.combine(MONDAY, datetime.min.time(), tzinfo=UTC)
TUESDAY = MONDAY + timedelta(days=1)


def test_an_arrival_is_buffered_by_the_response_time():
    assert buffered_ready_day(MONDAY, None, 2) == MONDAY + timedelta(days=2)


def test_an_in_house_end_is_not_buffered_by_the_response_time():
    assert buffered_ready_day(None, MONDAY, 2) == MONDAY


def test_a_mixed_position_is_ready_at_the_later_of_both_shares():
    # The external share arrives Monday, plus two days, after the in-house
    # share ends on Tuesday.
    assert buffered_ready_day(MONDAY, TUESDAY, 2) == MONDAY + timedelta(days=2)
    # The in-house share ends after the buffered arrival.
    late_end = MONDAY + timedelta(days=5)
    assert buffered_ready_day(MONDAY, late_end, 2) == late_end


def test_nothing_known_stays_unknown():
    assert buffered_ready_day(None, None, 2) is None


def test_the_handoff_follows_the_in_house_end():
    end = datetime(2026, 7, 27, 11, 20, tzinfo=UTC)
    predecessor = PredecessorPosition(
        position_id=10,
        sequence=1,
        kind=LotPositionKind.INTERNAL.value,
        external_ready_at=None,
        stored_internal_ready_at=MONDAY,
        stored_internal_ready_moment=end,
    )
    assert predecessor_ready_moment((predecessor,), None) == end
    assert predecessor_ready_moment((predecessor,), None, 30) == end + timedelta(minutes=30)


def test_the_walk_starts_the_next_in_house_order_after_the_handoff():
    """Position 1 runs on a machine, position 2 is a manual step after it:
    with 30 handoff minutes it starts 30 minutes after position 1 ends, on
    the same day, and the response time adds nothing."""
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    position_1 = replace(
        make_context(order_id=1, estimated_duration_minutes=200, not_before=MONDAY),
        lot_id=1,
        lot_position_id=10,
    )
    position_2 = replace(
        make_context(
            order_id=2,
            position_sequence=2,
            is_manual_step=True,
            estimated_duration_minutes=20,
        ),
        lot_id=1,
        lot_position_id=20,
        response_time_days=1,
        internal_handoff_minutes=30,
        predecessor_positions=(
            PredecessorPosition(
                position_id=10,
                sequence=1,
                kind=LotPositionKind.INTERNAL.value,
                external_ready_at=None,
                stored_internal_ready_at=None,
            ),
        ),
    )

    result, _ = schedule_all_propagated(
        machine_queues={1: [position_1]},
        machine_calendars={1: calendar},
        pool_queues={},
        pool_members={},
        manual_queue=[position_2],
        manual_calendar=calendar,
        unassigned=[],
        now=NOW,
    )

    end = result.by_machine[1][0].planned_end
    assert end is not None
    successor = result.manual[0]
    assert successor.planned_start == end + timedelta(minutes=30)
    assert successor.planned_start is not None
    assert successor.planned_start.date() == date(2026, 7, 27)
