"""
ProductionLot / LotStep / LotPosition endpoints. Prefix
`/production-lots`, flat kebab-case, matching this repo's actual
convention (no `/production/...` nesting exists anywhere); keeps the
prefix consistent with sibling routers like `/production-machines` and
`/production-orders`. Every lot, position, production order and demand
response carries the actions the reading user may take on it.
"""

from typing import Annotated

from fastapi import Depends
from fastapi import Query
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.fulfillment.adapters.inbound.api.deps.lots import get_add_lot_step_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.lots import get_append_lot_position_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.lots import get_approve_lot_source_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.lots import (
    get_assign_external_position_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.lots import get_auto_assign_lots_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.lots import get_cancel_lot_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.lots import get_complete_lot_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.lots import get_create_lot_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.lots import get_delete_lot_step_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.lots import get_hold_lot_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.lots import get_lot_demands_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.lots import get_lot_events_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.lots import (
    get_lot_material_receipts_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.lots import (
    get_lot_position_balances_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.lots import (
    get_lot_position_completions_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.lots import (
    get_lot_position_provisions_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.lots import get_lot_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.lots import get_lots_by_ids_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.lots import get_lots_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.lots import (
    get_record_lot_position_provision_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.lots import (
    get_regroup_lot_positions_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.lots import get_reject_lot_source_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.lots import get_reorder_lot_steps_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.lots import (
    get_replace_lot_structure_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.lots import get_resume_lot_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.lots import (
    get_switch_lot_material_source_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.lots import (
    get_unassign_external_position_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.lots import get_update_lot_step_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.lots import get_update_lot_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_assign_internal_position_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import get_lifecycle_actions
from src.modules.fulfillment.adapters.inbound.api.deps.production import get_replay_reads
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_scrap_lot_pieces_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import (
    AddLotStepRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import (
    AppendLotPositionRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import (
    ApproveLotSourceRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import (
    AssignExternalPositionRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import (
    AutoAssignLotGroupResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import (
    CancelLotRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import (
    CompleteLotRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import (
    HoldLotRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import (
    LotBulkReadParams,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import (
    LotCreateRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import (
    LotDemandResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import (
    LotEventResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import (
    LotFilterParams,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import (
    LotMaterialReceiptResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import (
    LotPositionBalanceResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import (
    LotPositionCompletionResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import (
    LotPositionProvisionResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import (
    LotPositionResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import LotResponse
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import (
    LotStepResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import (
    LotSummaryResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import (
    LotUpdateRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import (
    RecordLotPositionProvisionRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import (
    RegroupLotPositionsRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import (
    RejectLotSourceRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import (
    ReorderLotStepsRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import (
    ReplaceLotStructureRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import (
    ScrapLotPiecesRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import (
    ScrapPiecesResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import (
    SwitchLotMaterialSourceRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import (
    UpdateLotStepRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_order_schema import (
    AssignInternalPositionRequest,
)
from src.modules.fulfillment.application.dto.production_lot_dto import AddLotStepCommand
from src.modules.fulfillment.application.dto.production_lot_dto import AppendLotPositionCommand
from src.modules.fulfillment.application.dto.production_lot_dto import AssignExternalPositionCommand
from src.modules.fulfillment.application.dto.production_lot_dto import AutoAssignLotGroupResult
from src.modules.fulfillment.application.dto.production_lot_dto import CancelLotCommand
from src.modules.fulfillment.application.dto.production_lot_dto import CompleteLotCommand
from src.modules.fulfillment.application.dto.production_lot_dto import CreateLotCommand
from src.modules.fulfillment.application.dto.production_lot_dto import HoldLotCommand
from src.modules.fulfillment.application.dto.production_lot_dto import LotDemandResult
from src.modules.fulfillment.application.dto.production_lot_dto import LotEventResult
from src.modules.fulfillment.application.dto.production_lot_dto import LotMaterialReceiptResult
from src.modules.fulfillment.application.dto.production_lot_dto import LotPositionBalanceResult
from src.modules.fulfillment.application.dto.production_lot_dto import LotPositionCompletionResult
from src.modules.fulfillment.application.dto.production_lot_dto import LotPositionProvisionResult
from src.modules.fulfillment.application.dto.production_lot_dto import LotPositionResult
from src.modules.fulfillment.application.dto.production_lot_dto import LotResult
from src.modules.fulfillment.application.dto.production_lot_dto import LotStepResult
from src.modules.fulfillment.application.dto.production_lot_dto import LotSummaryResult
from src.modules.fulfillment.application.dto.production_lot_dto import (
    RecordLotPositionProvisionCommand,
)
from src.modules.fulfillment.application.dto.production_lot_dto import RegroupLotPositionsCommand
from src.modules.fulfillment.application.dto.production_lot_dto import RejectLotSourceCommand
from src.modules.fulfillment.application.dto.production_lot_dto import ReorderLotStepsCommand
from src.modules.fulfillment.application.dto.production_lot_dto import ReplaceLotStructureCommand
from src.modules.fulfillment.application.dto.production_lot_dto import ScrapLotPiecesCommand
from src.modules.fulfillment.application.dto.production_lot_dto import ScrapPiecesResult
from src.modules.fulfillment.application.dto.production_lot_dto import (
    SwitchLotMaterialSourceCommand,
)
from src.modules.fulfillment.application.dto.production_lot_dto import UpdateLotCommand
from src.modules.fulfillment.application.dto.production_lot_dto import UpdateLotStepCommand
from src.modules.fulfillment.application.dto.production_order_dto import (
    AssignInternalPositionCommand,
)
from src.modules.fulfillment.application.services.lifecycle_actions import LifecycleActions
from src.modules.fulfillment.application.services.replay_reads import ReplayReads
from src.modules.fulfillment.application.services.replay_reads import scrap_refs
from src.modules.fulfillment.application.use_cases.production_lot.approve_lot_source import (
    ApproveLotSource,
)
from src.modules.fulfillment.application.use_cases.production_lot.assign_external_position import (
    AssignExternalPosition,
)
from src.modules.fulfillment.application.use_cases.production_lot.assign_external_position import (
    UnassignExternalPosition,
)
from src.modules.fulfillment.application.use_cases.production_lot.auto_assign_lots import (
    AutoAssignLots,
)
from src.modules.fulfillment.application.use_cases.production_lot.create_lot import CreateLot
from src.modules.fulfillment.application.use_cases.production_lot.get_lot import GetLot
from src.modules.fulfillment.application.use_cases.production_lot.get_lot import GetLots
from src.modules.fulfillment.application.use_cases.production_lot.get_lot import GetLotsByIds
from src.modules.fulfillment.application.use_cases.production_lot.get_lot_completions import (
    GetLotPositionCompletions,
)
from src.modules.fulfillment.application.use_cases.production_lot.get_lot_demands import (
    GetLotDemands,
)
from src.modules.fulfillment.application.use_cases.production_lot.get_lot_events import GetLotEvents
from src.modules.fulfillment.application.use_cases.production_lot.get_lot_material_receipts import (
    GetLotMaterialReceipts,
)
from src.modules.fulfillment.application.use_cases.production_lot.get_lot_position_balances import (
    GetLotPositionBalances,
)
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import CancelLot
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import CompleteLot
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import HoldLot
from src.modules.fulfillment.application.use_cases.production_lot.lot_lifecycle import ResumeLot
from src.modules.fulfillment.application.use_cases.production_lot.lot_positions import (
    AppendLotPosition,
)
from src.modules.fulfillment.application.use_cases.production_lot.lot_positions import (
    RegroupLotPositions,
)
from src.modules.fulfillment.application.use_cases.production_lot.lot_steps import AddLotStep
from src.modules.fulfillment.application.use_cases.production_lot.lot_steps import DeleteLotStep
from src.modules.fulfillment.application.use_cases.production_lot.lot_steps import ReorderLotSteps
from src.modules.fulfillment.application.use_cases.production_lot.lot_steps import UpdateLotStep
from src.modules.fulfillment.application.use_cases.production_lot.record_lot_position_provision import (
    GetLotPositionProvisions,
)
from src.modules.fulfillment.application.use_cases.production_lot.record_lot_position_provision import (
    RecordLotPositionProvision,
)
from src.modules.fulfillment.application.use_cases.production_lot.reject_lot_source import (
    RejectLotSource,
)
from src.modules.fulfillment.application.use_cases.production_lot.replace_structure import (
    ReplaceLotStructure,
)
from src.modules.fulfillment.application.use_cases.production_lot.switch_lot_material_source import (
    SwitchLotMaterialSource,
)
from src.modules.fulfillment.application.use_cases.production_lot.update_lot import UpdateLot
from src.modules.fulfillment.application.use_cases.production_order.assign_internal_position import (
    AssignInternalPosition,
)
from src.modules.fulfillment.application.use_cases.production_order.scrap_lot_pieces import (
    ScrapLotPieces,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.idempotency import Idempotency
from src.modules.platform.adapters.inbound.api.idempotency import get_idempotency
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/", response_model=PageResponse[LotSummaryResponse])
async def read_lots(
    # Query-parameter model, not `Depends()`: only this binds the list
    # fields (`ids`, `statuses`) from repeated query keys. See the note on
    # DemandItemFilterParams in bought_item_schema.py.
    params: Annotated[LotFilterParams, Query()],
    actor: User = Depends(get_current_active_user),
    use_case: GetLots = Depends(get_lots_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> PageResponse[LotSummaryResult]:
    total, items = await use_case.execute(params.to_dto())
    await actions.lot_summaries(items, actor)
    return PageResponse(items=items, total=total, limit=params.limit, skip=params.skip or 0)


@router.post("/", response_model=LotResponse, status_code=status.HTTP_201_CREATED)
async def create_lot(
    body: LotCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateLot = Depends(get_create_lot_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> LotResult:
    cmd = CreateLotCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, cmd=cmd)
    await actions.lots([result], actor, production_orders=True)
    return result


@router.post("/auto-assign/preview", response_model=list[AutoAssignLotGroupResponse])
async def preview_auto_assign_lots(
    actor: User = Depends(get_current_active_user),
    use_case: AutoAssignLots = Depends(get_auto_assign_lots_use_case),
) -> list[AutoAssignLotGroupResult]:
    """Computes the (project, made item) lot groups Auto-Assign would
    create from currently-unallocated made-item demand, without
    committing anything."""
    return await use_case.preview(actor=actor)


@router.post("/auto-assign", response_model=list[LotResponse])
async def auto_assign_lots(
    actor: User = Depends(get_current_active_user),
    use_case: AutoAssignLots = Depends(get_auto_assign_lots_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> list[LotResult]:
    """Creates one lot per (project, made item) group covering every
    currently-unallocated made-item demand, 1:1 against its remaining
    quantity."""
    result = await use_case.execute(actor=actor)
    await actions.lots(result, actor, production_orders=True)
    return result


@router.get("/bulk", response_model=list[LotResponse])
async def read_lots_bulk(
    # Registered before /{lot_id} on purpose: FastAPI/Starlette match
    # routes in registration order, and /{lot_id} has no int converter, so
    # a bulk route added after it would never be reached (the path "bulk"
    # would bind to lot_id and 422 on int-conversion instead).
    params: Annotated[LotBulkReadParams, Query()],
    actor: User = Depends(get_current_active_user),
    use_case: GetLotsByIds = Depends(get_lots_by_ids_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> list[LotResult]:
    """Bulk full-lot read for a working set of ids (e.g. the schedule
    board hydrating full LotResponse objects, including positions with
    sequence, steps, and supplier_name, for several lots in one request
    instead of one GET /{lot_id} per lot, and unlike GET / can't be
    answered from the summary-shaped LotSummaryResponse). ids that don't
    exist are silently omitted from the result, never a 404, since a lot
    can vanish from a caller's working set (e.g. between it being listed
    and this refetch) without that being an error condition."""
    result = await use_case.execute(ids=params.ids, actor=actor)
    await actions.lots(result, actor)
    return result


@router.get("/{lot_id}", response_model=LotResponse)
async def read_lot(
    lot_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: GetLot = Depends(get_lot_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> LotResult:
    result = await use_case.execute(lot_id=lot_id, actor=actor)
    await actions.lots([result], actor)
    return result


@router.get("/{lot_id}/changelog", response_model=list[str])
async def read_lot_changelog(
    lot_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetLot = Depends(get_lot_use_case),
) -> list[str]:
    return await use_case.changelog(lot_id)


@router.get("/{lot_id}/completions", response_model=list[LotPositionCompletionResponse])
async def read_lot_completions(
    lot_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetLotPositionCompletions = Depends(get_lot_position_completions_use_case),
) -> list[LotPositionCompletionResult]:
    return await use_case.execute(lot_id=lot_id)


@router.get("/{lot_id}/position-balances", response_model=list[LotPositionBalanceResponse])
async def read_lot_position_balances(
    lot_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetLotPositionBalances = Depends(get_lot_position_balances_use_case),
) -> list[LotPositionBalanceResult]:
    """Where the pieces of each position went: arrived = good + scrap +
    rework + lost + WIP, with the ISO 22400 produced quantity."""
    return await use_case.execute(lot_id=lot_id)


@router.get("/{lot_id}/material-receipts", response_model=list[LotMaterialReceiptResponse])
async def read_lot_material_receipts(
    lot_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetLotMaterialReceipts = Depends(get_lot_material_receipts_use_case),
) -> list[LotMaterialReceiptResult]:
    """The receipts of the raw material the lot consumes, with the batch or
    heat number, delivery note and certificate each one recorded."""
    return await use_case.execute(lot_id=lot_id)


@router.get("/{lot_id}/events", response_model=list[LotEventResponse])
async def read_lot_events(
    lot_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetLotEvents = Depends(get_lot_events_use_case),
) -> list[LotEventResult]:
    return await use_case.execute(lot_id=lot_id)


@router.get("/{lot_id}/demands", response_model=list[LotDemandResponse])
async def read_lot_demands(
    lot_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: GetLotDemands = Depends(get_lot_demands_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> list[LotDemandResult]:
    result = await use_case.execute(lot_id=lot_id)
    await actions.made_demands(result, actor)
    return result


@router.patch("/{lot_id}", response_model=LotResponse)
async def update_lot(
    lot_id: int,
    body: LotUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateLot = Depends(get_update_lot_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> LotResult:
    cmd = UpdateLotCommand(**body.model_dump(exclude_unset=True))
    result = await use_case.execute(actor=actor, lot_id=lot_id, cmd=cmd)
    await actions.lots([result], actor, production_orders=True)
    return result


@router.put("/{lot_id}/material-source", response_model=LotResponse)
async def switch_lot_material_source(
    lot_id: int,
    body: SwitchLotMaterialSourceRequest,
    actor: User = Depends(get_current_active_user),
    use_case: SwitchLotMaterialSource = Depends(get_switch_lot_material_source_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> LotResult:
    cmd = SwitchLotMaterialSourceCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, lot_id=lot_id, cmd=cmd)
    await actions.lots([result], actor, production_orders=True)
    return result


@router.post("/{lot_id}/steps", response_model=LotStepResponse, status_code=status.HTTP_201_CREATED)
async def add_lot_step(
    lot_id: int,
    body: AddLotStepRequest,
    actor: User = Depends(get_current_active_user),
    use_case: AddLotStep = Depends(get_add_lot_step_use_case),
) -> LotStepResult:
    cmd = AddLotStepCommand(**body.model_dump())
    return await use_case.execute(actor=actor, lot_id=lot_id, cmd=cmd)


@router.patch("/{lot_id}/steps/{step_id}", response_model=LotStepResponse)
async def update_lot_step(
    lot_id: int,
    step_id: int,
    body: UpdateLotStepRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateLotStep = Depends(get_update_lot_step_use_case),
) -> LotStepResult:
    cmd = UpdateLotStepCommand(**body.model_dump())
    return await use_case.execute(actor=actor, step_id=step_id, cmd=cmd, lot_id=lot_id)


@router.delete("/{lot_id}/steps/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lot_step(
    lot_id: int,
    step_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: DeleteLotStep = Depends(get_delete_lot_step_use_case),
) -> None:
    await use_case.execute(actor=actor, step_id=step_id, lot_id=lot_id)


@router.put("/{lot_id}/steps/reorder", response_model=list[LotStepResponse])
async def reorder_lot_steps(
    lot_id: int,
    body: ReorderLotStepsRequest,
    actor: User = Depends(get_current_active_user),
    use_case: ReorderLotSteps = Depends(get_reorder_lot_steps_use_case),
) -> list[LotStepResult]:
    cmd = ReorderLotStepsCommand(**body.model_dump())
    return await use_case.execute(actor=actor, lot_id=lot_id, cmd=cmd)


@router.put("/{lot_id}/structure", response_model=list[LotPositionResponse])
async def replace_lot_structure(
    lot_id: int,
    body: ReplaceLotStructureRequest,
    actor: User = Depends(get_current_active_user),
    use_case: ReplaceLotStructure = Depends(get_replace_lot_structure_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> list[LotPositionResult]:
    cmd = ReplaceLotStructureCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, lot_id=lot_id, cmd=cmd)
    await actions.positions(result, actor)
    return result


@router.put("/{lot_id}/positions", response_model=list[LotPositionResponse])
async def regroup_lot_positions(
    lot_id: int,
    body: RegroupLotPositionsRequest,
    actor: User = Depends(get_current_active_user),
    use_case: RegroupLotPositions = Depends(get_regroup_lot_positions_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> list[LotPositionResult]:
    cmd = RegroupLotPositionsCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, lot_id=lot_id, cmd=cmd)
    await actions.positions(result, actor)
    return result


@router.post(
    "/{lot_id}/positions", response_model=LotPositionResponse, status_code=status.HTTP_201_CREATED
)
async def append_lot_position(
    lot_id: int,
    body: AppendLotPositionRequest,
    actor: User = Depends(get_current_active_user),
    use_case: AppendLotPosition = Depends(get_append_lot_position_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> LotPositionResult:
    cmd = AppendLotPositionCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, lot_id=lot_id, cmd=cmd)
    await actions.positions([result], actor)
    return result


@router.post("/{lot_id}/positions/{position_id}/assign", response_model=LotPositionResponse)
async def assign_external_position(
    lot_id: int,
    position_id: int,
    body: AssignExternalPositionRequest,
    actor: User = Depends(get_current_active_user),
    use_case: AssignExternalPosition = Depends(get_assign_external_position_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> LotPositionResult:
    cmd = AssignExternalPositionCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, lot_id=lot_id, position_id=position_id, cmd=cmd)
    await actions.positions([result], actor)
    return result


@router.post(
    "/{lot_id}/positions/{position_id}/assign-internal", response_model=LotPositionResponse
)
async def assign_internal_position(
    lot_id: int,
    position_id: int,
    body: AssignInternalPositionRequest,
    actor: User = Depends(get_current_active_user),
    use_case: AssignInternalPosition = Depends(get_assign_internal_position_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> LotPositionResult:
    cmd = AssignInternalPositionCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, lot_id=lot_id, position_id=position_id, cmd=cmd)
    await actions.positions([result], actor)
    return result


@router.delete("/{lot_id}/positions/{position_id}/assign", status_code=status.HTTP_204_NO_CONTENT)
async def unassign_external_position(
    lot_id: int,
    position_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: UnassignExternalPosition = Depends(get_unassign_external_position_use_case),
) -> None:
    await use_case.execute(actor=actor, lot_id=lot_id, position_id=position_id)


@router.post(
    "/{lot_id}/positions/{position_id}/provisions",
    response_model=LotPositionProvisionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def record_lot_position_provision(
    lot_id: int,
    position_id: int,
    body: RecordLotPositionProvisionRequest,
    actor: User = Depends(get_current_active_user),
    use_case: RecordLotPositionProvision = Depends(get_record_lot_position_provision_use_case),
) -> LotPositionProvisionResult:
    cmd = RecordLotPositionProvisionCommand(**body.model_dump())
    return await use_case.execute(actor=actor, lot_id=lot_id, position_id=position_id, cmd=cmd)


@router.get(
    "/{lot_id}/positions/{position_id}/provisions",
    response_model=list[LotPositionProvisionResponse],
)
async def read_lot_position_provisions(
    lot_id: int,
    position_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetLotPositionProvisions = Depends(get_lot_position_provisions_use_case),
) -> list[LotPositionProvisionResult]:
    return await use_case.execute(lot_id=lot_id, position_id=position_id)


@router.post("/{lot_id}/scrap", response_model=ScrapPiecesResponse)
async def scrap_lot_pieces(
    lot_id: int,
    body: ScrapLotPiecesRequest,
    actor: User = Depends(get_current_active_user),
    use_case: ScrapLotPieces = Depends(get_scrap_lot_pieces_use_case),
    idempotency: Idempotency = Depends(get_idempotency),
    replays: ReplayReads = Depends(get_replay_reads),
) -> ScrapPiecesResult:
    """Scraps pieces of the lot. With an Idempotency-Key, a retry is
    answered with the lot and the lots the disposition created instead of
    scrapping again."""
    cmd = ScrapLotPiecesCommand(**body.model_dump())
    return await idempotency.run(
        lambda: use_case.execute(actor=actor, lot_id=lot_id, cmd=cmd),
        written=scrap_refs,
        replay=replays.scrap,
    )


@router.post("/{lot_id}/cancel", response_model=LotResponse)
async def cancel_lot(
    lot_id: int,
    body: CancelLotRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CancelLot = Depends(get_cancel_lot_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> LotResult:
    cmd = CancelLotCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, lot_id=lot_id, cmd=cmd)
    await actions.lots([result], actor, production_orders=True)
    return result


@router.post("/{lot_id}/complete", response_model=LotResponse)
async def complete_lot(
    lot_id: int,
    body: CompleteLotRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CompleteLot = Depends(get_complete_lot_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> LotResult:
    cmd = CompleteLotCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, lot_id=lot_id, cmd=cmd)
    await actions.lots([result], actor, production_orders=True)
    return result


@router.post("/{lot_id}/hold", response_model=LotResponse)
async def hold_lot(
    lot_id: int,
    body: HoldLotRequest,
    actor: User = Depends(get_current_active_user),
    use_case: HoldLot = Depends(get_hold_lot_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> LotResult:
    cmd = HoldLotCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, lot_id=lot_id, cmd=cmd)
    await actions.lots([result], actor, production_orders=True)
    return result


@router.post("/{lot_id}/resume", response_model=LotResponse)
async def resume_lot(
    lot_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: ResumeLot = Depends(get_resume_lot_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> LotResult:
    result = await use_case.execute(actor=actor, lot_id=lot_id)
    await actions.lots([result], actor, production_orders=True)
    return result


@router.post("/{lot_id}/source/approve", response_model=LotResponse)
async def approve_lot_source(
    lot_id: int,
    body: ApproveLotSourceRequest,
    actor: User = Depends(get_current_active_user),
    use_case: ApproveLotSource = Depends(get_approve_lot_source_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> LotResult:
    """Releases a pending (or overturns a rejected) material source,
    creating its source item demand. Requires manage:lots, enforced in the
    use case (LotRules.assert_can_approve_source), not here."""
    result = await use_case.execute(
        actor=actor, lot_id=lot_id, expected_edit_version=body.expected_edit_version
    )
    await actions.lots([result], actor, production_orders=True)
    return result


@router.post("/{lot_id}/source/reject", response_model=LotResponse)
async def reject_lot_source(
    lot_id: int,
    body: RejectLotSourceRequest,
    actor: User = Depends(get_current_active_user),
    use_case: RejectLotSource = Depends(get_reject_lot_source_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> LotResult:
    """Rejects a pending material source with a required reason, no demand
    is created. Requires manage:lots, enforced in the use case."""
    cmd = RejectLotSourceCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, lot_id=lot_id, cmd=cmd)

    await actions.lots([result], actor, production_orders=True)
    return result
