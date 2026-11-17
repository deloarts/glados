"""
Admin settings endpoints of the Numbering tab for the production section:
production order numbering. Reads require read:settings; writes require
write:settings.
"""

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.fulfillment.adapters.inbound.api.deps.admin_settings import (
    get_production_settings_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.admin_settings import (
    get_update_production_settings_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.admin_settings_schema.production import (
    AdminProductionSettingsResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.admin_settings_schema.production import (
    UpdateProductionSettingsRequest,
)
from src.modules.fulfillment.application.dto.admin_settings_dto.production import (
    AdminProductionSettingsResult,
)
from src.modules.fulfillment.application.dto.admin_settings_dto.production import (
    UpdateProductionSettingsCommand,
)
from src.modules.fulfillment.application.use_cases.admin_settings.get_production_settings import (
    GetProductionSettings,
)
from src.modules.fulfillment.application.use_cases.admin_settings.update_production_settings import (
    UpdateProductionSettings,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/production", response_model=AdminProductionSettingsResponse)
async def get_production_settings(
    actor: User = Depends(get_current_active_user),
    use_case: GetProductionSettings = Depends(get_production_settings_use_case),
) -> AdminProductionSettingsResult:
    return await use_case.execute(actor=actor)


@router.put("/production", response_model=AdminProductionSettingsResponse)
async def update_production_settings(
    body: UpdateProductionSettingsRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateProductionSettings = Depends(get_update_production_settings_use_case),
) -> AdminProductionSettingsResult:
    """Configure the production-order numbering format. Requires write:settings."""
    cmd = UpdateProductionSettingsCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)
