"""
Admin settings endpoints of the Planning tab: the committed horizon, the
retention of recorded plans and the start of the booking quality view.
Reads require read:settings; writes require write:settings.
"""

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.fulfillment.adapters.inbound.api.deps.admin_settings import (
    get_planning_settings_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.admin_settings import (
    get_update_planning_settings_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.admin_settings_schema.planning import (
    AdminPlanningSettingsResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.admin_settings_schema.planning import (
    UpdatePlanningSettingsRequest,
)
from src.modules.fulfillment.application.dto.admin_settings_dto.planning import (
    AdminPlanningSettingsResult,
)
from src.modules.fulfillment.application.dto.admin_settings_dto.planning import (
    UpdatePlanningSettingsCommand,
)
from src.modules.fulfillment.application.use_cases.admin_settings.get_planning_settings import (
    GetPlanningSettings,
)
from src.modules.fulfillment.application.use_cases.admin_settings.update_planning_settings import (
    UpdatePlanningSettings,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/planning", response_model=AdminPlanningSettingsResponse)
async def get_planning_settings(
    actor: User = Depends(get_current_active_user),
    use_case: GetPlanningSettings = Depends(get_planning_settings_use_case),
) -> AdminPlanningSettingsResult:
    return await use_case.execute(actor=actor)


@router.put("/planning", response_model=AdminPlanningSettingsResponse)
async def update_planning_settings(
    body: UpdatePlanningSettingsRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdatePlanningSettings = Depends(get_update_planning_settings_use_case),
) -> AdminPlanningSettingsResult:
    """Set the committed horizon and the retention of recorded plans. Requires
    write:settings."""
    cmd = UpdatePlanningSettingsCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)
