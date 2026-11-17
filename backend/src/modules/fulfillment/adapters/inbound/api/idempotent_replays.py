"""
What the idempotent routes record of their writes and how a replay reads
the response back from it (idempotency.py). A replay answers with the
resources as they are now, which is what the IETF Idempotency-Key draft
asks for: a response consistent with the completed request.
"""

from src.modules.fulfillment.application.dto.order_dto import DeliverAllResult
from src.modules.fulfillment.application.dto.order_dto import DeliverAllSkippedLine
from src.modules.fulfillment.application.dto.order_dto import OrderItemResult
from src.modules.fulfillment.application.dto.quote_request_dto import AwardQuoteRequestResult
from src.modules.fulfillment.application.use_cases.order.get_order import GetOrders
from src.modules.fulfillment.application.use_cases.quote_request.award_quote_request import (
    awarded_orders,
)
from src.modules.fulfillment.application.use_cases.quote_request.get_quote_requests import (
    GetQuoteRequests,
)
from src.modules.platform.domain.entities.idempotency_key import ResourceRef
from src.modules.platform.domain.entities.user import User

ORDER = "order"
ORDER_ITEM = "order_item"
DEMAND = "demand"
QUOTE_REQUEST = "quote_request"
# A line deliver-all skipped, with the reason after the colon.
_SKIPPED_ORDER_ITEM = "skipped_order_item:"


def ids_of(refs: tuple[ResourceRef, ...], kind: str) -> list[int]:
    return [r.id for r in refs if r.kind == kind]


def order_item_refs(result: OrderItemResult) -> list[ResourceRef]:
    return [ResourceRef(ORDER, result.order_id), ResourceRef(ORDER_ITEM, result.id)]


async def replay_order_item(reader: GetOrders, refs: tuple[ResourceRef, ...]) -> OrderItemResult:
    order = await reader.get_one(order_id=ids_of(refs, ORDER)[0])
    item_id = ids_of(refs, ORDER_ITEM)[0]
    return next(item for item in order.items if item.id == item_id)


def deliver_all_refs(order_id: int, result: DeliverAllResult) -> list[ResourceRef]:
    return [
        ResourceRef(ORDER, order_id),
        *(ResourceRef(ORDER_ITEM, item.id) for item in result.delivered),
        *(
            ResourceRef(_SKIPPED_ORDER_ITEM + line.reason, line.order_item_id)
            for line in result.skipped
        ),
    ]


async def replay_deliver_all(reader: GetOrders, refs: tuple[ResourceRef, ...]) -> DeliverAllResult:
    order = await reader.get_one(order_id=ids_of(refs, ORDER)[0])
    items = {item.id: item for item in order.items}
    skipped = [
        DeliverAllSkippedLine.model_validate(
            {
                "order_item_id": ref.id,
                "position": items[ref.id].position,
                "reason": ref.kind.removeprefix(_SKIPPED_ORDER_ITEM),
            }
        )
        for ref in refs
        if ref.kind.startswith(_SKIPPED_ORDER_ITEM) and ref.id in items
    ]
    delivered = [items[i] for i in ids_of(refs, ORDER_ITEM) if i in items]
    return DeliverAllResult(delivered=delivered, skipped=skipped)


def demand_refs(demand_ids: list[int]) -> list[ResourceRef]:
    return [ResourceRef(DEMAND, i) for i in demand_ids]


def allocation_refs(demand_item_id: int, order_item_id: int | None) -> list[ResourceRef]:
    refs = [ResourceRef(DEMAND, demand_item_id)]
    if order_item_id is not None:
        refs.append(ResourceRef(ORDER_ITEM, order_item_id))
    return refs


def quote_request_award_refs(result: AwardQuoteRequestResult) -> list[ResourceRef]:
    return [
        ResourceRef(QUOTE_REQUEST, result.request.id),
        *(ResourceRef(ORDER, order.order_id) for order in result.orders),
    ]


async def replay_quote_request_award(
    reader: GetQuoteRequests, actor: User, refs: tuple[ResourceRef, ...]
) -> AwardQuoteRequestResult:
    """The request as it is now and the orders its awarded lines are on; the
    warnings of the first run are not kept."""
    request_id = ids_of(refs, QUOTE_REQUEST)[0]
    request = await reader.get_one(actor, request_id)
    return AwardQuoteRequestResult(
        request=request,
        orders=[
            o
            for o in awarded_orders(await reader.entity(request_id))
            if o.order_id in ids_of(refs, ORDER)
        ],
        warnings=[],
    )
