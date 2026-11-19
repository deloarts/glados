"""Use case factories: orders, order items, order files, deliveries."""

from fastapi import Depends

from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_bought_item_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_source_item_repo
from src.modules.catalogue.adapters.inbound.api.deps.repositories import get_supplier_repo
from src.modules.catalogue.ports.outbound.catalogue_queries import IBoughtItemQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import ISourceItemQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import ISupplierQueries
from src.modules.fulfillment.adapters.inbound.api.deps.lifecycle import get_lifecycle_lock_plan
from src.modules.fulfillment.adapters.inbound.api.deps.lifecycle import get_lifecycle_reconciler
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_create_lot_for_completion_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_recompute_machine_schedule_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_allocation_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_demand_item_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_fulfillment_settings_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_made_item_allocation_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_made_item_demand_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_order_file_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_order_item_delivery_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_order_item_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_order_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_production_lot_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_production_order_interruption_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_production_order_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_source_item_allocation_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_source_item_demand_repo,
)
from src.modules.fulfillment.application.services.delivery_tolerances import DeliveryTolerances
from src.modules.fulfillment.application.services.lifecycle_lock_plan import LockPlan
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases.order.cancel_order_item import CancelOrderItem
from src.modules.fulfillment.application.use_cases.order.close_order_item_short import (
    CloseOrderItemShort,
)
from src.modules.fulfillment.application.use_cases.order.correct_order_item_delivery import (
    CorrectOrderItemDelivery,
)
from src.modules.fulfillment.application.use_cases.order.create_order import CreateOrder
from src.modules.fulfillment.application.use_cases.order.create_order_item import CreateOrderItem
from src.modules.fulfillment.application.use_cases.order.delete_order_file import DeleteOrderFile
from src.modules.fulfillment.application.use_cases.order.delete_order_item import RemoveOrderItem
from src.modules.fulfillment.application.use_cases.order.download_order_file import (
    DownloadOrderFile,
)
from src.modules.fulfillment.application.use_cases.order.get_order import GetOrders
from src.modules.fulfillment.application.use_cases.order.get_order_files import GetOrderFiles
from src.modules.fulfillment.application.use_cases.order.mark_order_item_ordered import (
    MarkAllOrderItemsOrdered,
)
from src.modules.fulfillment.application.use_cases.order.mark_order_item_ordered import (
    MarkAllOrderItemsRequested,
)
from src.modules.fulfillment.application.use_cases.order.mark_order_item_ordered import (
    MarkOrderItemOrdered,
)
from src.modules.fulfillment.application.use_cases.order.mark_order_item_ordered import (
    MarkOrderItemRequested,
)
from src.modules.fulfillment.application.use_cases.order.mark_order_item_ready_for_pickup import (
    MarkOrderItemReadyForPickup,
)
from src.modules.fulfillment.application.use_cases.order.move_order_item import MoveOrderItem
from src.modules.fulfillment.application.use_cases.order.process_order_item_delivery import (
    DeliverAllOrderItems,
)
from src.modules.fulfillment.application.use_cases.order.process_order_item_delivery import (
    ProcessOrderItemDelivery,
)
from src.modules.fulfillment.application.use_cases.order.reopen_order_item import ReopenOrderItem
from src.modules.fulfillment.application.use_cases.order.set_order_extra_costs import (
    SetOrderExtraCosts,
)
from src.modules.fulfillment.application.use_cases.order.set_order_supplier_order_numbers import (
    SetOrderSupplierOrderNumbers,
)
from src.modules.fulfillment.application.use_cases.order.update_order import CancelOrder
from src.modules.fulfillment.application.use_cases.order.update_order import RequestOrder
from src.modules.fulfillment.application.use_cases.order.update_order import SubmitOrder
from src.modules.fulfillment.application.use_cases.order.update_order import UpdateOrder
from src.modules.fulfillment.application.use_cases.order.update_order_item import UpdateOrderItem
from src.modules.fulfillment.application.use_cases.order.upload_delivery_picture import (
    UploadDeliveryPicture,
)
from src.modules.fulfillment.application.use_cases.order.upload_order_file import UploadOrderFile
from src.modules.fulfillment.application.use_cases.production_lot.create_lot import CreateLot
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.bought_item_demand_repository import (
    IBoughtItemDemandItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.made_item_demand_repository import (
    IMadeItemDemandItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_file_repository import (
    IOrderFileRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemDeliveryRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_interruption_repository import (
    IProductionOrderInterruptionRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
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


def get_order_files_use_case(
    order_repo: IOrderRepository = Depends(get_order_repo),
    file_repo: IOrderFileRepository = Depends(get_order_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
) -> GetOrderFiles:
    return GetOrderFiles(order_repo=order_repo, file_repo=file_repo, storage=storage)


def get_upload_order_file_use_case(
    order_repo: IOrderRepository = Depends(get_order_repo),
    file_repo: IOrderFileRepository = Depends(get_order_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UploadOrderFile:
    return UploadOrderFile(order_repo=order_repo, file_repo=file_repo, storage=storage, uow=uow)


def get_upload_delivery_picture_use_case(
    order_repo: IOrderRepository = Depends(get_order_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    delivery_repo: IOrderItemDeliveryRepository = Depends(get_order_item_delivery_repo),
    file_repo: IOrderFileRepository = Depends(get_order_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> UploadDeliveryPicture:
    return UploadDeliveryPicture(
        order_repo=order_repo,
        order_item_repo=order_item_repo,
        delivery_repo=delivery_repo,
        file_repo=file_repo,
        storage=storage,
        uow=uow,
    )


def get_delete_order_file_use_case(
    file_repo: IOrderFileRepository = Depends(get_order_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> DeleteOrderFile:
    return DeleteOrderFile(file_repo=file_repo, storage=storage, uow=uow)


def get_download_order_file_use_case(
    file_repo: IOrderFileRepository = Depends(get_order_file_repo),
    storage: IStoragePort | None = Depends(get_optional_storage_adapter),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> DownloadOrderFile:
    return DownloadOrderFile(file_repo=file_repo, storage=storage, uow=uow)


def get_create_order_use_case(
    order_repo: IOrderRepository = Depends(get_order_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    admin_settings_repo: IFulfillmentSettingsRepository = Depends(get_fulfillment_settings_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
) -> CreateOrder:
    return CreateOrder(
        order_repo=order_repo,
        event_bus=event_bus,
        admin_settings_repo=admin_settings_repo,
        uow=uow,
    )


def get_update_order_use_case(
    order_repo: IOrderRepository = Depends(get_order_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    supplier_repo: ISupplierQueries = Depends(get_supplier_repo),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    lock_plan: LockPlan = Depends(get_lifecycle_lock_plan),
) -> UpdateOrder:
    return UpdateOrder(
        order_repo=order_repo,
        order_item_repo=order_item_repo,
        supplier_repo=supplier_repo,
        recompute_schedule=recompute_schedule,
        uow=uow,
        lock_plan=lock_plan,
    )


def get_set_order_extra_costs_use_case(
    order_repo: IOrderRepository = Depends(get_order_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    lock_plan: LockPlan = Depends(get_lifecycle_lock_plan),
) -> SetOrderExtraCosts:
    return SetOrderExtraCosts(
        order_repo=order_repo,
        order_item_repo=order_item_repo,
        uow=uow,
        lock_plan=lock_plan,
    )


def get_set_order_supplier_order_numbers_use_case(
    order_repo: IOrderRepository = Depends(get_order_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    lock_plan: LockPlan = Depends(get_lifecycle_lock_plan),
) -> SetOrderSupplierOrderNumbers:
    return SetOrderSupplierOrderNumbers(
        order_repo=order_repo,
        order_item_repo=order_item_repo,
        uow=uow,
        lock_plan=lock_plan,
    )


def get_submit_order_use_case(
    order_repo: IOrderRepository = Depends(get_order_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> SubmitOrder:
    return SubmitOrder(
        order_repo=order_repo,
        event_bus=event_bus,
        uow=uow,
        reconciler=reconciler,
        order_item_repo=order_item_repo,
    )


def get_request_order_use_case(
    order_repo: IOrderRepository = Depends(get_order_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> RequestOrder:
    return RequestOrder(
        order_repo=order_repo,
        event_bus=event_bus,
        uow=uow,
        reconciler=reconciler,
        order_item_repo=order_item_repo,
    )


def get_cancel_order_use_case(
    order_repo: IOrderRepository = Depends(get_order_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    source_item_allocation_repo: ISourceItemAllocationRepository = Depends(
        get_source_item_allocation_repo
    ),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> CancelOrder:
    return CancelOrder(
        order_repo=order_repo,
        order_item_repo=order_item_repo,
        allocation_repo=allocation_repo,
        recompute_schedule=recompute_schedule,
        event_bus=event_bus,
        uow=uow,
        reconciler=reconciler,
        source_item_allocation_repo=source_item_allocation_repo,
    )


def get_orders_use_case(
    order_repo: IOrderRepository = Depends(get_order_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
    demand_repo: IBoughtItemDemandItemRepository = Depends(get_demand_item_repo),
    delivery_repo: IOrderItemDeliveryRepository = Depends(get_order_item_delivery_repo),
    source_item_allocation_repo: ISourceItemAllocationRepository = Depends(
        get_source_item_allocation_repo
    ),
    source_item_demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
) -> GetOrders:
    return GetOrders(
        order_repo=order_repo,
        order_item_repo=order_item_repo,
        allocation_repo=allocation_repo,
        demand_repo=demand_repo,
        delivery_repo=delivery_repo,
        source_allocation_repo=source_item_allocation_repo,
        source_demand_repo=source_item_demand_repo,
    )


get_order_use_case = get_orders_use_case


def get_create_order_item_use_case(
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    bought_item_repo: IBoughtItemQueries = Depends(get_bought_item_repo),
    order_repo: IOrderRepository = Depends(get_order_repo),
    demand_repo: IBoughtItemDemandItemRepository = Depends(get_demand_item_repo),
    allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
    source_item_repo: ISourceItemQueries = Depends(get_source_item_repo),
    source_demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
    source_allocation_repo: ISourceItemAllocationRepository = Depends(
        get_source_item_allocation_repo
    ),
    project_repo: IProjectQueries = Depends(get_project_repo),
    supplier_repo: ISupplierQueries = Depends(get_supplier_repo),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> CreateOrderItem:
    return CreateOrderItem(
        order_item_repo=order_item_repo,
        item_repo=bought_item_repo,
        order_repo=order_repo,
        demand_repo=demand_repo,
        allocation_repo=allocation_repo,
        source_item_repo=source_item_repo,
        project_repo=project_repo,
        supplier_repo=supplier_repo,
        uow=uow,
        reconciler=reconciler,
        source_demand_repo=source_demand_repo,
        source_allocation_repo=source_allocation_repo,
        recompute_schedule=recompute_schedule,
    )


def get_update_order_item_use_case(
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    order_repo: IOrderRepository = Depends(get_order_repo),
    bought_item_repo: IBoughtItemQueries = Depends(get_bought_item_repo),
    allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
    demand_repo: IBoughtItemDemandItemRepository = Depends(get_demand_item_repo),
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    production_order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    source_allocation_repo: ISourceItemAllocationRepository = Depends(
        get_source_item_allocation_repo
    ),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    project_repo: IProjectQueries = Depends(get_project_repo),
) -> UpdateOrderItem:
    return UpdateOrderItem(
        order_item_repo=order_item_repo,
        order_repo=order_repo,
        catalogue_repo=bought_item_repo,
        allocation_repo=allocation_repo,
        demand_repo=demand_repo,
        lot_repo=lot_repo,
        production_order_repo=production_order_repo,
        recompute_schedule=recompute_schedule,
        uow=uow,
        reconciler=reconciler,
        project_repo=project_repo,
        source_allocation_repo=source_allocation_repo,
    )


def get_move_order_item_use_case(
    order_repo: IOrderRepository = Depends(get_order_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    recompute: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
) -> MoveOrderItem:
    return MoveOrderItem(
        order_repo=order_repo,
        order_item_repo=order_item_repo,
        uow=uow,
        reconciler=reconciler,
        recompute_schedule=recompute,
    )


def get_remove_order_item_use_case(
    order_repo: IOrderRepository = Depends(get_order_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    source_item_allocation_repo: ISourceItemAllocationRepository = Depends(
        get_source_item_allocation_repo
    ),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
) -> RemoveOrderItem:
    return RemoveOrderItem(
        order_repo=order_repo,
        order_item_repo=order_item_repo,
        allocation_repo=allocation_repo,
        recompute_schedule=recompute_schedule,
        uow=uow,
        reconciler=reconciler,
        source_item_allocation_repo=source_item_allocation_repo,
        lot_repo=lot_repo,
    )


def get_cancel_order_item_use_case(
    order_repo: IOrderRepository = Depends(get_order_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    source_item_allocation_repo: ISourceItemAllocationRepository = Depends(
        get_source_item_allocation_repo
    ),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> CancelOrderItem:
    return CancelOrderItem(
        order_repo=order_repo,
        order_item_repo=order_item_repo,
        allocation_repo=allocation_repo,
        recompute_schedule=recompute_schedule,
        uow=uow,
        reconciler=reconciler,
        source_item_allocation_repo=source_item_allocation_repo,
    )


def get_close_order_item_short_use_case(
    order_repo: IOrderRepository = Depends(get_order_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    source_item_allocation_repo: ISourceItemAllocationRepository = Depends(
        get_source_item_allocation_repo
    ),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> CloseOrderItemShort:
    return CloseOrderItemShort(
        order_repo=order_repo,
        order_item_repo=order_item_repo,
        allocation_repo=allocation_repo,
        recompute_schedule=recompute_schedule,
        uow=uow,
        reconciler=reconciler,
        source_item_allocation_repo=source_item_allocation_repo,
    )


def get_reopen_order_item_use_case(
    order_repo: IOrderRepository = Depends(get_order_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    project_repo: IProjectQueries = Depends(get_project_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> ReopenOrderItem:
    return ReopenOrderItem(
        order_repo=order_repo,
        order_item_repo=order_item_repo,
        project_repo=project_repo,
        uow=uow,
        reconciler=reconciler,
    )


def get_correct_order_item_delivery_use_case(
    order_repo: IOrderRepository = Depends(get_order_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    delivery_repo: IOrderItemDeliveryRepository = Depends(get_order_item_delivery_repo),
    allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
    demand_repo: IBoughtItemDemandItemRepository = Depends(get_demand_item_repo),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    source_item_allocation_repo: ISourceItemAllocationRepository = Depends(
        get_source_item_allocation_repo
    ),
    source_item_demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
) -> CorrectOrderItemDelivery:
    return CorrectOrderItemDelivery(
        order_repo=order_repo,
        order_item_repo=order_item_repo,
        delivery_repo=delivery_repo,
        allocation_repo=allocation_repo,
        demand_repo=demand_repo,
        recompute_schedule=recompute_schedule,
        uow=uow,
        reconciler=reconciler,
        source_item_allocation_repo=source_item_allocation_repo,
        source_item_demand_repo=source_item_demand_repo,
        lot_repo=lot_repo,
        event_bus=event_bus,
    )


def get_mark_order_item_ordered_use_case(
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    order_repo: IOrderRepository = Depends(get_order_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> MarkOrderItemOrdered:
    return MarkOrderItemOrdered(
        order_item_repo=order_item_repo,
        order_repo=order_repo,
        uow=uow,
        reconciler=reconciler,
    )


def get_mark_all_order_items_ordered_use_case(
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    order_repo: IOrderRepository = Depends(get_order_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> MarkAllOrderItemsOrdered:
    return MarkAllOrderItemsOrdered(
        order_item_repo=order_item_repo,
        order_repo=order_repo,
        uow=uow,
        reconciler=reconciler,
    )


def get_mark_order_item_requested_use_case(
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    order_repo: IOrderRepository = Depends(get_order_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> MarkOrderItemRequested:
    return MarkOrderItemRequested(
        order_item_repo=order_item_repo, order_repo=order_repo, uow=uow, reconciler=reconciler
    )


def get_mark_all_order_items_requested_use_case(
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    order_repo: IOrderRepository = Depends(get_order_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> MarkAllOrderItemsRequested:
    return MarkAllOrderItemsRequested(
        order_item_repo=order_item_repo, order_repo=order_repo, uow=uow, reconciler=reconciler
    )


def get_mark_order_item_ready_for_pickup_use_case(
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    order_repo: IOrderRepository = Depends(get_order_repo),
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    production_order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    lock_plan: LockPlan = Depends(get_lifecycle_lock_plan),
) -> MarkOrderItemReadyForPickup:
    return MarkOrderItemReadyForPickup(
        order_item_repo=order_item_repo,
        order_repo=order_repo,
        lot_repo=lot_repo,
        production_order_repo=production_order_repo,
        recompute_schedule=recompute_schedule,
        uow=uow,
        lock_plan=lock_plan,
    )


def get_process_order_item_delivery_use_case(
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    order_repo: IOrderRepository = Depends(get_order_repo),
    delivery_repo: IOrderItemDeliveryRepository = Depends(get_order_item_delivery_repo),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    made_item_demand_repo: IMadeItemDemandItemRepository = Depends(get_made_item_demand_repo),
    made_item_allocation_repo: IMadeItemAllocationRepository = Depends(
        get_made_item_allocation_repo
    ),
    source_item_demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
    source_item_allocation_repo: ISourceItemAllocationRepository = Depends(
        get_source_item_allocation_repo
    ),
    production_order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
    create_lot: CreateLot = Depends(get_create_lot_for_completion_use_case),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    interruption_repo: IProductionOrderInterruptionRepository = Depends(
        get_production_order_interruption_repo
    ),
    bought_item_allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
    settings_repo: IFulfillmentSettingsRepository = Depends(get_fulfillment_settings_repo),
    bought_item_repo: IBoughtItemQueries = Depends(get_bought_item_repo),
    source_item_repo: ISourceItemQueries = Depends(get_source_item_repo),
    project_repo: IProjectQueries | None = Depends(get_project_repo),
) -> ProcessOrderItemDelivery:
    return ProcessOrderItemDelivery(
        order_item_repo=order_item_repo,
        order_repo=order_repo,
        delivery_repo=delivery_repo,
        recompute_schedule=recompute_schedule,
        event_bus=event_bus,
        uow=uow,
        lot_repo=lot_repo,
        made_item_demand_repo=made_item_demand_repo,
        made_item_allocation_repo=made_item_allocation_repo,
        source_item_demand_repo=source_item_demand_repo,
        source_item_allocation_repo=source_item_allocation_repo,
        production_order_repo=production_order_repo,
        create_lot=create_lot,
        reconciler=reconciler,
        interruption_repo=interruption_repo,
        bought_item_allocation_repo=bought_item_allocation_repo,
        delivery_tolerances=DeliveryTolerances(settings_repo, bought_item_repo, source_item_repo),
        project_repo=project_repo,
    )


def get_deliver_all_order_items_use_case(
    order_repo: IOrderRepository = Depends(get_order_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    delivery_use_case: ProcessOrderItemDelivery = Depends(get_process_order_item_delivery_use_case),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    event_bus: IEventBus = Depends(get_transactional_event_bus),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> DeliverAllOrderItems:
    return DeliverAllOrderItems(
        order_repo=order_repo,
        order_item_repo=order_item_repo,
        delivery_use_case=delivery_use_case,
        event_bus=event_bus,
        uow=uow,
        reconciler=reconciler,
        recompute_schedule=recompute_schedule,
    )
