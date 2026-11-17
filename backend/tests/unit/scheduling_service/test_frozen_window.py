"""
The frozen window: a queued order whose planned start lies between now and
the end of the window keeps its planned window in a walk, as a pinned one
does, and its earliest start is explained as frozen; an order outside the
window, a late one and a running one are walked as before.
"""

import dataclasses
from datetime import UTC
from datetime import datetime
from datetime import timedelta

from src.modules.fulfillment.application.use_cases.production_schedule._walk_inputs import _freeze
from src.modules.fulfillment.domain.services.scheduling import build_machine_calendar
from src.modules.fulfillment.domain.services.scheduling.forward_walk import explain_earliest_start
from tests.unit.scheduling_service._helpers import MONDAY
from tests.unit.scheduling_service._helpers import WEEKDAY_HOURS
from tests.unit.scheduling_service._helpers import make_context
from tests.unit.scheduling_service._helpers import walk_machine_queue

_NOW = datetime.combine(MONDAY, datetime.min.time(), tzinfo=UTC) + timedelta(hours=8)


def _planned(order_id: int, starts_in_hours: float, *, status: str = "queued"):
    start = _NOW + timedelta(hours=starts_in_hours)
    return make_context(
        order_id=order_id,
        queue_sequence=order_id,
        status=status,
        existing_planned_start=start,
        existing_planned_end=start + timedelta(hours=1),
    )


def test_only_queued_orders_starting_inside_the_window_freeze() -> None:
    contexts = [
        _planned(1, 2),
        _planned(2, 30),
        _planned(3, -1),
        _planned(4, 2, status="in_progress"),
    ]

    frozen = _freeze(contexts, _NOW, _NOW + timedelta(hours=24))

    assert [c.frozen for c in frozen] == [True, False, False, False]


def test_a_frozen_order_keeps_its_window_and_is_explained_as_frozen() -> None:
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    # Planned three hours out although the machine is free right now.
    order = dataclasses.replace(_planned(1, 3), frozen=True)

    [placed] = walk_machine_queue([order], calendar, _NOW)

    assert placed.planned_start == order.existing_planned_start
    assert explain_earliest_start(order).reason == "frozen"


def test_an_order_outside_the_window_is_walked_forward() -> None:
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    order = _planned(1, 3)

    [placed] = walk_machine_queue([order], calendar, _NOW)

    assert placed.planned_start != order.existing_planned_start
