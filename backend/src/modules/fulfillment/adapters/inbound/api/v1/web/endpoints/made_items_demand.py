"""
Made-item demand endpoints, project needs for catalogue items. Mirrors
bought_items_demand.py, including the Excel batch-import routes (batch/
validate, batch/commit): a lookup-only importer keyed on part number +
revision instead of part number / order code + manufacturer, see
src/modules/fulfillment/application/use_cases/made_item_demand/batch_demand_items.py.

This triplication (bought/made/source demand and allocations) is
deliberate: the lifecycles genuinely differ. AllocationSource is
ORDER/STOCK here (awaiting OrderItem delivery) but LOT/STOCK on the
made-item side (awaiting ProductionLot completion); source-item demand
is one-shot and scoped to a single lot, bought demand is pooled and
reusable across many lots. Consolidating would require a discriminated
union or lowest-common-denominator interface. See
bought_items_demand.py for full rationale.
"""

from datetime import date
from datetime import tzinfo
from typing import Annotated

from fastapi import Depends
from fastapi import Query
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_cancel_made_item_demand_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_commit_batch_made_item_demands_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_create_made_item_demand_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_delete_made_item_demand_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.demands import get_made_item_demand_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_made_item_demands_pipeline_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.demands import get_made_item_demands_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_preview_cancel_made_item_demand_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_set_made_item_demand_item_bucket_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_update_made_item_demand_status_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_update_made_item_demand_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.demands import (
    get_validate_batch_made_item_demands_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import get_lifecycle_actions
from src.modules.fulfillment.adapters.inbound.api.idempotent_replays import DEMAND
from src.modules.fulfillment.adapters.inbound.api.idempotent_replays import demand_refs
from src.modules.fulfillment.adapters.inbound.api.idempotent_replays import ids_of
from src.modules.fulfillment.adapters.inbound.api.schemas.made_item_demand_schema import (
    CommitBatchMadeItemDemandsRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.made_item_demand_schema import (
    CommitBatchMadeItemDemandsResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.made_item_demand_schema import (
    DemandItemBucketRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.made_item_demand_schema import (
    MadeItemDemandCancelImpactResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.made_item_demand_schema import (
    MadeItemDemandCreateRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.made_item_demand_schema import (
    MadeItemDemandFilterParams,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.made_item_demand_schema import (
    MadeItemDemandResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.made_item_demand_schema import (
    MadeItemDemandUpdateRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.made_item_demand_schema import (
    MadeItemPipelinePageResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.made_item_demand_schema import (
    ValidateBatchMadeItemDemandsRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.made_item_demand_schema import (
    ValidateBatchMadeItemDemandsResponse,
)
from src.modules.fulfillment.application.dto.made_item_demand_dto import (
    CancelMadeItemDemandImpactResult,
)
from src.modules.fulfillment.application.dto.made_item_demand_dto import (
    CommitBatchMadeItemDemandsResult,
)
from src.modules.fulfillment.application.dto.made_item_demand_dto import CreateMadeItemDemandCommand
from src.modules.fulfillment.application.dto.made_item_demand_dto import MadeItemBatchDemandRowInput
from src.modules.fulfillment.application.dto.made_item_demand_dto import MadeItemDemandItemResult
from src.modules.fulfillment.application.dto.made_item_demand_dto import MadeItemPipelineResult
from src.modules.fulfillment.application.dto.made_item_demand_dto import UpdateMadeItemDemandCommand
from src.modules.fulfillment.application.dto.made_item_demand_dto import (
    ValidateBatchMadeItemDemandsResult,
)
from src.modules.fulfillment.application.services.lifecycle_actions import LifecycleActions
from src.modules.fulfillment.application.use_cases.made_item_demand.batch_demand_items import (
    CommitBatchMadeItemDemandRows,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.batch_demand_items import (
    ValidateBatchMadeItemDemandRows,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.cancel_demand import (
    CancelMadeItemDemand,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.cancel_demand import (
    PreviewCancelMadeItemDemand,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.create_demand_item import (
    CreateDemandItem,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.delete_demand_item import (
    DeleteDemandItem,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.get_demand_items import (
    GetDemandItem,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.get_demand_items import (
    GetDemandItems,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.get_demands_pipeline import (
    GetDemandsPipeline,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.set_demand_item_bucket import (
    SetDemandItemBucket,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.update_demand_item import (
    UpdateDemandItem,
)
from src.modules.fulfillment.application.use_cases.made_item_demand.update_demand_item_status import (
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


@router.get("/", response_model=PageResponse[MadeItemDemandResponse])
async def read_demand_items(
    # Query-parameter model, not `Depends()`: only this binds the list
    # fields (`ids`, `statuses`) from repeated query keys, see the note on
    # DemandItemFilterParams in bought_item_schema.py.
    params: Annotated[MadeItemDemandFilterParams, Query()],
    actor: User = Depends(get_current_active_user),
    use_case: GetDemandItems = Depends(get_made_item_demands_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> PageResponse[MadeItemDemandItemResult]:
    result = await use_case.execute(params.to_dto())
    await actions.made_demands(result.items, actor)
    return PageResponse.from_result(result, params)


@router.post("/", response_model=MadeItemDemandResponse, status_code=status.HTTP_201_CREATED)
async def create_demand_item(
    body: MadeItemDemandCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateDemandItem = Depends(get_create_made_item_demand_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> MadeItemDemandItemResult:
    cmd = CreateMadeItemDemandCommand(**body.model_dump(exclude_unset=True))
    result = await use_case.execute(actor=actor, cmd=cmd)
    await actions.made_demands([result], actor)
    return result


@router.get("/pipeline", response_model=MadeItemPipelinePageResponse)
async def read_demands_pipeline(
    terminal_since: date | None = Query(
        default=None,
        description="Include terminal (fulfilled/canceled) demands changed on or after this "
        "date. Defaults to the start of the current ISO week in the tenant's timezone.",
    ),
    _: User = Depends(get_current_active_user),
    zone: tzinfo = Depends(get_tenant_zone),
    use_case: GetDemandsPipeline = Depends(get_made_item_demands_pipeline_use_case),
) -> MadeItemPipelineResult:
    return await use_case.execute(
        terminal_since=terminal_since or start_of_iso_week(today_in(zone))
    )


@router.get("/{demand_id}", response_model=MadeItemDemandResponse)
async def read_demand_item(
    demand_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: GetDemandItem = Depends(get_made_item_demand_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> MadeItemDemandItemResult:
    result = await use_case.execute(demand_id=demand_id)
    await actions.made_demands([result], actor)
    return result


@router.get("/{demand_id}/changelog", response_model=list[str])
async def read_demand_item_changelog(
    demand_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetDemandItem = Depends(get_made_item_demand_use_case),
) -> list[str]:
    return await use_case.changelog(demand_id)


@router.put("/{demand_id}", response_model=MadeItemDemandResponse)
async def update_demand_item(
    demand_id: int,
    body: MadeItemDemandUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateDemandItem = Depends(get_update_made_item_demand_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> MadeItemDemandItemResult:
    cmd = UpdateMadeItemDemandCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, demand_id=demand_id, cmd=cmd)
    await actions.made_demands([result], actor)
    return result


@router.put("/{demand_id}/status", response_model=MadeItemDemandResponse)
async def update_demand_item_status(
    demand_id: int,
    new_status: str,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateDemandItemStatus = Depends(get_update_made_item_demand_status_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> MadeItemDemandItemResult:
    """Sets one of the two statuses a demand takes by hand: `canceled`,
    which cancels it as POST /{demand_id}/cancel does, or `fulfilled`, which
    marks it fulfilled. Open, allocated and ordered follow from the demand's
    allocations and are refused with 422. Needs write:demand_items, and
    manage:demand_items for both values, since both are irreversible.
    Requesting the status the demand already has returns it unchanged;
    canceling a fulfilled demand or marking a canceled one fulfilled
    answers 409."""
    result = await use_case.execute(actor=actor, demand_id=demand_id, new_status=new_status)
    await actions.made_demands([result], actor)
    return result


@router.post("/{demand_id}/cancel", response_model=MadeItemDemandResponse)
async def cancel_demand_item(
    demand_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: CancelMadeItemDemand = Depends(get_cancel_made_item_demand_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> MadeItemDemandItemResult:
    """Cancels the demand with everything that exists only because of it,
    as GET /{demand_id}/cancel-impact lists it: the lots built for it are
    canceled with their work, a lot shared with other demands only loses
    this demand's allocation, and its stock allocation is released. Needs
    write:demand_items and manage:demand_items; a fulfilled or canceled
    demand answers 409."""
    result = await use_case.execute(actor=actor, demand_id=demand_id)
    await actions.made_demands([result], actor)
    return result


@router.put("/{demand_id}/bucket", response_model=MadeItemDemandResponse)
async def set_demand_item_bucket(
    demand_id: int,
    body: DemandItemBucketRequest,
    actor: User = Depends(get_current_active_user),
    use_case: SetDemandItemBucket = Depends(get_set_made_item_demand_item_bucket_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> MadeItemDemandItemResult:
    result = await use_case.execute(actor=actor, demand_id=demand_id, bucket_id=body.bucket_id)
    await actions.made_demands([result], actor)
    return result


@router.get("/{demand_id}/cancel-impact", response_model=MadeItemDemandCancelImpactResponse)
async def read_demand_item_cancel_impact(
    demand_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: PreviewCancelMadeItemDemand = Depends(get_preview_cancel_made_item_demand_use_case),
) -> CancelMadeItemDemandImpactResult:
    """Everything canceling this demand would take down with it, the lots
    allocated to it, their raw-material demands, and the production orders
    / supplier order items behind them. Read-only: nothing is canceled
    until POST /{demand_id}/cancel (or the status route with `canceled`) is
    called."""
    return await use_case.execute(actor=actor, demand_id=demand_id)


@router.delete("/{demand_id}", response_model=MadeItemDemandResponse)
async def delete_demand_item(
    demand_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: DeleteDemandItem = Depends(get_delete_made_item_demand_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> MadeItemDemandItemResult:
    """Deletes a demand that holds no allocation. A demand with allocations
    answers 409 and is canceled instead, which releases them."""
    result = await use_case.execute(actor=actor, demand_id=demand_id)
    await actions.made_demands([result], actor)
    return result


@router.post("/batch/validate", response_model=ValidateBatchMadeItemDemandsResponse)
async def validate_batch_made_item_demands(
    body: ValidateBatchMadeItemDemandsRequest,
    actor: User = Depends(get_current_active_user),
    use_case: ValidateBatchMadeItemDemandRows = Depends(
        get_validate_batch_made_item_demands_use_case
    ),
) -> ValidateBatchMadeItemDemandsResult:
    rows = [MadeItemBatchDemandRowInput(**row.model_dump()) for row in body.rows]
    return await use_case.execute(actor=actor, rows=rows)


@router.post(
    "/batch/commit",
    response_model=CommitBatchMadeItemDemandsResponse,
    status_code=status.HTTP_201_CREATED,
)
async def commit_batch_made_item_demands(
    body: CommitBatchMadeItemDemandsRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CommitBatchMadeItemDemandRows = Depends(get_commit_batch_made_item_demands_use_case),
    idempotency: Idempotency = Depends(get_idempotency),
) -> CommitBatchMadeItemDemandsResult:
    """Creates the demands of an import. With an Idempotency-Key, a retry is
    answered with the demands the first request created instead of creating
    them again."""
    rows = [MadeItemBatchDemandRowInput(**row.model_dump()) for row in body.rows]

    async def replay(refs: tuple[ResourceRef, ...]) -> CommitBatchMadeItemDemandsResult:
        return CommitBatchMadeItemDemandsResult(created_demand_ids=ids_of(refs, DEMAND))

    return await idempotency.run(
        lambda: use_case.execute(actor=actor, rows=rows),
        written=lambda done: demand_refs(done.created_demand_ids),
        replay=replay,
    )
