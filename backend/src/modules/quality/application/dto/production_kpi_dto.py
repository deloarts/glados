"""
DTOs for the production KPI read model: one filter shared by every
endpoint, and one result DTO per endpoint, each a thin Pydantic mirror of
the corresponding src.modules.quality.domain.services.kpi_rules result.
"""

from datetime import date

from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.application.dto.base import ResultModel


class KpiFilter(BaseModel):
    date_from: date
    date_to: date
    machine_id: int | None = None
    machine_pool_id: int | None = None
    project_id: int | None = None
    customer_id: int | None = None


class RatioResult(ResultModel):
    value: float | None
    numerator: float
    denominator: float


class ThroughputTimeResult(ResultModel):
    median_days: float | None
    p90_days: float | None
    count: int


class ProductionKpiSummaryResult(ResultModel):
    schedule_adherence: RatioResult
    on_time_delivery: RatioResult
    throughput_time: ThroughputTimeResult
    first_pass_yield: RatioResult
    scrap_ratio: RatioResult
    rework_ratio: RatioResult
    # Overall (not per-machine) utilization/availability across every
    # machine in scope, None when no machine is in scope at all (an
    # empty pool, or a filter combination matching nothing).
    utilization: RatioResult | None
    availability: RatioResult | None
    # Shown only when utilization, availability and first_pass_yield are
    # all computable, see kpi_rules.compute_oee.
    oee: float | None


class WeeklyKpiPointResult(ResultModel):
    iso_week: str
    week_start: date
    schedule_adherence: RatioResult
    on_time_delivery: RatioResult


class ProductionKpiWeeklyResult(ResultModel):
    points: list[WeeklyKpiPointResult] = Field(default_factory=list)


class UtilizationRowResult(ResultModel):
    machine_id: int | None
    machine_internal_name: str
    net_minutes: int
    available_minutes: int | None
    utilization: RatioResult
    downtime_minutes: int | None
    availability: RatioResult | None


class ProductionKpiUtilizationResult(ResultModel):
    rows: list[UtilizationRowResult] = Field(default_factory=list)


class EstimateAccuracyRowResult(ResultModel):
    fabrication_method_id: int
    fabrication_method_name: dict[str, str]
    median_ratio: float | None
    count: int


class ProductionKpiEstimateAccuracyResult(ResultModel):
    rows: list[EstimateAccuracyRowResult] = Field(default_factory=list)


class WaitingTimeRowResult(ResultModel):
    position_kind: str
    median_days: float | None
    count: int


class ProductionKpiWaitingTimeResult(ResultModel):
    rows: list[WaitingTimeRowResult] = Field(default_factory=list)


class LateLotResult(ResultModel):
    lot_id: int
    lot_number: str
    target_date: date
    projected_end: date
    days_late: int
    # The reason naming what currently governs the lot's latest order's
    # earliest possible start (scheduling.explain_earliest_start),
    # None when that order has already finished (the delay traces to a
    # different, still-open position of the lot instead).
    driver_reason: str | None
    driver_date: date | None


class ProductionKpiLateLotsResult(ResultModel):
    rows: list[LateLotResult] = Field(default_factory=list)


class QualityByItemRowResult(ResultModel):
    made_item_id: int
    made_item_part_number: str
    made_item_article_name: str
    completed: float
    rejected: float
    rework: float
    scrap: float
    yield_ratio: RatioResult


class ProductionKpiQualityByItemResult(ResultModel):
    rows: list[QualityByItemRowResult] = Field(default_factory=list)


class ScrapByReasonRowResult(ResultModel):
    reason: str
    quantity: float
    share: RatioResult


class ProductionKpiScrapByReasonResult(ResultModel):
    rows: list[ScrapByReasonRowResult] = Field(default_factory=list)


class RejectedPerSupplierRowResult(ResultModel):
    supplier_id: int
    supplier_name: str
    delivered: float
    rejected: float
    rejected_ratio: RatioResult
    rejected_lost: float


class ProductionKpiRejectedPerSupplierResult(ResultModel):
    rows: list[RejectedPerSupplierRowResult] = Field(default_factory=list)
