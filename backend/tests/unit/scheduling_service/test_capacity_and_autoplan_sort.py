"""
Unit tests for the capacity summary and the auto-planner's due-date
backward pass / priority sort. No database, no HTTP, pure functions
only.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from datetime import timedelta
from zoneinfo import ZoneInfo

from src.modules.fulfillment.domain.services.scheduling import AutoPlanCandidate
from src.modules.fulfillment.domain.services.scheduling import ScheduledOrder
from src.modules.fulfillment.domain.services.scheduling import build_machine_calendar
from src.modules.fulfillment.domain.services.scheduling import compute_daily_capacity
from src.modules.fulfillment.domain.services.scheduling import compute_position_due_dates
from src.modules.fulfillment.domain.services.scheduling import position_lead_days
from src.modules.fulfillment.domain.services.scheduling import production_order_touches_date
from src.modules.fulfillment.domain.services.scheduling import sort_candidates
from src.modules.fulfillment.domain.services.scheduling import sort_candidates_by_critical_ratio
from src.modules.fulfillment.domain.services.scheduling import sort_candidates_by_edd
from src.modules.fulfillment.domain.services.scheduling import sort_candidates_by_fifo
from src.modules.fulfillment.domain.services.scheduling import sort_candidates_by_priority
from src.modules.fulfillment.domain.services.scheduling import sort_candidates_by_spt
from tests.unit.scheduling_service._helpers import MONDAY
from tests.unit.scheduling_service._helpers import SATURDAY
from tests.unit.scheduling_service._helpers import WEEKDAY_HOURS


def make_candidate(
    order_id: int,
    urgency_rank: int = 0,
    position_due_date: date | None = None,
    created_order: int | None = None,
    estimated_duration_minutes: int = 60,
) -> AutoPlanCandidate:
    return AutoPlanCandidate(
        order_id=order_id,
        urgency_rank=urgency_rank,
        position_due_date=position_due_date,
        created_order=created_order if created_order is not None else order_id,
        estimated_duration_minutes=estimated_duration_minutes,
    )


def test_compute_daily_capacity_sums_overlap_minutes_per_day():
    calendar = build_machine_calendar(WEEKDAY_HOURS, None, {})
    order_a = ScheduledOrder(
        order_id=1,
        planned_start=datetime.combine(MONDAY, datetime.min.time()) + timedelta(hours=8),
        planned_end=datetime.combine(MONDAY, datetime.min.time()) + timedelta(hours=10),
        conflicts=[],
    )
    result = compute_daily_capacity(calendar, [order_a], [MONDAY, SATURDAY])
    booked, available = result[MONDAY]
    assert booked == 120
    assert available == 480
    booked_sat, available_sat = result[SATURDAY]
    assert booked_sat == 0
    assert available_sat == 0


def test_position_lead_days_external_uses_settings_default():
    assert (
        position_lead_days("external", total_estimated_minutes=0, default_external_lead_days=5) == 5
    )


def test_position_lead_days_internal_converts_minutes_to_workdays():
    assert (
        position_lead_days("internal", total_estimated_minutes=480, default_external_lead_days=5)
        == 1
    )
    assert (
        position_lead_days("internal", total_estimated_minutes=481, default_external_lead_days=5)
        == 2
    )


def test_compute_position_due_dates_backward_pass():
    lot_target = date(2026, 8, 10)
    lead_days = {1: 2, 2: 3}  # position 1's lead time, position 2's lead time
    due = compute_position_due_dates([1, 2], lead_days, lot_target)
    assert due[2] == lot_target
    assert due[1] == lot_target - timedelta(days=3)  # due[1] = due[2] - lead_days[2]


def test_compute_position_due_dates_none_target_propagates_to_all():
    due = compute_position_due_dates([1, 2], {1: 2, 2: 3}, None)
    assert due == {1: None, 2: None}


def test_sort_candidates_by_priority_urgency_then_due_date_then_created():
    low_urgent_early_due = AutoPlanCandidate(
        1,
        urgency_rank=0,
        position_due_date=date(2026, 8, 1),
        created_order=1,
        estimated_duration_minutes=60,
    )
    critical = AutoPlanCandidate(
        2,
        urgency_rank=3,
        position_due_date=date(2026, 9, 1),
        created_order=2,
        estimated_duration_minutes=60,
    )
    no_due_date = AutoPlanCandidate(
        3,
        urgency_rank=0,
        position_due_date=None,
        created_order=3,
        estimated_duration_minutes=60,
    )
    same_urgency_later_due = AutoPlanCandidate(
        4,
        urgency_rank=0,
        position_due_date=date(2026, 8, 5),
        created_order=4,
        estimated_duration_minutes=60,
    )

    ordered = sort_candidates_by_priority(
        [low_urgent_early_due, critical, no_due_date, same_urgency_later_due]
    )
    assert [c.order_id for c in ordered] == [2, 1, 4, 3]


def test_sort_candidates_by_edd_ignores_urgency_entirely():
    urgent_but_later_due = make_candidate(1, urgency_rank=3, position_due_date=date(2026, 8, 10))
    low_priority_but_sooner_due = make_candidate(
        2, urgency_rank=0, position_due_date=date(2026, 8, 1)
    )
    no_due_date = make_candidate(3, urgency_rank=3, position_due_date=None)

    ordered = sort_candidates_by_edd(
        [urgent_but_later_due, low_priority_but_sooner_due, no_due_date]
    )

    assert [c.order_id for c in ordered] == [2, 1, 3]


def test_sort_candidates_by_fifo_ignores_urgency_and_due_date():
    urgent_created_later = make_candidate(
        1, urgency_rank=3, position_due_date=date(2026, 8, 1), created_order=5
    )
    low_priority_created_first = make_candidate(
        2, urgency_rank=0, position_due_date=date(2026, 9, 1), created_order=1
    )

    ordered = sort_candidates_by_fifo([urgent_created_later, low_priority_created_first])

    assert [c.order_id for c in ordered] == [2, 1]


def test_sort_candidates_by_spt_shortest_first_ignores_urgency_and_due_date():
    long_urgent_job = make_candidate(
        1, urgency_rank=3, position_due_date=date(2026, 8, 1), estimated_duration_minutes=480
    )
    short_low_priority_job = make_candidate(
        2, urgency_rank=0, position_due_date=date(2026, 9, 1), estimated_duration_minutes=30
    )

    ordered = sort_candidates_by_spt([long_urgent_job, short_low_priority_job])

    assert [c.order_id for c in ordered] == [2, 1]


def test_sort_candidates_by_critical_ratio_prefers_soonest_relative_to_duration():
    today = date(2026, 8, 1)
    # Due in 2 days, needs 1 day -> ratio 2.0
    tight_short_job = make_candidate(
        1, position_due_date=date(2026, 8, 3), estimated_duration_minutes=480
    )
    # Due in 20 days, needs 1 day -> ratio 20.0 (much less urgent)
    loose_short_job = make_candidate(
        2, position_due_date=date(2026, 8, 21), estimated_duration_minutes=480
    )
    no_due_date = make_candidate(3, position_due_date=None, estimated_duration_minutes=480)

    ordered = sort_candidates_by_critical_ratio(
        [loose_short_job, no_due_date, tight_short_job], today
    )

    assert [c.order_id for c in ordered] == [1, 2, 3]


def test_sort_candidates_dispatch_routes_to_each_strategy():
    urgent = make_candidate(1, urgency_rank=3, created_order=2)
    normal_created_first = make_candidate(2, urgency_rank=0, created_order=1)
    today = date(2026, 8, 1)

    priority_default = sort_candidates([urgent, normal_created_first], "unknown-strategy", today)
    fifo = sort_candidates([urgent, normal_created_first], "fifo", today)

    assert [c.order_id for c in priority_default] == [1, 2]  # urgency wins
    assert [c.order_id for c in fifo] == [2, 1]  # creation order wins


def test_production_order_touches_date_true_when_target_date_inside_window():
    start = datetime(2026, 8, 3, 8, 0)
    end = datetime(2026, 8, 5, 17, 0)
    assert production_order_touches_date(start, end, date(2026, 8, 4), zone=UTC) is True
    # The start day and the end day count as well.
    assert production_order_touches_date(start, end, date(2026, 8, 3), zone=UTC) is True
    assert production_order_touches_date(start, end, date(2026, 8, 5), zone=UTC) is True


def test_production_order_touches_date_false_outside_window():
    start = datetime(2026, 8, 3, 8, 0)
    end = datetime(2026, 8, 5, 17, 0)
    assert production_order_touches_date(start, end, date(2026, 8, 2), zone=UTC) is False
    assert production_order_touches_date(start, end, date(2026, 8, 6), zone=UTC) is False


def test_production_order_touches_date_false_when_not_yet_planned():
    assert production_order_touches_date(None, None, date(2026, 8, 4), zone=UTC) is False


VIENNA = ZoneInfo("Europe/Vienna")


def test_production_order_touches_date_takes_the_local_day_of_a_utc_start():
    """00:30 in Vienna on 15 July (summer time) is 22:30 UTC on 14 July, so
    an order starting then belongs to the local 15th, not the UTC 14th."""
    start = datetime(2026, 7, 14, 22, 30, tzinfo=UTC)
    end = datetime(2026, 7, 14, 23, 30, tzinfo=UTC)
    assert production_order_touches_date(start, end, date(2026, 7, 15), zone=VIENNA) is True
    assert production_order_touches_date(start, end, date(2026, 7, 14), zone=VIENNA) is False


def test_production_order_touches_date_spans_local_midnight():
    """A window from 23:30 to 00:30 local time touches both local days."""
    start = datetime(2026, 7, 14, 21, 30, tzinfo=UTC)  # 23:30 local on the 14th
    end = datetime(2026, 7, 14, 22, 30, tzinfo=UTC)  # 00:30 local on the 15th
    assert production_order_touches_date(start, end, date(2026, 7, 14), zone=VIENNA) is True
    assert production_order_touches_date(start, end, date(2026, 7, 15), zone=VIENNA) is True
    assert production_order_touches_date(start, end, date(2026, 7, 16), zone=VIENNA) is False


def test_production_order_touches_date_reads_a_naive_value_as_utc():
    start = datetime(2026, 7, 14, 22, 30)
    end = datetime(2026, 7, 14, 23, 0)
    assert production_order_touches_date(start, end, date(2026, 7, 15), zone=VIENNA) is True
    assert production_order_touches_date(start, end, date(2026, 7, 14), zone=VIENNA) is False


def test_every_ordering_keeps_the_orders_of_one_lot_in_chain_order() -> None:
    """Shortest first would put the lot's short second step ahead of its
    long first step, a cycle once both land on one machine."""
    long_first = AutoPlanCandidate(
        order_id=1,
        urgency_rank=0,
        position_due_date=None,
        created_order=1,
        estimated_duration_minutes=600,
        lot_id=7,
        position_sequence=1,
    )
    short_second = AutoPlanCandidate(
        order_id=2,
        urgency_rank=0,
        position_due_date=None,
        created_order=2,
        estimated_duration_minutes=30,
        lot_id=7,
        position_sequence=2,
    )
    other = AutoPlanCandidate(
        order_id=3,
        urgency_rank=0,
        position_due_date=None,
        created_order=3,
        estimated_duration_minutes=60,
        lot_id=8,
        position_sequence=1,
    )

    for strategy in ("spt", "critical_ratio", "edd", "fifo", "priority_edd"):
        ordered = [
            c.order_id
            for c in sort_candidates([short_second, other, long_first], strategy, date(2026, 1, 5))
        ]
        assert ordered.index(1) < ordered.index(2), strategy
