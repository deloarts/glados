"""The lifecycle repositories, lock plan and reconciler of one request."""

from fastapi import Depends

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
from src.modules.fulfillment.application.services.lifecycle_loader import LifecycleRepositories
from src.modules.fulfillment.application.services.lifecycle_lock_plan import LockPlan
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
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
    IOrderItemDeliveryRepository,
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
from src.modules.platform.ports.outbound.event_bus_port import IEventBus

# ── Lifecycle ─────────────────────────────────────────────────────────


def get_lifecycle_repositories(
    lots: IProductionLotRepository = Depends(get_production_lot_repo),
    production_orders: IProductionOrderRepository = Depends(get_production_order_repo),
    orders: IOrderRepository = Depends(get_order_repo),
    order_items: IOrderItemRepository = Depends(get_order_item_repo),
    bought_demands: IBoughtItemDemandItemRepository = Depends(get_demand_item_repo),
    bought_allocations: IBoughtItemAllocationRepository = Depends(get_allocation_repo),
    made_demands: IMadeItemDemandItemRepository = Depends(get_made_item_demand_repo),
    made_allocations: IMadeItemAllocationRepository = Depends(get_made_item_allocation_repo),
    source_demands: ISourceItemDemandRepository = Depends(get_source_item_demand_repo),
    source_allocations: ISourceItemAllocationRepository = Depends(get_source_item_allocation_repo),
    quote_requests: IQuoteRequestRepository = Depends(get_quote_request_repo),
    deliveries: IOrderItemDeliveryRepository = Depends(get_order_item_delivery_repo),
) -> LifecycleRepositories:
    """The lifecycle repositories on the request's session."""
    return LifecycleRepositories(
        lots=lots,
        production_orders=production_orders,
        orders=orders,
        order_items=order_items,
        bought_demands=bought_demands,
        bought_allocations=bought_allocations,
        made_demands=made_demands,
        made_allocations=made_allocations,
        source_demands=source_demands,
        source_allocations=source_allocations,
        quote_requests=quote_requests,
        deliveries=deliveries,
    )


def get_lifecycle_lock_plan(
    repositories: LifecycleRepositories = Depends(get_lifecycle_repositories),
) -> LockPlan:
    """One lock plan per request: FastAPI hands every dependant of one
    request the same instance, so a use case and its reconciler take their
    row locks through one plan, in one order."""
    return LockPlan(repositories)


def get_lifecycle_reconciler(
    repositories: LifecycleRepositories = Depends(get_lifecycle_repositories),
    lock_plan: LockPlan = Depends(get_lifecycle_lock_plan),
    bus: IEventBus = Depends(get_transactional_event_bus),
) -> LifecycleReconciler:
    """One reconciler per request, on the request's session, lock plan and
    transactional bus, so its locks follow the use case's and its writes and
    events commit with the use case."""
    return LifecycleReconciler(repositories, bus, lock_plan=lock_plan)
