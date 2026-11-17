"""
Quote request (RFQ) endpoints. A quote request asks several suppliers for an
offer on the same lines before anything is ordered; an award puts the lines
on draft orders of the suppliers that won them. Every route needs
write:orders except the reads. Each response carries the actions the reading
user may take on the request.
"""

from fastapi import Depends
from fastapi import Query
from fastapi import status
from fastapi.routing import APIRouter

from src.modules.fulfillment.adapters.inbound.api.deps.quote_requests import (
    get_add_quote_request_lines_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.quote_requests import (
    get_add_quote_request_suppliers_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.quote_requests import (
    get_award_quote_request_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.quote_requests import (
    get_create_quote_request_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.quote_requests import (
    get_drop_quote_request_line_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.quote_requests import (
    get_end_quote_request_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.quote_requests import (
    get_mark_quote_request_supplier_sent_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.quote_requests import (
    get_open_quote_request_links_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.quote_requests import (
    get_quote_requests_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.quote_requests import (
    get_remove_quote_request_line_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.quote_requests import (
    get_remove_quote_request_supplier_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.quote_requests import (
    get_reopen_quote_request_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.quote_requests import get_save_offer_use_case
from src.modules.fulfillment.adapters.inbound.api.deps.quote_requests import (
    get_substitute_quote_request_line_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.quote_requests import (
    get_update_quote_request_line_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.deps.quote_requests import (
    get_update_quote_request_use_case,
)
from src.modules.fulfillment.adapters.inbound.api.idempotent_replays import quote_request_award_refs
from src.modules.fulfillment.adapters.inbound.api.idempotent_replays import (
    replay_quote_request_award,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.quote_request_schema import (
    OfferSaveRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.quote_request_schema import (
    QuoteRequestAwardRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.quote_request_schema import (
    QuoteRequestAwardResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.quote_request_schema import (
    QuoteRequestCreateRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.quote_request_schema import (
    QuoteRequestFilterParams,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.quote_request_schema import (
    QuoteRequestLinesAddRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.quote_request_schema import (
    QuoteRequestLineSubstituteRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.quote_request_schema import (
    QuoteRequestLineUpdateRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.quote_request_schema import (
    QuoteRequestLinksResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.quote_request_schema import (
    QuoteRequestResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.quote_request_schema import (
    QuoteRequestSuppliersAddRequest,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.quote_request_schema import (
    QuoteRequestUpdateRequest,
)
from src.modules.fulfillment.application.dto.quote_request_dto import AddQuoteRequestLinesCommand
from src.modules.fulfillment.application.dto.quote_request_dto import (
    AddQuoteRequestSuppliersCommand,
)
from src.modules.fulfillment.application.dto.quote_request_dto import AwardQuoteRequestCommand
from src.modules.fulfillment.application.dto.quote_request_dto import AwardQuoteRequestResult
from src.modules.fulfillment.application.dto.quote_request_dto import CreateQuoteRequestCommand
from src.modules.fulfillment.application.dto.quote_request_dto import OpenQuoteRequestLinksResult
from src.modules.fulfillment.application.dto.quote_request_dto import QuoteRequestResult
from src.modules.fulfillment.application.dto.quote_request_dto import SaveOfferCommand
from src.modules.fulfillment.application.dto.quote_request_dto import (
    SubstituteQuoteRequestLineCommand,
)
from src.modules.fulfillment.application.dto.quote_request_dto import UpdateQuoteRequestCommand
from src.modules.fulfillment.application.dto.quote_request_dto import UpdateQuoteRequestLineCommand
from src.modules.fulfillment.application.use_cases.quote_request.award_quote_request import (
    AwardQuoteRequest,
)
from src.modules.fulfillment.application.use_cases.quote_request.edit_quote_request import (
    AddQuoteRequestLines,
)
from src.modules.fulfillment.application.use_cases.quote_request.edit_quote_request import (
    AddQuoteRequestSuppliers,
)
from src.modules.fulfillment.application.use_cases.quote_request.edit_quote_request import (
    CreateQuoteRequest,
)
from src.modules.fulfillment.application.use_cases.quote_request.edit_quote_request import (
    DropQuoteRequestLine,
)
from src.modules.fulfillment.application.use_cases.quote_request.edit_quote_request import (
    EndQuoteRequest,
)
from src.modules.fulfillment.application.use_cases.quote_request.edit_quote_request import (
    MarkQuoteRequestSupplierSent,
)
from src.modules.fulfillment.application.use_cases.quote_request.edit_quote_request import (
    RemoveQuoteRequestLine,
)
from src.modules.fulfillment.application.use_cases.quote_request.edit_quote_request import (
    RemoveQuoteRequestSupplier,
)
from src.modules.fulfillment.application.use_cases.quote_request.edit_quote_request import (
    ReopenQuoteRequest,
)
from src.modules.fulfillment.application.use_cases.quote_request.edit_quote_request import SaveOffer
from src.modules.fulfillment.application.use_cases.quote_request.edit_quote_request import (
    SubstituteQuoteRequestLine,
)
from src.modules.fulfillment.application.use_cases.quote_request.edit_quote_request import (
    UpdateQuoteRequest,
)
from src.modules.fulfillment.application.use_cases.quote_request.edit_quote_request import (
    UpdateQuoteRequestLine,
)
from src.modules.fulfillment.application.use_cases.quote_request.get_quote_requests import (
    GetOpenQuoteRequestLinks,
)
from src.modules.fulfillment.application.use_cases.quote_request.get_quote_requests import (
    GetQuoteRequests,
)
from src.modules.platform.adapters.inbound.api.auth_deps import get_current_active_user
from src.modules.platform.adapters.inbound.api.idempotency import Idempotency
from src.modules.platform.adapters.inbound.api.idempotency import get_idempotency
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageResponse
from src.modules.platform.domain.entities.user import User
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction

router = APIRouter()

_EDIT_VERSION = Query(description="The edit version read; a request that moved since answers 409.")


@router.get("/", response_model=PageResponse[QuoteRequestResponse])
async def list_quote_requests(
    params: QuoteRequestFilterParams = Depends(),
    actor: User = Depends(get_current_active_user),
    use_case: GetQuoteRequests = Depends(get_quote_requests_use_case),
) -> PageResponse[QuoteRequestResult]:
    result = await use_case.get_many(actor, params.to_dto())
    return PageResponse.from_result(result, params)


@router.post("/", response_model=QuoteRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_quote_request(
    body: QuoteRequestCreateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: CreateQuoteRequest = Depends(get_create_quote_request_use_case),
) -> QuoteRequestResult:
    """Creates a request, numbered from the quote request number format, with
    the suppliers and lines sent. A line names the demands it is for; that
    reserves nothing until the award."""
    return await use_case.execute(actor, CreateQuoteRequestCommand(**body.model_dump()))


@router.get("/open-links", response_model=QuoteRequestLinksResponse)
async def read_open_quote_request_links(
    bought_demand_ids: list[int] = Query(default_factory=list, max_length=500),
    source_demand_ids: list[int] = Query(default_factory=list, max_length=500),
    lot_position_ids: list[int] = Query(default_factory=list, max_length=500),
    _: User = Depends(get_current_active_user),
    use_case: GetOpenQuoteRequestLinks = Depends(get_open_quote_request_links_use_case),
) -> OpenQuoteRequestLinksResult:
    """The draft or sent requests whose open lines ask for each demand or
    lot position, for the "in quotation" markers of the tables."""
    return await use_case.execute(
        bought_demand_ids=bought_demand_ids,
        source_demand_ids=source_demand_ids,
        lot_position_ids=lot_position_ids,
    )


@router.get("/{request_id}", response_model=QuoteRequestResponse)
async def read_quote_request(
    request_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: GetQuoteRequests = Depends(get_quote_requests_use_case),
) -> QuoteRequestResult:
    return await use_case.get_one(actor, request_id)


@router.get("/{request_id}/changelog", response_model=list[str])
async def read_quote_request_changelog(
    request_id: int,
    _: User = Depends(get_current_active_user),
    use_case: GetQuoteRequests = Depends(get_quote_requests_use_case),
) -> list[str]:
    return await use_case.changelog(request_id)


@router.put("/{request_id}", response_model=QuoteRequestResponse)
async def update_quote_request(
    request_id: int,
    body: QuoteRequestUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateQuoteRequest = Depends(get_update_quote_request_use_case),
) -> QuoteRequestResult:
    cmd = UpdateQuoteRequestCommand(**body.model_dump(exclude_unset=True))
    return await use_case.execute(actor, request_id, cmd)


@router.post("/{request_id}/lines", response_model=QuoteRequestResponse)
async def add_quote_request_lines(
    request_id: int,
    body: QuoteRequestLinesAddRequest,
    actor: User = Depends(get_current_active_user),
    use_case: AddQuoteRequestLines = Depends(get_add_quote_request_lines_use_case),
) -> QuoteRequestResult:
    return await use_case.execute(
        actor, request_id, AddQuoteRequestLinesCommand(**body.model_dump())
    )


@router.put("/{request_id}/lines/{line_id}", response_model=QuoteRequestResponse)
async def update_quote_request_line(
    request_id: int,
    line_id: int,
    body: QuoteRequestLineUpdateRequest,
    actor: User = Depends(get_current_active_user),
    use_case: UpdateQuoteRequestLine = Depends(get_update_quote_request_line_use_case),
) -> QuoteRequestResult:
    cmd = UpdateQuoteRequestLineCommand(**body.model_dump(exclude_unset=True))
    return await use_case.execute(actor, request_id, line_id, cmd)


@router.delete("/{request_id}/lines/{line_id}", response_model=QuoteRequestResponse)
async def remove_quote_request_line(
    request_id: int,
    line_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: RemoveQuoteRequestLine = Depends(get_remove_quote_request_line_use_case),
) -> QuoteRequestResult:
    return await use_case.execute(actor, request_id, line_id)


@router.post("/{request_id}/lines/{line_id}/drop", response_model=QuoteRequestResponse)
async def drop_quote_request_line(
    request_id: int,
    line_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: DropQuoteRequestLine = Depends(get_drop_quote_request_line_use_case),
) -> QuoteRequestResult:
    """Gives an open line to nobody; the request no longer waits for it."""
    return await use_case.execute(actor, request_id, line_id, dropped=True)


@router.post("/{request_id}/lines/{line_id}/restore", response_model=QuoteRequestResponse)
async def restore_quote_request_line(
    request_id: int,
    line_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: DropQuoteRequestLine = Depends(get_drop_quote_request_line_use_case),
) -> QuoteRequestResult:
    """Takes back the drop of a line while the request is open."""
    return await use_case.execute(actor, request_id, line_id, dropped=False)


@router.post("/{request_id}/lines/{line_id}/substitute", response_model=QuoteRequestResponse)
async def substitute_quote_request_line(
    request_id: int,
    line_id: int,
    body: QuoteRequestLineSubstituteRequest,
    actor: User = Depends(get_current_active_user),
    use_case: SubstituteQuoteRequestLine = Depends(get_substitute_quote_request_line_use_case),
) -> QuoteRequestResult:
    """Replaces an open line for every supplier with a line for another item
    of its kind; removing the new line asks for the old one again."""
    cmd = SubstituteQuoteRequestLineCommand(**body.model_dump())
    return await use_case.execute(actor, request_id, line_id, cmd)


@router.post("/{request_id}/suppliers", response_model=QuoteRequestResponse)
async def add_quote_request_suppliers(
    request_id: int,
    body: QuoteRequestSuppliersAddRequest,
    actor: User = Depends(get_current_active_user),
    use_case: AddQuoteRequestSuppliers = Depends(get_add_quote_request_suppliers_use_case),
) -> QuoteRequestResult:
    """Adds suppliers to ask; an archived supplier may be added."""
    cmd = AddQuoteRequestSuppliersCommand(**body.model_dump())
    return await use_case.execute(actor, request_id, cmd)


@router.delete("/{request_id}/suppliers/{row_id}", response_model=QuoteRequestResponse)
async def remove_quote_request_supplier(
    request_id: int,
    row_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: RemoveQuoteRequestSupplier = Depends(get_remove_quote_request_supplier_use_case),
) -> QuoteRequestResult:
    """Removes a supplier with its offer, unless it won a line."""
    return await use_case.execute(actor, request_id, row_id)


@router.post("/{request_id}/suppliers/{row_id}/sent", response_model=QuoteRequestResponse)
async def mark_quote_request_supplier_sent(
    request_id: int,
    row_id: int,
    actor: User = Depends(get_current_active_user),
    use_case: MarkQuoteRequestSupplierSent = Depends(get_mark_quote_request_supplier_sent_use_case),
) -> QuoteRequestResult:
    """Records that the request went out to the supplier now; every open
    line counts as asked of it from then."""
    return await use_case.execute(actor, request_id, row_id)


@router.put("/{request_id}/suppliers/{row_id}/offer", response_model=QuoteRequestResponse)
async def save_quote_request_offer(
    request_id: int,
    row_id: int,
    body: OfferSaveRequest,
    actor: User = Depends(get_current_active_user),
    use_case: SaveOffer = Depends(get_save_offer_use_case),
) -> QuoteRequestResult:
    """Replaces the supplier's offer: a unit price or "no offer" per line,
    the extra costs, its validity and whether the supplier declined."""
    return await use_case.execute(actor, request_id, row_id, SaveOfferCommand(**body.model_dump()))


@router.post("/{request_id}/award", response_model=QuoteRequestAwardResponse)
async def award_quote_request(
    request_id: int,
    body: QuoteRequestAwardRequest,
    actor: User = Depends(get_current_active_user),
    use_case: AwardQuoteRequest = Depends(get_award_quote_request_use_case),
    reader: GetQuoteRequests = Depends(get_quote_requests_use_case),
    idempotency: Idempotency = Depends(get_idempotency),
) -> AwardQuoteRequestResult:
    """Puts each awarded line on a draft order of the supplier that won it,
    a new one or the existing draft named, with the demand allocations cut
    to what each demand still needs and the extra costs named per supplier.
    Answers the request, the orders and what the award did differently."""
    cmd = AwardQuoteRequestCommand(**body.model_dump())
    return await idempotency.run(
        lambda: use_case.execute(actor, request_id, cmd),
        written=quote_request_award_refs,
        replay=lambda refs: replay_quote_request_award(reader, actor, refs),
    )


@router.post("/{request_id}/close", response_model=QuoteRequestResponse)
async def close_quote_request(
    request_id: int,
    expected_edit_version: int = _EDIT_VERSION,
    actor: User = Depends(get_current_active_user),
    use_case: EndQuoteRequest = Depends(get_end_quote_request_use_case),
) -> QuoteRequestResult:
    """Closes a request with an awarded line; the open lines are dropped."""
    return await use_case.execute(actor, request_id, LifecycleAction.CLOSE, expected_edit_version)


@router.post("/{request_id}/cancel", response_model=QuoteRequestResponse)
async def cancel_quote_request(
    request_id: int,
    expected_edit_version: int = _EDIT_VERSION,
    actor: User = Depends(get_current_active_user),
    use_case: EndQuoteRequest = Depends(get_end_quote_request_use_case),
) -> QuoteRequestResult:
    """Cancels a request that awarded nothing; its demands stay open."""
    return await use_case.execute(actor, request_id, LifecycleAction.CANCEL, expected_edit_version)


@router.post("/{request_id}/reopen", response_model=QuoteRequestResponse)
async def reopen_quote_request(
    request_id: int,
    expected_edit_version: int = _EDIT_VERSION,
    actor: User = Depends(get_current_active_user),
    use_case: ReopenQuoteRequest = Depends(get_reopen_quote_request_use_case),
) -> QuoteRequestResult:
    """Reopens a closed request on which an award was voided since; the
    status is derived again and the line left open can be awarded anew."""
    return await use_case.execute(actor, request_id, expected_edit_version)
