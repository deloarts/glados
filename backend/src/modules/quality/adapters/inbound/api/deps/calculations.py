"""Use case factories: saved calculations of the engineering tools."""

from fastapi import Depends

from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_fulfillment_settings_repo,
)
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.quality.adapters.inbound.api.deps.controlled_documents import (
    build_controlled_document_deps,
)
from src.modules.quality.adapters.inbound.api.deps.controlled_documents import build_release_dep
from src.modules.quality.adapters.inbound.api.deps.repositories import get_calculation_repo
from src.modules.quality.application.use_cases.calculation.delete_calculation import (
    DeleteCalculation,
)
from src.modules.quality.application.use_cases.calculation.get_calculations import GetCalculation
from src.modules.quality.application.use_cases.calculation.get_calculations import (
    GetCalculationByPublicId,
)
from src.modules.quality.application.use_cases.calculation.get_calculations import (
    GetCalculationRevisions,
)
from src.modules.quality.application.use_cases.calculation.get_calculations import GetCalculations
from src.modules.quality.application.use_cases.calculation.lock_calculation import LockCalculation
from src.modules.quality.application.use_cases.calculation.lock_calculation import UnlockCalculation
from src.modules.quality.application.use_cases.calculation.release_calculation import (
    MarkCalculationInvalid,
)
from src.modules.quality.application.use_cases.calculation.release_calculation import (
    ReleaseCalculation,
)
from src.modules.quality.application.use_cases.calculation.revise_calculation import (
    ReviseCalculation,
)
from src.modules.quality.application.use_cases.calculation.save_calculation import CreateCalculation
from src.modules.quality.application.use_cases.calculation.save_calculation import (
    SetCalculationDevice,
)
from src.modules.quality.application.use_cases.calculation.save_calculation import UpdateCalculation
from src.modules.quality.ports.outbound.repositories.calculation_repository import (
    ICalculationRepository,
)
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_product_device_repo
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_product_repo
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_project_repo
from src.modules.workspace.ports.outbound.workspace_queries import IProductDeviceQueries
from src.modules.workspace.ports.outbound.workspace_queries import IProductQueries
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries

DEPS = build_controlled_document_deps(
    get_calculation_repo,
    get_many_cls=GetCalculations,
    get_one_cls=GetCalculation,
    get_revisions_cls=GetCalculationRevisions,
    get_by_public_id_cls=GetCalculationByPublicId,
    revise_cls=ReviseCalculation,
    mark_invalid_cls=MarkCalculationInvalid,
    delete_cls=DeleteCalculation,
    lock_cls=LockCalculation,
    unlock_cls=UnlockCalculation,
)

get_calculations_use_case = DEPS.get_many
get_calculation_use_case = DEPS.get_one
get_calculation_revisions_use_case = DEPS.get_revisions
get_calculation_by_public_id_use_case = DEPS.get_by_public_id


# Create and update also check the referenced device, so they take the
# device repository the shared factories do not provide.
def get_create_calculation_use_case(
    repo: ICalculationRepository = Depends(get_calculation_repo),
    project_repo: IProjectQueries = Depends(get_project_repo),
    product_repo: IProductQueries = Depends(get_product_repo),
    admin_settings_repo: IFulfillmentSettingsRepository = Depends(get_fulfillment_settings_repo),
    device_repo: IProductDeviceQueries = Depends(get_product_device_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> CreateCalculation:
    return CreateCalculation(
        repo,
        project_repo=project_repo,
        product_repo=product_repo,
        admin_settings_repo=admin_settings_repo,
        device_repo=device_repo,
        uow=uow,
    )


def get_update_calculation_use_case(
    repo: ICalculationRepository = Depends(get_calculation_repo),
    project_repo: IProjectQueries = Depends(get_project_repo),
    product_repo: IProductQueries = Depends(get_product_repo),
    device_repo: IProductDeviceQueries = Depends(get_product_device_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateCalculation:
    return UpdateCalculation(
        repo, project_repo=project_repo, product_repo=product_repo, device_repo=device_repo, uow=uow
    )


def get_set_calculation_device_use_case(
    repo: ICalculationRepository = Depends(get_calculation_repo),
    project_repo: IProjectQueries = Depends(get_project_repo),
    product_repo: IProductQueries = Depends(get_product_repo),
    device_repo: IProductDeviceQueries = Depends(get_product_device_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> SetCalculationDevice:
    return SetCalculationDevice(
        repo, project_repo=project_repo, product_repo=product_repo, device_repo=device_repo, uow=uow
    )


get_revise_calculation_use_case = DEPS.revise
get_release_calculation_use_case = build_release_dep(get_calculation_repo, ReleaseCalculation)
get_mark_calculation_invalid_use_case = DEPS.mark_invalid
get_delete_calculation_use_case = DEPS.delete
get_lock_calculation_use_case = DEPS.lock
get_unlock_calculation_use_case = DEPS.unlock
