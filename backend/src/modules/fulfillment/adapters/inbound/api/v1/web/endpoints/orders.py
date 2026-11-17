"""
Order and order item endpoints.
Orders group one or more order items sent to a supplier. Every order and
order item response carries the actions the reading user may take on it.
"""

from fastapi import Depends
from fastapi import Query
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.fulfillment.adapters.inbound.api.deps.orders import get_cancel_order_item_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.orders import get_cancel_order_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.orders import (
    get_close_order_item_short_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.orders import (
    get_correct_order_item_delivery_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.orders import get_create_order_item_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.orders import get_create_order_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.orders import (
    get_deliver_all_order_items_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.orders import (
    get_mark_all_order_items_ordered_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.orders import (
    get_mark_all_order_items_requested_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.orders import (
    get_mark_order_item_ordered_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.orders import (
    get_mark_order_item_ready_for_pickup_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.orders import (
    get_mark_order_item_requested_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.orders import get_move_order_item_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.orders import get_order_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.orders import get_orders_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.orders import get_remove_order_item_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.orders import get_reopen_order_item_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.orders import get_request_order_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.orders import (
    get_set_order_extra_costs_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.orders import get_submit_order_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.orders import get_update_order_item_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.orders import get_update_order_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.production import get_lifecycle_actions
from src.modules.fulfillment.adapters.inbound.api.idempotent_replays import deliver_all_refs
from src.modules.fulfillment.adapters.inbound.api.idempotent_replays import order_item_refs
from src.modules.fulfillment.adapters.inbound.api.idempotent_replays import replay_deliver_all
from src.modules.fulfillment.adapters.inbound.api.idempotent_replays import replay_order_item
from src.modules.fulfillment.adapters.inbound.api.schemas.order_schema import CorrectDeliveryRequest
from src.modules.fulfillment.adapters.inbound.api.schemas.order_schema import (
    DeliverAllOrderItemsRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.order_schema import DeliverAllResponse
from src.modules.fulfillment.adapters.inbound.api.schemas.order_schema import MoveOrderItemRequest
from src.modules.fulfillment.adapters.inbound.api.schemas.order_schema import OrderCreateRequest
from src.modules.fulfillment.adapters.inbound.api.schemas.order_schema import (
    OrderExtraCostsUpdateRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.order_schema import OrderFilterParams
from src.modules.fulfillment.adapters.inbound.api.schemas.order_schema import OrderItemCreateRequest
from src.modules.fulfillment.adapters.inbound.api.schemas.order_schema import OrderItemResponse
from src.modules.fulfillment.adapters.inbound.api.schemas.order_schema import OrderItemUpdateRequest
from src.modules.fulfillment.adapters.inbound.api.schemas.order_schema import OrderResponse
from src.modules.fulfillment.adapters.inbound.api.schemas.order_schema import OrderUpdateRequest
from src.modules.fulfillment.application.dto.order_dto import CreateOrderCommand
from src.modules.fulfillment.application.dto.order_dto import CreateOrderItemCommand
from src.modules.fulfillment.application.dto.order_dto import DeliverAllResult
from src.modules.fulfillment.application.dto.order_dto import OrderItemResult
from src.modules.fulfillment.application.dto.order_dto import OrderResult
from src.modules.fulfillment.application.dto.order_dto import SetOrderExtraCostsCommand
from src.modules.fulfillment.application.dto.order_dto import UpdateOrderCommand
from src.modules.fulfillment.application.dto.order_dto import UpdateOrderItemCommand
from src.modules.fulfillment.application.services.lifecycle_actions import LifecycleActions
from src.modules.fulfillment.application.use_cases.order.cancel_order_item import CancelOrderItem
from src.modules.fulfillment.application.use_cases.order.close_order_item_short import (
    CloseOrderItemShort,
)
from src.modules.fulfillment.application.use_cases.order.correct_order_item_delivery import (
    CorrectOrderItemDelivery,
)
from src.modules.fulfillment.application.use_cases.order.create_order import CreateOrder
from src.modules.fulfillment.application.use_cases.order.create_order_item import CreateOrderItem
from src.modules.fulfillment.application.use_cases.order.delete_order_item import RemoveOrderItem
from src.modules.fulfillment.application.use_cases.order.get_order import GetOrders
from src.modules.fulfillment.application.use_cases.order.mark_order_item_ordered import (
    MarkAllOrderItemsOrdered,
)
from src.modules.fulfillment.application.use_cases.order.mark_order_item_ordered import (
    MarkAllOrderItemsRequested,
)
from src.modules.fulfillment.application.use_cases.order.mark_order_item_ordered import (
    MarkOrderItemOrdered,
)
from src.modules.fulfillment.application.use_cases.order.mark_order_item_ordered import (
    MarkOrderItemRequested,
)
from src.modules.fulfillment.application.use_cases.order.mark_order_item_ready_for_pickup import (
    MarkOrderItemReadyForPickup,
)
from src.modules.fulfillment.application.use_cases.order.move_order_item import MoveOrderItem
from src.modules.fulfillment.application.use_cases.order.process_order_item_delivery import (
    DeliverAllOrderItems,
)
from src.modules.fulfillment.application.use_cases.order.reopen_order_item import ReopenOrderItem
from src.modules.fulfillment.application.use_cases.order.set_order_extra_costs import (
    SetOrderExtraCosts,
)
from src.modules.fulfillment.application.use_cases.order.update_order import CancelOrder
from src.modules.fulfillment.application.use_cases.order.update_order import RequestOrder
from src.modules.fulfillment.application.use_cases.order.update_order import SubmitOrder
from src.modules.fulfillment.application.use_cases.order.update_order import UpdateOrder
from src.modules.fulfillment.application.use_cases.order.update_order_item import UpdateOrderItem
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.idempotency import Idempotency
from src.modules.platform.adapters.inbound.api.idempotency import get_idempotency
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.user import User

router = APIRouter()


# ── Orders ────────────────────────────────────────────────────────────


@router.get("/", response_model=PageResponse[OrderResponse])
async def read_orders(
    params: OrderFilterParams = Depends(),
    actor: User = Depends(get_current_active_user),
    use_case: GetOrders = Depends(get_orders_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> PageResponse[OrderResult]:
    result = await use_case.get_many(params.to_dto())
    await actions.orders(result.items, actor)
    return PageResponse.from_result(result, params)


@router.post("/", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    body: OrderCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateOrder = Depends(get_create_order_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> OrderResult:
    cmd = CreateOrderCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, cmd=cmd)
    await actions.orders([result], actor)
    return result


@router.get("/{order_id}", response_model=OrderResponse)
async def read_order(
    order_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: GetOrders = Depends(get_order_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> OrderResult:
    result = await use_case.get_one(order_id=order_id)
    await actions.orders([result], actor)
    return result


@router.put("/{order_id}", response_model=OrderResponse)
async def update_order(
    order_id: int,
    body: OrderUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateOrder = Depends(get_update_order_use_case),
    reader: GetOrders = Depends(get_order_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> OrderResult:
    cmd = UpdateOrderCommand(**body.model_dump(exclude_unset=True))
    await use_case.execute(actor=actor, order_id=order_id, cmd=cmd)
    # Read back with its lines, which the write itself does not return.
    result = await reader.get_one(order_id=order_id)
    await actions.orders([result], actor)
    return result


@router.put("/{order_id}/extra-costs", response_model=OrderResponse)
async def set_order_extra_costs(
    order_id: int,
    body: OrderExtraCostsUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: SetOrderExtraCosts = Depends(get_set_order_extra_costs_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> OrderResult:
    """Replaces the order's extra costs (shipping, packaging, surcharges, a
    discount) with the list sent, in that order. Needs write:orders, and
    manage:orders once the order is past REQUESTED; a canceled order takes
    no change. Answers the order with its lines and totals."""
    cmd = SetOrderExtraCostsCommand(**body.model_dump())
    result = await use_case.execute(actor=actor, order_id=order_id, cmd=cmd)
    await actions.orders([result], actor)
    return result


@router.put("/{order_id}/request", response_model=OrderResponse)
async def request_order(
    order_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: RequestOrder = Depends(get_request_order_use_case),
    reader: GetOrders = Depends(get_order_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> OrderResult:
    """Records that the buyer sent a price request for a DRAFT order and marks
    its pending items requested. The order and those items then read
    REQUESTED; items already ordered stay ORDERED."""
    await use_case.execute(actor=actor, order_id=order_id)
    # Read back with its lines, which the write itself does not return.
    result = await reader.get_one(order_id=order_id)
    await actions.orders([result], actor)
    return result


@router.put("/{order_id}/submit", response_model=OrderResponse)
async def submit_order(
    order_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: SubmitOrder = Depends(get_submit_order_use_case),
    reader: GetOrders = Depends(get_order_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> OrderResult:
    """Places a DRAFT or REQUESTED order: records its ordered_date and marks
    its pending and requested items ordered, which moves their allocated
    demands to ORDERED and plans the positions of their made parts. The
    order and those items then read ORDERED."""
    await use_case.execute(actor=actor, order_id=order_id)
    # Read back with its lines, which the write itself does not return.
    result = await reader.get_one(order_id=order_id)
    await actions.orders([result], actor)
    return result


@router.put("/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(
    order_id: int,
    expected_edit_version: int = Query(
        description="The edit version read; a row that moved since answers 409."
    ),
    actor: User = Depends(get_current_active_user),
    use_case: CancelOrder = Depends(get_cancel_order_use_case),
    reader: GetOrders = Depends(get_order_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> OrderResult:
    """Cancels an order, unless it is already fully delivered or canceled.
    Items that received nothing are canceled and their allocations released,
    partially delivered items are closed short at the pieces they received,
    and delivered items stay as they are."""
    await use_case.execute(
        actor=actor, order_id=order_id, expected_edit_version=expected_edit_version
    )
    # Read back with its lines, which the write itself does not return.
    result = await reader.get_one(order_id=order_id)
    await actions.orders([result], actor)
    return result


# ── Order items ───────────────────────────────────────────────────────


@router.post(
    "/{order_id}/items", response_model=OrderItemResponse, status_code=status.HTTP_201_CREATED
)
async def create_order_item(
    order_id: int,
    body: OrderItemCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateOrderItem = Depends(get_create_order_item_use_case),
    idempotency: Idempotency = Depends(get_idempotency),
    reader: GetOrders = Depends(get_order_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> OrderItemResult:
    """Adds an item to the order. An order someone canceled takes no new
    item (409); one that reads canceled only because every item is canceled
    still takes one. With an Idempotency-Key, a retry is answered with the
    item the first request added instead of adding another."""
    # order_id from path takes precedence, prevents body/path mismatch
    data = body.model_dump()
    data["order_id"] = order_id
    cmd = CreateOrderItemCommand(**data)
    result = await idempotency.run(
        lambda: use_case.execute(actor=actor, cmd=cmd),
        written=order_item_refs,
        replay=lambda refs: replay_order_item(reader, refs),
    )
    await actions.order_items([result], actor)
    return result


@router.put("/{order_id}/items/{order_item_id}/mark-ordered", response_model=OrderItemResponse)
async def mark_order_item_ordered(
    order_id: int,
    order_item_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: MarkOrderItemOrdered = Depends(get_mark_order_item_ordered_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> OrderItemResult:
    """Transitions a single order item from PENDING or REQUESTED to ORDERED and
    records the line's ordered_date. Any other status is refused with 409."""
    result = await use_case.execute(actor=actor, order_id=order_id, order_item_id=order_item_id)
    await actions.order_items([result], actor)
    return result


@router.put("/{order_id}/mark-items-ordered", response_model=list[OrderItemResponse])
async def mark_all_order_items_ordered(
    order_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: MarkAllOrderItemsOrdered = Depends(get_mark_all_order_items_ordered_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> list[OrderItemResult]:
    """Transitions every PENDING or REQUESTED order item in an order to ORDERED.
    Lines in other statuses are skipped."""
    result = await use_case.execute(actor=actor, order_id=order_id)
    await actions.order_items(result, actor)
    return result


@router.put("/{order_id}/items/{order_item_id}/mark-requested", response_model=OrderItemResponse)
async def mark_order_item_requested(
    order_id: int,
    order_item_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: MarkOrderItemRequested = Depends(get_mark_order_item_requested_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> OrderItemResult:
    """Transitions a single order item from PENDING to REQUESTED. Any other
    status is refused with 409."""
    result = await use_case.execute(actor=actor, order_id=order_id, order_item_id=order_item_id)
    await actions.order_items([result], actor)
    return result


@router.put("/{order_id}/mark-items-requested", response_model=list[OrderItemResponse])
async def mark_all_order_items_requested(
    order_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: MarkAllOrderItemsRequested = Depends(get_mark_all_order_items_requested_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> list[OrderItemResult]:
    """Transitions all PENDING order items in an order to REQUESTED."""
    result = await use_case.execute(actor=actor, order_id=order_id)
    await actions.order_items(result, actor)
    return result


@router.put(
    "/{order_id}/items/{order_item_id}/mark-ready-for-pickup", response_model=OrderItemResponse
)
async def mark_order_item_ready_for_pickup(
    order_id: int,
    order_item_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: MarkOrderItemReadyForPickup = Depends(get_mark_order_item_ready_for_pickup_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> OrderItemResult:
    """Records that the supplier confirmed a batch is ready to collect. Optional,
    never required by any status transition, only refines scheduling estimates."""
    result = await use_case.execute(actor=actor, order_id=order_id, order_item_id=order_item_id)
    await actions.order_items([result], actor)
    return result


@router.put("/{order_id}/items/{order_item_id}", response_model=OrderItemResponse)
async def update_order_item(
    order_id: int,
    order_item_id: int,
    body: OrderItemUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateOrderItem = Depends(get_update_order_item_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> OrderItemResult:
    """Updates an order item. Its quantity changes only while it is pending,
    requested or ordered (409 otherwise); a partially delivered item is
    closed short instead. A made item's quantity never exceeds what its lot
    position's production orders leave it (422)."""
    cmd = UpdateOrderItemCommand(**body.model_dump())
    result = await use_case.execute(
        actor=actor, order_id=order_id, order_item_id=order_item_id, cmd=cmd
    )
    await actions.order_items([result], actor)
    return result


@router.put("/{order_id}/items/{order_item_id}/move", response_model=OrderItemResponse)
async def move_order_item(
    order_id: int,
    order_item_id: int,
    body: MoveOrderItemRequest,
    actor: User = Depends(get_current_active_user),
    use_case: MoveOrderItem = Depends(get_move_order_item_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> OrderItemResult:
    """Re-parents an order item onto a different order without touching its
    allocations or lot-position link. Only a pending, requested or ordered
    item on which nothing was delivered or rejected moves, and not onto an
    order someone canceled (409); an order that reads canceled only because
    every item is canceled takes it."""
    result = await use_case.execute(
        actor=actor,
        source_order_id=order_id,
        order_item_id=order_item_id,
        target_order_id=body.target_order_id,
    )
    await actions.order_items([result], actor)
    return result


@router.delete("/{order_id}/items/{order_item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_order_item(
    order_id: int,
    order_item_id: int,
    expected_edit_version: int = Query(
        description="The edit version read; a row that moved since answers 409."
    ),
    actor: User = Depends(get_current_active_user),
    use_case: RemoveOrderItem = Depends(get_remove_order_item_use_case),
) -> None:
    """Removes a pending or requested order item and releases its
    allocations. An ordered item is canceled instead (409), and a canceled,
    partially delivered or delivered item stays on the order."""
    await use_case.execute(
        actor=actor,
        order_id=order_id,
        order_item_id=order_item_id,
        expected_edit_version=expected_edit_version,
    )


@router.post("/{order_id}/items/{order_item_id}/cancel", response_model=OrderItemResponse)
async def cancel_order_item(
    order_id: int,
    order_item_id: int,
    expected_edit_version: int = Query(
        description="The edit version read; a row that moved since answers 409."
    ),
    actor: User = Depends(get_current_active_user),
    use_case: CancelOrderItem = Depends(get_cancel_order_item_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> OrderItemResult:
    """Cancels a pending, requested or ordered item on which nothing was
    delivered or lost yet and releases every allocation on it; the item
    stays on the order as canceled. An item that received pieces is closed
    short instead (409). Needs the same permission as removing an item."""
    result = await use_case.execute(
        actor=actor,
        order_id=order_id,
        order_item_id=order_item_id,
        expected_edit_version=expected_edit_version,
    )
    await actions.order_items([result], actor)
    return result


@router.post("/{order_id}/items/{order_item_id}/close-short", response_model=OrderItemResponse)
async def close_order_item_short(
    order_id: int,
    order_item_id: int,
    expected_edit_version: int = Query(
        description="The edit version read; a row that moved since answers 409."
    ),
    actor: User = Depends(get_current_active_user),
    use_case: CloseOrderItemShort = Depends(get_close_order_item_short_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> OrderItemResult:
    """Closes an ordered or partially delivered item at the pieces delivered
    or lost on it, because the supplier sends nothing more: the item reads
    delivered and records the close, and the allocations on it are fitted
    into its delivered pieces, the newest demand first. An item that
    received nothing is canceled instead (409). Needs the same permission
    as updating the item."""
    result = await use_case.execute(
        actor=actor,
        order_id=order_id,
        order_item_id=order_item_id,
        expected_edit_version=expected_edit_version,
    )
    await actions.order_items([result], actor)
    return result


@router.post("/{order_id}/items/{order_item_id}/reopen", response_model=OrderItemResponse)
async def reopen_order_item(
    order_id: int,
    order_item_id: int,
    expected_edit_version: int = Query(
        description="The edit version read; a row that moved since answers 409."
    ),
    actor: User = Depends(get_current_active_user),
    use_case: ReopenOrderItem = Depends(get_reopen_order_item_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> OrderItemResult:
    """Reopens an item closed short: its quantity goes back to what it was
    before the close and the item waits for the rest again. Refused (409)
    for an item that is not closed short, a MADE item, an item of a
    canceled order and an item that moved since the client read it. Needs
    the same permission as updating the item."""
    result = await use_case.execute(
        actor=actor,
        order_id=order_id,
        order_item_id=order_item_id,
        expected_edit_version=expected_edit_version,
    )
    await actions.order_items([result], actor)
    return result


@router.post(
    "/{order_id}/items/{order_item_id}/deliveries/{delivery_id}/correct",
    response_model=OrderItemResponse,
)
async def correct_order_item_delivery(
    order_id: int,
    order_item_id: int,
    delivery_id: int,
    body: CorrectDeliveryRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CorrectOrderItemDelivery = Depends(get_correct_order_item_delivery_use_case),
    idempotency: Idempotency = Depends(get_idempotency),
    reader: GetOrders = Depends(get_order_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> OrderItemResult:
    """Takes back accepted pieces of one delivery of an item with a
    correction row, which names the delivery and the reason; the item's
    delivered total drops by the same amount, and the returned item lists
    its delivery rows. With `body.rejection` the pieces are taken back as
    rejected ones, for damage found after receipt: the item's rejected
    totals grow by them, lost pieces refit its allocations, and the
    rejection is announced as one at receipt is. Refused with 409 on a made item, on an item that is
    neither partially delivered nor delivered, on a row that is itself a
    correction, beyond what the delivery accepted less earlier corrections
    of it, beyond the item's delivered total, and while a demand allocated
    to the item is fulfilled. A row not on the item answers 404, and a
    quantity that is not a positive finite number, a blank reason or a
    correction with neither a reason nor a rejection 422.
    Requires receive:deliveries. With an Idempotency-Key, a retry is
    answered with the item instead of booking the correction again."""
    result = await idempotency.run(
        lambda: use_case.execute(
            actor=actor,
            order_id=order_id,
            order_item_id=order_item_id,
            delivery_id=delivery_id,
            quantity=body.quantity,
            reason=body.reason,
            expected_edit_version=body.expected_edit_version,
            rejection=body.rejection.to_value() if body.rejection is not None else None,
        ),
        written=order_item_refs,
        replay=lambda refs: replay_order_item(reader, refs),
    )
    await actions.order_items([result], actor)
    return result


@router.put("/{order_id}/deliver-all-items", response_model=DeliverAllResponse)
async def deliver_all_order_items(
    order_id: int,
    storage_place: str | None = None,
    body: DeliverAllOrderItemsRequest | None = None,
    actor: User = Depends(get_current_active_user),
    use_case: DeliverAllOrderItems = Depends(get_deliver_all_order_items_use_case),
    idempotency: Idempotency = Depends(get_idempotency),
    reader: GetOrders = Depends(get_order_use_case),
    actions: LifecycleActions = Depends(get_lifecycle_actions),
) -> DeliverAllResult:
    """Runs the full delivery pipeline for every item of an order that can
    take a delivery by the single delivery rule: ordered or partially
    delivered, on an order that is not canceled, and for a MADE line on a
    lot that is not canceled. Every other item is skipped and listed with
    the reason, an item moved to another order while the request waited
    for it as moved. All items are booked in one transaction, so an item
    that fails leaves every item of the order undelivered. A rejection for
    an item not on the order answers 404, one for an item that takes no
    delivery or was moved meanwhile 409.

    `body.rejections` optionally books a rejection on individual lines
    (by order_item_id) in the same call; every other deliverable line
    still gets its full remaining quantity delivered. A rejection works as
    on `PUT /bought-items-allocations/order-item/{order_item_id}/deliver`.
    `body.delivery_note_number` and `body.damage_noted_on_delivery_note`
    are recorded on every delivery row booked.

    Requires receive:deliveries. With an Idempotency-Key, a retry is
    answered with the lines as booked instead of delivering again."""
    rejections = [r.to_input() for r in (body.rejections if body else [])]
    result = await idempotency.run(
        lambda: use_case.execute(
            actor=actor,
            order_id=order_id,
            storage_place=storage_place,
            rejections=rejections,
            delivery_note_number=body.delivery_note_number if body else None,
            damage_noted_on_delivery_note=body.damage_noted_on_delivery_note if body else False,
        ),
        written=lambda booked: deliver_all_refs(order_id, booked),
        replay=lambda refs: replay_deliver_all(reader, refs),
    )
    await actions.order_items(result.delivered, actor)
    return result
