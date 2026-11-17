"""Use case factories: the tenant holidays."""

from fastapi import Depends

from src.modules.platform.adapters.inbound.api.deps.bindings import get_schedule_recompute
from src.modules.platform.adapters.inbound.api.deps.bindings import get_tenant_holiday_repo
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.application.services.schedule_recompute_port import ScheduleRecompute
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
from src.modules.platform.ports.outbound.repositories.tenant_holiday_repository import (
    ITenantHolidayRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork

# ── Tenant holidays ─────────────────────────────────────────────────────


def get_list_tenant_holidays_use_case(
    calendar_repo: ITenantHolidayRepository = Depends(get_tenant_holiday_repo),
) -> ListTenantHolidays:
    return ListTenantHolidays(calendar_repo)


def get_create_tenant_holiday_use_case(
    calendar_repo: ITenantHolidayRepository = Depends(get_tenant_holiday_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    recompute: ScheduleRecompute = Depends(get_schedule_recompute),
) -> CreateTenantHoliday:
    return CreateTenantHoliday(calendar_repo, uow=uow, recompute_schedule=recompute)


def get_update_tenant_holiday_use_case(
    calendar_repo: ITenantHolidayRepository = Depends(get_tenant_holiday_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    recompute: ScheduleRecompute = Depends(get_schedule_recompute),
) -> UpdateTenantHoliday:
    return UpdateTenantHoliday(calendar_repo, uow=uow, recompute_schedule=recompute)


def get_delete_tenant_holiday_use_case(
    calendar_repo: ITenantHolidayRepository = Depends(get_tenant_holiday_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    recompute: ScheduleRecompute = Depends(get_schedule_recompute),
) -> DeleteTenantHoliday:
    return DeleteTenantHoliday(calendar_repo, uow=uow, recompute_schedule=recompute)
