"""
Which integrations are switched on and configured, for the overview on the
admin Host tab. It reads the settings of several modules, so it sits in the
read tier. Requires read:settings.
"""

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.domain.entities.user import User
from src.read.adapters.inbound.api.deps import get_integrations_overview_use_case
from src.read.adapters.inbound.api.schemas.admin_settings_schema.integrations_overview import (
    IntegrationsOverviewResponse,
)
from src.read.application.dto.admin_settings_dto.integrations_overview import (
    IntegrationsOverviewResult,
)
from src.read.application.use_cases.admin_settings.get_integrations_overview import (
    GetIntegrationsOverview,
)

router = APIRouter()


@router.get("/host/integrations", response_model=IntegrationsOverviewResponse)
async def get_integrations_overview(
    actor: User = Depends(get_current_active_user),
    use_case: GetIntegrationsOverview = Depends(get_integrations_overview_use_case),
) -> IntegrationsOverviewResult:
    """Return each integration as active, incomplete or off. Requires read:settings."""
    return await use_case.execute(actor=actor)
