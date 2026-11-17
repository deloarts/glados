"""Use case factories: the EPLAN Data Portal settings (read, update, connection
test).
"""

from fastapi import Depends

from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_article_group_repo
from src.modules.catalogue.ports.outbound.catalogue_queries import IArticleGroupQueries
from src.modules.external_data.adapters.inbound.api.deps.repositories import (
    get_external_data_settings_repo,
)
from src.modules.external_data.adapters.inbound.api.deps.services import (
    get_eplan_data_portal_factory,
)
from src.modules.external_data.application.use_cases.admin_settings.get_edp_settings import (
    GetEdpSettings,
)
from src.modules.external_data.application.use_cases.admin_settings.update_edp_settings import (
    UpdateEdpSettings,
)
from src.modules.external_data.application.use_cases.admin_settings.verify_edp_connection import (
    VerifyEdpConnection,
)
from src.modules.external_data.ports.outbound.eplan_data_portal_port import IEplanDataPortalFactory
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


def get_edp_settings_use_case(
    repo: IExternalDataSettingsRepository = Depends(get_external_data_settings_repo),
) -> GetEdpSettings:
    return GetEdpSettings(repo)


def get_update_edp_settings_use_case(
    repo: IExternalDataSettingsRepository = Depends(get_external_data_settings_repo),
    article_group_repo: IArticleGroupQueries = Depends(get_article_group_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateEdpSettings:
    return UpdateEdpSettings(repo, article_group_repo, uow=uow)


def get_verify_edp_connection_use_case(
    repo: IExternalDataSettingsRepository = Depends(get_external_data_settings_repo),
    portal_factory: IEplanDataPortalFactory = Depends(get_eplan_data_portal_factory),
) -> VerifyEdpConnection:
    return VerifyEdpConnection(repo, portal_factory)
