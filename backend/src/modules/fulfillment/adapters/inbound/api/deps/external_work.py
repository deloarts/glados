"""Dependency factories of the procurement list of external work."""

from fastapi import Depends

from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_supplier_repo
from src.modules.catalogue.ports.outbound.catalogue_queries import ISupplierQueries
from src.modules.fulfillment.adapters.inbound.api.deps.production import get_scheduling_repos
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_fulfillment_settings_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_production_lot_repo
from src.modules.fulfillment.application.services.scheduling_context import SchedulingRepos
from src.modules.fulfillment.application.use_cases.external_work.get_external_work import (
    GetExternalWork,
)
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)


def get_external_work_use_case(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    supplier_repo: ISupplierQueries = Depends(get_supplier_repo),
    settings_repo: IFulfillmentSettingsRepository = Depends(get_fulfillment_settings_repo),
    scheduling_repos: SchedulingRepos = Depends(get_scheduling_repos),
) -> GetExternalWork:
    return GetExternalWork(lot_repo, supplier_repo, settings_repo, scheduling_repos)
