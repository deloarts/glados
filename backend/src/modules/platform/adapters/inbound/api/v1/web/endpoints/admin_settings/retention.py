"""
Admin settings endpoints for the Retention tab. All reads require
read:settings; all writes require write:settings.
"""

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_retention_settings_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_update_retention_settings_use_case,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.retention import (
    AdminRetentionSettingsResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.retention import (
    UpdateRetentionSettingsRequest,
)
from src.modules.platform.application.dto.admin_settings_dto.retention import (
    AdminRetentionSettingsResult,
)
from src.modules.platform.application.dto.admin_settings_dto.retention import (
    UpdateRetentionSettingsCommand,
)
from src.modules.platform.application.use_cases.admin_settings.get_retention_settings import (
    GetRetentionSettings,
)
from src.modules.platform.application.use_cases.admin_settings.update_retention_settings import (
    UpdateRetentionSettings,
)
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/retention", response_model=AdminRetentionSettingsResponse)
async def get_retention_settings(
    actor: User = Depends(get_current_active_user),
    use_case: GetRetentionSettings = Depends(get_retention_settings_use_case),
) -> AdminRetentionSettingsResult:
    return await use_case.execute(actor=actor)


@router.put("/retention", response_model=AdminRetentionSettingsResponse)
async def update_retention_settings(
    body: UpdateRetentionSettingsRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateRetentionSettings = Depends(get_update_retention_settings_use_case),
) -> AdminRetentionSettingsResult:
    """Configure data retention policies. Requires write:settings."""
    cmd = UpdateRetentionSettingsCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)
