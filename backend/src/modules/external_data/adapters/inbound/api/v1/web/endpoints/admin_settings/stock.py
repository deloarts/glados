"""
Admin settings endpoints for the stock service tab: the settings and the
connection test. Reads require read:settings, everything else
write:settings. Validation errors never echo the request input, so a
rejected API key is not reflected back.
"""

from fastapi import Depends
from fastapi.routing import APIRouter

from src.modules.external_data.adapters.inbound.api.deps.stock import get_stock_settings_use_case
from src.modules.external_data.adapters.inbound.api.deps.stock import (
    get_update_stock_settings_use_case,
)
from src.modules.external_data.adapters.inbound.api.deps.stock import (
    get_verify_stock_service_use_case,
)
from src.modules.external_data.adapters.inbound.api.schemas.admin_settings_schema.stock import (
    AdminStockSettingsResponse,
)
from src.modules.external_data.adapters.inbound.api.schemas.admin_settings_schema.stock import (
    StockServiceTestResponse,
)
from src.modules.external_data.adapters.inbound.api.schemas.admin_settings_schema.stock import (
    UpdateStockSettingsRequest,
)
from src.modules.external_data.adapters.inbound.api.schemas.admin_settings_schema.stock import (
    VerifyStockServiceRequest,
)
from src.modules.external_data.application.dto.admin_settings_dto.stock import (
    AdminStockSettingsResult,
)
from src.modules.external_data.application.dto.admin_settings_dto.stock import (
    StockServiceTestResult,
)
from src.modules.external_data.application.dto.admin_settings_dto.stock import (
    UpdateStockSettingsCommand,
)
from src.modules.external_data.application.dto.admin_settings_dto.stock import (
    VerifyStockServiceCommand,
)
from src.modules.external_data.application.use_cases.admin_settings.get_stock_settings import (
    GetStockSettings,
)
from src.modules.external_data.application.use_cases.admin_settings.update_stock_settings import (
    UpdateStockSettings,
)
from src.modules.external_data.application.use_cases.admin_settings.verify_stock_service import (
    VerifyStockService,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.no_echo_route import NoInputEchoRoute
from src.modules.platform.domain.entities.user import User

router = APIRouter(route_class=NoInputEchoRoute)


@router.get("/stock", response_model=AdminStockSettingsResponse)
async def get_stock_settings(
    actor: User = Depends(get_current_active_user),
    use_case: GetStockSettings = Depends(get_stock_settings_use_case),
) -> AdminStockSettingsResult:
    return await use_case.execute(actor=actor)


@router.put("/stock", response_model=AdminStockSettingsResponse)
async def update_stock_settings(
    body: UpdateStockSettingsRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateStockSettings = Depends(get_update_stock_settings_use_case),
) -> AdminStockSettingsResult:
    """Configure the stock service. Enabling needs a service URL and an API
    key; an empty API key clears the stored one."""
    cmd = UpdateStockSettingsCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)


@router.post("/stock/test", response_model=StockServiceTestResponse)
async def test_stock_service(
    body: VerifyStockServiceRequest,
    actor: User = Depends(get_current_active_user),
    use_case: VerifyStockService = Depends(get_verify_stock_service_use_case),
) -> StockServiceTestResult:
    """Probe the stock service with the given or stored URL and API key."""
    cmd = VerifyStockServiceCommand(**body.model_dump())
    return await use_case.execute(actor=actor, cmd=cmd)
