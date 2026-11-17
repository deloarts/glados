"""
Allocation endpoints:
  Manual CRUD:
    POST   /allocations/                                     create allocation
    GET    /allocations/demand/{demand_id}                   list for demand
    GET    /allocations/order-item/{order_item_id}           list for order item
    PUT    /allocations/demand/{demand_id}/order-item/{oid}  update quantity
    DELETE /allocations/demand/{demand_id}/order-item/{oid}  remove
    PUT    /allocations/demand/{demand_id}/stock             set stock allocation quantity
    DELETE /allocations/demand/{demand_id}/stock             remove stock allocation

  Summary / analytics:
    GET    /allocations/demand/{demand_id}/summary           quantity breakdown

  Engine:
    POST   /allocations/demand/{demand_id}/auto-allocate          greedy auto allocation
    POST   /allocations/demand/{demand_id}/fulfill-from-stock     cover demand from stock

  Delivery processing:
    PUT    /allocations/order-item/{order_item_id}/deliver   deliver + cascade fulfillment
"""

from typing import Annotated

from fastapi import Depends
from fastapi import Query
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.fulfillment.adapters.inbound.api.deps.allocations import get_auto_allocate_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.allocations import (
    get_create_allocation_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.allocations import (
    get_delete_allocation_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.allocations import (
    get_delete_stock_allocation_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.allocations import (
    get_fulfill_demand_from_stock_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.allocations import (
    get_get_allocations_for_demand_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.allocations import (
    get_get_allocations_for_order_item_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.allocations import (
    get_update_allocation_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.allocations import (
    get_update_stock_allocation_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_demand_summary_batch_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.demands import get_demand_summary_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.orders import get_order_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.orders import (
    get_process_order_item_delivery_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import get_lifecycle_actions
from src.modules.fulfillment.adapters.inbound.api.idempotent_replays import allocation_refs
from src.modules.fulfillment.adapters.inbound.api.idempotent_replays import demand_refs
from src.modules.fulfillment.adapters.inbound.api.idempotent_replays import order_item_refs
from src.modules.fulfillment.adapters.inbound.api.idempotent_replays import replay_order_item
from src.modules.fulfillment.adapters.inbound.api.schemas.allocation_schema import (
    AllocationCreateRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.allocation_schema import (
    AllocationResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.allocation_schema import (
    AllocationUpdateRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.allocation_schema import (
    AutoAllocateResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.allocation_schema import (
    DemandSummaryResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.allocation_schema import (
    FulfillFromStockRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.allocation_schema import (
    FulfillFromStockResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.allocation_schema import (
    StockAllocationUpdateRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.order_schema import (
    DeliveryRejectionRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.order_schema import OrderItemResponse
from src.modules.fulfillment.application.dto.allocation_dto import AllocationResult
from src.modules.fulfillment.application.dto.allocation_dto import AutoAllocateCommand
from src.modules.fulfillment.application.dto.allocation_dto import AutoAllocateResult
from src.modules.fulfillment.application.dto.allocation_dto import CreateAllocationCommand
from src.modules.fulfillment.application.dto.allocation_dto import DemandSummaryResult
from src.modules.fulfillment.application.dto.allocation_dto import FulfillFromStockCommand
from src.modules.fulfillment.application.dto.allocation_dto import FulfillFromStockResult
from src.modules.fulfillment.application.dto.allocation_dto import UpdateAllocationCommand
from src.modules.fulfillment.application.dto.allocation_dto import UpdateStockAllocationCommand
from src.modules.fulfillment.application.dto.order_dto import OrderItemResult
from src.modules.fulfillment.application.services.lifecycle_actions import LifecycleActions
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
from src.modules.fulfillment.application.use_cases.bought_item_demand.get_allocations import (
    GetDemandSummary,
)
from src.modules.fulfillment.application.use_cases.bought_item_demand.get_allocations import (
    GetDemandSummaryBatch,
)
from src.modules.fulfillment.application.use_cases.order.get_order import GetOrders
from src.modules.fulfillment.application.use_cases.order.process_order_item_delivery import (
    ProcessOrderItemDelivery,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.idempotency import Idempotency
from src.modules.platform.adapters.inbound.api.idempotency import get_idempotency
from src.modules.platform.adapters.inbound.api.schemas.quantity_fields import Quantity
from src.modules.platform.domain.entities.idempotency_key import ResourceRef
from src.modules.platform.domain.entities.user import User

router = APIRouter()


# ── Manual allocation CRUD ────────────────────────────────────────────


@router.post("/", response_model=AllocationResponse, status_code=status.HTTP_201_CREATED)
async def create_allocation(
    body: AllocationCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateAllocation = Depends(get_create_allocation_use_case),
    idempotency: Idempotency = Depends(get_idempotency),
    reader: GetAllocationsForDemand = Depends(get_get_allocations_for_demand_use_case),
) -> AllocationResult:
    """Allocates a demand on an order line. With an Idempotency-Key, a retry
    is answered with the allocation instead of being refused as a second
    one."""
    cmd = CreateAllocationCommand(**body.model_dump())

    async def replay(_refs: tuple[ResourceRef, ...]) -> AllocationResult:
        held = await reader.execute(demand_item_id=cmd.demand_item_id)
        return next(a for a in held if a.order_item_id == cmd.order_item_id)

    return await idempotency.run(
        lambda: use_case.execute(actor=actor, cmd=cmd),
        written=lambda made: allocation_refs(made.demand_item_id, made.order_item_id),
        replay=replay,
    )


@router.get("/demand/{demand_id}", response_model=list[AllocationResponse])
async def get_allocations_for_demand(
    demand_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetAllocationsForDemand = Depends(get_get_allocations_for_demand_use_case),
) -> list[AllocationResult]:
    return await use_case.execute(demand_item_id=demand_id)


@router.get("/order-item/{order_item_id}", response_model=list[AllocationResponse])
async def get_allocations_for_order_item(
    order_item_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetAllocationsForOrderItem = Depends(get_get_allocations_for_order_item_use_case),
) -> list[AllocationResult]:
    return await use_case.execute(order_item_id=order_item_id)


@router.put(
    "/demand/{demand_id}/order-item/{order_item_id}",
    response_model=AllocationResponse,
)
async def update_allocation(
    demand_id: int,
    order_item_id: int,
    body: AllocationUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateAllocation = Depends(get_update_allocation_use_case),
) -> AllocationResult:
    cmd = UpdateAllocationCommand(**body.model_dump())
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
async def delete_allocation(
    demand_id: int,
    order_item_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: DeleteAllocation = Depends(get_delete_allocation_use_case),
) -> None:
    await use_case.execute(actor=actor, demand_item_id=demand_id, order_item_id=order_item_id)


@router.put(
    "/demand/{demand_id}/stock",
    response_model=AllocationResponse,
)
async def update_stock_allocation(
    demand_id: int,
    body: StockAllocationUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateStockAllocation = Depends(get_update_stock_allocation_use_case),
) -> AllocationResult:
    """Manually overrides the stock-sourced allocation quantity for a demand."""
    cmd = UpdateStockAllocationCommand(**body.model_dump())
    return await use_case.execute(actor=actor, demand_item_id=demand_id, cmd=cmd)


@router.delete(
    "/demand/{demand_id}/stock",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_stock_allocation(
    demand_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: DeleteStockAllocation = Depends(get_delete_stock_allocation_use_case),
) -> None:
    await use_case.execute(actor=actor, demand_item_id=demand_id)


# ── Quantity summary ──────────────────────────────────────────────────


@router.get("/demand/{demand_id}/summary", response_model=DemandSummaryResponse)
async def get_demand_summary(
    demand_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetDemandSummary = Depends(get_demand_summary_use_case),
) -> DemandSummaryResult:
    """
    Returns the full quantity breakdown for a demand item:
    total / allocated / delivered / remaining / unallocated / in_transit.
    """
    return await use_case.execute(demand_item_id=demand_id)


@router.post("/demands/summary-batch", response_model=dict[int, DemandSummaryResponse])
async def get_demand_summary_batch(
    demand_ids: list[int],
    _: User = Depends(get_current_active_user),
    use_case: GetDemandSummaryBatch = Depends(get_demand_summary_batch_use_case),
) -> dict[int, DemandSummaryResult]:
    """
    Batch quantity breakdown for multiple demand items.
    Returns a dict keyed by demand_item_id.
    Used by the frontend demand list to show remaining per row.
    """
    return await use_case.execute(demand_item_ids=demand_ids)


# ── Auto-allocation engine ────────────────────────────────────────────


@router.post("/demand/{demand_id}/auto-allocate", response_model=AutoAllocateResponse)
async def auto_allocate(
    demand_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: AutoAllocate = Depends(get_auto_allocate_use_case),
) -> AutoAllocateResult:
    """
    Greedy allocation engine: links this demand to open order items
    (same catalogue item) until the demand is fully covered or no
    candidates remain. Priority: ORDERED first, then earliest
    expected delivery, then most available quantity.
    """
    cmd = AutoAllocateCommand(demand_item_id=demand_id)
    return await use_case.execute(actor=actor, cmd=cmd)


@router.post(
    "/demand/{demand_id}/fulfill-from-stock",
    response_model=FulfillFromStockResponse,
)
async def fulfill_demand_from_stock(
    demand_id: int,
    body: FulfillFromStockRequest,
    actor: User = Depends(get_current_active_user),
    use_case: FulfillDemandFromStock = Depends(get_fulfill_demand_from_stock_use_case),
    idempotency: Idempotency = Depends(get_idempotency),
) -> FulfillFromStockResult:
    """
    Covers (part of) a demand directly from stock instead of via an order.
    No stock level is tracked here, that ledger lives in another service.
    With an Idempotency-Key, a retry is answered with what the demand holds
    from stock instead of taking the quantity again.
    """
    cmd = FulfillFromStockCommand(demand_item_id=demand_id, quantity=body.quantity)
    return await idempotency.run(
        lambda: use_case.execute(actor=actor, cmd=cmd),
        written=lambda done: demand_refs([done.demand_item_id]),
        replay=lambda _refs: use_case.replay(demand_id, body.quantity),
    )


# ── Delivery processing ───────────────────────────────────────────────


@router.put("/order-item/{order_item_id}/deliver", response_model=OrderItemResponse)
async def deliver_order_item(
    order_item_id: int,
    quantity: Annotated[Quantity | None, Query()] = None,
    storage_place: str | None = None,
    body: DeliveryRejectionRequest | None = None,
    actor: User = Depends(get_current_active_user),
    use_case: ProcessOrderItemDelivery = Depends(get_process_order_item_delivery_use_case),
    idempotency: Idempotency = Depends(get_idempotency),
    reader: GetOrders = Depends(get_order_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> OrderItemResult:
    """Book a delivery on one order line. It records `quantity` units (by
    default the remaining amount minus any rejected quantity in `body`),
    marks the line partially delivered or delivered, recomputes the
    coverage of the linked demands, fulfils the covered ones, rolls up the
    order status and queues the delivery notifications.

    `body` is needed only when the delivery also rejects pieces (reason,
    outcome and note). With outcome "lost" on a MADE line, the lot is
    closed short the way a scrap booking closes it, with a replacement lot
    unless `create_replacement` is false; on any other line the rejected
    quantity reduces demand coverage. With outcome "redeliver", only the
    stale expected_delivery_date is cleared.

    Only an ordered or partially delivered line takes a delivery, and only
    while its order is not canceled and, for a MADE line, its lot is not
    canceled; any other line answers 409. A quantity that is not a finite
    number answers 422.

    Requires receive:deliveries rather than write:orders or manage:orders,
    since recording a delivery is a warehouse action, not an order edit.
    With an Idempotency-Key, a retry is answered with the line instead of
    booking the delivery again.
    """
    rejection = body or DeliveryRejectionRequest()

    async def deliver() -> OrderItemResult:
        return await use_case.execute(
            actor=actor,
            order_item_id=order_item_id,
            quantity=quantity,
            storage_place=storage_place,
            quantity_rejected=rejection.quantity_rejected,
            rejection_reason=(
                rejection.rejection_reason.value if rejection.rejection_reason else None
            ),
            rejection_note=rejection.rejection_note,
            rejection_outcome=(
                rejection.rejection_outcome.value if rejection.rejection_outcome else None
            ),
            create_replacement=rejection.create_replacement,
            material=rejection.material(),
        )

    result = await idempotency.run(
        deliver,
        written=order_item_refs,
        replay=lambda refs: replay_order_item(reader, refs),
    )
    await actions.order_items([result], actor)
    return result
