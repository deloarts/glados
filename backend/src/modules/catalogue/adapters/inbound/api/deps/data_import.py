"""Use case factories: the data import settings (read and update on the admin
tab) and the import profile every spreadsheet import reads.
"""

from fastapi import Depends

from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_catalogue_settings_repo
from src.modules.catalogue.application.use_cases.admin_settings.get_data_import_settings import (
    GetDataImportSettings,
)
from src.modules.catalogue.application.use_cases.admin_settings.update_data_import_settings import (
    UpdateDataImportSettings,
)
from src.modules.catalogue.application.use_cases.data_import.get_data_import_profile import (
    GetDataImportProfile,
)
from src.modules.catalogue.ports.outbound.catalogue_settings_repository import (
    ICatalogueSettingsRepository,
)
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


def get_data_import_settings_use_case(
    repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
) -> GetDataImportSettings:
    return GetDataImportSettings(repo)


def get_update_data_import_settings_use_case(
    repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateDataImportSettings:
    return UpdateDataImportSettings(repo, uow=uow)


def get_data_import_profile_use_case(
    repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
) -> GetDataImportProfile:
    return GetDataImportProfile(repo)
