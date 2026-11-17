"""
Tenant holiday calendar endpoints, prefix `/holidays`. Every signed-in user
can read the calendar; changes and deletes require write:machines.
"""

from fastapi import Depends
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.holidays import (
    get_create_tenant_holiday_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.holidays import (
    get_delete_tenant_holiday_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.holidays import (
    get_list_tenant_holidays_use_case,
)
from src.modules.platform.adapters.inbound.api.deps.holidays import (
    get_update_tenant_holiday_use_case,
)
from src.modules.platform.adapters.inbound.api.schemas.tenant_holiday_schema import (
    SaveTenantHolidayRequest,
)
from src.modules.platform.adapters.inbound.api.schemas.tenant_holiday_schema import (
    TenantHolidayResponse,
)
from src.modules.platform.application.dto.tenant_holiday_dto import SaveTenantHolidayCommand
from src.modules.platform.application.dto.tenant_holiday_dto import TenantHolidayResult
from src.modules.platform.application.use_cases.tenant_holiday.tenant_holidays import (
    CreateTenantHoliday,
)
from src.modules.platform.application.use_cases.tenant_holiday.tenant_holidays import (
    DeleteTenantHoliday,
)
from src.modules.platform.application.use_cases.tenant_holiday.tenant_holidays import (
    ListTenantHolidays,
)
from src.modules.platform.application.use_cases.tenant_holiday.tenant_holidays import (
    UpdateTenantHoliday,
)
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/", response_model=list[TenantHolidayResponse])
async def list_tenant_holidays(
    _: User = Depends(get_current_active_user),
    use_case: ListTenantHolidays = Depends(get_list_tenant_holidays_use_case),
) -> list[TenantHolidayResult]:
    return await use_case.execute()


@router.post("/", response_model=TenantHolidayResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant_holiday(
    body: SaveTenantHolidayRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateTenantHoliday = Depends(get_create_tenant_holiday_use_case),
) -> TenantHolidayResult:
    """Add a public holiday or plant shutdown. Requires write:machines."""
    return await use_case.execute(actor=actor, cmd=SaveTenantHolidayCommand(**body.model_dump()))


@router.put("/{holiday_id}", response_model=TenantHolidayResponse)
async def update_tenant_holiday(
    holiday_id: int,
    body: SaveTenantHolidayRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateTenantHoliday = Depends(get_update_tenant_holiday_use_case),
) -> TenantHolidayResult:
    """Change a holiday. Requires write:machines."""
    return await use_case.execute(
        actor=actor, holiday_id=holiday_id, cmd=SaveTenantHolidayCommand(**body.model_dump())
    )


@router.delete("/{holiday_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant_holiday(
    holiday_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: DeleteTenantHoliday = Depends(get_delete_tenant_holiday_use_case),
) -> None:
    """Remove a holiday. Requires write:machines."""
    await use_case.execute(actor=actor, holiday_id=holiday_id)
