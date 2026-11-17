"""
Admin settings endpoints of the Numbering tab for the made item section:
made item numbering and revisions. Reads require read:settings; writes
require write:settings.
"""

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.catalogue.adapters.inbound.api.deps.admin_settings import (
    get_made_item_settings_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.admin_settings import (
    get_update_made_item_settings_use_case,
)
from src.modules.catalogue.adapters.inbound.api.schemas.admin_settings_schema.made_items import (
    AdminMadeItemSettingsResponse,
)
from src.modules.catalogue.adapters.inbound.api.schemas.admin_settings_schema.made_items import (
    UpdateMadeItemSettingsRequest,
)
from src.modules.catalogue.application.dto.admin_settings_dto.made_items import (
    AdminMadeItemSettingsResult,
)
from src.modules.catalogue.application.dto.admin_settings_dto.made_items import (
    UpdateMadeItemSettingsCommand,
)
from src.modules.catalogue.application.use_cases.admin_settings.get_made_item_settings import (
    GetMadeItemSettings,
)
from src.modules.catalogue.application.use_cases.admin_settings.update_made_item_settings import (
    UpdateMadeItemSettings,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/made-items", response_model=AdminMadeItemSettingsResponse)
async def get_made_item_settings(
    actor: User = Depends(get_current_active_user),
    use_case: GetMadeItemSettings = Depends(get_made_item_settings_use_case),
) -> AdminMadeItemSettingsResult:
    return await use_case.execute(actor=actor)


@router.put("/made-items", response_model=AdminMadeItemSettingsResponse)
async def update_made_item_settings(
    body: UpdateMadeItemSettingsRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateMadeItemSettings = Depends(get_update_made_item_settings_use_case),
) -> AdminMadeItemSettingsResult:
    """Configure the made-item numbering format. Requires write:settings."""
    cmd = UpdateMadeItemSettingsCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)
