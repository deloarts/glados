"""Use-case factories of the quote request (RFQ) routes. The award reuses the
order and lot assignment use cases of the same request, so it shares their
session, unit of work, lock plan and lifecycle reconciler.
"""

from fastapi import Depends

from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_bought_item_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_source_item_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_supplier_repo
from src.modules.catalogue.ports.outbound.catalogue_queries import IBoughtItemQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import ISourceItemQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import ISupplierQueries
from src.modules.fulfillment.adapters.inbound.api.deps.lifecycle import get_lifecycle_reconciler
from src.modules.fulfillment.adapters.inbound.api.deps.lots import (
    get_assign_external_position_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.orders import get_create_order_item_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.orders import get_create_order_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_recompute_machine_schedule_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_allocation_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_demand_item_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_fulfillment_settings_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_order_item_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_order_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_production_lot_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_quote_request_file_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_quote_request_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_quote_request_supplier_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_source_item_allocation_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_source_item_demand_repo,
)
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases.order.create_order import CreateOrder
from src.modules.fulfillment.application.use_cases.order.create_order_item import CreateOrderItem
from src.modules.fulfillment.application.use_cases.production_lot.assign_external_position import (
    AssignExternalPosition,
)
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.application.use_cases.quote_request._lines import LineRepositories
from src.modules.fulfillment.application.use_cases.quote_request.award_quote_request import (
    AwardQuoteRequest,
)
from src.modules.fulfillment.application.use_cases.quote_request.award_quote_request import (
    AwardRepositories,
)
from src.modules.fulfillment.application.use_cases.quote_request.edit_quote_request import (
    AddQuoteRequestLines,
)
from src.modules.fulfillment.application.use_cases.quote_request.edit_quote_request import (
    AddQuoteRequestSuppliers,
)
from src.modules.fulfillment.application.use_cases.quote_request.edit_quote_request import (
    CreateQuoteRequest,
)
from src.modules.fulfillment.application.use_cases.quote_request.edit_quote_request import (
    DropQuoteRequestLine,
)
from src.modules.fulfillment.application.use_cases.quote_request.edit_quote_request import (
    EndQuoteRequest,
)
from src.modules.fulfillment.application.use_cases.quote_request.edit_quote_request import (
    MarkQuoteRequestSupplierSent,
)
from src.modules.fulfillment.application.use_cases.quote_request.edit_quote_request import (
    RemoveQuoteRequestLine,
)
from src.modules.fulfillment.application.use_cases.quote_request.edit_quote_request import (
    RemoveQuoteRequestSupplier,
)
from src.modules.fulfillment.application.use_cases.quote_request.edit_quote_request import (
    ReopenQuoteRequest,
)
from src.modules.fulfillment.application.use_cases.quote_request.edit_quote_request import SaveOffer
from src.modules.fulfillment.application.use_cases.quote_request.edit_quote_request import (
    SubstituteQuoteRequestLine,
)
from src.modules.fulfillment.application.use_cases.quote_request.edit_quote_request import (
    UpdateQuoteRequest,
)
from src.modules.fulfillment.application.use_cases.quote_request.edit_quote_request import (
    UpdateQuoteRequestLine,
)
from src.modules.fulfillment.application.use_cases.quote_request.get_quote_requests import (
    GetOpenQuoteRequestLinks,
)
from src.modules.fulfillment.application.use_cases.quote_request.get_quote_requests import (
    GetQuoteRequests,
)
from src.modules.fulfillment.application.use_cases.quote_request.offer_files import DeleteOfferFile
from src.modules.fulfillment.application.use_cases.quote_request.offer_files import (
    DownloadOfferFile,
)
from src.modules.fulfillment.application.use_cases.quote_request.offer_files import GetOfferFiles
from src.modules.fulfillment.application.use_cases.quote_request.offer_files import UploadOfferFile
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemDemandItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.quote_request_file_repository import (
    IQuoteRequestFileRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.quote_request_file_repository import (
    IQuoteRequestSupplierRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.quote_request_repository import (
    IQuoteRequestRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemDemandRepository,
)
from src.modules.platform.adapters.inbound.api.deps.database import get_transactional_event_bus
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.adapters.inbound.api.deps.services import get_optional_storage_adapter
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_project_repo
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries


def get_line_repositories(
    bought_item_repo: IBoughtItemQueries = Depends(get_bought_item_repo),
    source_item_repo: ISourceItemQueries = Depends(get_source_item_repo),
    bought_demand_repo: IBoughtItemDemandItemRepository = Depends(get_demand_item_repo),
    source_demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    project_repo: IProjectQueries = Depends(get_project_repo),
) -> LineRepositories:
    return LineRepositories(
        bought_items=bought_item_repo,
        source_items=source_item_repo,
        bought_demands=bought_demand_repo,
        source_demands=source_demand_repo,
        lots=lot_repo,
        projects=project_repo,
    )


def get_quote_requests_use_case(
    request_repo: IQuoteRequestRepository = Depends(get_quote_request_repo),
) -> GetQuoteRequests:
    return GetQuoteRequests(request_repo)


def get_open_quote_request_links_use_case(
    request_repo: IQuoteRequestRepository = Depends(get_quote_request_repo),
) -> GetOpenQuoteRequestLinks:
    return GetOpenQuoteRequestLinks(request_repo)


def get_create_quote_request_use_case(
    request_repo: IQuoteRequestRepository = Depends(get_quote_request_repo),
    line_repos: LineRepositories = Depends(get_line_repositories),
    supplier_repo: ISupplierQueries = Depends(get_supplier_repo),
    admin_settings_repo: IFulfillmentSettingsRepository = Depends(get_fulfillment_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> CreateQuoteRequest:
    return CreateQuoteRequest(
        request_repo, line_repos, supplier_repo, admin_settings_repo, uow=uow, reconciler=reconciler
    )


def get_add_quote_request_lines_use_case(
    request_repo: IQuoteRequestRepository = Depends(get_quote_request_repo),
    line_repos: LineRepositories = Depends(get_line_repositories),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> AddQuoteRequestLines:
    return AddQuoteRequestLines(request_repo, line_repos, uow=uow, reconciler=reconciler)


def get_update_quote_request_use_case(
    request_repo: IQuoteRequestRepository = Depends(get_quote_request_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> UpdateQuoteRequest:
    return UpdateQuoteRequest(request_repo, uow=uow, reconciler=reconciler)


def get_update_quote_request_line_use_case(
    request_repo: IQuoteRequestRepository = Depends(get_quote_request_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> UpdateQuoteRequestLine:
    return UpdateQuoteRequestLine(request_repo, uow=uow, reconciler=reconciler)


def get_remove_quote_request_line_use_case(
    request_repo: IQuoteRequestRepository = Depends(get_quote_request_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> RemoveQuoteRequestLine:
    return RemoveQuoteRequestLine(request_repo, uow=uow, reconciler=reconciler)


def get_drop_quote_request_line_use_case(
    request_repo: IQuoteRequestRepository = Depends(get_quote_request_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    project_repo: IProjectQueries = Depends(get_project_repo),
) -> DropQuoteRequestLine:
    return DropQuoteRequestLine(
        request_repo, uow=uow, reconciler=reconciler, project_repo=project_repo
    )


def get_substitute_quote_request_line_use_case(
    request_repo: IQuoteRequestRepository = Depends(get_quote_request_repo),
    line_repos: LineRepositories = Depends(get_line_repositories),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> SubstituteQuoteRequestLine:
    return SubstituteQuoteRequestLine(request_repo, line_repos, uow=uow, reconciler=reconciler)


def get_add_quote_request_suppliers_use_case(
    request_repo: IQuoteRequestRepository = Depends(get_quote_request_repo),
    supplier_repo: ISupplierQueries = Depends(get_supplier_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> AddQuoteRequestSuppliers:
    return AddQuoteRequestSuppliers(request_repo, supplier_repo, uow=uow, reconciler=reconciler)


def get_remove_quote_request_supplier_use_case(
    request_repo: IQuoteRequestRepository = Depends(get_quote_request_repo),
    file_repo: IQuoteRequestFileRepository = Depends(get_quote_request_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> RemoveQuoteRequestSupplier:
    return RemoveQuoteRequestSupplier(
        request_repo, file_repo, storage, uow=uow, reconciler=reconciler
    )


def get_offer_files_use_case(
    row_repo: IQuoteRequestSupplierRepository = Depends(get_quote_request_supplier_repo),
    file_repo: IQuoteRequestFileRepository = Depends(get_quote_request_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
) -> GetOfferFiles:
    return GetOfferFiles(row_repo, file_repo, storage)


def get_upload_offer_file_use_case(
    row_repo: IQuoteRequestSupplierRepository = Depends(get_quote_request_supplier_repo),
    file_repo: IQuoteRequestFileRepository = Depends(get_quote_request_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UploadOfferFile:
    return UploadOfferFile(row_repo, file_repo, storage, uow=uow)


def get_delete_offer_file_use_case(
    file_repo: IQuoteRequestFileRepository = Depends(get_quote_request_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> DeleteOfferFile:
    return DeleteOfferFile(file_repo, storage, uow=uow)


def get_download_offer_file_use_case(
    file_repo: IQuoteRequestFileRepository = Depends(get_quote_request_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> DownloadOfferFile:
    return DownloadOfferFile(file_repo, storage, uow=uow)


def get_mark_quote_request_supplier_sent_use_case(
    request_repo: IQuoteRequestRepository = Depends(get_quote_request_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> MarkQuoteRequestSupplierSent:
    return MarkQuoteRequestSupplierSent(request_repo, uow=uow, reconciler=reconciler)


def get_save_offer_use_case(
    request_repo: IQuoteRequestRepository = Depends(get_quote_request_repo),
    line_repos: LineRepositories = Depends(get_line_repositories),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> SaveOffer:
    return SaveOffer(request_repo, line_repos, uow=uow, reconciler=reconciler)


def get_end_quote_request_use_case(
    request_repo: IQuoteRequestRepository = Depends(get_quote_request_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> EndQuoteRequest:
    return EndQuoteRequest(request_repo, uow=uow, reconciler=reconciler)


def get_reopen_quote_request_use_case(
    request_repo: IQuoteRequestRepository = Depends(get_quote_request_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> ReopenQuoteRequest:
    return ReopenQuoteRequest(request_repo, uow=uow, reconciler=reconciler)


def get_award_quote_request_use_case(
    request_repo: IQuoteRequestRepository = Depends(get_quote_request_repo),
    order_repo: IOrderRepository = Depends(get_order_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    project_repo: IProjectQueries = Depends(get_project_repo),
    bought_demand_repo: IBoughtItemDemandItemRepository = Depends(get_demand_item_repo),
    bought_allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
    source_demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
    source_allocation_repo: ISourceItemAllocationRepository = Depends(
        get_source_item_allocation_repo
    ),
    create_order: CreateOrder = Depends(get_create_order_use_case),
    create_order_item: CreateOrderItem = Depends(get_create_order_item_use_case),
    assign_external: AssignExternalPosition = Depends(get_assign_external_position_use_case),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    settings_repo: IFulfillmentSettingsRepository = Depends(get_fulfillment_settings_repo),
) -> AwardQuoteRequest:
    return AwardQuoteRequest(
        AwardRepositories(
            requests=request_repo,
            orders=order_repo,
            order_items=order_item_repo,
            lots=lot_repo,
            projects=project_repo,
            bought_demands=bought_demand_repo,
            bought_allocations=bought_allocation_repo,
            source_demands=source_demand_repo,
            source_allocations=source_allocation_repo,
        ),
        create_order=create_order,
        create_order_item=create_order_item,
        assign_external=assign_external,
        event_bus=event_bus,
        uow=uow,
        reconciler=reconciler,
        recompute_schedule=recompute_schedule,
        settings_repo=settings_repo,
    )
