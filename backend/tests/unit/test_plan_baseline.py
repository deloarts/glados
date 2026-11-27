"""
The rules of the nightly baseline (domain/services/plan_baseline.py): the end
of the committed horizon over working days, the orders it records, and when
each lot was planned to finish.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from zoneinfo import ZoneInfo

from src.modules.fulfillment.domain.services.plan_baseline import baseline_entries
from src.modules.fulfillment.domain.services.plan_baseline import commit_horizon_end
from src.modules.fulfillment.domain.services.plan_baseline import lot_planned_finishes
from src.modules.fulfillment.domain.services.scheduling.machine_calendar import MachineCalendar
from src.modules.fulfillment.domain.services.scheduling.machine_calendar import (
    build_machine_calendar,
)
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from tests.unit.production_order._helpers import make_order

VIENNA = ZoneInfo("Europe/Vienna")
# Monday to Friday, eight hours from 08:00.
WEEKDAYS = {0: 480, 1: 480, 2: 480, 3: 480, 4: 480, 5: 0, 6: 0}
THURSDAY = date(2026, 3, 5)


def _calendar(holidays: tuple[date, ...] = ()) -> MachineCalendar:
    return build_machine_calendar(WEEKDAYS, None, {}, zone=VIENNA, holidays=holidays)


def _local_midnight(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=VIENNA).astimezone(UTC)


def test_the_horizon_counts_working_days_across_the_weekend() -> None:
    # Thursday, Friday, Monday, Tuesday, Wednesday: it ends at Thursday's start.
    end = commit_horizon_end(THURSDAY, 5, _calendar())

    assert end == _local_midnight(date(2026, 3, 12))


def test_a_holiday_does_not_count_as_a_working_day() -> None:
    end = commit_horizon_end(THURSDAY, 2, _calendar(holidays=(date(2026, 3, 6),)))

    # Thursday, then Monday, since Friday is a holiday.
    assert end == _local_midnight(date(2026, 3, 10))


def test_a_weekend_day_starts_the_count_on_monday() -> None:
    end = commit_horizon_end(date(2026, 3, 7), 1, _calendar())

    assert end == _local_midnight(date(2026, 3, 10))


def test_the_baseline_records_dated_open_orders_before_the_horizon_in_queue_order() -> None:
    horizon = _local_midnight(date(2026, 3, 12))
    inside = make_order(id=2, machine_id=1, queue_sequence=2)
    inside.planned_start = horizon - timedelta(days=1)
    first = make_order(id=3, machine_id=1, queue_sequence=1)
    first.planned_start = horizon - timedelta(days=2)
    beyond = make_order(id=4, machine_id=1, queue_sequence=3)
    beyond.planned_start = horizon
    undated = make_order(id=5, machine_id=1, queue_sequence=4)
    done = make_order(id=6, machine_id=1, status=ProductionOrderStatus.COMPLETED)
    done.planned_start = horizon - timedelta(days=3)

    entries = baseline_entries([inside, first, beyond, undated, done], horizon)

    assert [e.production_order_id for e in entries] == [3, 2]
    assert entries[0].duration_minutes == first.estimated_duration_minutes


def test_a_lot_finishes_at_its_latest_end_plus_the_wait_after_its_position() -> None:
    end = datetime(2026, 3, 5, 12, tzinfo=UTC)
    early = make_order(id=1, lot_position_id=10)
    early.planned_end = end - timedelta(hours=3)
    late = make_order(id=2, lot_position_id=11)
    late.planned_end = end
    undated = make_order(id=3, lot_position_id=12)

    finishes = lot_planned_finishes([early, late, undated], {10: 1, 11: 1, 12: 2}, {11: 120})

    assert finishes == {1: end + timedelta(minutes=120)}
