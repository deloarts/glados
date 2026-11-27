"""
Read-only production KPI endpoints: schedule adherence, on-time
delivery, throughput time, utilization, availability, first pass yield,
scrap/rework, estimate accuracy, waiting time, OEE, scrap by reason and
rejected-at-receipt per supplier, each computed on request from the
current data, never cached or pre-aggregated. Same plain-authentication
read access as the schedule board (no dedicated permission).
"""

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.domain.entities.user import User
from src.modules.quality.adapters.inbound.api.deps.production_kpis import (
    get_compute_production_kpis_use_case,
)
from src.modules.quality.adapters.inbound.api.schemas.production_kpi_schema import (
    ProductionKpiFilterParams,
)
from src.modules.quality.application.dto.production_kpi_dto import ProductionKpiBookingQualityResult
from src.modules.quality.application.dto.production_kpi_dto import (
    ProductionKpiEstimateAccuracyResult,
)
from src.modules.quality.application.dto.production_kpi_dto import ProductionKpiLateLotsResult
from src.modules.quality.application.dto.production_kpi_dto import ProductionKpiQualityByItemResult
from src.modules.quality.application.dto.production_kpi_dto import (
    ProductionKpiRejectedPerSupplierResult,
)
from src.modules.quality.application.dto.production_kpi_dto import ProductionKpiScrapByReasonResult
from src.modules.quality.application.dto.production_kpi_dto import ProductionKpiSummaryResult
from src.modules.quality.application.dto.production_kpi_dto import ProductionKpiUtilizationResult
from src.modules.quality.application.dto.production_kpi_dto import ProductionKpiWaitingTimeResult
from src.modules.quality.application.dto.production_kpi_dto import ProductionKpiWeeklyResult
from src.modules.quality.application.use_cases.production_kpi.compute_production_kpis import (
    ComputeProductionKpis,
)

router = APIRouter()


@router.get("/summary", response_model=ProductionKpiSummaryResult)
async def read_summary(
    params: ProductionKpiFilterParams = Depends(),
    _: User = Depends(get_current_active_user),
    use_case: ComputeProductionKpis = Depends(get_compute_production_kpis_use_case),
) -> ProductionKpiSummaryResult:
    return await use_case.summary(params.to_filter())


@router.get("/weekly", response_model=ProductionKpiWeeklyResult)
async def read_weekly(
    params: ProductionKpiFilterParams = Depends(),
    _: User = Depends(get_current_active_user),
    use_case: ComputeProductionKpis = Depends(get_compute_production_kpis_use_case),
) -> ProductionKpiWeeklyResult:
    return await use_case.weekly(params.to_filter())


@router.get("/utilization", response_model=ProductionKpiUtilizationResult)
async def read_utilization(
    params: ProductionKpiFilterParams = Depends(),
    _: User = Depends(get_current_active_user),
    use_case: ComputeProductionKpis = Depends(get_compute_production_kpis_use_case),
) -> ProductionKpiUtilizationResult:
    return await use_case.utilization(params.to_filter())


@router.get("/estimate-accuracy", response_model=ProductionKpiEstimateAccuracyResult)
async def read_estimate_accuracy(
    params: ProductionKpiFilterParams = Depends(),
    _: User = Depends(get_current_active_user),
    use_case: ComputeProductionKpis = Depends(get_compute_production_kpis_use_case),
) -> ProductionKpiEstimateAccuracyResult:
    return await use_case.estimate_accuracy(params.to_filter())


@router.get("/booking-quality", response_model=ProductionKpiBookingQualityResult)
async def read_booking_quality(
    params: ProductionKpiFilterParams = Depends(),
    _: User = Depends(get_current_active_user),
    use_case: ComputeProductionKpis = Depends(get_compute_production_kpis_use_case),
) -> ProductionKpiBookingQualityResult:
    """Orders that ran through hours without working time, final completions
    without an assessment and manual pauses without a cause, in the period."""
    return await use_case.booking_quality(params.to_filter())


@router.get("/waiting-time", response_model=ProductionKpiWaitingTimeResult)
async def read_waiting_time(
    params: ProductionKpiFilterParams = Depends(),
    _: User = Depends(get_current_active_user),
    use_case: ComputeProductionKpis = Depends(get_compute_production_kpis_use_case),
) -> ProductionKpiWaitingTimeResult:
    return await use_case.waiting_time(params.to_filter())


@router.get("/late-lots", response_model=ProductionKpiLateLotsResult)
async def read_late_lots(
    params: ProductionKpiFilterParams = Depends(),
    _: User = Depends(get_current_active_user),
    use_case: ComputeProductionKpis = Depends(get_compute_production_kpis_use_case),
) -> ProductionKpiLateLotsResult:
    return await use_case.late_lots(params.to_filter())


@router.get("/quality-by-item", response_model=ProductionKpiQualityByItemResult)
async def read_quality_by_item(
    params: ProductionKpiFilterParams = Depends(),
    _: User = Depends(get_current_active_user),
    use_case: ComputeProductionKpis = Depends(get_compute_production_kpis_use_case),
) -> ProductionKpiQualityByItemResult:
    return await use_case.quality_by_item(params.to_filter())


@router.get("/scrap-by-reason", response_model=ProductionKpiScrapByReasonResult)
async def read_scrap_by_reason(
    params: ProductionKpiFilterParams = Depends(),
    _: User = Depends(get_current_active_user),
    use_case: ComputeProductionKpis = Depends(get_compute_production_kpis_use_case),
) -> ProductionKpiScrapByReasonResult:
    return await use_case.scrap_by_reason(params.to_filter())


@router.get("/rejected-per-supplier", response_model=ProductionKpiRejectedPerSupplierResult)
async def read_rejected_per_supplier(
    params: ProductionKpiFilterParams = Depends(),
    _: User = Depends(get_current_active_user),
    use_case: ComputeProductionKpis = Depends(get_compute_production_kpis_use_case),
) -> ProductionKpiRejectedPerSupplierResult:
    return await use_case.rejected_per_supplier(params.to_filter())
