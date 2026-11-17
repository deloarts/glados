"""
Every admin settings section in one response, for the settings page. It
reads the sections of every module, so it sits in the read tier. Requires
read:settings.
"""

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.domain.entities.user import User
from src.read.adapters.inbound.api.deps import get_all_admin_settings_use_case
from src.read.adapters.inbound.api.schemas.admin_settings_schema.all_settings import (
    AllAdminSettingsResponse,
)
from src.read.application.dto.admin_settings_dto.all_settings import AllAdminSettingsResult
from src.read.application.use_cases.admin_settings.get_all_admin_settings import GetAllAdminSettings

router = APIRouter()


@router.get("/", response_model=AllAdminSettingsResponse)
async def get_all_settings(
    actor: User = Depends(get_current_active_user),
    use_case: GetAllAdminSettings = Depends(get_all_admin_settings_use_case),
) -> AllAdminSettingsResult:
    """Return all admin settings in a single response. Requires read:settings."""
    return await use_case.execute(actor=actor)
