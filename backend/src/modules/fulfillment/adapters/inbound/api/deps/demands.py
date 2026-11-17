"""Use case factories: demand items (bought/source/made), demand summaries,
batch validation, made-item demand cancelation cascade.
"""

from fastapi import Depends

from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_bought_item_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_made_item_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_supplier_repo
from src.modules.catalogue.ports.outbound.catalogue_queries import IBoughtItemQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import IMadeItemQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import ISupplierQueries
from src.modules.fulfillment.adapters.inbound.api.deps.lifecycle import get_lifecycle_lock_plan
from src.modules.fulfillment.adapters.inbound.api.deps.lifecycle import get_lifecycle_reconciler
from src.modules.fulfillment.adapters.inbound.api.deps.lots import get_cancel_lot_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_recompute_machine_schedule_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_allocation_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_bought_item_demand_bucket_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_demand_item_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_fulfillment_settings_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_made_item_allocation_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_made_item_demand_bucket_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_made_item_demand_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_order_item_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_order_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_production_lot_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_production_order_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_source_item_allocation_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_source_item_demand_bucket_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_source_item_demand_repo,
)
from src.modules.fulfillment.application.services.lifecycle_lock_plan import LockPlan
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases.bought_item_demand.batch_demand_items import (
    CommitBatchDemandRows,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.batch_demand_items import (
    ValidateBatchDemandRows,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.cancel_demand_item import (
    CancelDemandItem,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.create_demand_item import (
    CreateDemandItem,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.delete_demand_item import (
    DeleteDemandItem,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.get_allocations import (
    GetDemandSummary,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.get_allocations import (
    GetDemandSummaryBatch,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.get_demand_items import (
    GetDemandItem,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.get_demand_items import (
    GetDemandItems,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.get_demands_pipeline import (
    GetDemandsPipeline,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.set_demand_item_bucket import (
    SetDemandItemBucket,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.update_demand_item import (
    UpdateDemandItem,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.update_demand_item_status import (
    UpdateDemandItemStatus,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.batch_demand_items import (
    CommitBatchMadeItemDemandRows,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.batch_demand_items import (
    ValidateBatchMadeItemDemandRows,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.cancel_demand import (
    CancelImpactCollector,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.cancel_demand import (
    CancelMadeItemDemand,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.cancel_demand import (
    PreviewCancelMadeItemDemand,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.create_demand_item import (
    CreateDemandItem as CreateMadeItemDemandItem,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.delete_demand_item import (
    DeleteDemandItem as DeleteMadeItemDemandItem,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.get_allocations import (
    GetDemandSummary as GetMadeItemDemandSummary,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.get_allocations import (
    GetDemandSummaryBatch as GetMadeItemDemandSummaryBatch,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.get_demand_items import (
    GetDemandItem as GetMadeItemDemandItem,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.get_demand_items import (
    GetDemandItems as GetMadeItemDemandItems,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.get_demands_pipeline import (
    GetDemandsPipeline as GetMadeItemDemandsPipeline,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.set_demand_item_bucket import (
    SetDemandItemBucket as SetMadeItemDemandItemBucket,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.update_demand_item import (
    UpdateDemandItem as UpdateMadeItemDemandItem,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.update_demand_item_status import (
    UpdateDemandItemStatus as UpdateMadeItemDemandItemStatus,
)
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import CancelLot
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.application.use_cases.source_item_allocation.get_allocations import (
    GetSourceItemDemandSummary,
)
from src.modules.fulfillment.application.use_cases.source_item_allocation.get_allocations import (
    GetSourceItemDemandSummaryBatch,
)
from src.modules.fulfillment.application.use_cases.source_item_demand.cancel_source_item_demand import (
    CancelSourceItemDemand,
)
from src.modules.fulfillment.application.use_cases.source_item_demand.create_source_item_demand import (
    CreateSourceItemDemand,
)
from src.modules.fulfillment.application.use_cases.source_item_demand.get_source_item_demand import (
    GetSourceItemDemand,
)
from src.modules.fulfillment.application.use_cases.source_item_demand.get_source_item_demand import (
    GetSourceItemDemands,
)
from src.modules.fulfillment.application.use_cases.source_item_demand.set_demand_item_bucket import (
    SetDemandItemBucket as SetSourceItemDemandItemBucket,
)
from src.modules.fulfillment.application.use_cases.source_item_demand.update_source_item_demand import (
    UpdateSourceItemDemand,
)
from src.modules.fulfillment.application.use_cases.source_item_demand.update_source_item_demand_status import (
    UpdateSourceItemDemandStatus,
)
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_bucket_repository import (
    IBoughtItemDemandBucketRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemDemandItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_bucket_repository import (
    IMadeItemDemandBucketRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemDemandItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_bucket_repository import (
    ISourceItemDemandBucketRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemDemandRepository,
)
from src.modules.platform.adapters.inbound.api.deps.database import get_transactional_event_bus
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.ports.outbound.event_bus_port import IEventBus
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_project_repo
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries


def get_create_source_item_demand_use_case(
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
    project_repo: IProjectQueries = Depends(get_project_repo),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> CreateSourceItemDemand:
    return CreateSourceItemDemand(
        lot_repo=lot_repo,
        demand_repo=demand_repo,
        project_repo=project_repo,
        recompute_schedule=recompute_schedule,
        uow=uow,
        reconciler=reconciler,
    )


def get_update_source_item_demand_use_case(
    demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    allocation_repo: ISourceItemAllocationRepository = Depends(get_source_item_allocation_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> UpdateSourceItemDemand:
    return UpdateSourceItemDemand(
        demand_repo=demand_repo,
        lot_repo=lot_repo,
        allocation_repo=allocation_repo,
        uow=uow,
        reconciler=reconciler,
    )


def get_cancel_source_item_demand_use_case(
    demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    allocation_repo: ISourceItemAllocationRepository = Depends(get_source_item_allocation_repo),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    cancel_lot: CancelLot = Depends(get_cancel_lot_use_case),
) -> CancelSourceItemDemand:
    return CancelSourceItemDemand(
        demand_repo=demand_repo,
        lot_repo=lot_repo,
        allocation_repo=allocation_repo,
        recompute_schedule=recompute_schedule,
        uow=uow,
        reconciler=reconciler,
        cancel_lot=cancel_lot,
    )


def get_update_source_item_demand_status_use_case(
    demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
    cancel_use_case: CancelSourceItemDemand = Depends(get_cancel_source_item_demand_use_case),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    allocation_repo: ISourceItemAllocationRepository = Depends(get_source_item_allocation_repo),
    bought_allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
) -> UpdateSourceItemDemandStatus:
    return UpdateSourceItemDemandStatus(
        demand_repo=demand_repo,
        cancel_use_case=cancel_use_case,
        uow=uow,
        reconciler=reconciler,
        allocation_repo=allocation_repo,
        bought_allocation_repo=bought_allocation_repo,
        order_item_repo=order_item_repo,
    )


def get_set_source_item_demand_item_bucket_use_case(
    demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
    bucket_repo: ISourceItemDemandBucketRepository = Depends(get_source_item_demand_bucket_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> SetSourceItemDemandItemBucket:
    return SetSourceItemDemandItemBucket(demand_repo=demand_repo, bucket_repo=bucket_repo, uow=uow)


def get_source_item_demand_use_case(
    demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
) -> GetSourceItemDemand:
    return GetSourceItemDemand(demand_repo=demand_repo)


def get_source_item_demands_use_case(
    demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
) -> GetSourceItemDemands:
    return GetSourceItemDemands(demand_repo=demand_repo)


def get_create_demand_item_use_case(
    demand_repo: IBoughtItemDemandItemRepository = Depends(get_demand_item_repo),
    bought_item_repo: IBoughtItemQueries = Depends(get_bought_item_repo),
    project_repo: IProjectQueries = Depends(get_project_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> CreateDemandItem:
    return CreateDemandItem(
        demand_repo=demand_repo,
        item_repo=bought_item_repo,
        project_repo=project_repo,
        event_bus=event_bus,
        uow=uow,
        reconciler=reconciler,
    )


def get_update_demand_item_use_case(
    demand_repo: IBoughtItemDemandItemRepository = Depends(get_demand_item_repo),
    allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> UpdateDemandItem:
    return UpdateDemandItem(
        demand_repo=demand_repo,
        uow=uow,
        reconciler=reconciler,
        allocation_repo=allocation_repo,
    )


def get_cancel_demand_item_use_case(
    demand_repo: IBoughtItemDemandItemRepository = Depends(get_demand_item_repo),
    allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> CancelDemandItem:
    return CancelDemandItem(
        demand_repo=demand_repo, allocation_repo=allocation_repo, uow=uow, reconciler=reconciler
    )


def get_update_demand_item_status_use_case(
    demand_repo: IBoughtItemDemandItemRepository = Depends(get_demand_item_repo),
    cancel_use_case: CancelDemandItem = Depends(get_cancel_demand_item_use_case),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
    source_allocation_repo: ISourceItemAllocationRepository = Depends(
        get_source_item_allocation_repo
    ),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
) -> UpdateDemandItemStatus:
    return UpdateDemandItemStatus(
        demand_repo=demand_repo,
        cancel_use_case=cancel_use_case,
        uow=uow,
        reconciler=reconciler,
        allocation_repo=allocation_repo,
        source_allocation_repo=source_allocation_repo,
        order_item_repo=order_item_repo,
    )


def get_demand_item_use_case(
    demand_repo: IBoughtItemDemandItemRepository = Depends(get_demand_item_repo),
) -> GetDemandItem:
    return GetDemandItem(demand_repo=demand_repo)


def get_demand_items_use_case(
    demand_repo: IBoughtItemDemandItemRepository = Depends(get_demand_item_repo),
) -> GetDemandItems:
    return GetDemandItems(demand_repo=demand_repo)


def get_demands_pipeline_use_case(
    demand_repo: IBoughtItemDemandItemRepository = Depends(get_demand_item_repo),
    allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    order_repo: IOrderRepository = Depends(get_order_repo),
) -> GetDemandsPipeline:
    return GetDemandsPipeline(
        demand_repo=demand_repo,
        allocation_repo=allocation_repo,
        order_item_repo=order_item_repo,
        order_repo=order_repo,
    )


def get_delete_demand_item_use_case(
    demand_repo: IBoughtItemDemandItemRepository = Depends(get_demand_item_repo),
    allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    lock_plan: LockPlan = Depends(get_lifecycle_lock_plan),
) -> DeleteDemandItem:
    return DeleteDemandItem(
        demand_repo=demand_repo, allocation_repo=allocation_repo, uow=uow, lock_plan=lock_plan
    )


def get_set_demand_item_bucket_use_case(
    demand_repo: IBoughtItemDemandItemRepository = Depends(get_demand_item_repo),
    bucket_repo: IBoughtItemDemandBucketRepository = Depends(get_bought_item_demand_bucket_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> SetDemandItemBucket:
    return SetDemandItemBucket(demand_repo=demand_repo, bucket_repo=bucket_repo, uow=uow)


def get_validate_batch_demands_use_case(
    bought_item_repo: IBoughtItemQueries = Depends(get_bought_item_repo),
    project_repo: IProjectQueries = Depends(get_project_repo),
    supplier_repo: ISupplierQueries = Depends(get_supplier_repo),
    settings_repo: IFulfillmentSettingsRepository = Depends(get_fulfillment_settings_repo),
) -> ValidateBatchDemandRows:
    return ValidateBatchDemandRows(
        item_repo=bought_item_repo,
        project_repo=project_repo,
        supplier_repo=supplier_repo,
        settings_repo=settings_repo,
    )


def get_commit_batch_demands_use_case(
    demand_repo: IBoughtItemDemandItemRepository = Depends(get_demand_item_repo),
    bought_item_repo: IBoughtItemQueries = Depends(get_bought_item_repo),
    project_repo: IProjectQueries = Depends(get_project_repo),
    supplier_repo: ISupplierQueries = Depends(get_supplier_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    settings_repo: IFulfillmentSettingsRepository = Depends(get_fulfillment_settings_repo),
) -> CommitBatchDemandRows:
    return CommitBatchDemandRows(
        demand_repo=demand_repo,
        item_repo=bought_item_repo,
        project_repo=project_repo,
        supplier_repo=supplier_repo,
        uow=uow,
        event_bus=event_bus,
        reconciler=reconciler,
        settings_repo=settings_repo,
    )


def get_demand_summary_use_case(
    demand_repo: IBoughtItemDemandItemRepository = Depends(get_demand_item_repo),
    allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    order_repo: IOrderRepository = Depends(get_order_repo),
    bought_item_repo: IBoughtItemQueries = Depends(get_bought_item_repo),
) -> GetDemandSummary:
    return GetDemandSummary(
        demand_repo=demand_repo,
        allocation_repo=allocation_repo,
        order_item_repo=order_item_repo,
        order_repo=order_repo,
        catalogue_repo=bought_item_repo,
    )


def get_demand_summary_batch_use_case(
    demand_repo: IBoughtItemDemandItemRepository = Depends(get_demand_item_repo),
    allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    order_repo: IOrderRepository = Depends(get_order_repo),
    bought_item_repo: IBoughtItemQueries = Depends(get_bought_item_repo),
) -> GetDemandSummaryBatch:
    return GetDemandSummaryBatch(
        demand_repo=demand_repo,
        allocation_repo=allocation_repo,
        order_item_repo=order_item_repo,
        order_repo=order_repo,
        catalogue_repo=bought_item_repo,
    )


def get_source_item_demand_summary_use_case(
    demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
    allocation_repo: ISourceItemAllocationRepository = Depends(get_source_item_allocation_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    order_repo: IOrderRepository = Depends(get_order_repo),
    bought_allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
) -> GetSourceItemDemandSummary:
    return GetSourceItemDemandSummary(
        demand_repo=demand_repo,
        allocation_repo=allocation_repo,
        order_item_repo=order_item_repo,
        order_repo=order_repo,
        bought_allocation_repo=bought_allocation_repo,
    )


def get_source_item_demand_summary_batch_use_case(
    demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
    allocation_repo: ISourceItemAllocationRepository = Depends(get_source_item_allocation_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    order_repo: IOrderRepository = Depends(get_order_repo),
    bought_allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
) -> GetSourceItemDemandSummaryBatch:
    return GetSourceItemDemandSummaryBatch(
        demand_repo=demand_repo,
        allocation_repo=allocation_repo,
        order_item_repo=order_item_repo,
        order_repo=order_repo,
        bought_allocation_repo=bought_allocation_repo,
    )


def get_create_made_item_demand_use_case(
    demand_repo: IMadeItemDemandItemRepository = Depends(get_made_item_demand_repo),
    made_item_repo: IMadeItemQueries = Depends(get_made_item_repo),
    project_repo: IProjectQueries = Depends(get_project_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> CreateMadeItemDemandItem:
    return CreateMadeItemDemandItem(
        demand_repo=demand_repo,
        made_item_repo=made_item_repo,
        project_repo=project_repo,
        event_bus=event_bus,
        uow=uow,
        reconciler=reconciler,
    )


def get_validate_batch_made_item_demands_use_case(
    made_item_repo: IMadeItemQueries = Depends(get_made_item_repo),
    project_repo: IProjectQueries = Depends(get_project_repo),
    settings_repo: IFulfillmentSettingsRepository = Depends(get_fulfillment_settings_repo),
) -> ValidateBatchMadeItemDemandRows:
    return ValidateBatchMadeItemDemandRows(
        item_repo=made_item_repo,
        project_repo=project_repo,
        settings_repo=settings_repo,
    )


def get_commit_batch_made_item_demands_use_case(
    demand_repo: IMadeItemDemandItemRepository = Depends(get_made_item_demand_repo),
    made_item_repo: IMadeItemQueries = Depends(get_made_item_repo),
    project_repo: IProjectQueries = Depends(get_project_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    settings_repo: IFulfillmentSettingsRepository = Depends(get_fulfillment_settings_repo),
) -> CommitBatchMadeItemDemandRows:
    return CommitBatchMadeItemDemandRows(
        demand_repo=demand_repo,
        item_repo=made_item_repo,
        project_repo=project_repo,
        uow=uow,
        event_bus=event_bus,
        reconciler=reconciler,
        settings_repo=settings_repo,
    )


def get_update_made_item_demand_use_case(
    demand_repo: IMadeItemDemandItemRepository = Depends(get_made_item_demand_repo),
    made_item_repo: IMadeItemQueries = Depends(get_made_item_repo),
    allocation_repo: IMadeItemAllocationRepository = Depends(get_made_item_allocation_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> UpdateMadeItemDemandItem:
    return UpdateMadeItemDemandItem(
        demand_repo=demand_repo,
        made_item_repo=made_item_repo,
        uow=uow,
        reconciler=reconciler,
        allocation_repo=allocation_repo,
    )


def get_made_item_demand_use_case(
    demand_repo: IMadeItemDemandItemRepository = Depends(get_made_item_demand_repo),
) -> GetMadeItemDemandItem:
    return GetMadeItemDemandItem(demand_repo=demand_repo)


def get_made_item_demands_use_case(
    demand_repo: IMadeItemDemandItemRepository = Depends(get_made_item_demand_repo),
) -> GetMadeItemDemandItems:
    return GetMadeItemDemandItems(demand_repo=demand_repo)


def get_made_item_demands_pipeline_use_case(
    demand_repo: IMadeItemDemandItemRepository = Depends(get_made_item_demand_repo),
    allocation_repo: IMadeItemAllocationRepository = Depends(get_made_item_allocation_repo),
) -> GetMadeItemDemandsPipeline:
    return GetMadeItemDemandsPipeline(demand_repo=demand_repo, allocation_repo=allocation_repo)


def get_delete_made_item_demand_use_case(
    demand_repo: IMadeItemDemandItemRepository = Depends(get_made_item_demand_repo),
    allocation_repo: IMadeItemAllocationRepository = Depends(get_made_item_allocation_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    lock_plan: LockPlan = Depends(get_lifecycle_lock_plan),
) -> DeleteMadeItemDemandItem:
    return DeleteMadeItemDemandItem(
        demand_repo=demand_repo, allocation_repo=allocation_repo, uow=uow, lock_plan=lock_plan
    )


def get_set_made_item_demand_item_bucket_use_case(
    demand_repo: IMadeItemDemandItemRepository = Depends(get_made_item_demand_repo),
    bucket_repo: IMadeItemDemandBucketRepository = Depends(get_made_item_demand_bucket_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> SetMadeItemDemandItemBucket:
    return SetMadeItemDemandItemBucket(demand_repo=demand_repo, bucket_repo=bucket_repo, uow=uow)


def get_made_item_demand_summary_use_case(
    demand_repo: IMadeItemDemandItemRepository = Depends(get_made_item_demand_repo),
    allocation_repo: IMadeItemAllocationRepository = Depends(get_made_item_allocation_repo),
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
) -> GetMadeItemDemandSummary:
    return GetMadeItemDemandSummary(
        demand_repo=demand_repo, allocation_repo=allocation_repo, lot_repo=lot_repo
    )


def get_made_item_demand_summary_batch_use_case(
    demand_repo: IMadeItemDemandItemRepository = Depends(get_made_item_demand_repo),
    allocation_repo: IMadeItemAllocationRepository = Depends(get_made_item_allocation_repo),
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
) -> GetMadeItemDemandSummaryBatch:
    return GetMadeItemDemandSummaryBatch(
        demand_repo=demand_repo, allocation_repo=allocation_repo, lot_repo=lot_repo
    )


def get_made_item_cancel_impact_collector(
    demand_repo: IMadeItemDemandItemRepository = Depends(get_made_item_demand_repo),
    allocation_repo: IMadeItemAllocationRepository = Depends(get_made_item_allocation_repo),
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    production_order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    order_repo: IOrderRepository = Depends(get_order_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    source_item_demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
    source_item_allocation_repo: ISourceItemAllocationRepository = Depends(
        get_source_item_allocation_repo
    ),
) -> CancelImpactCollector:
    return CancelImpactCollector(
        demand_repo=demand_repo,
        allocation_repo=allocation_repo,
        lot_repo=lot_repo,
        production_order_repo=production_order_repo,
        order_repo=order_repo,
        order_item_repo=order_item_repo,
        source_item_demand_repo=source_item_demand_repo,
        source_item_allocation_repo=source_item_allocation_repo,
    )


def get_preview_cancel_made_item_demand_use_case(
    demand_repo: IMadeItemDemandItemRepository = Depends(get_made_item_demand_repo),
    collector: CancelImpactCollector = Depends(get_made_item_cancel_impact_collector),
) -> PreviewCancelMadeItemDemand:
    return PreviewCancelMadeItemDemand(demand_repo=demand_repo, collector=collector)


def get_cancel_made_item_demand_use_case(
    demand_repo: IMadeItemDemandItemRepository = Depends(get_made_item_demand_repo),
    allocation_repo: IMadeItemAllocationRepository = Depends(get_made_item_allocation_repo),
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    collector: CancelImpactCollector = Depends(get_made_item_cancel_impact_collector),
    cancel_lot: CancelLot = Depends(get_cancel_lot_use_case),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> CancelMadeItemDemand:
    """FastAPI hands this factory and the CancelLot it depends on the same
    per-request reconciler, which the cancel cascade registers its
    production orders with."""
    return CancelMadeItemDemand(
        demand_repo=demand_repo,
        allocation_repo=allocation_repo,
        lot_repo=lot_repo,
        collector=collector,
        cancel_lot=cancel_lot,
        recompute_schedule=recompute_schedule,
        event_bus=event_bus,
        uow=uow,
        reconciler=reconciler,
    )


def get_update_made_item_demand_status_use_case(
    demand_repo: IMadeItemDemandItemRepository = Depends(get_made_item_demand_repo),
    cancel_use_case: CancelMadeItemDemand = Depends(get_cancel_made_item_demand_use_case),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> UpdateMadeItemDemandItemStatus:
    return UpdateMadeItemDemandItemStatus(
        demand_repo=demand_repo,
        cancel_use_case=cancel_use_case,
        uow=uow,
        reconciler=reconciler,
    )
