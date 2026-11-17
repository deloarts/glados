"""
Unit tests for src/modules/quality/domain/services/kpi_rules.py's pure formulas, covering
every KPI definition including the empty-input/zero-denominator cases
that must resolve to a None ratio rather than a division by zero.
"""

from datetime import UTC
from datetime import date
from datetime import datetime
from zoneinfo import ZoneInfo

from src.modules.fulfillment.domain.entities.production_order_interruption import (
    ProductionOrderInterruption,
)
from src.modules.quality.domain.services import kpi_rules

VIENNA = ZoneInfo("Europe/Vienna")


def _interruption(paused_at: datetime, resumed_at: datetime | None) -> ProductionOrderInterruption:
    return ProductionOrderInterruption(
        id=1,
        production_order_id=1,
        paused_at=paused_at,
        resumed_at=resumed_at,
        paused_by_id=1,
        resumed_by_id=1 if resumed_at else None,
        created=paused_at,
    )


def _order(
    order_id=1,
    machine_id=1,
    lot_id=1,
    actual_start=datetime(2026, 1, 1, 8, 0, tzinfo=UTC),
    actual_end=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
    planned_end_at_start=None,
    estimated_duration_minutes=60,
    interruptions=(),
    fabrication_methods=(),
) -> kpi_rules.CompletedOrderRow:
    return kpi_rules.CompletedOrderRow(
        order_id=order_id,
        machine_id=machine_id,
        lot_id=lot_id,
        actual_start=actual_start,
        actual_end=actual_end,
        planned_end_at_start=planned_end_at_start,
        estimated_duration_minutes=estimated_duration_minutes,
        interruptions=tuple(interruptions),
        fabrication_methods=tuple(fabrication_methods),
    )


def _completion(
    completion_id=1,
    made_item_id=1,
    made_item_part_number="PN-1",
    made_item_article_name="Bracket",
    quantity=10.0,
    quantity_accepted=10.0,
    quantity_rejected=0.0,
    quantity_rework=0.0,
    quantity_scrap=0.0,
) -> kpi_rules.CompletionRow:
    return kpi_rules.CompletionRow(
        completion_id=completion_id,
        made_item_id=made_item_id,
        made_item_part_number=made_item_part_number,
        made_item_article_name=made_item_article_name,
        quantity=quantity,
        quantity_accepted=quantity_accepted,
        quantity_rejected=quantity_rejected,
        quantity_rework=quantity_rework,
        quantity_scrap=quantity_scrap,
    )


def _lot(
    lot_id=1,
    lot_number="L-1",
    created=datetime(2026, 1, 1, tzinfo=UTC),
    completed_at=datetime(2026, 1, 5, tzinfo=UTC),
    target_date=None,
) -> kpi_rules.LotRow:
    return kpi_rules.LotRow(
        lot_id=lot_id,
        lot_number=lot_number,
        created=created,
        completed_at=completed_at,
        target_date=target_date,
    )


class TestRatio:
    def test_zero_denominator_is_none(self):
        result = kpi_rules.ratio(5, 0)
        assert result.value is None
        assert result.numerator == 5
        assert result.denominator == 0

    def test_normal_division(self):
        result = kpi_rules.ratio(1, 4)
        assert result.value == 0.25


class TestPercentileAndMedian:
    def test_empty_is_none(self):
        assert kpi_rules.median([]) is None
        assert kpi_rules.percentile([], 0.9) is None

    def test_single_value(self):
        assert kpi_rules.median([5.0]) == 5.0

    def test_median_odd_count(self):
        assert kpi_rules.median([1.0, 3.0, 2.0]) == 2.0

    def test_median_even_count_interpolates(self):
        assert kpi_rules.median([1.0, 2.0, 3.0, 4.0]) == 2.5

    def test_p90_interpolates(self):
        # rank = (10-1)*0.9 = 8.1 -> between index 8 (value 9) and 9 (value 10)
        values = [float(i) for i in range(1, 11)]
        assert kpi_rules.percentile(values, 0.9) == 9.1


class TestScheduleAdherence:
    def test_empty_orders_is_none(self):
        result = kpi_rules.compute_schedule_adherence([])
        assert result.value is None
        assert result.denominator == 0

    def test_no_baseline_excluded_from_both_sides(self):
        order = _order(planned_end_at_start=None)
        result = kpi_rules.compute_schedule_adherence([order])
        assert result.value is None
        assert result.denominator == 0

    def test_on_time_and_late_split(self):
        on_time = _order(
            order_id=1,
            actual_end=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
            planned_end_at_start=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
        )
        late = _order(
            order_id=2,
            actual_end=datetime(2026, 1, 1, 11, 0, tzinfo=UTC),
            planned_end_at_start=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
        )
        exactly_on_time = _order(
            order_id=3,
            actual_end=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
            planned_end_at_start=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
        )
        result = kpi_rules.compute_schedule_adherence([on_time, late, exactly_on_time])
        assert result.numerator == 2
        assert result.denominator == 3
        assert result.value == 2 / 3


class TestOnTimeDelivery:
    def test_empty_is_none(self):
        assert kpi_rules.compute_on_time_delivery([]).value is None

    def test_no_target_date_excluded(self):
        lot = _lot(target_date=None)
        result = kpi_rules.compute_on_time_delivery([lot])
        assert result.denominator == 0
        assert result.value is None

    def test_on_time_and_late_split(self):
        on_time = _lot(
            lot_id=1, completed_at=datetime(2026, 1, 5, tzinfo=UTC), target_date=date(2026, 1, 5)
        )
        late = _lot(
            lot_id=2, completed_at=datetime(2026, 1, 6, tzinfo=UTC), target_date=date(2026, 1, 5)
        )
        result = kpi_rules.compute_on_time_delivery([on_time, late])
        assert result.numerator == 1
        assert result.denominator == 2

    def test_completion_counts_on_the_tenant_day(self):
        """23:30 UTC on 5 January is already 6 January in Vienna."""
        lot = _lot(
            completed_at=datetime(2026, 1, 5, 23, 30, tzinfo=UTC), target_date=date(2026, 1, 5)
        )
        assert kpi_rules.compute_on_time_delivery([lot], VIENNA).value == 0.0


class TestThroughputTime:
    def test_empty_is_none(self):
        result = kpi_rules.compute_throughput_time([])
        assert result.median_days is None
        assert result.p90_days is None
        assert result.count == 0

    def test_known_values(self):
        lots = [
            _lot(
                lot_id=1,
                created=datetime(2026, 1, 1, tzinfo=UTC),
                completed_at=datetime(2026, 1, 3, tzinfo=UTC),
            ),
            _lot(
                lot_id=2,
                created=datetime(2026, 1, 1, tzinfo=UTC),
                completed_at=datetime(2026, 1, 5, tzinfo=UTC),
            ),
        ]
        result = kpi_rules.compute_throughput_time(lots)
        assert result.median_days == 3.0
        assert result.count == 2


class TestFirstPassYieldScrapRework:
    def test_empty_is_none(self):
        assert kpi_rules.compute_first_pass_yield([]).value is None
        assert kpi_rules.compute_scrap_ratio([]).value is None
        assert kpi_rules.compute_rework_ratio([]).value is None

    def test_zero_total_quantity_is_none(self):
        completion = _completion(quantity=0.0, quantity_accepted=0.0)
        assert kpi_rules.compute_first_pass_yield([completion]).value is None

    def test_normal_ratios(self):
        completion = _completion(
            quantity=10.0,
            quantity_accepted=7.0,
            quantity_rejected=3.0,
            quantity_rework=2.0,
            quantity_scrap=1.0,
        )
        assert kpi_rules.compute_first_pass_yield([completion]).value == 0.7
        assert kpi_rules.compute_scrap_ratio([completion]).value == 0.1
        assert kpi_rules.compute_rework_ratio([completion]).value == 0.2


class TestUtilization:
    def test_empty_orders_and_capacity(self):
        rows = kpi_rules.compute_utilization([], [])
        # Always includes the manual bucket, with no denominator.
        assert len(rows) == 1
        assert rows[0].machine_id is None
        assert rows[0].ratio.value is None

    def test_machine_with_capacity_and_no_orders_is_zero(self):
        capacity = [
            kpi_rules.CapacityRow(machine_id=1, machine_internal_name="M1", available_minutes=480)
        ]
        rows = kpi_rules.compute_utilization([], capacity)
        machine_row = next(r for r in rows if r.machine_id == 1)
        assert machine_row.net_minutes == 0
        assert machine_row.ratio.value == 0.0

    def test_net_minutes_over_available(self):
        order = _order(
            machine_id=1,
            actual_start=datetime(2026, 1, 1, 8, 0, tzinfo=UTC),
            actual_end=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
        )
        capacity = [
            kpi_rules.CapacityRow(machine_id=1, machine_internal_name="M1", available_minutes=120)
        ]
        rows = kpi_rules.compute_utilization([order], capacity)
        machine_row = next(r for r in rows if r.machine_id == 1)
        assert machine_row.net_minutes == 60
        assert machine_row.ratio.value == 0.5

    def test_manual_orders_have_no_machine_and_no_ratio(self):
        order = _order(machine_id=None)
        rows = kpi_rules.compute_utilization([order], [])
        manual_row = next(r for r in rows if r.machine_id is None)
        assert manual_row.net_minutes == 60
        assert manual_row.ratio.value is None

    def test_order_on_machine_without_capacity_row_gets_none_ratio(self):
        order = _order(machine_id=99)
        rows = kpi_rules.compute_utilization([order], [])
        leftover_row = next(r for r in rows if r.machine_id == 99)
        assert leftover_row.net_minutes == 60
        assert leftover_row.ratio.value is None


class TestAvailability:
    def test_zero_available_minutes_is_none(self):
        capacity = [
            kpi_rules.CapacityRow(machine_id=1, machine_internal_name="M1", available_minutes=0)
        ]
        rows = kpi_rules.compute_availability(capacity, [])
        assert rows[0].ratio.value is None

    def test_downtime_reduces_ratio(self):
        capacity = [
            kpi_rules.CapacityRow(machine_id=1, machine_internal_name="M1", available_minutes=480)
        ]
        downtime = [kpi_rules.DowntimeRow(machine_id=1, minutes=120)]
        rows = kpi_rules.compute_availability(capacity, downtime)
        assert rows[0].downtime_minutes == 120
        assert rows[0].ratio.value == 360 / 480

    def test_downtime_exceeding_available_clamps_at_zero(self):
        capacity = [
            kpi_rules.CapacityRow(machine_id=1, machine_internal_name="M1", available_minutes=100)
        ]
        downtime = [kpi_rules.DowntimeRow(machine_id=1, minutes=500)]
        rows = kpi_rules.compute_availability(capacity, downtime)
        assert rows[0].ratio.value == 0.0


class TestEstimateAccuracy:
    def test_empty_is_empty_list(self):
        assert kpi_rules.compute_estimate_accuracy([]) == []

    def test_zero_estimate_excluded(self):
        order = _order(
            estimated_duration_minutes=0,
            fabrication_methods=[kpi_rules.FabricationMethodRef(1, "Milling")],
        )
        assert kpi_rules.compute_estimate_accuracy([order]) == []

    def test_missing_net_minutes_excluded(self):
        order = _order(
            actual_start=None,
            fabrication_methods=[kpi_rules.FabricationMethodRef(1, "Milling")],
        )
        assert kpi_rules.compute_estimate_accuracy([order]) == []

    def test_order_contributes_to_every_method_of_its_position(self):
        order = _order(
            actual_start=datetime(2026, 1, 1, 8, 0, tzinfo=UTC),
            actual_end=datetime(2026, 1, 1, 9, 0, tzinfo=UTC),
            estimated_duration_minutes=60,
            fabrication_methods=[
                kpi_rules.FabricationMethodRef(1, "Milling"),
                kpi_rules.FabricationMethodRef(2, "Turning"),
            ],
        )
        rows = kpi_rules.compute_estimate_accuracy([order])
        assert {r.fabrication_method_id for r in rows} == {1, 2}
        for row in rows:
            assert row.median_ratio == 1.0
            assert row.count == 1


class TestWaitingTime:
    def test_empty_is_empty_list(self):
        assert kpi_rules.compute_waiting_time([]) == []

    def test_missing_predecessor_ready_excluded(self):
        row = kpi_rules.WaitingRow(
            order_id=1,
            position_kind="internal",
            actual_start=datetime(2026, 1, 5, tzinfo=UTC),
            predecessor_ready=None,
        )
        assert kpi_rules.compute_waiting_time([row]) == []

    def test_grouped_by_position_kind(self):
        internal_row = kpi_rules.WaitingRow(
            order_id=1,
            position_kind="internal",
            actual_start=datetime(2026, 1, 5, tzinfo=UTC),
            predecessor_ready=date(2026, 1, 3),
        )
        external_row = kpi_rules.WaitingRow(
            order_id=2,
            position_kind="external",
            actual_start=datetime(2026, 1, 10, tzinfo=UTC),
            predecessor_ready=date(2026, 1, 8),
        )
        rows = kpi_rules.compute_waiting_time([internal_row, external_row])
        by_kind = {r.position_kind: r for r in rows}
        assert by_kind["internal"].median_days == 2.0
        assert by_kind["internal"].count == 1
        assert by_kind["external"].median_days == 2.0

    def test_the_start_counts_on_the_tenant_day(self):
        """23:30 UTC on 4 January is 5 January in Vienna, two days after the 3rd."""
        row = kpi_rules.WaitingRow(
            order_id=1,
            position_kind="internal",
            actual_start=datetime(2026, 1, 4, 23, 30, tzinfo=UTC),
            predecessor_ready=date(2026, 1, 3),
        )
        assert kpi_rules.compute_waiting_time([row], VIENNA)[0].median_days == 2.0


class TestQualityByItem:
    def test_empty_is_empty_list(self):
        assert kpi_rules.compute_quality_by_item([]) == []

    def test_grouped_by_made_item_with_yield(self):
        first = _completion(
            made_item_id=1, quantity=10.0, quantity_accepted=8.0, quantity_rejected=2.0
        )
        second = _completion(
            made_item_id=1, quantity=5.0, quantity_accepted=5.0, quantity_rejected=0.0
        )
        other_item = _completion(made_item_id=2, quantity=0.0, quantity_accepted=0.0)
        rows = kpi_rules.compute_quality_by_item([first, second, other_item])
        by_item = {r.made_item_id: r for r in rows}
        assert by_item[1].completed == 15.0
        assert by_item[1].rejected == 2.0
        assert by_item[1].yield_ratio.value == 13 / 15
        assert by_item[2].yield_ratio.value is None  # zero-quantity total


class TestIsLotLate:
    def test_none_effective_end_is_not_late(self):
        assert kpi_rules.is_lot_late(None, date(2026, 1, 1)) is False

    def test_none_target_date_is_not_late(self):
        assert kpi_rules.is_lot_late(datetime(2026, 1, 1, tzinfo=UTC), None) is False

    def test_after_target_is_late(self):
        assert kpi_rules.is_lot_late(datetime(2026, 1, 6, tzinfo=UTC), date(2026, 1, 5)) is True

    def test_on_target_is_not_late(self):
        assert (
            kpi_rules.is_lot_late(datetime(2026, 1, 5, 23, 0, tzinfo=UTC), date(2026, 1, 5))
            is False
        )

    def test_the_finish_is_read_on_the_tenant_day(self):
        """23:00 UTC on 5 January is midnight of 6 January in Vienna."""
        end = datetime(2026, 1, 5, 23, 0, tzinfo=UTC)
        assert kpi_rules.is_lot_late(end, date(2026, 1, 5), VIENNA) is True


class TestPerformance:
    def test_empty_is_none(self):
        assert kpi_rules.compute_performance([]).value is None

    def test_capped_at_one(self):
        # Estimated 30, worked 60 (ran slower than estimated) -> 0.5, no cap.
        slow_order = _order(
            estimated_duration_minutes=30,
            actual_start=datetime(2026, 1, 1, 8, tzinfo=UTC),
            actual_end=datetime(2026, 1, 1, 9, tzinfo=UTC),
        )
        result = kpi_rules.compute_performance([slow_order])
        assert result.value == 0.5

        # Estimated 120, worked 60 (faster than estimated) -> would be 2.0, capped at 1.
        fast_order = _order(
            estimated_duration_minutes=120,
            actual_start=datetime(2026, 1, 1, 8, tzinfo=UTC),
            actual_end=datetime(2026, 1, 1, 9, tzinfo=UTC),
        )
        result = kpi_rules.compute_performance([fast_order])
        assert result.value == 1.0


class TestOee:
    def test_none_when_availability_missing(self):
        missing = kpi_rules.Ratio(None, 0, 0)
        present = kpi_rules.Ratio(1.0, 1, 1)
        assert kpi_rules.compute_oee(missing, present, present, present) is None

    def test_none_when_utilization_missing(self):
        missing = kpi_rules.Ratio(None, 0, 0)
        present = kpi_rules.Ratio(1.0, 1, 1)
        assert kpi_rules.compute_oee(present, missing, present, present) is None

    def test_none_when_yield_missing(self):
        missing = kpi_rules.Ratio(None, 0, 0)
        present = kpi_rules.Ratio(1.0, 1, 1)
        assert kpi_rules.compute_oee(present, present, missing, present) is None

    def test_none_when_performance_missing(self):
        missing = kpi_rules.Ratio(None, 0, 0)
        present = kpi_rules.Ratio(1.0, 1, 1)
        assert kpi_rules.compute_oee(present, present, present, missing) is None

    def test_multiplies_the_three_factors(self):
        availability = kpi_rules.Ratio(0.9, 9, 10)
        utilization = kpi_rules.Ratio(0.8, 8, 10)  # only gates, does not multiply
        yield_ratio = kpi_rules.Ratio(0.95, 19, 20)
        performance = kpi_rules.Ratio(0.5, 5, 10)
        result = kpi_rules.compute_oee(availability, utilization, yield_ratio, performance)
        assert result == 0.9 * 0.5 * 0.95


class TestIsoWeeks:
    def test_single_day_period_returns_one_week(self):
        weeks = kpi_rules.iso_weeks_in_period(date(2026, 1, 5), date(2026, 1, 5))
        assert len(weeks) == 1
        key, week_start = weeks[0]
        assert key == "2026-W02"
        assert week_start == date(2026, 1, 5)  # 2026-01-05 is a Monday

    def test_period_spanning_two_weeks(self):
        weeks = kpi_rules.iso_weeks_in_period(date(2026, 1, 9), date(2026, 1, 12))
        keys = [key for key, _ in weeks]
        assert keys == ["2026-W02", "2026-W03"]


class TestWeeklySeries:
    def test_empty_still_lists_every_week(self):
        points = kpi_rules.compute_weekly_series([], [], date(2026, 1, 5), date(2026, 1, 11))
        assert len(points) == 1
        assert points[0].schedule_adherence.value is None
        assert points[0].on_time_delivery.value is None

    def test_orders_and_lots_bucketed_into_their_own_week(self):
        order = _order(
            actual_end=datetime(2026, 1, 6, tzinfo=UTC),
            planned_end_at_start=datetime(2026, 1, 6, tzinfo=UTC),
        )
        lot = _lot(completed_at=datetime(2026, 1, 6, tzinfo=UTC), target_date=date(2026, 1, 6))
        points = kpi_rules.compute_weekly_series(
            [order], [lot], date(2026, 1, 5), date(2026, 1, 11)
        )
        assert len(points) == 1
        assert points[0].iso_week == "2026-W02"
        assert points[0].schedule_adherence.value == 1.0
        assert points[0].on_time_delivery.value == 1.0

    def test_a_sunday_night_finish_falls_into_the_tenant_week(self):
        """23:30 UTC on Sunday 11 January is Monday 12 January in Vienna."""
        end = datetime(2026, 1, 11, 23, 30, tzinfo=UTC)
        order = _order(actual_end=end, planned_end_at_start=end)
        points = kpi_rules.compute_weekly_series(
            [order], [], date(2026, 1, 5), date(2026, 1, 18), VIENNA
        )
        by_week = {point.iso_week: point for point in points}
        assert by_week["2026-W02"].schedule_adherence.value is None
        assert by_week["2026-W03"].schedule_adherence.value == 1.0
