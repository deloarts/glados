"""Use case factory: the production KPIs."""

from fastapi import Depends

from src.modules.fulfillment.adapters.inbound.api.deps.production import get_scheduling_repos
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_fulfillment_settings_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_machine_calendar_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_machine_downtime_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_machine_pool_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_production_machine_repo,
)
from src.modules.fulfillment.application.facade.scheduling import IMachineCalendarRepository
from src.modules.fulfillment.application.facade.scheduling import IMachinePoolRepository
from src.modules.fulfillment.application.facade.scheduling import IProductionMachineRepository
from src.modules.fulfillment.application.facade.scheduling import SchedulingRepos
from src.modules.fulfillment.ports.outbound.fulfillment_queries import IMachineDowntimeQueries
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
from src.modules.quality.adapters.inbound.api.deps.repositories import get_production_kpi_repo
from src.modules.quality.application.use_cases.production_kpi.compute_production_kpis import (
    ComputeProductionKpis,
)
from src.modules.quality.ports.outbound.repositories.production_kpi_repository import (
    IProductionKpiRepository,
)


def get_compute_production_kpis_use_case(
    kpi_repo: IProductionKpiRepository = Depends(get_production_kpi_repo),
    repos: SchedulingRepos = Depends(get_scheduling_repos),
    machine_repo: IProductionMachineRepository = Depends(get_production_machine_repo),
    pool_repo: IMachinePoolRepository = Depends(get_machine_pool_repo),
    calendar_repo: IMachineCalendarRepository = Depends(get_machine_calendar_repo),
    settings_repo: IFulfillmentSettingsRepository = Depends(get_fulfillment_settings_repo),
    downtime_repo: IMachineDowntimeQueries = Depends(get_machine_downtime_repo),
) -> ComputeProductionKpis:
    return ComputeProductionKpis(
        kpi_repo=kpi_repo,
        scheduling_repos=repos,
        machine_repo=machine_repo,
        pool_repo=pool_repo,
        calendar_repo=calendar_repo,
        settings_repo=settings_repo,
        downtime_repo=downtime_repo,
    )
