"""
Admin settings endpoints for the AI agent settings. Reads require
read:settings; writes require write:settings.
"""

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_agent_settings_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.admin_settings import (
    get_update_agent_settings_use_case,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.agents import (
    AdminAgentSettingsResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.admin_settings_schema.agents import (
    UpdateAgentSettingsRequest,
)
from src.modules.platform.application.dto.admin_settings_dto.agents import AdminAgentSettingsResult
from src.modules.platform.application.dto.admin_settings_dto.agents import (
    UpdateAgentSettingsCommand,
)
from src.modules.platform.application.use_cases.admin_settings.get_agent_settings import (
    GetAgentSettings,
)
from src.modules.platform.application.use_cases.admin_settings.update_agent_settings import (
    UpdateAgentSettings,
)
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/agents", response_model=AdminAgentSettingsResponse)
async def get_agent_settings(
    actor: User = Depends(get_current_active_user),
    use_case: GetAgentSettings = Depends(get_agent_settings_use_case),
) -> AdminAgentSettingsResult:
    return await use_case.execute(actor=actor)


@router.put("/agents", response_model=AdminAgentSettingsResponse)
async def update_agent_settings(
    body: UpdateAgentSettingsRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateAgentSettings = Depends(get_update_agent_settings_use_case),
) -> AdminAgentSettingsResult:
    """Update the AI agent settings. Requires write:settings."""
    cmd = UpdateAgentSettingsCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)
