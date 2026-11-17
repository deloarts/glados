"""
"Demand Source Item" pipeline endpoints: create a demand for a lot's source
item, list/inspect demands, manually override status, cancel. Allocation
(assign to an order, auto-allocate, fulfill from stock) lives under
source_item_allocations.py.

This triplication (bought/made/source demand + allocations) is
deliberate, not test/cleanup debt. See the rationale recorded in
bought_items_demand.py's docstring.
"""

from typing import Annotated

from fastapi import Depends
from fastapi import Query
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_cancel_source_item_demand_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_create_source_item_demand_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_set_source_item_demand_item_bucket_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_source_item_demand_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_source_item_demands_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_update_source_item_demand_status_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_update_source_item_demand_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import get_lifecycle_actions
from src.modules.fulfillment.adapters.inbound.api.schemas.source_item_demand_schema import (
    DemandItemBucketRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.source_item_demand_schema import (
    SourceItemDemandCreateRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.source_item_demand_schema import (
    SourceItemDemandFilterParams,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.source_item_demand_schema import (
    SourceItemDemandResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.source_item_demand_schema import (
    SourceItemDemandUpdateRequest,
)
from src.modules.fulfillment.application.dto.source_item_demand_dto import (
    CreateSourceItemDemandCommand,
)
from src.modules.fulfillment.application.dto.source_item_demand_dto import SourceItemDemandResult
from src.modules.fulfillment.application.dto.source_item_demand_dto import (
    UpdateSourceItemDemandCommand,
)
from src.modules.fulfillment.application.services.lifecycle_actions import LifecycleActions
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
    SetDemandItemBucket,
)
from src.modules.fulfillment.application.use_cases.source_item_demand.update_source_item_demand import (
    UpdateSourceItemDemand,
)
from src.modules.fulfillment.application.use_cases.source_item_demand.update_source_item_demand_status import (
    UpdateSourceItemDemandStatus,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/", response_model=PageResponse[SourceItemDemandResponse])
async def read_source_item_demands(
    # Query-parameter model, not `Depends()`: only this binds the list
    # field (`ids`) from repeated query keys. See the note on
    # DemandItemFilterParams in bought_item_schema.py.
    params: Annotated[SourceItemDemandFilterParams, Query()],
    actor: User = Depends(get_current_active_user),
    use_case: GetSourceItemDemands = Depends(get_source_item_demands_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> PageResponse[SourceItemDemandResult]:
    result = await use_case.execute(params.to_dto())
    await actions.source_demands(result.items, actor)
    return PageResponse.from_result(result, params)


@router.post("/", response_model=SourceItemDemandResponse, status_code=status.HTTP_201_CREATED)
async def create_source_item_demand(
    body: SourceItemDemandCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateSourceItemDemand = Depends(get_create_source_item_demand_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> SourceItemDemandResult:
    cmd = CreateSourceItemDemandCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, cmd=cmd)
    await actions.source_demands([result], actor)
    return result


@router.get("/{demand_id}", response_model=SourceItemDemandResponse)
async def read_source_item_demand(
    demand_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: GetSourceItemDemand = Depends(get_source_item_demand_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> SourceItemDemandResult:
    result = await use_case.execute(demand_id=demand_id)
    await actions.source_demands([result], actor)
    return result


@router.put("/{demand_id}", response_model=SourceItemDemandResponse)
async def update_source_item_demand(
    demand_id: int,
    body: SourceItemDemandUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateSourceItemDemand = Depends(get_update_source_item_demand_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> SourceItemDemandResult:
    cmd = UpdateSourceItemDemandCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, demand_id=demand_id, cmd=cmd)
    await actions.source_demands([result], actor)
    return result


@router.put("/{demand_id}/status", response_model=SourceItemDemandResponse)
async def update_source_item_demand_status(
    demand_id: int,
    new_status: str,
    cancel_lot: bool | None = None,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateSourceItemDemandStatus = Depends(get_update_source_item_demand_status_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> SourceItemDemandResult:
    """Sets one of the two statuses a demand takes by hand: `canceled`,
    which cancels it as POST /{demand_id}/cancel does, or `fulfilled`, which
    marks it fulfilled. Open, allocated and ordered follow from the demand's
    allocations and are refused with 422. Needs write:demand_items, and
    manage:demand_items for both values, since both are irreversible,
    instead of the lot permission the cancel route asks for. Requesting the
    status the demand already has returns it unchanged; canceling a
    fulfilled demand or marking a canceled one fulfilled answers 409.
    `cancel_lot` is the choice the cancel route takes for the lot."""
    result = await use_case.execute(
        actor=actor, demand_id=demand_id, new_status=new_status, cancel_lot=cancel_lot
    )
    await actions.source_demands([result], actor)
    return result


@router.put("/{demand_id}/bucket", response_model=SourceItemDemandResponse)
async def set_demand_item_bucket(
    demand_id: int,
    body: DemandItemBucketRequest,
    actor: User = Depends(get_current_active_user),
    use_case: SetDemandItemBucket = Depends(get_set_source_item_demand_item_bucket_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> SourceItemDemandResult:
    result = await use_case.execute(actor=actor, demand_id=demand_id, bucket_id=body.bucket_id)
    await actions.source_demands([result], actor)
    return result


@router.post("/{demand_id}/cancel", response_model=SourceItemDemandResponse)
async def cancel_source_item_demand(
    demand_id: int,
    cancel_lot: bool | None = None,
    actor: User = Depends(get_current_active_user),
    use_case: CancelSourceItemDemand = Depends(get_cancel_source_item_demand_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> SourceItemDemandResult:
    """Cancels the lot's raw material demand: records the cancel, releases
    every allocation it holds and unlinks it from its lot, so the lot can
    demand its material again. Needs the lot's update permission; a
    fulfilled or canceled demand answers 409, and so does the demand of a
    lot that has started production.

    While the lot has not ended, `cancel_lot` is required (422 without it):
    true cancels the lot as well, which needs the lot's cancel permission
    and settles the demand with it; false cancels only the demand, and the
    lot waits on raw material until its source is switched."""
    result = await use_case.execute(actor=actor, demand_id=demand_id, cancel_lot=cancel_lot)

    await actions.source_demands([result], actor)
    return result
