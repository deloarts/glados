"""
Admin settings endpoints for the Security tab. All reads require
read:settings; all writes require write:settings.
"""

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_security_settings_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_update_security_settings_use_case,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.security import (
    AdminSecuritySettingsResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.security import (
    UpdateSecuritySettingsRequest,
)
from src.modules.platform.application.dto.admin_settings_dto.security import (
    AdminSecuritySettingsResult,
)
from src.modules.platform.application.dto.admin_settings_dto.security import (
    UpdateSecuritySettingsCommand,
)
from src.modules.platform.application.use_cases.admin_settings.get_security_settings import (
    GetSecuritySettings,
)
from src.modules.platform.application.use_cases.admin_settings.update_security_settings import (
    UpdateSecuritySettings,
)
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/security", response_model=AdminSecuritySettingsResponse)
async def get_security_settings(
    actor: User = Depends(get_current_active_user),
    use_case: GetSecuritySettings = Depends(get_security_settings_use_case),
) -> AdminSecuritySettingsResult:
    return await use_case.execute(actor=actor)


@router.put("/security", response_model=AdminSecuritySettingsResponse)
async def update_security_settings(
    body: UpdateSecuritySettingsRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateSecuritySettings = Depends(get_update_security_settings_use_case),
) -> AdminSecuritySettingsResult:
    """Update authentication and security policy settings. Requires write:settings."""
    cmd = UpdateSecuritySettingsCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)
