"""
Converts src.modules.quality.domain.services.kpi_rules result dataclasses into the
Pydantic result DTOs the production KPI endpoints return.
"""

from dataclasses import asdict
from datetime import datetime

from src.modules.quality.application.dto.production_kpi_dto import EstimateAccuracyRowResult
from src.modules.quality.application.dto.production_kpi_dto import MissingAssessmentRowResult
from src.modules.quality.application.dto.production_kpi_dto import OutsideWorkingTimeRowResult
from src.modules.quality.application.dto.production_kpi_dto import ProductionKpiBookingQualityResult
from src.modules.quality.application.dto.production_kpi_dto import QualityByItemRowResult
from src.modules.quality.application.dto.production_kpi_dto import RatioResult
from src.modules.quality.application.dto.production_kpi_dto import RejectedPerSupplierRowResult
from src.modules.quality.application.dto.production_kpi_dto import ScrapByReasonRowResult
from src.modules.quality.application.dto.production_kpi_dto import ThroughputTimeResult
from src.modules.quality.application.dto.production_kpi_dto import UncausedPauseRowResult
from src.modules.quality.application.dto.production_kpi_dto import UtilizationRowResult
from src.modules.quality.application.dto.production_kpi_dto import WaitingTimeRowResult
from src.modules.quality.application.dto.production_kpi_dto import WeeklyKpiPointResult
from src.modules.quality.domain.services import kpi_rules
from src.modules.quality.domain.services.booking_quality import BookingQuality


def to_ratio_result(ratio: kpi_rules.Ratio) -> RatioResult:
    return RatioResult(value=ratio.value, numerator=ratio.numerator, denominator=ratio.denominator)


def to_throughput_result(result: kpi_rules.ThroughputResult) -> ThroughputTimeResult:
    return ThroughputTimeResult(
        median_days=result.median_days, p90_days=result.p90_days, count=result.count
    )


def to_weekly_point_result(row: kpi_rules.WeeklyKpiRow) -> WeeklyKpiPointResult:
    return WeeklyKpiPointResult(
        iso_week=row.iso_week,
        week_start=row.week_start,
        schedule_adherence=to_ratio_result(row.schedule_adherence),
        on_time_delivery=to_ratio_result(row.on_time_delivery),
    )


def to_estimate_accuracy_row_result(
    row: kpi_rules.EstimateAccuracyRow,
) -> EstimateAccuracyRowResult:
    return EstimateAccuracyRowResult(
        fabrication_method_id=row.fabrication_method_id,
        fabrication_method_name=row.fabrication_method_name.as_dict(),
        median_ratio=row.median_ratio,
        count=row.count,
    )


def to_waiting_time_row_result(row: kpi_rules.WaitingTimeRow) -> WaitingTimeRowResult:
    return WaitingTimeRowResult(
        position_kind=row.position_kind, median_days=row.median_days, count=row.count
    )


def to_quality_by_item_row_result(row: kpi_rules.QualityByItemRow) -> QualityByItemRowResult:
    return QualityByItemRowResult(
        made_item_id=row.made_item_id,
        made_item_part_number=row.made_item_part_number,
        made_item_article_name=row.made_item_article_name,
        completed=row.completed,
        rejected=row.rejected,
        rework=row.rework,
        scrap=row.scrap,
        yield_ratio=to_ratio_result(row.yield_ratio),
    )


def to_scrap_by_reason_row_result(row: kpi_rules.ScrapByReasonRow) -> ScrapByReasonRowResult:
    return ScrapByReasonRowResult(
        reason=row.reason, quantity=row.quantity, share=to_ratio_result(row.share)
    )


def to_rejected_per_supplier_row_result(
    row: kpi_rules.RejectedPerSupplierRow,
) -> RejectedPerSupplierRowResult:
    return RejectedPerSupplierRowResult(
        supplier_id=row.supplier_id,
        supplier_name=row.supplier_name,
        delivered=row.delivered,
        rejected=row.rejected,
        rejected_ratio=to_ratio_result(row.rejected_ratio),
        rejected_lost=row.rejected_lost,
    )


def to_utilization_row_result(
    utilization: kpi_rules.UtilizationRow, availability: kpi_rules.AvailabilityRow | None
) -> UtilizationRowResult:
    return UtilizationRowResult(
        machine_id=utilization.machine_id,
        machine_internal_name=utilization.machine_internal_name,
        net_minutes=utilization.net_minutes,
        available_minutes=availability.available_minutes if availability else None,
        utilization=to_ratio_result(utilization.ratio),
        downtime_minutes=availability.downtime_minutes if availability else None,
        availability=to_ratio_result(availability.ratio) if availability else None,
    )


def to_booking_quality_result(
    quality: BookingQuality, *, since: datetime
) -> ProductionKpiBookingQualityResult:
    return ProductionKpiBookingQualityResult(
        booking_quality_since=since,
        orders_with_bookings=quality.orders_with_bookings,
        outside_working_time=[
            OutsideWorkingTimeRowResult(**asdict(row)) for row in quality.outside_working_time
        ],
        final_completions=quality.final_completions,
        missing_assessments=[
            MissingAssessmentRowResult(**asdict(row)) for row in quality.missing_assessments
        ],
        manual_pauses=quality.manual_pauses,
        uncaused_pauses=[UncausedPauseRowResult(**asdict(row)) for row in quality.uncaused_pauses],
    )
