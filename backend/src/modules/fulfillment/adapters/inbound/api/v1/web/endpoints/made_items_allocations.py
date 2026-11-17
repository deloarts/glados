"""
Made-item allocation endpoints, currently a stock-only surface:
  GET    /demand/{demand_id}                    list for demand
  PUT    /demand/{demand_id}/stock               set stock allocation quantity
  DELETE /demand/{demand_id}/stock               remove stock allocation
  GET    /demand/{demand_id}/summary             quantity breakdown
  POST   /demands/summary-batch                  batch quantity breakdown
  POST   /demand/{demand_id}/fulfill-from-stock  cover demand from stock

No create/update/delete-by-lot, no auto-allocate, no deliver route yet,
those would key off a production lot allocation, which isn't implemented.
"""

from fastapi import Depends
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.fulfillment.adapters.inbound.api.deps.allocations import (
    get_delete_made_item_stock_allocation_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.allocations import (
    get_fulfill_made_item_demand_from_stock_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.allocations import (
    get_made_item_get_allocations_for_demand_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.allocations import (
    get_update_made_item_stock_allocation_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_made_item_demand_summary_batch_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_made_item_demand_summary_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.idempotent_replays import demand_refs
from src.modules.fulfillment.adapters.inbound.api.schemas.made_item_allocation_schema import (
    MadeItemAllocationResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.made_item_allocation_schema import (
    MadeItemDemandSummaryResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.made_item_allocation_schema import (
    MadeItemFulfillFromStockRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.made_item_allocation_schema import (
    MadeItemFulfillFromStockResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.made_item_allocation_schema import (
    MadeItemStockAllocationUpdateRequest,
)
from src.modules.fulfillment.application.dto.made_item_allocation_dto import (
    FulfillMadeItemFromStockCommand,
)
from src.modules.fulfillment.application.dto.made_item_allocation_dto import (
    FulfillMadeItemFromStockResult,
)
from src.modules.fulfillment.application.dto.made_item_allocation_dto import (
    MadeItemAllocationResult,
)
from src.modules.fulfillment.application.dto.made_item_allocation_dto import (
    MadeItemDemandSummaryResult,
)
from src.modules.fulfillment.application.dto.made_item_allocation_dto import (
    UpdateMadeItemStockAllocationCommand,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.fulfill_from_stock import (
    FulfillDemandFromStock,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.get_allocations import (
    GetAllocationsForDemand,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.get_allocations import (
    GetDemandSummary,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.get_allocations import (
    GetDemandSummaryBatch,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.stock_allocation import (
    DeleteStockAllocation,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.stock_allocation import (
    UpdateStockAllocation,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.idempotency import Idempotency
from src.modules.platform.adapters.inbound.api.idempotency import get_idempotency
from src.modules.platform.domain.entities.user import User

router = APIRouter()


# ── Manual (stock) allocation CRUD ────────────────────────────────────


@router.get("/demand/{demand_id}", response_model=list[MadeItemAllocationResponse])
async def get_allocations_for_demand(
    demand_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetAllocationsForDemand = Depends(get_made_item_get_allocations_for_demand_use_case),
) -> list[MadeItemAllocationResult]:
    return await use_case.execute(demand_item_id=demand_id)


@router.put(
    "/demand/{demand_id}/stock",
    response_model=MadeItemAllocationResponse,
)
async def update_stock_allocation(
    demand_id: int,
    body: MadeItemStockAllocationUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateStockAllocation = Depends(get_update_made_item_stock_allocation_use_case),
) -> MadeItemAllocationResult:
    """Manually overrides the stock-sourced allocation quantity for a demand."""
    cmd = UpdateMadeItemStockAllocationCommand(**body.model_dump())
    return await use_case.execute(actor=actor, demand_item_id=demand_id, cmd=cmd)


@router.delete(
    "/demand/{demand_id}/stock",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_stock_allocation(
    demand_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: DeleteStockAllocation = Depends(get_delete_made_item_stock_allocation_use_case),
) -> None:
    await use_case.execute(actor=actor, demand_item_id=demand_id)


# ── Quantity summary ──────────────────────────────────────────────────


@router.get("/demand/{demand_id}/summary", response_model=MadeItemDemandSummaryResponse)
async def get_demand_summary(
    demand_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetDemandSummary = Depends(get_made_item_demand_summary_use_case),
) -> MadeItemDemandSummaryResult:
    """
    Returns the full quantity breakdown for a demand item:
    total / allocated / delivered / remaining / unallocated / in_transit.
    """
    return await use_case.execute(demand_item_id=demand_id)


@router.post("/demands/summary-batch", response_model=dict[int, MadeItemDemandSummaryResponse])
async def get_demand_summary_batch(
    demand_ids: list[int],
    _: User = Depends(get_current_active_user),
    use_case: GetDemandSummaryBatch = Depends(get_made_item_demand_summary_batch_use_case),
) -> dict[int, MadeItemDemandSummaryResult]:
    """
    Batch quantity breakdown for multiple demand items.
    Returns a dict keyed by demand_item_id.
    Used by the frontend demand list to show remaining per row.
    """
    return await use_case.execute(demand_item_ids=demand_ids)


# ── Stock fulfilment ───────────────────────────────────────────────────


@router.post(
    "/demand/{demand_id}/fulfill-from-stock",
    response_model=MadeItemFulfillFromStockResponse,
)
async def fulfill_demand_from_stock(
    demand_id: int,
    body: MadeItemFulfillFromStockRequest,
    actor: User = Depends(get_current_active_user),
    use_case: FulfillDemandFromStock = Depends(get_fulfill_made_item_demand_from_stock_use_case),
    idempotency: Idempotency = Depends(get_idempotency),
) -> FulfillMadeItemFromStockResult:
    """
    Covers (part of) a demand directly from stock instead of via a lot.
    No stock level is tracked here, that ledger lives in another service.
    With an Idempotency-Key, a retry is answered with what the demand holds
    from stock instead of taking the quantity again.
    """
    cmd = FulfillMadeItemFromStockCommand(demand_item_id=demand_id, quantity=body.quantity)
    return await idempotency.run(
        lambda: use_case.execute(actor=actor, cmd=cmd),
        written=lambda done: demand_refs([done.demand_item_id]),
        replay=lambda _refs: use_case.replay(demand_id, body.quantity),
    )
