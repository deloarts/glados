"""Use case factories: products and projects."""

from fastapi import Depends

from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_catalogue_settings_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_customer_repo
from src.modules.catalogue.ports.outbound.catalogue_queries import ICustomerQueries
from src.modules.catalogue.ports.outbound.catalogue_settings_repository import (
    ICatalogueSettingsRepository,
)
from src.modules.platform.adapters.inbound.api.deps.bindings import get_schedule_recompute
from src.modules.platform.adapters.inbound.api.deps.database import get_transactional_event_bus
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.adapters.inbound.api.deps.repositories import get_user_repo
from src.modules.platform.application.services.schedule_recompute_port import ScheduleRecompute
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.repositories.user_repository import IUserRepository
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.adapters.inbound.api.deps.bindings import get_product_work
from src.modules.workspace.adapters.inbound.api.deps.bindings import get_project_work
from src.modules.workspace.adapters.inbound.api.deps.bindings import get_project_work_propagation
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_plc_environment_repo
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_product_repo
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_project_repo
from src.modules.workspace.application.services.project_actions import ProjectActions
from src.modules.workspace.application.use_cases.product.archive_product import ArchiveProduct
from src.modules.workspace.application.use_cases.product.create_product import CreateProduct
from src.modules.workspace.application.use_cases.product.get_product import GetMyProducts
from src.modules.workspace.application.use_cases.product.get_product import GetProduct
from src.modules.workspace.application.use_cases.product.get_product import GetProductByNumber
from src.modules.workspace.application.use_cases.product.get_product import GetProducts
from src.modules.workspace.application.use_cases.product.get_product_summary import (
    GetProductSummary,
)
from src.modules.workspace.application.use_cases.product.restore_product import RestoreProduct
from src.modules.workspace.application.use_cases.product.update_product import UpdateProduct
from src.modules.workspace.application.use_cases.project.create_project import CreateProject
from src.modules.workspace.application.use_cases.project.delete_project import DeleteProject
from src.modules.workspace.application.use_cases.project.get_project import GetMyProjects
from src.modules.workspace.application.use_cases.project.get_project import GetProject
from src.modules.workspace.application.use_cases.project.get_project import GetProjectByNumber
from src.modules.workspace.application.use_cases.project.get_project import GetProjects
from src.modules.workspace.application.use_cases.project.get_project import GetProjectsByProductId
from src.modules.workspace.application.use_cases.project.get_project_summary import (
    GetProjectSummary,
)
from src.modules.workspace.application.use_cases.project.update_project import UpdateProject
from src.modules.workspace.ports.outbound.project_work_port import IProductWork
from src.modules.workspace.ports.outbound.project_work_port import IProjectWork
from src.modules.workspace.ports.outbound.project_work_port import IProjectWorkPropagation
from src.modules.workspace.ports.outbound.repositories.plc_environment_repository import (
    IPlcEnvironmentRepository,
)
from src.modules.workspace.ports.outbound.repositories.product_repository import IProductRepository
from src.modules.workspace.ports.outbound.repositories.project_repository import IProjectRepository


def get_create_product_use_case(
    product_repo: IProductRepository = Depends(get_product_repo),
    user_repo: IUserRepository = Depends(get_user_repo),
    customer_repo: ICustomerQueries | None = Depends(get_customer_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    settings_repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    environment_repo: IPlcEnvironmentRepository = Depends(get_plc_environment_repo),
) -> CreateProduct:
    return CreateProduct(
        product_repo=product_repo,
        user_repo=user_repo,
        customer_repo=customer_repo,
        event_bus=event_bus,
        settings_repo=settings_repo,
        uow=uow,
        environment_repo=environment_repo,
    )


def get_update_product_use_case(
    product_repo: IProductRepository = Depends(get_product_repo),
    user_repo: IUserRepository = Depends(get_user_repo),
    customer_repo: ICustomerQueries | None = Depends(get_customer_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    settings_repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    environment_repo: IPlcEnvironmentRepository = Depends(get_plc_environment_repo),
) -> UpdateProduct:
    return UpdateProduct(
        product_repo=product_repo,
        user_repo=user_repo,
        customer_repo=customer_repo,
        event_bus=event_bus,
        settings_repo=settings_repo,
        uow=uow,
        environment_repo=environment_repo,
    )


def get_archive_product_use_case(
    product_repo: IProductRepository = Depends(get_product_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> ArchiveProduct:
    return ArchiveProduct(product_repo=product_repo, uow=uow)


def get_restore_product_use_case(
    product_repo: IProductRepository = Depends(get_product_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> RestoreProduct:
    return RestoreProduct(product_repo=product_repo, uow=uow)


def get_product_use_case(
    product_repo: IProductRepository = Depends(get_product_repo),
) -> GetProduct:
    return GetProduct(product_repo=product_repo)


def get_product_summary_use_case(
    product_repo: IProductRepository = Depends(get_product_repo),
    order_repo: IProductWork = Depends(get_product_work),
) -> GetProductSummary:
    return GetProductSummary(product_repo=product_repo, order_repo=order_repo)


def get_products_use_case(
    product_repo: IProductRepository = Depends(get_product_repo),
) -> GetProducts:
    return GetProducts(product_repo=product_repo)


def get_product_by_number_use_case(
    product_repo: IProductRepository = Depends(get_product_repo),
) -> GetProductByNumber:
    return GetProductByNumber(product_repo=product_repo)


def get_my_products_use_case(
    product_repo: IProductRepository = Depends(get_product_repo),
) -> GetMyProducts:
    return GetMyProducts(product_repo=product_repo)


def get_create_project_use_case(
    project_repo: IProjectRepository = Depends(get_project_repo),
    user_repo: IUserRepository = Depends(get_user_repo),
    product_repo: IProductRepository = Depends(get_product_repo),
    customer_repo: ICustomerQueries | None = Depends(get_customer_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    settings_repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> CreateProject:
    return CreateProject(
        project_repo=project_repo,
        user_repo=user_repo,
        product_repo=product_repo,
        customer_repo=customer_repo,
        event_bus=event_bus,
        settings_repo=settings_repo,
        uow=uow,
    )


def get_project_actions(work: IProjectWork = Depends(get_project_work)) -> ProjectActions:
    """Fills the status moves and live work counts of the project results."""
    return ProjectActions(work)


def get_update_project_use_case(
    project_repo: IProjectRepository = Depends(get_project_repo),
    user_repo: IUserRepository = Depends(get_user_repo),
    product_repo: IProductRepository = Depends(get_product_repo),
    customer_repo: ICustomerQueries | None = Depends(get_customer_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    settings_repo: ICatalogueSettingsRepository = Depends(get_catalogue_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    work: IProjectWork = Depends(get_project_work),
    propagation: IProjectWorkPropagation = Depends(get_project_work_propagation),
    recompute_schedule: ScheduleRecompute = Depends(get_schedule_recompute),
) -> UpdateProject:
    return UpdateProject(
        project_repo=project_repo,
        user_repo=user_repo,
        product_repo=product_repo,
        customer_repo=customer_repo,
        event_bus=event_bus,
        settings_repo=settings_repo,
        uow=uow,
        work=work,
        propagation=propagation,
        recompute_schedule=recompute_schedule,
    )


def get_delete_project_use_case(
    project_repo: IProjectRepository = Depends(get_project_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    work: IProjectWork = Depends(get_project_work),
) -> DeleteProject:
    return DeleteProject(
        project_repo=project_repo,
        event_bus=event_bus,
        uow=uow,
        work=work,
    )


def get_project_use_case(
    project_repo: IProjectRepository = Depends(get_project_repo),
) -> GetProject:
    return GetProject(project_repo=project_repo)


def get_project_summary_use_case(
    project_repo: IProjectRepository = Depends(get_project_repo),
    work: IProjectWork = Depends(get_project_work),
) -> GetProjectSummary:
    return GetProjectSummary(project_repo=project_repo, work=work)


def get_projects_use_case(
    project_repo: IProjectRepository = Depends(get_project_repo),
) -> GetProjects:
    return GetProjects(project_repo=project_repo)


def get_project_by_number_use_case(
    project_repo: IProjectRepository = Depends(get_project_repo),
) -> GetProjectByNumber:
    return GetProjectByNumber(project_repo=project_repo)


def get_projects_by_product_id_use_case(
    project_repo: IProjectRepository = Depends(get_project_repo),
) -> GetProjectsByProductId:
    return GetProjectsByProductId(project_repo=project_repo)


def get_my_projects_use_case(
    project_repo: IProjectRepository = Depends(get_project_repo),
) -> GetMyProjects:
    return GetMyProjects(project_repo=project_repo)
