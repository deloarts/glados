"""Use case factories: stock allocations (bought/source/made items)."""

from fastapi import Depends

from src.modules.fulfillment.adapters.inbound.api.deps.lifecycle import get_lifecycle_reconciler
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_recompute_machine_schedule_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_allocation_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_demand_item_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_made_item_allocation_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_made_item_demand_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_order_item_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_order_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_source_item_allocation_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_source_item_demand_repo,
)
from src.modules.fulfillment.application.services.allocation_fill import LineFillRepos
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases.bought_item_demand.auto_allocate import (
    AutoAllocate,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.create_allocation import (
    CreateAllocation,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.create_allocation import (
    DeleteAllocation,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.create_allocation import (
    DeleteStockAllocation,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.create_allocation import (
    UpdateAllocation,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.create_allocation import (
    UpdateStockAllocation,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.fulfill_from_stock import (
    FulfillDemandFromStock,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.get_allocations import (
    GetAllocationsForDemand,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.get_allocations import (
    GetAllocationsForOrderItem,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.fulfill_from_stock import (
    FulfillDemandFromStock as FulfillMadeItemDemandFromStock,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.get_allocations import (
    GetAllocationsForDemand as GetMadeItemAllocationsForDemand,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.stock_allocation import (
    DeleteStockAllocation as DeleteMadeItemStockAllocation,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.stock_allocation import (
    UpdateStockAllocation as UpdateMadeItemStockAllocation,
)
from src.modules.fulfillment.application.use_cases.production_schedule.recompute_machine_schedule import (
    RecomputeMachineSchedule,
)
from src.modules.fulfillment.application.use_cases.source_item_allocation.auto_allocate import (
    AutoAllocateSourceItemDemand,
)
from src.modules.fulfillment.application.use_cases.source_item_allocation.create_allocation import (
    CreateSourceItemAllocation,
)
from src.modules.fulfillment.application.use_cases.source_item_allocation.create_allocation import (
    DeleteSourceItemAllocation,
)
from src.modules.fulfillment.application.use_cases.source_item_allocation.create_allocation import (
    DeleteSourceItemStockAllocation,
)
from src.modules.fulfillment.application.use_cases.source_item_allocation.create_allocation import (
    UpdateSourceItemAllocation,
)
from src.modules.fulfillment.application.use_cases.source_item_allocation.create_allocation import (
    UpdateSourceItemStockAllocation,
)
from src.modules.fulfillment.application.use_cases.source_item_allocation.fulfill_from_stock import (
    FulfillSourceItemDemandFromStock,
)
from src.modules.fulfillment.application.use_cases.source_item_allocation.get_allocations import (
    GetAllocationsForOrderItem as GetSourceItemAllocationsForOrderItem,
)
from src.modules.fulfillment.application.use_cases.source_item_allocation.get_allocations import (
    GetAllocationsForSourceItemDemand,
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
from src.modules.fulfillment.ports.outbound.repositories.order_repository import (
    IOrderItemRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.order_repository import IOrderRepository
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemAllocationRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.source_item_demand_repository import (
    ISourceItemDemandRepository,
)
from src.modules.platform.adapters.inbound.api.deps.database import get_unit_of_work
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_project_repo
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries


def get_auto_allocate_use_case(
    demand_repo: IBoughtItemDemandItemRepository = Depends(get_demand_item_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
    project_repo: IProjectQueries = Depends(get_project_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    source_allocation_repo: ISourceItemAllocationRepository = Depends(
        get_source_item_allocation_repo
    ),
) -> AutoAllocate:
    return AutoAllocate(
        demand_repo=demand_repo,
        order_item_repo=order_item_repo,
        allocation_repo=allocation_repo,
        uow=uow,
        reconciler=reconciler,
        fill_repos=LineFillRepos(bought=allocation_repo, source=source_allocation_repo),
        project_repo=project_repo,
    )


def get_fulfill_demand_from_stock_use_case(
    demand_repo: IBoughtItemDemandItemRepository = Depends(get_demand_item_repo),
    allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> FulfillDemandFromStock:
    return FulfillDemandFromStock(
        demand_repo=demand_repo,
        allocation_repo=allocation_repo,
        order_item_repo=order_item_repo,
        uow=uow,
        reconciler=reconciler,
    )


def get_create_allocation_use_case(
    allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
    demand_repo: IBoughtItemDemandItemRepository = Depends(get_demand_item_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    source_allocation_repo: ISourceItemAllocationRepository = Depends(
        get_source_item_allocation_repo
    ),
) -> CreateAllocation:
    return CreateAllocation(
        allocation_repo=allocation_repo,
        demand_repo=demand_repo,
        order_item_repo=order_item_repo,
        uow=uow,
        reconciler=reconciler,
        fill_repos=LineFillRepos(bought=allocation_repo, source=source_allocation_repo),
    )


def get_update_allocation_use_case(
    allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
    demand_repo: IBoughtItemDemandItemRepository = Depends(get_demand_item_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    source_allocation_repo: ISourceItemAllocationRepository = Depends(
        get_source_item_allocation_repo
    ),
) -> UpdateAllocation:
    return UpdateAllocation(
        allocation_repo=allocation_repo,
        demand_repo=demand_repo,
        order_item_repo=order_item_repo,
        uow=uow,
        reconciler=reconciler,
        fill_repos=LineFillRepos(bought=allocation_repo, source=source_allocation_repo),
    )


def get_delete_allocation_use_case(
    allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
    demand_repo: IBoughtItemDemandItemRepository = Depends(get_demand_item_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    source_allocation_repo: ISourceItemAllocationRepository = Depends(
        get_source_item_allocation_repo
    ),
) -> DeleteAllocation:
    return DeleteAllocation(
        allocation_repo=allocation_repo,
        demand_repo=demand_repo,
        order_item_repo=order_item_repo,
        uow=uow,
        reconciler=reconciler,
        fill_repos=LineFillRepos(bought=allocation_repo, source=source_allocation_repo),
    )


def get_update_stock_allocation_use_case(
    allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
    demand_repo: IBoughtItemDemandItemRepository = Depends(get_demand_item_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> UpdateStockAllocation:
    return UpdateStockAllocation(
        allocation_repo=allocation_repo,
        demand_repo=demand_repo,
        order_item_repo=order_item_repo,
        uow=uow,
        reconciler=reconciler,
    )


def get_delete_stock_allocation_use_case(
    allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
    demand_repo: IBoughtItemDemandItemRepository = Depends(get_demand_item_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> DeleteStockAllocation:
    return DeleteStockAllocation(
        allocation_repo=allocation_repo,
        demand_repo=demand_repo,
        order_item_repo=order_item_repo,
        uow=uow,
        reconciler=reconciler,
    )


def get_get_allocations_for_demand_use_case(
    allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    order_repo: IOrderRepository = Depends(get_order_repo),
    demand_repo: IBoughtItemDemandItemRepository = Depends(get_demand_item_repo),
) -> GetAllocationsForDemand:
    return GetAllocationsForDemand(
        allocation_repo=allocation_repo,
        order_item_repo=order_item_repo,
        order_repo=order_repo,
        demand_repo=demand_repo,
    )


def get_get_allocations_for_order_item_use_case(
    allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    order_repo: IOrderRepository = Depends(get_order_repo),
    demand_repo: IBoughtItemDemandItemRepository = Depends(get_demand_item_repo),
) -> GetAllocationsForOrderItem:
    return GetAllocationsForOrderItem(
        allocation_repo=allocation_repo,
        order_item_repo=order_item_repo,
        order_repo=order_repo,
        demand_repo=demand_repo,
    )


def get_auto_allocate_source_item_demand_use_case(
    demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    allocation_repo: ISourceItemAllocationRepository = Depends(get_source_item_allocation_repo),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    project_repo: IProjectQueries = Depends(get_project_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    bought_allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
) -> AutoAllocateSourceItemDemand:
    return AutoAllocateSourceItemDemand(
        demand_repo=demand_repo,
        order_item_repo=order_item_repo,
        allocation_repo=allocation_repo,
        recompute_schedule=recompute_schedule,
        uow=uow,
        reconciler=reconciler,
        fill_repos=LineFillRepos(bought=bought_allocation_repo, source=allocation_repo),
        project_repo=project_repo,
    )


def get_fulfill_source_item_demand_from_stock_use_case(
    demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
    allocation_repo: ISourceItemAllocationRepository = Depends(get_source_item_allocation_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> FulfillSourceItemDemandFromStock:
    return FulfillSourceItemDemandFromStock(
        demand_repo=demand_repo,
        allocation_repo=allocation_repo,
        order_item_repo=order_item_repo,
        recompute_schedule=recompute_schedule,
        uow=uow,
        reconciler=reconciler,
    )


def get_create_source_item_allocation_use_case(
    allocation_repo: ISourceItemAllocationRepository = Depends(get_source_item_allocation_repo),
    demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    bought_allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
) -> CreateSourceItemAllocation:
    return CreateSourceItemAllocation(
        allocation_repo=allocation_repo,
        demand_repo=demand_repo,
        order_item_repo=order_item_repo,
        recompute_schedule=recompute_schedule,
        uow=uow,
        reconciler=reconciler,
        fill_repos=LineFillRepos(bought=bought_allocation_repo, source=allocation_repo),
    )


def get_update_source_item_allocation_use_case(
    allocation_repo: ISourceItemAllocationRepository = Depends(get_source_item_allocation_repo),
    demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    bought_allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
) -> UpdateSourceItemAllocation:
    return UpdateSourceItemAllocation(
        allocation_repo=allocation_repo,
        demand_repo=demand_repo,
        order_item_repo=order_item_repo,
        recompute_schedule=recompute_schedule,
        uow=uow,
        reconciler=reconciler,
        fill_repos=LineFillRepos(bought=bought_allocation_repo, source=allocation_repo),
    )


def get_delete_source_item_allocation_use_case(
    allocation_repo: ISourceItemAllocationRepository = Depends(get_source_item_allocation_repo),
    demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
    bought_allocation_repo: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
) -> DeleteSourceItemAllocation:
    return DeleteSourceItemAllocation(
        allocation_repo=allocation_repo,
        demand_repo=demand_repo,
        order_item_repo=order_item_repo,
        recompute_schedule=recompute_schedule,
        uow=uow,
        reconciler=reconciler,
        fill_repos=LineFillRepos(bought=bought_allocation_repo, source=allocation_repo),
    )


def get_update_source_item_stock_allocation_use_case(
    allocation_repo: ISourceItemAllocationRepository = Depends(get_source_item_allocation_repo),
    demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> UpdateSourceItemStockAllocation:
    return UpdateSourceItemStockAllocation(
        allocation_repo=allocation_repo,
        demand_repo=demand_repo,
        order_item_repo=order_item_repo,
        recompute_schedule=recompute_schedule,
        uow=uow,
        reconciler=reconciler,
    )


def get_delete_source_item_stock_allocation_use_case(
    allocation_repo: ISourceItemAllocationRepository = Depends(get_source_item_allocation_repo),
    demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    recompute_schedule: RecomputeMachineSchedule = Depends(get_recompute_machine_schedule_use_case),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> DeleteSourceItemStockAllocation:
    return DeleteSourceItemStockAllocation(
        allocation_repo=allocation_repo,
        demand_repo=demand_repo,
        order_item_repo=order_item_repo,
        recompute_schedule=recompute_schedule,
        uow=uow,
        reconciler=reconciler,
    )


def get_get_source_item_allocations_for_demand_use_case(
    allocation_repo: ISourceItemAllocationRepository = Depends(get_source_item_allocation_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    order_repo: IOrderRepository = Depends(get_order_repo),
    demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
) -> GetAllocationsForSourceItemDemand:
    return GetAllocationsForSourceItemDemand(
        allocation_repo=allocation_repo,
        order_item_repo=order_item_repo,
        order_repo=order_repo,
        demand_repo=demand_repo,
    )


def get_get_source_item_allocations_for_order_item_use_case(
    allocation_repo: ISourceItemAllocationRepository = Depends(get_source_item_allocation_repo),
    order_item_repo: IOrderItemRepository = Depends(get_order_item_repo),
    order_repo: IOrderRepository = Depends(get_order_repo),
    demand_repo: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
) -> GetSourceItemAllocationsForOrderItem:
    return GetSourceItemAllocationsForOrderItem(
        allocation_repo=allocation_repo,
        order_item_repo=order_item_repo,
        order_repo=order_repo,
        demand_repo=demand_repo,
    )


def get_update_made_item_stock_allocation_use_case(
    allocation_repo: IMadeItemAllocationRepository = Depends(get_made_item_allocation_repo),
    demand_repo: IMadeItemDemandItemRepository = Depends(get_made_item_demand_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> UpdateMadeItemStockAllocation:
    return UpdateMadeItemStockAllocation(
        allocation_repo=allocation_repo,
        demand_repo=demand_repo,
        uow=uow,
        reconciler=reconciler,
    )


def get_delete_made_item_stock_allocation_use_case(
    allocation_repo: IMadeItemAllocationRepository = Depends(get_made_item_allocation_repo),
    demand_repo: IMadeItemDemandItemRepository = Depends(get_made_item_demand_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> DeleteMadeItemStockAllocation:
    return DeleteMadeItemStockAllocation(
        allocation_repo=allocation_repo,
        demand_repo=demand_repo,
        uow=uow,
        reconciler=reconciler,
    )


def get_made_item_get_allocations_for_demand_use_case(
    allocation_repo: IMadeItemAllocationRepository = Depends(get_made_item_allocation_repo),
) -> GetMadeItemAllocationsForDemand:
    return GetMadeItemAllocationsForDemand(allocation_repo=allocation_repo)


def get_fulfill_made_item_demand_from_stock_use_case(
    demand_repo: IMadeItemDemandItemRepository = Depends(get_made_item_demand_repo),
    allocation_repo: IMadeItemAllocationRepository = Depends(get_made_item_allocation_repo),
    uow: IUnitOfWork = Depends(get_unit_of_work),
    reconciler: LifecycleReconciler = Depends(get_lifecycle_reconciler),
) -> FulfillMadeItemDemandFromStock:
    return FulfillMadeItemDemandFromStock(
        demand_repo=demand_repo,
        allocation_repo=allocation_repo,
        uow=uow,
        reconciler=reconciler,
    )
