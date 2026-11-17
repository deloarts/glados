"""
Admin settings endpoints for the Maintenance tab. All reads require
read:settings; all writes require write:settings.
"""

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_maintenance_settings_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_update_maintenance_settings_use_case,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.maintenance import (
    AdminMaintenanceSettingsResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.maintenance import (
    UpdateMaintenanceSettingsRequest,
)
from src.modules.platform.application.dto.admin_settings_dto.maintenance import (
    AdminMaintenanceSettingsResult,
)
from src.modules.platform.application.dto.admin_settings_dto.maintenance import (
    UpdateMaintenanceSettingsCommand,
)
from src.modules.platform.application.use_cases.admin_settings.get_maintenance_settings import (
    GetMaintenanceSettings,
)
from src.modules.platform.application.use_cases.admin_settings.update_maintenance_settings import (
    UpdateMaintenanceSettings,
)
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/maintenance", response_model=AdminMaintenanceSettingsResponse)
async def get_maintenance_settings(
    actor: User = Depends(get_current_active_user),
    use_case: GetMaintenanceSettings = Depends(get_maintenance_settings_use_case),
) -> AdminMaintenanceSettingsResult:
    return await use_case.execute(actor=actor)


@router.put("/maintenance", response_model=AdminMaintenanceSettingsResponse)
async def update_maintenance_settings(
    body: UpdateMaintenanceSettingsRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateMaintenanceSettings = Depends(get_update_maintenance_settings_use_case),
) -> AdminMaintenanceSettingsResult:
    """Enable or disable maintenance mode. Requires write:settings."""
    cmd = UpdateMaintenanceSettingsCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)
