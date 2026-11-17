"""
Demand item endpoints, project needs for catalogue items.

This module and made_items_demand.py/source_item_demands.py (+ the
matching *_allocations.py trio) are a deliberate triplication, not an
oversight. The lifecycles genuinely differ: AllocationSource is
ORDER/STOCK here (an allocation awaits an OrderItem's delivery) but
LOT/STOCK on the made-item side (an allocation awaits a ProductionLot's
completion); source-item demand is one-shot and scoped to a single lot
(SourceItemDemandItem's docstring), bought demand is pooled and
reusable across many lots. Consolidating would need a discriminated
union or a lowest-common-denominator interface for a case with real,
load-bearing divergence.
"""

from datetime import date
from datetime import tzinfo
from typing import Annotated

from fastapi import Depends
from fastapi import Query
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_cancel_demand_item_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_commit_batch_demands_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_create_demand_item_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_delete_demand_item_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.demands import get_demand_item_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.demands import get_demand_items_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.demands import get_demands_pipeline_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_set_demand_item_bucket_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_update_demand_item_status_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_update_demand_item_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_validate_batch_demands_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import get_lifecycle_actions
from src.modules.fulfillment.adapters.inbound.api.idempotent_replays import DEMAND
from src.modules.fulfillment.adapters.inbound.api.idempotent_replays import demand_refs
from src.modules.fulfillment.adapters.inbound.api.idempotent_replays import ids_of
from src.modules.fulfillment.adapters.inbound.api.schemas.bought_item_demand_schema import (
    CommitBatchDemandsRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.bought_item_demand_schema import (
    CommitBatchDemandsResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.bought_item_demand_schema import (
    DemandItemBucketRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.bought_item_demand_schema import (
    DemandItemCreateRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.bought_item_demand_schema import (
    DemandItemFilterParams,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.bought_item_demand_schema import (
    DemandItemResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.bought_item_demand_schema import (
    DemandItemUpdateRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.bought_item_demand_schema import (
    PipelinePageResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.bought_item_demand_schema import (
    ValidateBatchDemandsRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.bought_item_demand_schema import (
    ValidateBatchDemandsResponse,
)
from src.modules.fulfillment.application.dto.bought_item_demand_dto import BatchDemandRowInput
from src.modules.fulfillment.application.dto.bought_item_demand_dto import CommitBatchDemandsResult
from src.modules.fulfillment.application.dto.bought_item_demand_dto import CreateDemandItemCommand
from src.modules.fulfillment.application.dto.bought_item_demand_dto import DemandItemResult
from src.modules.fulfillment.application.dto.bought_item_demand_dto import PipelineResult
from src.modules.fulfillment.application.dto.bought_item_demand_dto import UpdateDemandItemCommand
from src.modules.fulfillment.application.dto.bought_item_demand_dto import (
    ValidateBatchDemandsResult,
)
from src.modules.fulfillment.application.services.lifecycle_actions import LifecycleActions
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
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.deps.misc import get_tenant_zone
from src.modules.platform.adapters.inbound.api.idempotency import Idempotency
from src.modules.platform.adapters.inbound.api.idempotency import get_idempotency
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.idempotency_key import ResourceRef
from src.modules.platform.domain.entities.user import User
from src.shared_kernel.domain.services.clock import start_of_iso_week
from src.shared_kernel.domain.services.clock import today_in

router = APIRouter()


@router.get("/", response_model=PageResponse[DemandItemResponse])
async def read_demand_items(
    # Query-parameter model, not `Depends()`: see the note on
    # DemandItemFilterParams for why (list fields).
    params: Annotated[DemandItemFilterParams, Query()],
    actor: User = Depends(get_current_active_user),
    use_case: GetDemandItems = Depends(get_demand_items_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> PageResponse[DemandItemResult]:
    result = await use_case.execute(params.to_dto())
    await actions.bought_demands(result.items, actor)
    return PageResponse.from_result(result, params)


@router.post("/", response_model=DemandItemResponse, status_code=status.HTTP_201_CREATED)
async def create_demand_item(
    body: DemandItemCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateDemandItem = Depends(get_create_demand_item_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> DemandItemResult:
    cmd = CreateDemandItemCommand(**body.model_dump(exclude_unset=True))
    result = await use_case.execute(actor=actor, cmd=cmd)
    await actions.bought_demands([result], actor)
    return result


@router.get("/pipeline", response_model=PipelinePageResponse)
async def read_demands_pipeline(
    terminal_since: date | None = Query(
        default=None,
        description="Include terminal (fulfilled/canceled) demands changed on or after this "
        "date. Defaults to the start of the current ISO week in the tenant's timezone.",
    ),
    _: User = Depends(get_current_active_user),
    zone: tzinfo = Depends(get_tenant_zone),
    use_case: GetDemandsPipeline = Depends(get_demands_pipeline_use_case),
) -> PipelineResult:
    return await use_case.execute(
        terminal_since=terminal_since or start_of_iso_week(today_in(zone))
    )


@router.get("/{demand_id}", response_model=DemandItemResponse)
async def read_demand_item(
    demand_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: GetDemandItem = Depends(get_demand_item_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> DemandItemResult:
    result = await use_case.execute(demand_id=demand_id)
    await actions.bought_demands([result], actor)
    return result


@router.get("/{demand_id}/changelog", response_model=list[str])
async def read_demand_item_changelog(
    demand_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetDemandItem = Depends(get_demand_item_use_case),
) -> list[str]:
    return await use_case.changelog(demand_id)


@router.put("/{demand_id}", response_model=DemandItemResponse)
async def update_demand_item(
    demand_id: int,
    body: DemandItemUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateDemandItem = Depends(get_update_demand_item_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> DemandItemResult:
    cmd = UpdateDemandItemCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, demand_id=demand_id, cmd=cmd)
    await actions.bought_demands([result], actor)
    return result


@router.put("/{demand_id}/status", response_model=DemandItemResponse)
async def update_demand_item_status(
    demand_id: int,
    new_status: str,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateDemandItemStatus = Depends(get_update_demand_item_status_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> DemandItemResult:
    """Sets one of the two statuses a demand takes by hand: `canceled`,
    which cancels it as POST /{demand_id}/cancel does, or `fulfilled`, which
    marks it fulfilled. Open, allocated and ordered follow from the demand's
    allocations and are refused with 422. Needs write:demand_items, and
    manage:demand_items for both values, since both are irreversible.
    Requesting the status the demand already has returns it unchanged;
    canceling a fulfilled demand or marking a canceled one fulfilled
    answers 409."""
    result = await use_case.execute(actor=actor, demand_id=demand_id, new_status=new_status)
    await actions.bought_demands([result], actor)
    return result


@router.post("/{demand_id}/cancel", response_model=DemandItemResponse)
async def cancel_demand_item(
    demand_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: CancelDemandItem = Depends(get_cancel_demand_item_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> DemandItemResult:
    """Cancels the demand: records the cancel, releases every allocation it
    holds on order lines and from stock, and notifies its creator when
    someone else canceled it. Needs write:demand_items and
    manage:demand_items; a fulfilled or canceled demand answers 409."""
    result = await use_case.execute(actor=actor, demand_id=demand_id)
    await actions.bought_demands([result], actor)
    return result


@router.put("/{demand_id}/bucket", response_model=DemandItemResponse)
async def set_demand_item_bucket(
    demand_id: int,
    body: DemandItemBucketRequest,
    actor: User = Depends(get_current_active_user),
    use_case: SetDemandItemBucket = Depends(get_set_demand_item_bucket_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> DemandItemResult:
    result = await use_case.execute(actor=actor, demand_id=demand_id, bucket_id=body.bucket_id)
    await actions.bought_demands([result], actor)
    return result


@router.delete("/{demand_id}", response_model=DemandItemResponse)
async def delete_demand_item(
    demand_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: DeleteDemandItem = Depends(get_delete_demand_item_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> DemandItemResult:
    """Deletes a demand that holds no allocation. A demand with allocations
    answers 409 and is canceled instead, which releases them."""
    result = await use_case.execute(actor=actor, demand_id=demand_id)
    await actions.bought_demands([result], actor)
    return result


@router.post("/batch/validate", response_model=ValidateBatchDemandsResponse)
async def validate_batch_demands(
    body: ValidateBatchDemandsRequest,
    actor: User = Depends(get_current_active_user),
    use_case: ValidateBatchDemandRows = Depends(get_validate_batch_demands_use_case),
) -> ValidateBatchDemandsResult:
    rows = [BatchDemandRowInput(**row.model_dump()) for row in body.rows]
    return await use_case.execute(actor=actor, rows=rows)


@router.post(
    "/batch/commit", response_model=CommitBatchDemandsResponse, status_code=status.HTTP_201_CREATED
)
async def commit_batch_demands(
    body: CommitBatchDemandsRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CommitBatchDemandRows = Depends(get_commit_batch_demands_use_case),
    idempotency: Idempotency = Depends(get_idempotency),
) -> CommitBatchDemandsResult:
    """Creates the demands of an import. With an Idempotency-Key, a retry is
    answered with the demands the first request created instead of creating
    them again."""
    rows = [BatchDemandRowInput(**row.model_dump()) for row in body.rows]

    async def replay(refs: tuple[ResourceRef, ...]) -> CommitBatchDemandsResult:
        return CommitBatchDemandsResult(created_demand_ids=ids_of(refs, DEMAND))

    return await idempotency.run(
        lambda: use_case.execute(actor=actor, rows=rows),
        written=lambda done: demand_refs(done.created_demand_ids),
        replay=replay,
    )
