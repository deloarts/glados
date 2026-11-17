"""
Admin settings endpoints for the Notifications tab, including the
signed-in banner. All reads require read:settings; all writes require
write:settings.
"""

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_banner_settings_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_notification_settings_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_update_banner_settings_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_update_notification_settings_use_case,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.banner import (
    AdminBannerSettingsResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.banner import (
    UpdateBannerSettingsRequest,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.notifications import (
    AdminNotificationSettingsResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.notifications import (
    UpdateNotificationSettingsRequest,
)
from src.modules.platform.application.dto.admin_settings_dto.banner import AdminBannerSettingsResult
from src.modules.platform.application.dto.admin_settings_dto.banner import (
    UpdateBannerSettingsCommand,
)
from src.modules.platform.application.dto.admin_settings_dto.notifications import (
    AdminNotificationSettingsResult,
)
from src.modules.platform.application.dto.admin_settings_dto.notifications import (
    UpdateNotificationSettingsCommand,
)
from src.modules.platform.application.use_cases.admin_settings.get_banner_settings import (
    GetBannerSettings,
)
from src.modules.platform.application.use_cases.admin_settings.get_notification_settings import (
    GetNotificationSettings,
)
from src.modules.platform.application.use_cases.admin_settings.update_banner_settings import (
    UpdateBannerSettings,
)
from src.modules.platform.application.use_cases.admin_settings.update_notification_settings import (
    UpdateNotificationSettings,
)
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/notifications", response_model=AdminNotificationSettingsResponse)
async def get_notification_settings(
    actor: User = Depends(get_current_active_user),
    use_case: GetNotificationSettings = Depends(get_notification_settings_use_case),
) -> AdminNotificationSettingsResult:
    return await use_case.execute(actor=actor)


@router.put("/notifications", response_model=AdminNotificationSettingsResponse)
async def update_notification_settings(
    body: UpdateNotificationSettingsRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateNotificationSettings = Depends(get_update_notification_settings_use_case),
) -> AdminNotificationSettingsResult:
    """Configure outbound webhook notifications. Requires write:settings."""
    cmd = UpdateNotificationSettingsCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)


@router.get("/banner", response_model=AdminBannerSettingsResponse)
async def get_banner_settings(
    actor: User = Depends(get_current_active_user),
    use_case: GetBannerSettings = Depends(get_banner_settings_use_case),
) -> AdminBannerSettingsResult:
    return await use_case.execute(actor=actor)


@router.put("/banner", response_model=AdminBannerSettingsResponse)
async def update_banner_settings(
    body: UpdateBannerSettingsRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateBannerSettings = Depends(get_update_banner_settings_use_case),
) -> AdminBannerSettingsResult:
    """Full replace of the signed-in banner, like maintenance. Requires
    write:settings."""
    cmd = UpdateBannerSettingsCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)
