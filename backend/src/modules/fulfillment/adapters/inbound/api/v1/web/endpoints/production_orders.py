"""
ProductionOrder endpoints. Prefix `/production-orders`, flat
kebab-case, matching this repo's established convention (see
production_lots.py's docstring). Assignment of a position to machines
stays under /production-lots/{lot_id}/positions/{position_id}/assign-internal
(mirrors where the EXTERNAL assign endpoint lives), everything here
operates on an already-created production order. Every production order
response carries the actions the reading user may take on it.
"""

from typing import Annotated

from fastapi import Depends
from fastapi import Query
from fastapi.routing import APIRouter

from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_cancel_production_order_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import get_lifecycle_actions
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_manufacturing_assessment_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_merge_production_orders_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_pause_production_order_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_production_order_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_production_orders_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_reassign_production_order_machine_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_record_manufacturing_assessment_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_record_production_order_completion_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_reorder_production_orders_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import get_replay_reads
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_reverse_production_order_completion_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_scrap_production_pieces_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_split_production_order_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_start_production_order_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.production import (
    get_update_production_order_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import (
    ScrapPiecesResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_order_schema import (
    CancelProductionOrderRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_order_schema import (
    ManufacturingAssessmentResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_order_schema import (
    MergeProductionOrdersRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_order_schema import (
    PauseProductionOrderRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_order_schema import (
    ProductionOrderFilterParams,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_order_schema import (
    ProductionOrderResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_order_schema import (
    ReassignProductionOrderMachineRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_order_schema import (
    RecordManufacturingAssessmentRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_order_schema import (
    RecordProductionOrderCompletionRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_order_schema import (
    ReorderProductionOrdersRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_order_schema import (
    ReverseCompletionRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_order_schema import (
    ScrapProductionPiecesRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_order_schema import (
    SplitProductionOrderRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_order_schema import (
    StartProductionOrderRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_order_schema import (
    UpdateProductionOrderRequest,
)
from src.modules.fulfillment.application.dto.production_lot_dto import ScrapPiecesResult
from src.modules.fulfillment.application.dto.production_order_dto import (
    CancelProductionOrderCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    ManufacturingAssessmentResult,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    MergeProductionOrdersCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import PauseProductionOrderCommand
from src.modules.fulfillment.application.dto.production_order_dto import ProductionOrderResult
from src.modules.fulfillment.application.dto.production_order_dto import (
    ReassignProductionOrderMachineCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    RecordManufacturingAssessmentCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    RecordProductionOrderCompletionCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    ReorderProductionOrdersCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import (
    ScrapProductionPiecesCommand,
)
from src.modules.fulfillment.application.dto.production_order_dto import SplitProductionOrderCommand
from src.modules.fulfillment.application.dto.production_order_dto import StartProductionOrderCommand
from src.modules.fulfillment.application.dto.production_order_dto import (
    UpdateProductionOrderCommand,
)
from src.modules.fulfillment.application.services.lifecycle_actions import LifecycleActions
from src.modules.fulfillment.application.services.replay_reads import PRODUCTION_ORDER
from src.modules.fulfillment.application.services.replay_reads import ReplayReads
from src.modules.fulfillment.application.services.replay_reads import created_lot_refs
from src.modules.fulfillment.application.services.replay_reads import scrap_refs
from src.modules.fulfillment.application.use_cases.production_order.get_manufacturing_assessment import (
    GetManufacturingAssessment,
)
from src.modules.fulfillment.application.use_cases.production_order.get_order import (
    GetProductionOrder,
)
from src.modules.fulfillment.application.use_cases.production_order.get_order import (
    GetProductionOrders,
)
from src.modules.fulfillment.application.use_cases.production_order.merge_production_orders import (
    MergeProductionOrders,
)
from src.modules.fulfillment.application.use_cases.production_order.production_order_lifecycle import (
    CancelProductionOrder,
)
from src.modules.fulfillment.application.use_cases.production_order.production_order_lifecycle import (
    PauseProductionOrder,
)
from src.modules.fulfillment.application.use_cases.production_order.production_order_lifecycle import (
    StartProductionOrder,
)
from src.modules.fulfillment.application.use_cases.production_order.reassign_production_order_machine import (
    ReassignProductionOrderMachine,
)
from src.modules.fulfillment.application.use_cases.production_order.record_manufacturing_assessment import (
    RecordManufacturingAssessment,
)
from src.modules.fulfillment.application.use_cases.production_order.record_production_order_completion import (
    RecordProductionOrderCompletion,
)
from src.modules.fulfillment.application.use_cases.production_order.reorder_production_orders import (
    ReorderProductionOrders,
)
from src.modules.fulfillment.application.use_cases.production_order.reverse_production_order_completion import (
    ReverseProductionOrderCompletion,
)
from src.modules.fulfillment.application.use_cases.production_order.scrap_production_pieces import (
    ScrapProductionPieces,
)
from src.modules.fulfillment.application.use_cases.production_order.split_production_order import (
    SplitProductionOrder,
)
from src.modules.fulfillment.application.use_cases.production_order.update_production_order import (
    UpdateProductionOrder,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.idempotency import Idempotency
from src.modules.platform.adapters.inbound.api.idempotency import get_idempotency
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.idempotency_key import ResourceRef
from src.modules.platform.domain.entities.user import User

router = APIRouter()


@router.get("/", response_model=PageResponse[ProductionOrderResponse])
async def read_production_orders(
    params: Annotated[ProductionOrderFilterParams, Query()],
    actor: User = Depends(get_current_active_user),
    use_case: GetProductionOrders = Depends(get_production_orders_use_case),
) -> PageResponse[ProductionOrderResult]:
    total, items = await use_case.execute(params.to_dto(), actor=actor)
    return PageResponse(items=items, total=total, limit=params.limit, skip=params.skip or 0)


@router.get("/{production_order_id}", response_model=ProductionOrderResponse)
async def read_production_order(
    production_order_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: GetProductionOrder = Depends(get_production_order_use_case),
) -> ProductionOrderResult:
    return await use_case.execute(production_order_id=production_order_id, actor=actor)


@router.patch("/{production_order_id}", response_model=ProductionOrderResponse)
async def update_production_order(
    production_order_id: int,
    body: UpdateProductionOrderRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateProductionOrder = Depends(get_update_production_order_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> ProductionOrderResult:
    cmd = UpdateProductionOrderCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, production_order_id=production_order_id, cmd=cmd)
    await actions.production_orders([result], actor)
    return result


@router.post("/{production_order_id}/split", response_model=list[ProductionOrderResponse])
async def split_production_order(
    production_order_id: int,
    body: SplitProductionOrderRequest,
    actor: User = Depends(get_current_active_user),
    use_case: SplitProductionOrder = Depends(get_split_production_order_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> list[ProductionOrderResult]:
    cmd = SplitProductionOrderCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, production_order_id=production_order_id, cmd=cmd)
    await actions.production_orders(result, actor)
    return result


@router.post("/merge", response_model=ProductionOrderResponse)
async def merge_production_orders(
    body: MergeProductionOrdersRequest,
    actor: User = Depends(get_current_active_user),
    use_case: MergeProductionOrders = Depends(get_merge_production_orders_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> ProductionOrderResult:
    cmd = MergeProductionOrdersCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, cmd=cmd)
    await actions.production_orders([result], actor)
    return result


@router.put("/{production_order_id}/machine", response_model=ProductionOrderResponse)
async def reassign_production_order_machine(
    production_order_id: int,
    body: ReassignProductionOrderMachineRequest,
    actor: User = Depends(get_current_active_user),
    use_case: ReassignProductionOrderMachine = Depends(
        get_reassign_production_order_machine_use_case
    ),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> ProductionOrderResult:
    cmd = ReassignProductionOrderMachineCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, production_order_id=production_order_id, cmd=cmd)
    await actions.production_orders([result], actor)
    return result


@router.put("/machines/unassigned/queue", response_model=list[ProductionOrderResponse])
async def reorder_unassigned_production_orders(
    body: ReorderProductionOrdersRequest,
    actor: User = Depends(get_current_active_user),
    use_case: ReorderProductionOrders = Depends(get_reorder_production_orders_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> list[ProductionOrderResult]:
    cmd = ReorderProductionOrdersCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, machine_id=None, cmd=cmd)
    await actions.production_orders(result, actor)
    return result


@router.put("/machines/{machine_id}/queue", response_model=list[ProductionOrderResponse])
async def reorder_production_orders(
    machine_id: int,
    body: ReorderProductionOrdersRequest,
    actor: User = Depends(get_current_active_user),
    use_case: ReorderProductionOrders = Depends(get_reorder_production_orders_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> list[ProductionOrderResult]:
    cmd = ReorderProductionOrdersCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, machine_id=machine_id, cmd=cmd)
    await actions.production_orders(result, actor)
    return result


@router.put("/machines/pools/{pool_id}/queue", response_model=list[ProductionOrderResponse])
async def reorder_pool_production_orders(
    pool_id: int,
    body: ReorderProductionOrdersRequest,
    actor: User = Depends(get_current_active_user),
    use_case: ReorderProductionOrders = Depends(get_reorder_production_orders_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> list[ProductionOrderResult]:
    """Reorder one machine pool's queue. A pool's queue is ordered on its
    own, apart from every machine's queue and from the unassigned queue."""
    cmd = ReorderProductionOrdersCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, machine_id=None, cmd=cmd, machine_pool_id=pool_id)
    await actions.production_orders(result, actor)
    return result


@router.post("/{production_order_id}/start", response_model=ProductionOrderResponse)
async def start_production_order(
    production_order_id: int,
    body: StartProductionOrderRequest,
    actor: User = Depends(get_current_active_user),
    use_case: StartProductionOrder = Depends(get_start_production_order_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> ProductionOrderResult:
    cmd = StartProductionOrderCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, production_order_id=production_order_id, cmd=cmd)
    await actions.production_orders([result], actor)
    return result


@router.post("/{production_order_id}/pause", response_model=ProductionOrderResponse)
async def pause_production_order(
    production_order_id: int,
    body: PauseProductionOrderRequest,
    actor: User = Depends(get_current_active_user),
    use_case: PauseProductionOrder = Depends(get_pause_production_order_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> ProductionOrderResult:
    cmd = PauseProductionOrderCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, production_order_id=production_order_id, cmd=cmd)
    await actions.production_orders([result], actor)
    return result


@router.post("/{production_order_id}/cancel", response_model=ProductionOrderResponse)
async def cancel_production_order(
    production_order_id: int,
    body: CancelProductionOrderRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CancelProductionOrder = Depends(get_cancel_production_order_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> ProductionOrderResult:
    cmd = CancelProductionOrderCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, production_order_id=production_order_id, cmd=cmd)
    await actions.production_orders([result], actor)
    return result


@router.post("/{production_order_id}/completions", response_model=ProductionOrderResponse)
async def record_production_order_completion(
    production_order_id: int,
    body: RecordProductionOrderCompletionRequest,
    actor: User = Depends(get_current_active_user),
    use_case: RecordProductionOrderCompletion = Depends(
        get_record_production_order_completion_use_case
    ),
    idempotency: Idempotency = Depends(get_idempotency),
    replays: ReplayReads = Depends(get_replay_reads),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> ProductionOrderResult:
    """Books a completion. With an Idempotency-Key, a retry is answered with
    the order and the lots its disposition created instead of booking the
    completion again."""
    cmd = RecordProductionOrderCompletionCommand(**body.model_dump())
    result = await idempotency.run(
        lambda: use_case.execute(actor=actor, production_order_id=production_order_id, cmd=cmd),
        written=lambda booked: [
            ResourceRef(PRODUCTION_ORDER, booked.id),
            *created_lot_refs(booked.created_lots),
        ],
        replay=replays.production_order,
    )
    await actions.production_orders([result], actor)
    return result


@router.post(
    "/{production_order_id}/completions/{completion_id}/reverse",
    response_model=ProductionOrderResponse,
)
async def reverse_production_order_completion(
    production_order_id: int,
    completion_id: int,
    body: ReverseCompletionRequest,
    actor: User = Depends(get_current_active_user),
    use_case: ReverseProductionOrderCompletion = Depends(
        get_reverse_production_order_completion_use_case
    ),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> ProductionOrderResult:
    """Takes back a mistaken completion with a reversal that books its
    pieces negative and keeps both rows. Needs manage:production_orders; a
    completion that rejected pieces, one already reversed, one on a finished
    lot and one whose pieces the next position already used answer 409."""
    result = await use_case.execute(actor, production_order_id, completion_id, body.reason)
    await actions.production_orders([result], actor)
    return result


@router.post("/{production_order_id}/scrap", response_model=ScrapPiecesResponse)
async def scrap_production_pieces(
    production_order_id: int,
    body: ScrapProductionPiecesRequest,
    actor: User = Depends(get_current_active_user),
    use_case: ScrapProductionPieces = Depends(get_scrap_production_pieces_use_case),
    idempotency: Idempotency = Depends(get_idempotency),
    replays: ReplayReads = Depends(get_replay_reads),
) -> ScrapPiecesResult:
    """Scraps pieces of the order. With an Idempotency-Key, a retry is
    answered with the lot and the lots the disposition created instead of
    scrapping again."""
    cmd = ScrapProductionPiecesCommand(production_order_id=production_order_id, **body.model_dump())
    return await idempotency.run(
        lambda: use_case.execute(actor=actor, cmd=cmd),
        written=scrap_refs,
        replay=replays.scrap,
    )


@router.post("/{production_order_id}/assessment", response_model=ManufacturingAssessmentResponse)
async def record_manufacturing_assessment(
    production_order_id: int,
    body: RecordManufacturingAssessmentRequest,
    actor: User = Depends(get_current_active_user),
    use_case: RecordManufacturingAssessment = Depends(get_record_manufacturing_assessment_use_case),
) -> ManufacturingAssessmentResult:
    cmd = RecordManufacturingAssessmentCommand(**body.model_dump())
    return await use_case.execute(actor=actor, production_order_id=production_order_id, cmd=cmd)


@router.get("/{production_order_id}/assessment", response_model=ManufacturingAssessmentResponse)
async def read_manufacturing_assessment(
    production_order_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetManufacturingAssessment = Depends(get_manufacturing_assessment_use_case),
) -> ManufacturingAssessmentResult:
    return await use_case.execute(production_order_id=production_order_id)
