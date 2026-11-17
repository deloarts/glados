"""Use case factories: the production settings tab."""

from fastapi import Depends

from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_inspection_method_repo
from src.modules.catalogue.ports.outbound.catalogue_queries import IInspectionMethodQueries
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_recompute_machine_schedule_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_fulfillment_settings_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_production_lot_repo
from src.modules.fulfillment.application.use_cases.admin_settings.get_production_settings import (
    GetProductionSettings,
)
from src.modules.fulfillment.application.use_cases.admin_settings.update_production_settings import (
    UpdateProductionSettings,
)
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


def get_production_settings_use_case(
    repo: IFulfillmentSettingsRepository = Depends(get_fulfillment_settings_repo),
) -> GetProductionSettings:
    return GetProductionSettings(repo)


def get_update_production_settings_use_case(
    repo: IFulfillmentSettingsRepository = Depends(get_fulfillment_settings_repo),
    inspection_method_repo: IInspectionMethodQueries = Depends(get_inspection_method_repo),
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    recompute: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
) -> UpdateProductionSettings:
    return UpdateProductionSettings(
        repo, inspection_method_repo, lot_repo, uow=uow, recompute_schedule=recompute
    )
