"""
Admin settings endpoints for the Features tab. All reads require
read:settings; all writes require write:settings.
"""

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_feature_settings_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_update_feature_settings_use_case,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.features import (
    AdminFeatureSettingsResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.features import (
    UpdateFeatureSettingsRequest,
)
from src.modules.platform.application.dto.admin_settings_dto.features import (
    AdminFeatureSettingsResult,
)
from src.modules.platform.application.dto.admin_settings_dto.features import (
    UpdateFeatureSettingsCommand,
)
from src.modules.platform.application.use_cases.admin_settings.get_feature_settings import (
    GetFeatureSettings,
)
from src.modules.platform.application.use_cases.admin_settings.update_feature_settings import (
    UpdateFeatureSettings,
)
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/features", response_model=AdminFeatureSettingsResponse)
async def get_feature_settings(
    actor: User = Depends(get_current_active_user),
    use_case: GetFeatureSettings = Depends(get_feature_settings_use_case),
) -> AdminFeatureSettingsResult:
    return await use_case.execute(actor=actor)


@router.put("/features", response_model=AdminFeatureSettingsResponse)
async def update_feature_settings(
    body: UpdateFeatureSettingsRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateFeatureSettings = Depends(get_update_feature_settings_use_case),
) -> AdminFeatureSettingsResult:
    """Toggle feature flags. Requires write:settings."""
    cmd = UpdateFeatureSettingsCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)
