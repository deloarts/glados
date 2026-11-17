"""Use case factories: the stock service settings (read, update, connection
test).
"""

from fastapi import Depends

from src.modules.external_data.adapters.inbound.api.deps.repositories import (
    get_external_data_settings_repo,
)
from src.modules.external_data.adapters.inbound.api.deps.services import get_stock_service_factory
from src.modules.external_data.application.use_cases.admin_settings.get_stock_settings import (
    GetStockSettings,
)
from src.modules.external_data.application.use_cases.admin_settings.update_stock_settings import (
    UpdateStockSettings,
)
from src.modules.external_data.application.use_cases.admin_settings.verify_stock_service import (
    VerifyStockService,
)
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.external_data.ports.outbound.stock_service_port import IStockServiceFactory
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


def get_stock_settings_use_case(
    repo: IExternalDataSettingsRepository = Depends(get_external_data_settings_repo),
) -> GetStockSettings:
    return GetStockSettings(repo)


def get_update_stock_settings_use_case(
    repo: IExternalDataSettingsRepository = Depends(get_external_data_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateStockSettings:
    return UpdateStockSettings(repo, uow=uow)


def get_verify_stock_service_use_case(
    service_factory: IStockServiceFactory = Depends(get_stock_service_factory),
    repo: IExternalDataSettingsRepository = Depends(get_external_data_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> VerifyStockService:
    return VerifyStockService(service_factory, repo, uow)
