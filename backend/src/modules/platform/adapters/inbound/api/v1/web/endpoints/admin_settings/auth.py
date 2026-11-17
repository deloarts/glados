"""
Admin settings endpoints for the Auth tab. All reads require read:settings;
all writes require write:settings.
"""

from fastapi import Depends
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.admin_settings import get_auth_settings_use_case
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_update_auth_settings_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_verify_ldap_connection_use_case,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.auth import (
    AdminAuthSettingsResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.auth import (
    UpdateAuthSettingsRequest,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.auth import (
    VerifyLdapConnectionRequest,
)
from src.modules.platform.application.dto.admin_settings_dto.auth import AdminAuthSettingsResult
from src.modules.platform.application.dto.admin_settings_dto.auth import UpdateAuthSettingsCommand
from src.modules.platform.application.dto.admin_settings_dto.auth import VerifyLdapConnectionCommand
from src.modules.platform.application.use_cases.admin_settings.get_auth_settings import (
    GetAuthSettings,
)
from src.modules.platform.application.use_cases.admin_settings.update_auth_settings import (
    UpdateAuthSettings,
)
from src.modules.platform.application.use_cases.admin_settings.verify_ldap_connection import (
    VerifyLdapConnection,
)
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/auth", response_model=AdminAuthSettingsResponse)
async def get_auth_settings(
    actor: User = Depends(get_current_active_user),
    use_case: GetAuthSettings = Depends(get_auth_settings_use_case),
) -> AdminAuthSettingsResult:
    return await use_case.execute(actor=actor)


@router.put("/auth", response_model=AdminAuthSettingsResponse)
async def update_auth_settings(
    body: UpdateAuthSettingsRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateAuthSettings = Depends(get_update_auth_settings_use_case),
) -> AdminAuthSettingsResult:
    """Update authentication provider settings. Requires write:settings."""
    cmd = UpdateAuthSettingsCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)


@router.post("/auth/ldap/test", status_code=status.HTTP_204_NO_CONTENT)
async def verify_ldap_connection(
    body: VerifyLdapConnectionRequest,
    actor: User = Depends(get_current_active_user),
    use_case: VerifyLdapConnection = Depends(get_verify_ldap_connection_use_case),
) -> None:
    """Bind to the directory with the supplied settings and credentials.

    204 = bound. 400 = reached the directory but the credentials were
    rejected, or the configuration is incomplete. 503 = could not reach the
    directory at all. Requires write:settings.
    """
    # No try/except: the domain errors map to the three verdicts in
    # exception_handlers, and the admin must be able to tell them apart.
    cmd = VerifyLdapConnectionCommand(**body.model_dump())
    await use_case.execute(actor=actor, cmd=cmd)
