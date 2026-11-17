"""
Source item demand allocation endpoints, mirrors bought_items_allocations.py.
  Manual CRUD:
    POST   /source-item-allocations/                                     create allocation
    GET    /source-item-allocations/demand/{demand_id}                   list for demand
    GET    /source-item-allocations/order-item/{order_item_id}           list for order item
    PUT    /source-item-allocations/demand/{demand_id}/order-item/{oid}  update quantity
    DELETE /source-item-allocations/demand/{demand_id}/order-item/{oid}  remove
    PUT    /source-item-allocations/demand/{demand_id}/stock             set stock allocation qty
    DELETE /source-item-allocations/demand/{demand_id}/stock             remove stock allocation

  Summary / analytics:
    GET    /source-item-allocations/demand/{demand_id}/summary           quantity breakdown

  Engine:
    POST   /source-item-allocations/demand/{demand_id}/auto-allocate       greedy auto allocation
    POST   /source-item-allocations/demand/{demand_id}/fulfill-from-stock  cover demand from stock

Delivery processing stays on bought_items_allocations.py's shared
PUT /allocations/order-item/{order_item_id}/deliver, ProcessOrderItemDelivery
handles both cascades internally, gated on receive:deliveries.
"""

from fastapi import Depends
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.fulfillment.adapters.inbound.api.deps.allocations import (
    get_auto_allocate_source_item_demand_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.allocations import (
    get_create_source_item_allocation_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.allocations import (
    get_delete_source_item_allocation_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.allocations import (
    get_delete_source_item_stock_allocation_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.allocations import (
    get_fulfill_source_item_demand_from_stock_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.allocations import (
    get_get_source_item_allocations_for_demand_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.allocations import (
    get_get_source_item_allocations_for_order_item_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.allocations import (
    get_update_source_item_allocation_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.allocations import (
    get_update_source_item_stock_allocation_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_source_item_demand_summary_batch_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_source_item_demand_summary_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.idempotent_replays import allocation_refs
from src.modules.fulfillment.adapters.inbound.api.idempotent_replays import demand_refs
from src.modules.fulfillment.adapters.inbound.api.schemas.source_item_allocation_schema import (
    AutoAllocateSourceItemDemandResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.source_item_allocation_schema import (
    FulfillSourceItemDemandFromStockRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.source_item_allocation_schema import (
    FulfillSourceItemDemandFromStockResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.source_item_allocation_schema import (
    SourceItemAllocationCreateRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.source_item_allocation_schema import (
    SourceItemAllocationResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.source_item_allocation_schema import (
    SourceItemAllocationUpdateRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.source_item_allocation_schema import (
    SourceItemDemandSummaryResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.source_item_allocation_schema import (
    SourceItemStockAllocationUpdateRequest,
)
from src.modules.fulfillment.application.dto.source_item_allocation_dto import (
    AutoAllocateSourceItemDemandCommand,
)
from src.modules.fulfillment.application.dto.source_item_allocation_dto import (
    AutoAllocateSourceItemDemandResult,
)
from src.modules.fulfillment.application.dto.source_item_allocation_dto import (
    CreateSourceItemAllocationCommand,
)
from src.modules.fulfillment.application.dto.source_item_allocation_dto import (
    FulfillSourceItemDemandFromStockCommand,
)
from src.modules.fulfillment.application.dto.source_item_allocation_dto import (
    FulfillSourceItemDemandFromStockResult,
)
from src.modules.fulfillment.application.dto.source_item_allocation_dto import (
    SourceItemAllocationResult,
)
from src.modules.fulfillment.application.dto.source_item_allocation_dto import (
    SourceItemDemandSummaryResult,
)
from src.modules.fulfillment.application.dto.source_item_allocation_dto import (
    UpdateSourceItemAllocationCommand,
)
from src.modules.fulfillment.application.dto.source_item_allocation_dto import (
    UpdateSourceItemStockAllocationCommand,
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
    GetAllocationsForOrderItem,
)
from src.modules.fulfillment.application.use_cases.source_item_allocation.get_allocations import (
    GetAllocationsForSourceItemDemand,
)
from src.modules.fulfillment.application.use_cases.source_item_allocation.get_allocations import (
    GetSourceItemDemandSummary,
)
from src.modules.fulfillment.application.use_cases.source_item_allocation.get_allocations import (
    GetSourceItemDemandSummaryBatch,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.idempotency import Idempotency
from src.modules.platform.adapters.inbound.api.idempotency import get_idempotency
from src.modules.platform.domain.entities.idempotency_key import ResourceRef
from src.modules.platform.domain.entities.user import User

router = APIRouter()


# ── Manual allocation CRUD ────────────────────────────────────────────


@router.post("/", response_model=SourceItemAllocationResponse, status_code=status.HTTP_201_CREATED)
async def create_source_item_allocation(
    body: SourceItemAllocationCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateSourceItemAllocation = Depends(get_create_source_item_allocation_use_case),
    idempotency: Idempotency = Depends(get_idempotency),
    reader: GetAllocationsForSourceItemDemand = Depends(
        get_get_source_item_allocations_for_demand_use_case
    ),
) -> SourceItemAllocationResult:
    """Allocates a source item demand on an order line. With an
    Idempotency-Key, a retry is answered with the allocation instead of
    being refused as a second one."""
    cmd = CreateSourceItemAllocationCommand(**body.model_dump())

    async def replay(_refs: tuple[ResourceRef, ...]) -> SourceItemAllocationResult:
        held = await reader.execute(demand_item_id=cmd.demand_item_id)
        return next(a for a in held if a.order_item_id == cmd.order_item_id)

    return await idempotency.run(
        lambda: use_case.execute(actor=actor, cmd=cmd),
        written=lambda made: allocation_refs(made.demand_item_id, made.order_item_id),
        replay=replay,
    )


@router.get("/demand/{demand_id}", response_model=list[SourceItemAllocationResponse])
async def get_allocations_for_source_item_demand(
    demand_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetAllocationsForSourceItemDemand = Depends(
        get_get_source_item_allocations_for_demand_use_case
    ),
) -> list[SourceItemAllocationResult]:
    return await use_case.execute(demand_item_id=demand_id)


@router.get("/order-item/{order_item_id}", response_model=list[SourceItemAllocationResponse])
async def get_source_item_allocations_for_order_item(
    order_item_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetAllocationsForOrderItem = Depends(
        get_get_source_item_allocations_for_order_item_use_case
    ),
) -> list[SourceItemAllocationResult]:
    return await use_case.execute(order_item_id=order_item_id)


@router.put(
    "/demand/{demand_id}/order-item/{order_item_id}",
    response_model=SourceItemAllocationResponse,
)
async def update_source_item_allocation(
    demand_id: int,
    order_item_id: int,
    body: SourceItemAllocationUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateSourceItemAllocation = Depends(get_update_source_item_allocation_use_case),
) -> SourceItemAllocationResult:
    cmd = UpdateSourceItemAllocationCommand(**body.model_dump())
    return await use_case.execute(
        actor=actor,
        demand_item_id=demand_id,
        order_item_id=order_item_id,
        cmd=cmd,
    )


@router.delete(
    "/demand/{demand_id}/order-item/{order_item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_source_item_allocation(
    demand_id: int,
    order_item_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: DeleteSourceItemAllocation = Depends(get_delete_source_item_allocation_use_case),
) -> None:
    await use_case.execute(actor=actor, demand_item_id=demand_id, order_item_id=order_item_id)


@router.put(
    "/demand/{demand_id}/stock",
    response_model=SourceItemAllocationResponse,
)
async def update_source_item_stock_allocation(
    demand_id: int,
    body: SourceItemStockAllocationUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateSourceItemStockAllocation = Depends(
        get_update_source_item_stock_allocation_use_case
    ),
) -> SourceItemAllocationResult:
    """Manually overrides the stock-sourced allocation quantity for a demand."""
    cmd = UpdateSourceItemStockAllocationCommand(**body.model_dump())
    return await use_case.execute(actor=actor, demand_item_id=demand_id, cmd=cmd)


@router.delete(
    "/demand/{demand_id}/stock",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_source_item_stock_allocation(
    demand_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: DeleteSourceItemStockAllocation = Depends(
        get_delete_source_item_stock_allocation_use_case
    ),
) -> None:
    await use_case.execute(actor=actor, demand_item_id=demand_id)


# ── Quantity summary ──────────────────────────────────────────────────


@router.get("/demand/{demand_id}/summary", response_model=SourceItemDemandSummaryResponse)
async def get_source_item_demand_summary(
    demand_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetSourceItemDemandSummary = Depends(get_source_item_demand_summary_use_case),
) -> SourceItemDemandSummaryResult:
    """
    Returns the full quantity breakdown for a source item demand:
    total / allocated / delivered / remaining / unallocated / in_transit.
    """
    return await use_case.execute(demand_item_id=demand_id)


@router.post("/demands/summary-batch", response_model=dict[int, SourceItemDemandSummaryResponse])
async def get_source_item_demand_summary_batch(
    demand_ids: list[int],
    _: User = Depends(get_current_active_user),
    use_case: GetSourceItemDemandSummaryBatch = Depends(
        get_source_item_demand_summary_batch_use_case
    ),
) -> dict[int, SourceItemDemandSummaryResult]:
    """
    Batch quantity breakdown for multiple demand items.
    Returns a dict keyed by demand_item_id.
    Used by the frontend demand list to show remaining per row.
    """
    return await use_case.execute(demand_item_ids=demand_ids)


# ── Auto-allocation engine ────────────────────────────────────────────


@router.post(
    "/demand/{demand_id}/auto-allocate", response_model=AutoAllocateSourceItemDemandResponse
)
async def auto_allocate_source_item_demand(
    demand_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: AutoAllocateSourceItemDemand = Depends(get_auto_allocate_source_item_demand_use_case),
) -> AutoAllocateSourceItemDemandResult:
    """
    Greedy allocation engine: links this demand to open order items
    (same material) until the demand is fully covered or no candidates
    remain. Priority: ORDERED first, then earliest expected delivery,
    then most available quantity.
    """
    cmd = AutoAllocateSourceItemDemandCommand(demand_item_id=demand_id)
    return await use_case.execute(actor=actor, cmd=cmd)


@router.post(
    "/demand/{demand_id}/fulfill-from-stock",
    response_model=FulfillSourceItemDemandFromStockResponse,
)
async def fulfill_source_item_demand_from_stock(
    demand_id: int,
    body: FulfillSourceItemDemandFromStockRequest,
    actor: User = Depends(get_current_active_user),
    use_case: FulfillSourceItemDemandFromStock = Depends(
        get_fulfill_source_item_demand_from_stock_use_case
    ),
    idempotency: Idempotency = Depends(get_idempotency),
) -> FulfillSourceItemDemandFromStockResult:
    """
    Covers (part of) a demand directly from stock instead of via an order.
    No stock level is tracked here, that ledger lives in another service.
    With an Idempotency-Key, a retry is answered with what the demand holds
    from stock instead of taking the quantity again.
    """
    cmd = FulfillSourceItemDemandFromStockCommand(demand_item_id=demand_id, quantity=body.quantity)
    return await idempotency.run(
        lambda: use_case.execute(actor=actor, cmd=cmd),
        written=lambda done: demand_refs([done.demand_item_id]),
        replay=lambda _refs: use_case.replay(demand_id, body.quantity),
    )
