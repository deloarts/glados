"""Planning & fulfillment's implementation of the project work propagation
port of Workspace, which the composition root binds at startup."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.fulfillment.adapters.inbound.api.deps.lifecycle import get_lifecycle_lock_plan
from src.modules.fulfillment.adapters.inbound.api.deps.lifecycle import get_lifecycle_repositories
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_allocation_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_demand_item_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_made_item_allocation_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_made_item_demand_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_order_item_delivery_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_order_item_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_order_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_production_lot_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_production_order_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import get_quote_request_repo
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_source_item_allocation_repo,
)
from src.modules.fulfillment.adapters.inbound.api.deps.repositories import (
    get_source_item_demand_repo,
)
from src.modules.fulfillment.application.services.lifecycle_lock_plan import LockPlan
from src.modules.fulfillment.application.services.project_work_propagation import (
    ProjectWorkPropagation,
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
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    IProductionLotRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    IProductionOrderRepository,
)
from src.modules.workspace.adapters.inbound.api.deps.repositories import get_project_repo
from src.modules.workspace.ports.outbound.project_work_port import IProjectWorkPropagation
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries


def get_project_work_propagation(
    project_repo: IProjectQueries = Depends(get_project_repo),
    lot_repo: IProductionLotRepository = Depends(get_production_lot_repo),
    made_demand_repo: IMadeItemDemandItemRepository = Depends(get_made_item_demand_repo),
    bought_demand_repo: IBoughtItemDemandItemRepository = Depends(get_demand_item_repo),
    made_allocation_repo: IMadeItemAllocationRepository = Depends(get_made_item_allocation_repo),
    lock_plan: LockPlan = Depends(get_lifecycle_lock_plan),
    order_repo: IProductionOrderRepository = Depends(get_production_order_repo),
) -> IProjectWorkPropagation:
    """Planning & fulfillment's implementation of the Workspace port."""
    return ProjectWorkPropagation(
        project_repo=project_repo,
        lot_repo=lot_repo,
        made_demand_repo=made_demand_repo,
        bought_demand_repo=bought_demand_repo,
        made_allocation_repo=made_allocation_repo,
        lock_plan=lock_plan,
        order_repo=order_repo,
    )


def build_project_work_propagation(db: AsyncSession) -> IProjectWorkPropagation:
    """get_project_work_propagation on one session, which the composition
    root binds to Workspace's port. Its lock plan is its own, since a project
    update runs no lifecycle reconciler that would share one."""
    lot_repo = get_production_lot_repo(db)
    production_order_repo = get_production_order_repo(db)
    made_demand_repo = get_made_item_demand_repo(db)
    bought_demand_repo = get_demand_item_repo(db)
    made_allocation_repo = get_made_item_allocation_repo(db)
    repositories = get_lifecycle_repositories(
        lots=lot_repo,
        production_orders=production_order_repo,
        orders=get_order_repo(db),
        order_items=get_order_item_repo(db),
        bought_demands=bought_demand_repo,
        bought_allocations=get_allocation_repo(db),
        made_demands=made_demand_repo,
        made_allocations=made_allocation_repo,
        source_demands=get_source_item_demand_repo(db),
        source_allocations=get_source_item_allocation_repo(db),
        quote_requests=get_quote_request_repo(db),
        deliveries=get_order_item_delivery_repo(db),
    )
    return get_project_work_propagation(
        project_repo=get_project_repo(db),
        lot_repo=lot_repo,
        made_demand_repo=made_demand_repo,
        bought_demand_repo=bought_demand_repo,
        made_allocation_repo=made_allocation_repo,
        lock_plan=get_lifecycle_lock_plan(repositories),
        order_repo=production_order_repo,
    )
