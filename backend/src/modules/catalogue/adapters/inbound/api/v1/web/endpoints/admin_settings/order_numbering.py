"""
Admin settings endpoints of the Numbering tab for the order section: bought
item and order numbering, the PDM part number pattern and the delivery
tolerances. Reads require read:settings; writes require write:settings.
"""

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.catalogue.adapters.inbound.api.deps.admin_settings import (
    get_order_settings_use_case,
)
from src.modules.catalogue.adapters.inbound.api.deps.admin_settings import (
    get_update_order_settings_use_case,
)
from src.modules.catalogue.adapters.inbound.api.schemas.admin_settings_schema.orders import (
    AdminOrderSettingsResponse,
)
from src.modules.catalogue.adapters.inbound.api.schemas.admin_settings_schema.orders import (
    UpdateOrderSettingsRequest,
)
from src.modules.catalogue.application.dto.admin_settings_dto.orders import AdminOrderSettingsResult
from src.modules.catalogue.application.dto.admin_settings_dto.orders import (
    UpdateOrderSettingsCommand,
)
from src.modules.catalogue.application.use_cases.admin_settings.get_order_settings import (
    GetOrderSettings,
)
from src.modules.catalogue.application.use_cases.admin_settings.update_order_settings import (
    UpdateOrderSettings,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/orders", response_model=AdminOrderSettingsResponse)
async def get_order_settings(
    actor: User = Depends(get_current_active_user),
    use_case: GetOrderSettings = Depends(get_order_settings_use_case),
) -> AdminOrderSettingsResult:
    return await use_case.execute(actor=actor)


@router.put("/orders", response_model=AdminOrderSettingsResponse)
async def update_order_settings(
    body: UpdateOrderSettingsRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateOrderSettings = Depends(get_update_order_settings_use_case),
) -> AdminOrderSettingsResult:
    """Configure the order numbering format. Requires write:settings."""
    cmd = UpdateOrderSettingsCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)
