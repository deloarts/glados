"""
Edge cases of the wait after a step and of the walk's placement reasons: a
step at a supplier known only by its forecast, a line that already arrived,
a pool order held by its member machine, a resumed order on pace, a
completed position whose wait still runs, and an in-house step that has no
order yet.
"""

from dataclasses import replace
from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import time
from datetime import timedelta

from src.modules.fulfillment.application.services.scheduling_context import build_order_context
from src.modules.fulfillment.domain.entities.production_order_completion import (
    ProductionOrderCompletion,
)
from src.modules.fulfillment.domain.entities.production_order_interruption import (
    ProductionOrderInterruption,
)
from src.modules.fulfillment.domain.policies.wait_after import StepWait
from src.modules.fulfillment.domain.policies.wait_after import position_wait_after_minutes
from src.modules.fulfillment.domain.services.scheduling import PredecessorPosition
from src.modules.fulfillment.domain.services.scheduling import build_machine_calendar
from src.modules.fulfillment.domain.services.scheduling import resolve_chain_external_forecasts
from src.modules.fulfillment.domain.services.scheduling import schedule_all
from src.modules.fulfillment.domain.services.scheduling import schedule_all_propagated
from src.modules.fulfillment.domain.services.scheduling.external_work import ExternalWorkChain
from src.modules.fulfillment.domain.services.scheduling.external_work import latest_pickup_dates
from src.modules.fulfillment.domain.services.scheduling.forward_walk import place_on_queue
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
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
NOW = datetime.combine(MONDAY, time(8), tzinfo=UTC)


def _at(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=UTC)


def _manual_successor(*predecessors, **values):
    return replace(
        make_context(order_id=3, position_sequence=3, is_manual_step=True),
        lot_id=1,
        lot_position_id=30,
        predecessor_positions=predecessors,
        **values,
    )


def test_a_step_at_a_supplier_known_only_by_its_forecast_is_named_as_such():
    """Position 2 is at a supplier without any date: the walk dates the
    next step from the forecast, and the reason says so instead of naming
    the in-house position 1."""
    milling = replace(
        make_context(order_id=1, estimated_duration_minutes=60, not_before=MONDAY),
        lot_id=1,
        lot_position_id=10,
    )
    internal = PredecessorPosition(
        position_id=10,
        sequence=1,
        kind=LotPositionKind.INTERNAL.value,
        external_ready_at=None,
        stored_internal_ready_at=None,
    )
    external = PredecessorPosition(
        position_id=20,
        sequence=2,
        kind=LotPositionKind.EXTERNAL.value,
        external_ready_at=None,
        stored_internal_ready_at=None,
        lead_days=5,
    )
    result, _ = schedule_all_propagated(
        machine_queues={1: [milling]},
        machine_calendars={1: CALENDAR},
        pool_queues={},
        pool_members={},
        manual_queue=[_manual_successor(internal, external, response_time_days=1)],
        manual_calendar=CALENDAR,
        unassigned=[],
        now=NOW,
    )
    reason = result.manual[0].reason
    assert reason is not None
    assert (reason.kind, reason.forecast, reason.position_id) == ("order_line", True, 20)
    assert reason.expected_date == reason.day - timedelta(days=1)  # type: ignore[operator]


def test_a_line_that_arrived_names_its_arrival_day():
    arrived = PredecessorPosition(
        position_id=20,
        sequence=2,
        kind=LotPositionKind.EXTERNAL.value,
        external_ready_at=MONDAY,
        stored_internal_ready_at=None,
        typed_external_date=None,
        order_item_id=52,
    )
    successor = _manual_successor(arrived, response_time_days=1, predecessor_ready_at=TUESDAY)
    reason = place_on_queue(successor, None, CALENDAR, NOW).reason
    assert reason is not None
    assert (reason.kind, reason.arrived, reason.expected_date) == ("order_line", True, MONDAY)


def test_a_pool_order_held_by_its_member_names_the_order_ahead():
    on_machine = make_context(order_id=1, estimated_duration_minutes=120)
    pooled = make_context(order_id=2, estimated_duration_minutes=60, machine_pool_id=7)
    result = schedule_all(
        machine_queues={1: [on_machine]},
        machine_calendars={1: CALENDAR},
        pool_queues={7: [pooled]},
        pool_members={7: [1]},
        manual_queue=[],
        manual_calendar=CALENDAR,
        unassigned=[],
        now=NOW,
    )
    reason = result.by_pool[7][0].reason
    assert reason is not None
    assert (reason.kind, reason.previous_order_id) == ("queue", 1)


def _resumed(**values):
    """10 pieces of 30 minutes, resumed Monday 10:00 with 2 done, so the
    eight left end at 14:00."""
    return replace(
        make_context(
            order_id=1,
            status="in_progress",
            actual_start=_at(MONDAY, 8),
            estimated_duration_minutes=320,
        ),
        last_resumed_at=_at(MONDAY, 10),
        quantity=10.0,
        minutes_per_piece=30.0,
        pieces_processed_at_resume=2.0,
        **values,
    )


def test_a_resumed_order_on_pace_is_no_overrun():
    """At 11:00 with 4 done it is on pace: six pieces left end at 14:00,
    the end the resume set, and nothing overruns."""
    placement = place_on_queue(_resumed(pieces_processed=4.0), None, CALENDAR, _at(MONDAY, 11))
    assert placement.planned_end == _at(MONDAY, 14)
    assert placement.reason is not None
    assert placement.reason.overrun is False


def test_a_resumed_order_ahead_of_pace_keeps_the_end_the_resume_set():
    placement = place_on_queue(_resumed(pieces_processed=9.0), None, CALENDAR, _at(MONDAY, 11))
    assert placement.planned_end == _at(MONDAY, 14)


def _completion(quantity: float, created: datetime) -> ProductionOrderCompletion:
    return ProductionOrderCompletion(
        id=0,
        created=created,
        production_order_id=20,
        quantity=quantity,
        quantity_accepted=quantity,
        quantity_rejected=0.0,
        completion_date=created.date(),
        note=None,
        operator_id=1,
        recorded_by_id=1,
    )


async def test_the_context_counts_the_pieces_booked_before_the_resume():
    lot = make_lot()
    lot.positions = [make_position(id=1, sequence=1)]
    order = make_order(id=20, lot_position_id=1)
    order.status = ProductionOrderStatus.IN_PROGRESS
    order.interruptions = [
        ProductionOrderInterruption(
            id=1,
            production_order_id=20,
            paused_at=_at(MONDAY, 9),
            resumed_at=_at(MONDAY, 10),
            paused_by_id=1,
            resumed_by_id=1,
            created=_at(MONDAY, 9),
        )
    ]
    order.completions = [_completion(2.0, _at(MONDAY, 8, 50)), _completion(3.0, _at(MONDAY, 11))]

    ctx = await build_order_context(
        order, lot, machine=None, repos=build_repos(orders=[order]), target_date=None, zone=UTC
    )

    assert ctx.pieces_processed == 5.0
    assert ctx.pieces_processed_at_resume == 2.0


def test_a_completed_position_in_its_wait_gets_no_forecast():
    """A completed MIXED position whose wait still runs is in the chain, but
    the walk forecasts nothing for it, so its stored dates stay."""
    completed = PredecessorPosition(
        position_id=20,
        sequence=1,
        kind=LotPositionKind.MIXED.value,
        external_ready_at=MONDAY,
        stored_internal_ready_at=None,
        wait_after_minutes=1440,
        completed=True,
        completed_ready_at=TUESDAY,
        completed_ready_moment=_at(TUESDAY, 9),
    )
    assert resolve_chain_external_forecasts((completed,), {}, 1) == {}


def test_an_in_house_step_without_an_order_counts_its_wait():
    """An unassigned position nobody outsources will be done in house, so its
    wait counts in the backward pass, as it will once it has an order."""
    steps = [StepWait(1, False, 2880)]
    assert position_wait_after_minutes(LotPositionKind.UNASSIGNED, steps) == 2880
    outsourced = [StepWait(1, True, 2880)]
    assert position_wait_after_minutes(LotPositionKind.UNASSIGNED, outsourced) == 0

    hardening = PredecessorPosition(
        position_id=10,
        sequence=1,
        kind=LotPositionKind.EXTERNAL.value,
        external_ready_at=None,
        stored_internal_ready_at=None,
        lead_days=4,
    )
    painting = PredecessorPosition(
        position_id=20,
        sequence=2,
        kind=LotPositionKind.UNASSIGNED.value,
        external_ready_at=None,
        stored_internal_ready_at=None,
        wait_after_minutes=2880,
    )
    chain = ExternalWorkChain(
        lot_id=1,
        positions=(hardening, painting),
        external_position_ids=frozenset({10}),
        target_date=date(2026, 12, 20),
        remaining_minutes_by_position={20: 30},
    )
    # Painting takes a day of work and two of waiting before the 20th, so the
    # hardening is back by the 17th and leaves four days before.
    assert latest_pickup_dates(chain, 0) == {10: date(2026, 12, 13)}
