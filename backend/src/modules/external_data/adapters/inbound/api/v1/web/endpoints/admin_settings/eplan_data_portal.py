"""
Admin settings endpoints for the EPLAN Data Portal tab: the settings and
the connection test. Reads require read:settings, everything else
write:settings.
"""

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.external_data.adapters.inbound.api.deps.eplan_data_portal import (
    get_edp_settings_use_case,
)
from src.modules.external_data.adapters.inbound.api.deps.eplan_data_portal import (
    get_update_edp_settings_use_case,
)
from src.modules.external_data.adapters.inbound.api.deps.eplan_data_portal import (
    get_verify_edp_connection_use_case,
)
from src.modules.external_data.adapters.inbound.api.schemas.admin_settings_schema.eplan_data_portal import (
    AdminEdpSettingsResponse,
)
from src.modules.external_data.adapters.inbound.api.schemas.admin_settings_schema.eplan_data_portal import (
    EdpConnectionTestResponse,
)
from src.modules.external_data.adapters.inbound.api.schemas.admin_settings_schema.eplan_data_portal import (
    UpdateEdpSettingsRequest,
)
from src.modules.external_data.adapters.inbound.api.schemas.admin_settings_schema.eplan_data_portal import (
    VerifyEdpConnectionRequest,
)
from src.modules.external_data.application.dto.admin_settings_dto.eplan_data_portal import (
    AdminEdpSettingsResult,
)
from src.modules.external_data.application.dto.admin_settings_dto.eplan_data_portal import (
    EdpConnectionTestResult,
)
from src.modules.external_data.application.dto.admin_settings_dto.eplan_data_portal import (
    UpdateEdpSettingsCommand,
)
from src.modules.external_data.application.dto.admin_settings_dto.eplan_data_portal import (
    VerifyEdpConnectionCommand,
)
from src.modules.external_data.application.use_cases.admin_settings.get_edp_settings import (
    GetEdpSettings,
)
from src.modules.external_data.application.use_cases.admin_settings.update_edp_settings import (
    UpdateEdpSettings,
)
from src.modules.external_data.application.use_cases.admin_settings.verify_edp_connection import (
    VerifyEdpConnection,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/eplan-data-portal", response_model=AdminEdpSettingsResponse)
async def get_edp_settings(
    actor: User = Depends(get_current_active_user),
    use_case: GetEdpSettings = Depends(get_edp_settings_use_case),
) -> AdminEdpSettingsResult:
    return await use_case.execute(actor=actor)


@router.put("/eplan-data-portal", response_model=AdminEdpSettingsResponse)
async def update_edp_settings(
    body: UpdateEdpSettingsRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateEdpSettings = Depends(get_update_edp_settings_use_case),
) -> AdminEdpSettingsResult:
    """Configure the Data Portal. Enabling needs a token; an empty token
    clears the stored one and switches the lookups off."""
    cmd = UpdateEdpSettingsCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)


@router.post("/eplan-data-portal/test", response_model=EdpConnectionTestResponse)
async def test_edp_connection(
    body: VerifyEdpConnectionRequest,
    actor: User = Depends(get_current_active_user),
    use_case: VerifyEdpConnection = Depends(get_verify_edp_connection_use_case),
) -> EdpConnectionTestResult:
    """Probe the Data Portal with the given or stored URL and token."""
    cmd = VerifyEdpConnectionCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)
