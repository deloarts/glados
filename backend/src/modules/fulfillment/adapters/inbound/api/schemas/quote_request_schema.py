"""
HTTP request and response schemas of the quote request (RFQ) routes.
"""

from datetime import date
from datetime import datetime
from typing import Annotated
from typing import Literal

from fastapi import Query
from pydantic import BaseModel
from pydantic import Field
from pydantic import model_validator

from src.modules.fulfillment.domain.value_objects.extra_cost_kind import ExtraCostKind
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.quote_request_status import (
    QuoteRequestDemandFamily,
)
from src.modules.fulfillment.domain.value_objects.quote_request_status import QuoteRequestLineState
from src.modules.fulfillment.domain.value_objects.quote_request_status import QuoteRequestStatus
from src.modules.fulfillment.ports.outbound.repositories.quote_request_repository import (
    QuoteRequestFilterDto,
)
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.platform.adapters.inbound.api.schemas.quantity_fields import PositiveQuantity
from src.modules.platform.adapters.inbound.api.schemas.user_schema import PublicUserResponse
from src.modules.platform.const import MAX_PAGE_SIZE
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction

# ══════════════════════════════════════════════════════════════════════
# Requests
# ══════════════════════════════════════════════════════════════════════


class QuoteRequestLineDemandRequest(BaseModel):
    family: QuoteRequestDemandFamily
    demand_item_id: int = Field(..., gt=0)
    quantity: PositiveQuantity


class QuoteRequestLineRequest(BaseModel):
    """What a line asks for: exactly one of a bought item, a source item, a
    lot position or a free-text name. A bought or source line may name the
    demands it is for; a share reserves nothing until the award."""

    bought_item_id: int | None = Field(default=None, gt=0)
    source_item_id: int | None = Field(default=None, gt=0)
    lot_position_id: int | None = Field(default=None, gt=0)
    virtual_name: str | None = Field(default=None, max_length=200)
    # Required except for a lot position, which takes its lot's project.
    project_id: int | None = Field(default=None, gt=0)
    quantity: PositiveQuantity
    unit: str = Field(..., min_length=1, max_length=20)
    note: str | None = None
    demands: list[QuoteRequestLineDemandRequest] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def _one_identity(self) -> "QuoteRequestLineRequest":
        named = [
            self.bought_item_id is not None,
            self.source_item_id is not None,
            self.lot_position_id is not None,
            bool((self.virtual_name or "").strip()),
        ]
        if sum(named) != 1:
            raise ValueError(
                "Exactly one of bought_item_id, source_item_id, lot_position_id or "
                "virtual_name must be provided."
            )
        return self


class QuoteRequestCreateRequest(BaseModel):
    note: str | None = None
    deadline: date | None = None
    supplier_ids: list[int] = Field(default_factory=list, max_length=50)
    lines: list[QuoteRequestLineRequest] = Field(default_factory=list, max_length=200)


class QuoteRequestLinesAddRequest(BaseModel):
    lines: list[QuoteRequestLineRequest] = Field(..., min_length=1, max_length=200)


class QuoteRequestUpdateRequest(BaseModel):
    note: str | None = None
    deadline: date | None = None
    # The edit version read; a request that moved since answers 409.
    expected_edit_version: int


class QuoteRequestLineUpdateRequest(BaseModel):
    quantity: PositiveQuantity | None = None
    note: str | None = None


class QuoteRequestLineSubstituteRequest(BaseModel):
    """Another item for a line, for every supplier: a bought item for a
    bought line or a source item for a source line, with an optional
    reason."""

    bought_item_id: int | None = Field(default=None, gt=0)
    source_item_id: int | None = Field(default=None, gt=0)
    reason: str | None = Field(default=None, max_length=500)


class QuoteRequestSuppliersAddRequest(BaseModel):
    supplier_ids: list[int] = Field(..., min_length=1, max_length=50)


class QuoteLineRequest(BaseModel):
    line_id: int = Field(..., gt=0)
    # Net unit price in cents; left out with no_offer.
    unit_price: int | None = Field(default=None, ge=0)
    no_offer: bool = False
    lead_time_days: int | None = Field(default=None, ge=0, le=3650)
    min_quantity: PositiveQuantity | None = None
    note: str | None = None
    # An alternative item the supplier offered instead, of the line's kind,
    # with the reason it gave; left out for the line's own item.
    substitute_bought_item_id: int | None = Field(default=None, gt=0)
    substitute_source_item_id: int | None = Field(default=None, gt=0)
    substitute_reason: str | None = Field(default=None, max_length=500)


class QuoteExtraCostRequest(BaseModel):
    kind: ExtraCostKind
    # Net, in cents; a discount is sent as a positive amount.
    amount: int = Field(..., gt=0)
    label: str | None = Field(default=None, max_length=120)
    note: str | None = None
    # The request line the cost belongs to; left out for the whole offer.
    line_id: int | None = Field(default=None, gt=0)


class OfferSaveRequest(BaseModel):
    """A supplier's whole offer, replacing what was recorded before."""

    quotes: list[QuoteLineRequest] = Field(default_factory=list, max_length=200)
    extra_costs: list[QuoteExtraCostRequest] = Field(default_factory=list, max_length=50)
    valid_until: date | None = None
    note: str | None = None
    declined: bool = False


class AwardLineRequest(BaseModel):
    line_id: int = Field(..., gt=0)
    supplier_row_id: int = Field(..., gt=0)


class AwardSupplierRequest(BaseModel):
    supplier_row_id: int = Field(..., gt=0)
    # An existing draft order of the supplier to add the lines to; left out
    # for a new order.
    target_order_id: int | None = Field(default=None, gt=0)
    extra_costs: list[QuoteExtraCostRequest] = Field(default_factory=list, max_length=50)


class QuoteRequestAwardRequest(BaseModel):
    awards: list[AwardLineRequest] = Field(..., min_length=1, max_length=200)
    # Per winning supplier: the order to add to and the extra costs to book.
    # A winning supplier left out gets a new order and its offer's costs.
    suppliers: list[AwardSupplierRequest] = Field(default_factory=list, max_length=50)
    expected_edit_version: int


class QuoteRequestFilterParams:
    def __init__(
        self,
        skip: Annotated[int | None, Query(ge=0)] = None,
        limit: Annotated[int | None, Query(ge=1, le=MAX_PAGE_SIZE)] = None,
        ids: Annotated[list[int] | None, Query(max_length=200)] = None,
        status: Annotated[list[QuoteRequestStatus] | None, Query()] = None,
        supplier_id: Annotated[int | None, Query()] = None,
        creator_id: Annotated[int | None, Query()] = None,
        search: Annotated[str | None, Query(max_length=200)] = None,
        order_by: Annotated[
            Literal["id", "request_number", "created", "deadline", "status"] | None, Query()
        ] = None,
        order_dir: Annotated[Literal["asc", "desc"] | None, Query()] = None,
    ) -> None:
        self.skip = skip
        self.limit = limit
        self.ids = ids
        self.status = status
        self.supplier_id = supplier_id
        self.creator_id = creator_id
        self.search = search
        self.order_by = order_by
        self.order_dir = order_dir

    def to_dto(self) -> QuoteRequestFilterDto:
        return QuoteRequestFilterDto(
            skip=self.skip,
            limit=self.limit,
            ids=self.ids,
            status=[s.value for s in self.status] if self.status else None,
            supplier_id=self.supplier_id,
            creator_id=self.creator_id,
            search=self.search,
            order_by=self.order_by,
            order_dir=self.order_dir,
        )


# ══════════════════════════════════════════════════════════════════════
# Responses
# ══════════════════════════════════════════════════════════════════════


class QuoteRequestLineDemandResponse(ResponseModel):
    family: QuoteRequestDemandFamily
    demand_item_id: int
    quantity: float


class QuoteRequestLineResponse(EntityResponse):
    position: int
    line_type: OrderLineType
    quantity: float
    unit: str
    created: datetime
    note: str | None
    item_name: str
    item_code: str
    bought_item_id: int | None
    source_item_id: int | None
    lot_position_id: int | None
    lot_id: int | None
    lot_number: str
    virtual_name: str | None
    project_id: int | None
    project_number: str
    state: QuoteRequestLineState
    awarded_supplier_id: int | None
    awarded_price: int | None
    awarded_at: datetime | None
    # The line was awarded and the order line of that award was canceled or
    # removed since; the line is open again, the award fields keep what was
    # awarded.
    award_voided: bool
    dropped_at: datetime | None
    order_item_id: int | None
    order_id: int | None
    order_number: str
    # Why the line asks for another item than its demands; a replaced line
    # names the line that replaced it.
    substitute_reason: str | None
    substituted_by_line_id: int | None
    demands: list[QuoteRequestLineDemandResponse]
    cheapest_supplier_id: int | None


class QuoteResponse(ResponseModel):
    line_id: int
    unit_price: int | None
    no_offer: bool
    lead_time_days: int | None
    min_quantity: float | None
    note: str | None
    # The alternative item quoted instead of the line's, if any.
    substitute_bought_item_id: int | None
    substitute_source_item_id: int | None
    substitute_reason: str | None
    substitute_item_name: str
    substitute_item_code: str


class QuoteExtraCostResponse(ResponseModel):
    kind: ExtraCostKind
    amount: int
    position: int
    label: str | None
    note: str | None
    line_id: int | None


class QuoteRequestSupplierResponse(EntityResponse):
    supplier_id: int
    supplier_name: str
    supplier_archived: bool
    position: int
    sent_at: datetime | None
    responded_at: datetime | None
    declined_at: datetime | None
    valid_until: date | None
    note: str | None
    quotes: list[QuoteResponse]
    extra_costs: list[QuoteExtraCostResponse]
    lines_total: int
    extra_costs_total: int
    total: int
    priced_lines: int
    not_asked_line_ids: list[int]
    has_awarded_lines: bool


class QuoteRequestResponse(EntityResponse):
    request_number: str
    status: QuoteRequestStatus
    actions: list[LifecycleAction]
    created: datetime
    changed: datetime | None
    note: str | None
    deadline: date | None
    closed_at: datetime | None
    canceled_at: datetime | None
    edit_version: int
    creator_id: int
    creator: PublicUserResponse | None
    changed_by_id: int | None
    changed_by: PublicUserResponse | None
    lines: list[QuoteRequestLineResponse]
    suppliers: list[QuoteRequestSupplierResponse]
    cheapest_complete_supplier_id: int | None


class AwardedOrderResponse(ResponseModel):
    order_id: int
    order_number: str
    supplier_id: int
    supplier_name: str
    created: bool
    line_ids: list[int]


class AwardWarningResponse(ResponseModel):
    line_id: int
    kind: Literal["share_capped", "line_skipped"]
    message: str


class QuoteRequestAwardResponse(ResponseModel):
    request: QuoteRequestResponse
    orders: list[AwardedOrderResponse]
    warnings: list[AwardWarningResponse]


class OpenQuoteRequestRefResponse(ResponseModel):
    id: int
    request_number: str


class QuoteRequestLinksResponse(ResponseModel):
    bought_demands: dict[int, list[OpenQuoteRequestRefResponse]]
    source_demands: dict[int, list[OpenQuoteRequestRefResponse]]
    lot_positions: dict[int, list[OpenQuoteRequestRefResponse]]
