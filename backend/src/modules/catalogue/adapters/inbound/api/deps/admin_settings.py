"""Use case factories: the order and made item settings tabs."""

from fastapi import Depends

from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_catalogue_settings_repo
from src.modules.catalogue.application.use_cases.admin_settings.get_made_item_settings import (
    GetMadeItemSettings,
)
from src.modules.catalogue.application.use_cases.admin_settings.get_order_settings import (
    GetOrderSettings,
)
from src.modules.catalogue.application.use_cases.admin_settings.update_made_item_settings import (
    UpdateMadeItemSettings,
)
from src.modules.catalogue.application.use_cases.admin_settings.update_order_settings import (
    UpdateOrderSettings,
)
from src.modules.catalogue.ports.outbound.catalogue_settings_repository import (
    ICatalogueSettingsRepository,
)
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


def get_order_settings_use_case(
    repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
) -> GetOrderSettings:
    return GetOrderSettings(repo)


def get_update_order_settings_use_case(
    repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateOrderSettings:
    return UpdateOrderSettings(repo, uow=uow)


def get_made_item_settings_use_case(
    repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
) -> GetMadeItemSettings:
    return GetMadeItemSettings(repo)


def get_update_made_item_settings_use_case(
    repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateMadeItemSettings:
    return UpdateMadeItemSettings(repo, uow=uow)
