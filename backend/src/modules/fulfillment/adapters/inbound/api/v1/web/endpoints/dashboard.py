"""
The dashboard summary, `/dashboard`. Status counts and the recent spend are
computed here, so the dashboard never pages through whole lists.
"""

from datetime import tzinfo

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.fulfillment.adapters.inbound.api.deps.dashboard import (
    get_dashboard_summary_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.dashboard_schema import (
    DashboardSummaryResponse,
)
from src.modules.fulfillment.application.dto.dashboard_dto import DashboardSummaryResult
from src.modules.fulfillment.application.use_cases.dashboard.get_dashboard_summary import (
    GetDashboardSummary,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.misc import get_tenant_zone
from src.modules.platform.domain.entities.user import User
from src.shared_kernel.domain.services.clock import today_in

router = APIRouter()


@router.get("/summary", response_model=DashboardSummaryResponse)
async def read_dashboard_summary(
    _: User = Depends(get_current_active_user),
    zone: tzinfo = Depends(get_tenant_zone),
    use_case: GetDashboardSummary = Depends(get_dashboard_summary_use_case),
) -> DashboardSummaryResult:
    return await use_case.execute(today_in(zone), zone)
