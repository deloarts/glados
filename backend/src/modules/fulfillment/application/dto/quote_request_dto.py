"""
DTOs of the quote request (RFQ) vertical: the commands that build a request
from demands, add suppliers, record their offers and award the lines, and the
results that show a request with its offers compared.
"""

from datetime import date
from datetime import datetime
from typing import Literal

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
from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.base import ResultModel
from src.modules.platform.application.dto.user_dto import PublicUserResult

# ══════════════════════════════════════════════════════════════════════
# Commands
# ══════════════════════════════════════════════════════════════════════


class QuoteRequestLineDemandInput(BaseModel):
    family: QuoteRequestDemandFamily
    demand_item_id: int = Field(..., gt=0)
    quantity: float = Field(..., gt=0)


class QuoteRequestLineInput(BaseModel):
    """What a line asks for: exactly one of a bought item, a source item, a
    lot position or a free-text name, with the demands it is for."""

    bought_item_id: int | None = Field(default=None, gt=0)
    source_item_id: int | None = Field(default=None, gt=0)
    lot_position_id: int | None = Field(default=None, gt=0)
    virtual_name: str | None = None
    project_id: int | None = Field(default=None, gt=0)
    quantity: float = Field(..., gt=0)
    unit: str = Field(..., min_length=1)
    note: str | None = None
    demands: list[QuoteRequestLineDemandInput] = Field(default_factory=list, max_length=200)

    @model_validator(mode="after")
    def _one_identity(self) -> "QuoteRequestLineInput":
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
        if self.demands and (self.lot_position_id is not None or self.virtual_name):
            raise ValueError("Only a bought or source item line takes demand shares.")
        ids = [(d.family, d.demand_item_id) for d in self.demands]
        if len(ids) != len(set(ids)):
            raise ValueError("A demand may take a share of the line only once.")
        return self

    @property
    def line_type(self) -> OrderLineType:
        if self.bought_item_id is not None:
            return OrderLineType.BOUGHT
        if self.source_item_id is not None:
            return OrderLineType.SOURCE
        if self.lot_position_id is not None:
            return OrderLineType.MADE
        return OrderLineType.VIRTUAL


class CreateQuoteRequestCommand(BaseModel):
    note: str | None = None
    deadline: date | None = None
    supplier_ids: list[int] = Field(default_factory=list, max_length=50)
    lines: list[QuoteRequestLineInput] = Field(default_factory=list, max_length=200)


class AddQuoteRequestLinesCommand(BaseModel):
    lines: list[QuoteRequestLineInput] = Field(..., min_length=1, max_length=200)


class UpdateQuoteRequestCommand(BaseModel):
    note: str | None = None
    deadline: date | None = None
    expected_edit_version: int | None = None


class UpdateQuoteRequestLineCommand(BaseModel):
    quantity: float | None = Field(default=None, gt=0)
    note: str | None = None
    expected_edit_version: int | None = None


class SubstituteQuoteRequestLineCommand(BaseModel):
    """Replaces a line for every supplier with a line for another item of
    its kind, which takes over the demand shares."""

    bought_item_id: int | None = Field(default=None, gt=0)
    source_item_id: int | None = Field(default=None, gt=0)
    reason: str | None = None


class AddQuoteRequestSuppliersCommand(BaseModel):
    supplier_ids: list[int] = Field(..., min_length=1, max_length=50)


class QuoteInput(BaseModel):
    line_id: int = Field(..., gt=0)
    unit_price: int | None = Field(default=None, ge=0)
    no_offer: bool = False
    lead_time_days: int | None = Field(default=None, ge=0)
    min_quantity: float | None = Field(default=None, gt=0)
    note: str | None = None
    # An alternative item the supplier offered instead, of the line's kind,
    # and the reason it gave; both left out for the line's own item.
    substitute_bought_item_id: int | None = Field(default=None, gt=0)
    substitute_source_item_id: int | None = Field(default=None, gt=0)
    substitute_reason: str | None = None


class QuoteExtraCostInput(BaseModel):
    kind: ExtraCostKind
    amount: int = Field(..., gt=0)
    label: str | None = None
    note: str | None = None
    line_id: int | None = Field(default=None, gt=0)


class SaveOfferCommand(BaseModel):
    """A supplier's whole offer, replacing what was recorded before."""

    quotes: list[QuoteInput] = Field(default_factory=list, max_length=200)
    extra_costs: list[QuoteExtraCostInput] = Field(default_factory=list, max_length=50)
    valid_until: date | None = None
    note: str | None = None
    # The supplier said it will not quote; its prices stay as recorded.
    declined: bool = False
    expected_edit_version: int | None = None


class AwardLineInput(BaseModel):
    line_id: int = Field(..., gt=0)
    supplier_row_id: int = Field(..., gt=0)


class AwardSupplierInput(BaseModel):
    """What the award books for one winning supplier: an existing draft
    order of that supplier to add the lines to, or None for a new one, and
    the extra costs to put on the order."""

    supplier_row_id: int = Field(..., gt=0)
    target_order_id: int | None = Field(default=None, gt=0)
    extra_costs: list[QuoteExtraCostInput] = Field(default_factory=list, max_length=50)


class AwardQuoteRequestCommand(BaseModel):
    awards: list[AwardLineInput] = Field(..., min_length=1, max_length=200)
    suppliers: list[AwardSupplierInput] = Field(default_factory=list, max_length=50)
    expected_edit_version: int | None = None

    @model_validator(mode="after")
    def _each_line_once(self) -> "AwardQuoteRequestCommand":
        lines = [a.line_id for a in self.awards]
        if len(lines) != len(set(lines)):
            raise ValueError("An award names each line once.")
        rows = [s.supplier_row_id for s in self.suppliers]
        if len(rows) != len(set(rows)):
            raise ValueError("An award names each supplier once.")
        return self


class QuoteRequestActionCommand(BaseModel):
    expected_edit_version: int | None = None


# ══════════════════════════════════════════════════════════════════════
# Results
# ══════════════════════════════════════════════════════════════════════


class QuoteRequestLineDemandResult(ResultModel):
    family: QuoteRequestDemandFamily
    demand_item_id: int
    quantity: float


class QuoteRequestLineResult(ResultBase):
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
    # The award was voided: the order line it created was canceled or
    # removed, and the line is open again.
    award_voided: bool
    dropped_at: datetime | None
    order_item_id: int | None
    order_id: int | None
    order_number: str
    substitute_reason: str | None
    substituted_by_line_id: int | None
    demands: list[QuoteRequestLineDemandResult]
    # The supplier row with the lowest unit price for the line, if any.
    cheapest_supplier_id: int | None


class QuoteResult(ResultModel):
    line_id: int
    unit_price: int | None
    no_offer: bool
    lead_time_days: int | None
    min_quantity: float | None
    note: str | None
    substitute_bought_item_id: int | None
    substitute_source_item_id: int | None
    substitute_reason: str | None
    substitute_item_name: str
    substitute_item_code: str


class QuoteExtraCostResult(ResultModel):
    kind: ExtraCostKind
    amount: int
    position: int
    label: str | None
    note: str | None
    line_id: int | None


class QuoteRequestSupplierResult(ResultBase):
    supplier_id: int
    supplier_name: str
    supplier_archived: bool
    position: int
    sent_at: datetime | None
    responded_at: datetime | None
    declined_at: datetime | None
    valid_until: date | None
    note: str | None
    quotes: list[QuoteResult]
    extra_costs: list[QuoteExtraCostResult]
    # The offer in net cents: priced lines times their quantities, the
    # extra costs with a discount subtracted, and both added.
    lines_total: int
    extra_costs_total: int
    total: int
    priced_lines: int
    # The lines added after the request last went out to the supplier.
    not_asked_line_ids: list[int]
    # Whether the supplier won a line, which keeps it on the request.
    has_awarded_lines: bool


class QuoteRequestResult(ResultBase):
    request_number: str
    status: QuoteRequestStatus
    actions: list[str] = Field(default_factory=list)
    created: datetime
    changed: datetime | None
    note: str | None
    deadline: date | None
    closed_at: datetime | None
    canceled_at: datetime | None
    edit_version: int
    creator_id: int
    creator: PublicUserResult | None
    changed_by_id: int | None
    changed_by: PublicUserResult | None
    lines: list[QuoteRequestLineResult]
    suppliers: list[QuoteRequestSupplierResult]
    # The supplier row whose offer prices every live line at the lowest
    # total, extra costs included.
    cheapest_complete_supplier_id: int | None


class AwardedOrderResult(ResultModel):
    order_id: int
    order_number: str
    supplier_id: int
    supplier_name: str
    created: bool  # a new draft order, else an existing one took the lines
    line_ids: list[int]


class AwardWarningResult(ResultModel):
    """Something the award did differently from the request: a demand share
    cut to what the demand still needed, or a line that could not go onto an
    order and stays open."""

    line_id: int
    kind: Literal["share_capped", "line_skipped"]
    message: str


class AwardQuoteRequestResult(ResultModel):
    request: QuoteRequestResult
    orders: list[AwardedOrderResult]
    warnings: list[AwardWarningResult]


class OpenQuoteRequestRefResult(ResultModel):
    id: int
    request_number: str


class OpenQuoteRequestLinksResult(ResultModel):
    """The open quote requests asking for each demand or lot position."""

    bought_demands: dict[int, list[OpenQuoteRequestRefResult]]
    source_demands: dict[int, list[OpenQuoteRequestRefResult]]
    lot_positions: dict[int, list[OpenQuoteRequestRefResult]]


class PaginatedQuoteRequests:
    def __init__(self, total: int, items: list[QuoteRequestResult]):
        self.total = total
        self.items = items
