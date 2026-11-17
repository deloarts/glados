"""
Use case factories of the read tier's routes: the settings overview, global
search and the state machine catalogue. The whole settings record is bound by
the composition root at startup (`src/bootstrap/bindings.py`), since its store
is assembled from the stores of every module.
"""

from collections.abc import Callable

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.platform.adapters.inbound.api.deps.binding import Binding
from src.modules.platform.adapters.inbound.api.deps.database import get_db
from src.modules.platform.adapters.inbound.api.deps.database import repo_factory
from src.modules.platform.infrastructure.config.settings import cfg
from src.read.adapters.outbound.persistence.repositories.global_search_repository import (
    SqlAlchemyGlobalSearchRepository,
)
from src.read.application.use_cases.admin_settings.get_all_admin_settings import GetAllAdminSettings
from src.read.application.use_cases.admin_settings.get_integrations_overview import (
    GetIntegrationsOverview,
)
from src.read.application.use_cases.search.global_search import GlobalSearch
from src.read.application.use_cases.state_machine.get_state_machine_catalog import (
    GetStateMachineCatalog,
)
from src.read.ports.outbound.repositories.admin_settings_repository import IAdminSettingsRepository
from src.read.ports.outbound.repositories.global_search_repository import IGlobalSearchRepository

admin_settings: Binding[Callable[[AsyncSession], IAdminSettingsRepository]] = Binding(
    "The whole settings record"
)


def get_admin_settings_repo(
    db: AsyncSession = Depends(get_db, scope="function"),
) -> IAdminSettingsRepository:
    return admin_settings.get()(db)


get_global_search_repo: Callable[[AsyncSession], IGlobalSearchRepository] = repo_factory(
    SqlAlchemyGlobalSearchRepository
)


def get_all_admin_settings_use_case(
    repo: IAdminSettingsRepository = Depends(get_admin_settings_repo),
) -> GetAllAdminSettings:
    return GetAllAdminSettings(
        repo,
        cfg.domain,
        pdm_mutating_operations_enabled=cfg.pdm.allow_mutating_operations,
    )


def get_integrations_overview_use_case(
    repo: IAdminSettingsRepository = Depends(get_admin_settings_repo),
) -> GetIntegrationsOverview:
    return GetIntegrationsOverview(repo)


def get_state_machine_catalog_use_case() -> GetStateMachineCatalog:
    return GetStateMachineCatalog()


def get_global_search_use_case(
    repo: IGlobalSearchRepository = Depends(get_global_search_repo),
) -> GlobalSearch:
    return GlobalSearch(repo)
