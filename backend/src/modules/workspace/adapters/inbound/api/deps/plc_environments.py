"""Use case factories: PLC environments."""

from fastapi import Depends

from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_catalogue_settings_repo
from src.modules.catalogue.ports.outbound.catalogue_settings_repository import (
    ICatalogueSettingsRepository,
)
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_plc_environment_repo
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_plc_manual_tag_repo
from src.modules.workspace.adapters.inbound.api.deps.repositories import (
    get_product_device_kind_repo,
)
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_product_device_repo
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_product_repo
from src.modules.workspace.application.use_cases.plc_environment.environments import (
    CreatePlcEnvironment,
)
from src.modules.workspace.application.use_cases.plc_environment.environments import (
    GetPlcEnvironments,
)
from src.modules.workspace.application.use_cases.plc_environment.environments import (
    GetPlcEnvironmentTemplate,
)
from src.modules.workspace.application.use_cases.plc_environment.environments import (
    SetPlcEnvironmentArchived,
)
from src.modules.workspace.application.use_cases.plc_environment.environments import (
    UpdatePlcEnvironment,
)
from src.modules.workspace.application.use_cases.plc_environment.tags import CreateManualPlcTag
from src.modules.workspace.application.use_cases.plc_environment.tags import DeleteManualPlcTag
from src.modules.workspace.application.use_cases.plc_environment.tags import GetProductPlcTags
from src.modules.workspace.application.use_cases.plc_environment.tags import SetSignalTagName
from src.modules.workspace.application.use_cases.plc_environment.tags import UpdateManualPlcTag
from src.modules.workspace.ports.outbound.repositories.plc_environment_repository import (
    IPlcEnvironmentRepository,
)
from src.modules.workspace.ports.outbound.repositories.plc_manual_tag_repository import (
    IPlcManualTagRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_device_repository import (
    IProductDeviceRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_device_resource_repository import (
    IProductDeviceKindRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_repository import IProductRepository


def get_plc_environments_use_case(
    repo: IPlcEnvironmentRepository = Depends(get_plc_environment_repo),
) -> GetPlcEnvironments:
    return GetPlcEnvironments(repo)


def get_plc_environment_template_use_case() -> GetPlcEnvironmentTemplate:
    return GetPlcEnvironmentTemplate()


def get_create_plc_environment_use_case(
    repo: IPlcEnvironmentRepository = Depends(get_plc_environment_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> CreatePlcEnvironment:
    return CreatePlcEnvironment(repo, uow=uow)


def get_update_plc_environment_use_case(
    repo: IPlcEnvironmentRepository = Depends(get_plc_environment_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdatePlcEnvironment:
    return UpdatePlcEnvironment(repo, uow=uow)


def get_set_plc_environment_archived_use_case(
    repo: IPlcEnvironmentRepository = Depends(get_plc_environment_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> SetPlcEnvironmentArchived:
    return SetPlcEnvironmentArchived(repo, uow=uow)


def get_product_plc_tags_use_case(
    product_repo: IProductRepository = Depends(get_product_repo),
    device_repo: IProductDeviceRepository = Depends(get_product_device_repo),
    kind_repo: IProductDeviceKindRepository = Depends(get_product_device_kind_repo),
    environment_repo: IPlcEnvironmentRepository = Depends(get_plc_environment_repo),
    manual_repo: IPlcManualTagRepository = Depends(get_plc_manual_tag_repo),
    settings_repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
) -> GetProductPlcTags:
    return GetProductPlcTags(
        product_repo, device_repo, kind_repo, environment_repo, manual_repo, settings_repo
    )


def get_create_manual_plc_tag_use_case(
    product_repo: IProductRepository = Depends(get_product_repo),
    manual_repo: IPlcManualTagRepository = Depends(get_plc_manual_tag_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> CreateManualPlcTag:
    return CreateManualPlcTag(product_repo, manual_repo, uow=uow)


def get_update_manual_plc_tag_use_case(
    product_repo: IProductRepository = Depends(get_product_repo),
    manual_repo: IPlcManualTagRepository = Depends(get_plc_manual_tag_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UpdateManualPlcTag:
    return UpdateManualPlcTag(product_repo, manual_repo, uow=uow)


def get_delete_manual_plc_tag_use_case(
    product_repo: IProductRepository = Depends(get_product_repo),
    manual_repo: IPlcManualTagRepository = Depends(get_plc_manual_tag_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> DeleteManualPlcTag:
    return DeleteManualPlcTag(product_repo, manual_repo, uow=uow)


def get_set_signal_tag_name_use_case(
    product_repo: IProductRepository = Depends(get_product_repo),
    device_repo: IProductDeviceRepository = Depends(get_product_device_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> SetSignalTagName:
    return SetSignalTagName(product_repo, device_repo, uow=uow)
