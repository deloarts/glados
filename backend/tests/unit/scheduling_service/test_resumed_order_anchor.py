"""
A running order that was paused and resumed is placed from its latest
resume, because actual_start keeps the first start for the net work time.
The forward walk, the earliest-start explanation and the context builder
agree on that anchor; an order that never resumed still anchors at
actual_start, which the existing walk tests cover.
"""

from dataclasses import replace
from datetime import UTC
from datetime import datetime

from src.modules.fulfillment.application.services.scheduling_context import build_order_context
from src.modules.fulfillment.domain.entities.production_order_interruption import (
    ProductionOrderInterruption,
)
from src.modules.fulfillment.domain.services.production_time_rules import last_resumed_at
from src.modules.fulfillment.domain.services.scheduling import OrderSchedulingContext
from src.modules.fulfillment.domain.services.scheduling import advance_machine_queue
from src.modules.fulfillment.domain.services.scheduling import build_machine_calendar
from src.modules.fulfillment.domain.services.scheduling import explain_earliest_start
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from tests.unit.scheduling_service._helpers import MONDAY
from tests.unit.scheduling_service._helpers import TUESDAY
from tests.unit.scheduling_service._helpers import WEEKDAY_HOURS
from tests.unit.scheduling_service._helpers import make_context
from tests.unit.scheduling_service._helpers import walk_machine_queue
from tests.unit.test_predecessor_chain_resolution import build_repos
from tests.unit.test_predecessor_chain_resolution import make_lot
from tests.unit.test_predecessor_chain_resolution import make_order
from tests.unit.test_predecessor_chain_resolution import make_position


def _monday(hour: int) -> datetime:
    return datetime(MONDAY.year, MONDAY.month, MONDAY.day, hour, tzinfo=UTC)


def _interruption(paused_at: datetime, resumed_at: datetime | None) -> ProductionOrderInterruption:
    return ProductionOrderInterruption(
        id=0,
        production_order_id=1,
        paused_at=paused_at,
        resumed_at=resumed_at,
        paused_by_id=1,
        resumed_by_id=1 if resumed_at is not None else None,
        created=paused_at,
    )


def _resumed_running_order() -> OrderSchedulingContext:
    """Started at 08:00, paused at 10:00, resumed at 11:00, four hours
    estimated."""
    return replace(
        make_context(
            status=ProductionOrderStatus.IN_PROGRESS.value,
            actual_start=_monday(8),
            estimated_duration_minutes=240,
        ),
        last_resumed_at=_monday(11),
    )


def test_resumed_order_is_placed_from_its_latest_resume():
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})

    planned_start, planned_end, cursor = advance_machine_queue(
        _resumed_running_order(), None, calendar, _monday(7)
    )

    assert (planned_start, planned_end, cursor) == (_monday(11), _monday(15), _monday(15))


def test_queue_behind_a_resumed_order_starts_after_its_window():
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    queued = make_context(order_id=2, queue_sequence=2, estimated_duration_minutes=60)

    results = walk_machine_queue([_resumed_running_order(), queued], calendar, _monday(7))

    assert results[1].planned_start == _monday(15)


def test_explanation_dates_a_resumed_order_by_its_latest_resume():
    """The resume is naive and the start aware; the walk reads both as UTC
    before comparing them."""
    ctx = replace(
        make_context(status=ProductionOrderStatus.IN_PROGRESS.value, actual_start=_monday(8)),
        last_resumed_at=datetime(TUESDAY.year, TUESDAY.month, TUESDAY.day, 9),
    )

    explanation = explain_earliest_start(ctx)

    assert (explanation.reason, explanation.date) == ("in_progress", TUESDAY)


def test_last_resumed_at_is_the_end_of_the_latest_closed_interruption():
    interruptions = [
        _interruption(_monday(9), _monday(10)),
        _interruption(_monday(12), _monday(13)),
        _interruption(_monday(14), None),
    ]

    assert last_resumed_at(interruptions) == _monday(13)


def test_last_resumed_at_is_none_until_an_interruption_closes():
    assert last_resumed_at([]) is None
    assert last_resumed_at([_interruption(_monday(9), None)]) is None


async def test_build_order_context_takes_the_latest_resume_from_the_interruptions():
    lot = make_lot()
    lot.positions = [make_position(id=1, sequence=1, kind=LotPositionKind.INTERNAL)]
    order = make_order(id=1, lot_position_id=1)
    order.status = ProductionOrderStatus.IN_PROGRESS
    order.actual_start = _monday(8)
    order.interruptions = [_interruption(_monday(10), _monday(11))]

    ctx = await build_order_context(
        order, lot, machine=None, repos=build_repos(orders=[order]), target_date=None, zone=UTC
    )

    assert ctx.actual_start == _monday(8)
    assert ctx.last_resumed_at == _monday(11)
