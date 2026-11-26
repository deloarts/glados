"""
A running order that overruns pushes the steps after it. With pieces
booked, its planned end is the later of its original end and now plus the
pieces left; without any, the later of its original end and now. After a
resume with pieces booked, the original end counts only the pieces left, so
a pause does not count the whole estimate again.
"""

from dataclasses import replace
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import time

from src.modules.fulfillment.application.services.scheduling_context import build_order_context
from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)
from src.modules.fulfillment.domain.services.scheduling import build_machine_calendar
from src.modules.fulfillment.domain.services.scheduling import schedule_all
from src.modules.fulfillment.domain.services.scheduling.forward_walk import place_on_queue
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from tests.unit.scheduling_service._helpers import MONDAY
from tests.unit.scheduling_service._helpers import TUESDAY
from tests.unit.scheduling_service._helpers import WEEKDAY_HOURS
from tests.unit.scheduling_service._helpers import make_context
from tests.unit.test_response_time_days_buffer import build_repos
from tests.unit.test_response_time_days_buffer import make_lot
from tests.unit.test_response_time_days_buffer import make_order
from tests.unit.test_response_time_days_buffer import make_position

CALENDAR = build_machine_calendar(WEEKDAY_HOURS, None, {})


def _at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=UTC)


def _running(**values):
    """Started Monday 08:00 with an estimate of 240 minutes for 10 pieces
    of 30 minutes each after its setup, so it should end at 12:00."""
    return replace(
        make_context(
            order_id=1,
            status="in_progress",
            actual_start=_at(MONDAY, 8),
            estimated_duration_minutes=240,
        ),
        **{"quantity": 10.0, "minutes_per_piece": 30.0, **values},
    )


def _end(ctx, now: datetime) -> datetime | None:
    return place_on_queue(ctx, None, CALENDAR, now).planned_end


def test_an_order_on_time_keeps_its_original_end():
    assert _end(_running(), _at(MONDAY, 10)) == _at(MONDAY, 12)


def test_an_overrun_without_booked_pieces_ends_now():
    placement = place_on_queue(_running(), None, CALENDAR, _at(MONDAY, 14))
    assert placement.planned_start == _at(MONDAY, 8)
    assert placement.planned_end == _at(MONDAY, 14)


def test_an_overrun_with_booked_pieces_ends_after_the_pieces_left():
    # Four of ten pieces at 13:00, six left of 30 minutes: 16:00.
    assert _end(_running(pieces_processed=4.0), _at(MONDAY, 13)) == _at(MONDAY, 16)


def test_the_pieces_left_continue_on_the_next_working_day():
    # Six pieces left at 15:00: one hour today, two hours from 08:00 Tuesday.
    assert _end(_running(pieces_processed=4.0), _at(MONDAY, 15)) == _at(TUESDAY, 10)


def test_an_order_ahead_of_its_estimate_keeps_its_original_end():
    assert _end(_running(pieces_processed=9.0), _at(MONDAY, 9)) == _at(MONDAY, 12)


def test_an_overrun_outside_working_time_ends_when_work_resumes():
    assert _end(_running(), _at(MONDAY, 20)) == _at(TUESDAY, 8)


def test_a_resume_with_booked_pieces_counts_only_the_pieces_left():
    """Resumed Tuesday 08:00 with five pieces done: five pieces left take
    150 minutes, not the whole estimate again."""
    resumed = _running(
        pieces_processed=5.0, pieces_processed_at_resume=5.0, last_resumed_at=_at(TUESDAY, 8)
    )
    placement = place_on_queue(resumed, None, CALENDAR, _at(TUESDAY, 8))
    assert placement.planned_start == _at(TUESDAY, 8)
    assert placement.planned_end == _at(TUESDAY, 10, 30)


def test_a_resume_without_booked_pieces_counts_the_whole_estimate():
    resumed = _running(last_resumed_at=_at(TUESDAY, 8))
    assert _end(resumed, _at(TUESDAY, 8)) == _at(TUESDAY, 12)


def test_an_order_without_an_estimate_ends_now_while_it_runs():
    no_estimate = _running(minutes_per_piece=0.0, pieces_processed=3.0)
    no_estimate = replace(no_estimate, estimated_duration_minutes=0)
    assert _end(no_estimate, _at(MONDAY, 14)) == _at(MONDAY, 14)


def test_the_next_order_on_the_machine_follows_the_stretched_end():
    queued = make_context(order_id=2, queue_sequence=2, estimated_duration_minutes=60)
    result = schedule_all(
        machine_queues={1: [_running(pieces_processed=4.0), queued]},
        machine_calendars={1: CALENDAR},
        pool_queues={},
        pool_members={},
        manual_queue=[],
        manual_calendar=CALENDAR,
        unassigned=[],
        now=_at(MONDAY, 13),
    )
    placed = {s.order_id: s for s in result.by_machine[1]}
    assert placed[1].planned_end == _at(MONDAY, 16)
    assert placed[2].planned_start == _at(TUESDAY, 8)


def _completion(quantity: float) -> ProductionOrderCompletion:
    return ProductionOrderCompletion(
        id=0,
        created=datetime(2026, 1, 10, tzinfo=UTC),
        production_order_id=20,
        quantity=quantity,
        quantity_accepted=quantity,
        quantity_rejected=0.0,
        completion_date=date(2026, 1, 10),
        note=None,
        operator_id=1,
        recorded_by_id=1,
    )


async def test_the_context_carries_the_progress_and_nets_out_a_reversal():
    lot = make_lot()
    position = make_position(id=1, sequence=1)
    lot.positions = [position]
    order = make_order(id=20, lot_position_id=1)
    order.status = ProductionOrderStatus.IN_PROGRESS
    order.completions = [_completion(4.0), _completion(-4.0), _completion(3.0)]

    ctx = await build_order_context(
        order, lot, machine=None, repos=build_repos(orders=[order]), target_date=None, zone=UTC
    )

    assert ctx.quantity == order.quantity
    assert ctx.pieces_processed == 3.0
    # make_position's step takes 2 minutes per piece.
    assert ctx.minutes_per_piece == 2.0
