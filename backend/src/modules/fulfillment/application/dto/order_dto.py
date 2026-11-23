"""
DTOs for the generic Order/OrderItem vertical.
"""

from datetime import date
from datetime import datetime
from typing import Literal

from pydantic import BaseModel
from pydantic import Field
from pydantic import model_validator

from src.modules.fulfillment.domain.value_objects.extra_cost_kind import ExtraCostKind
from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.base import ResultModel
from src.modules.platform.application.dto.user_dto import PublicUserResult
from src.modules.platform.domain.services.quantities import quantity_gt

# ══════════════════════════════════════════════════════════════════════
# Order
# ══════════════════════════════════════════════════════════════════════


class CreateOrderCommand(BaseModel):
    supplier_id: int = Field(..., gt=0)
    note: str | None = None


class UpdateOrderCommand(BaseModel):
    note: str | None = None
    expected_delivery_date: date | None = None
    storage_place: str | None = None
    supplier_id: int | None = None
    update_items_delivery_date: bool = False
    # The edit version the client read; a row that moved since answers 409.
    expected_edit_version: int | None = None


class OrderExtraCostInput(BaseModel):
    """One extra cost of an order as a request names it."""

    kind: ExtraCostKind
    amount: int = Field(..., gt=0)
    label: str | None = None
    note: str | None = None
    order_item_id: int | None = Field(default=None, gt=0)


class SetOrderExtraCostsCommand(BaseModel):
    """The whole list of an order's extra costs, in display order."""

    costs: list[OrderExtraCostInput] = Field(default_factory=list, max_length=50)
    # The edit version the client read; a row that moved since answers 409.
    expected_edit_version: int | None = None


class SetOrderSupplierOrderNumbersCommand(BaseModel):
    """The whole list of an order's supplier order numbers, in entry order."""

    numbers: list[str] = Field(default_factory=list)
    # The edit version the client read; a row that moved since answers 409.
    expected_edit_version: int | None = None


class OrderExtraCostResult(ResultBase):
    kind: ExtraCostKind
    amount: int
    position: int
    label: str | None
    note: str | None
    order_item_id: int | None


class OrderQuoteRequestResult(ResultModel):
    id: int
    request_number: str


class OrderResult(ResultBase):
    order_number: str
    status: str
    # The lifecycle actions the reading user may take now, from the intent
    # table (lifecycle/intents.py); empty where no user is known.
    actions: list[str] = Field(default_factory=list)
    # The actions the state allows now but the reading user lacks a
    # permission for, each with that permission, which the client shows
    # disabled and names.
    blocked_actions: dict[str, str] = Field(default_factory=dict)
    created: datetime
    changed: datetime | None
    note: str | None
    ordered_date: datetime | None
    expected_delivery_date: date | None
    delivery_date: datetime | None
    storage_place: str | None
    supplier_order_numbers: list[str] = Field(default_factory=list)
    creator_id: int
    creator: PublicUserResult | None
    changed_by_id: int | None
    changed_by: PublicUserResult | None
    supplier_id: int
    supplier_name: str
    supplier_vat_id: str
    supplier_archived: bool = False
    # Lifecycle intents, read-only (see the Order entity).
    requested_at: datetime | None = None
    canceled_at: datetime | None = None
    edit_version: int = 0
    items: list["OrderItemResult"] = Field(default_factory=list)
    extra_costs: list[OrderExtraCostResult] = Field(default_factory=list)
    # The quote requests the order's lines were awarded from.
    quote_requests: list[OrderQuoteRequestResult] = Field(default_factory=list)

    # ── Totals in net cents (domain/services/extra_cost_rules.py) ─────
    # The priced lines that are not canceled, None while no line carries
    # a price; the extra costs with discounts subtracted; and both added,
    # None while the order has neither.
    lines_total: int | None = None
    extra_costs_total: int = 0
    net_total: int | None = None

    # ── Derived from the items (see OrderMapper.to_result) ────────────
    # An order has no orderer or receiver column of its own; those live
    # per line, because lines can be ordered and received separately. The
    # order docket still wants one name for each, so they are summarised
    # here once rather than in every consumer.
    total_items: float = 0.0  # Σ quantity × items_per_unit across the lines
    orderer_full_name: str = ""  # the first line's orderer, by position
    delivered_by_full_name: str = ""  # receiver of the most recent delivery


# ══════════════════════════════════════════════════════════════════════
# OrderItem
# ══════════════════════════════════════════════════════════════════════


class OrderLineDemandAllocationInput(BaseModel):
    """How much of a new order line one demand takes."""

    demand_item_id: int = Field(..., gt=0)
    quantity: float = Field(..., gt=0)


def check_line_demand_allocations(
    quantity: float,
    *,
    bought_item_id: int | None,
    virtual_name: str | None,
    bought: list[OrderLineDemandAllocationInput],
    source: list[OrderLineDemandAllocationInput],
) -> None:
    """Raises ValueError unless the demands a new line takes fit it: each
    demand once, bought demands only on a bought line, none on a free-text
    line, and together no more than the line's quantity."""
    if virtual_name and (bought or source):
        raise ValueError("A free-text line takes no demand allocations.")
    if bought and bought_item_id is None:
        raise ValueError("Bought item demands are allocated on a bought item line only.")
    for allocations in (bought, source):
        ids = [a.demand_item_id for a in allocations]
        if len(ids) != len(set(ids)):
            raise ValueError("A demand may take a share of the line only once.")
    if quantity_gt(sum(a.quantity for a in (*bought, *source)), quantity):
        raise ValueError("The demand allocations exceed the line's quantity.")


class CreateOrderItemCommand(BaseModel):
    bought_item_id: int | None = Field(default=None, gt=0)
    source_item_id: int | None = Field(default=None, gt=0)
    virtual_name: str | None = None
    order_id: int = Field(..., gt=0)
    supplier_id: int = Field(..., gt=0)
    project_id: int = Field(..., gt=0)
    quantity: float = Field(..., gt=0)
    unit: str = Field(..., min_length=1)
    items_per_unit: float = Field(default=1.0, gt=0)
    price: int | None = None  # net, in EUR cents
    note: str | None = None
    expected_delivery_date: date | None = None
    expected_pickup_date: date | None = None
    bought_demand_allocations: list[OrderLineDemandAllocationInput] = Field(default_factory=list)
    source_demand_allocations: list[OrderLineDemandAllocationInput] = Field(default_factory=list)
    substitute_reason: str | None = None

    @model_validator(mode="after")
    def require_exactly_one_item_reference(self) -> "CreateOrderItemCommand":
        provided = [
            self.bought_item_id is not None,
            self.source_item_id is not None,
            bool(self.virtual_name),
        ]
        if sum(provided) != 1:
            raise ValueError(
                "Exactly one of bought_item_id, source_item_id, or virtual_name must be provided."
            )
        check_line_demand_allocations(
            self.quantity,
            bought_item_id=self.bought_item_id,
            virtual_name=self.virtual_name,
            bought=self.bought_demand_allocations,
            source=self.source_demand_allocations,
        )
        return self


class UpdateOrderItemCommand(BaseModel):
    quantity: float = Field(..., gt=0)
    unit: str = Field(..., min_length=1)
    items_per_unit: float = Field(default=1.0, gt=0)
    price: int | None = None
    note: str | None = None
    expected_delivery_date: date | None = None
    expected_pickup_date: date | None = None
    storage_place: str | None = None
    bought_item_id: int | None = None
    virtual_name: str | None = None
    substitute_reason: str | None = None
    project_id: int | None = None
    position: int | None = Field(default=None, gt=0)
    # The edit version the client read; a row that moved since answers 409.
    expected_edit_version: int | None = None


class DemandSubstitutionInfo(ResultModel):
    demand_item_id: int
    original_item_id: int
    original_item_order_code_1: str
    original_item_article_name: str
    substitute_reason: str | None
    quantity: float


class DeliveryRecordInfo(ResultBase):
    quantity: float
    delivery_date: datetime
    storage_place: str | None
    receiver_id: int | None
    receiver: PublicUserResult | None
    quantity_rejected: float
    rejection_reason: str | None
    rejection_note: str | None
    rejection_outcome: str | None
    # Set on a correction row, whose negative quantity takes back accepted
    # pieces of the delivery row it names. A correction that rejects the
    # pieces it takes back, damage found after receipt, carries them in
    # quantity_rejected with their reason and outcome instead of a
    # correction reason.
    corrects_delivery_id: int | None = None
    correction_reason: str | None = None
    # The received material's origin: batch or heat number, delivery note,
    # certificate.
    supplier_batch: str | None = None
    delivery_note_number: str | None = None
    certificate_reference: str | None = None
    # Whether damage was noted on the carrier's delivery note at handover.
    damage_noted_on_delivery_note: bool = False


class DeliveryRejectionInput(BaseModel):
    """One line's rejection booking within a DeliverAllOrderItems call,
    per-line, since only some of an order's lines may be rejected in a
    single bulk delivery. See ProcessOrderItemDelivery.execute for what
    each field does."""

    order_item_id: int = Field(..., gt=0)
    quantity_rejected: float = Field(..., gt=0)
    rejection_reason: str
    rejection_note: str | None = None
    rejection_outcome: str
    create_replacement: bool = True


class OrderItemResult(ResultBase):
    status: str
    # The lifecycle actions the reading user may take now, from the intent
    # table (lifecycle/intents.py); empty where no user is known.
    actions: list[str] = Field(default_factory=list)
    # The actions the state allows now but the reading user lacks a
    # permission for, each with that permission, which the client shows
    # disabled and names.
    blocked_actions: dict[str, str] = Field(default_factory=dict)
    created: datetime
    changed: datetime | None
    position: int
    quantity: float
    quantity_delivered: float
    quantity_rejected: float
    quantity_rejected_lost: float
    unit: str
    items_per_unit: float
    price: int | None
    note: str | None
    ordered_date: datetime | None
    expected_delivery_date: date | None
    delivery_date: datetime | None
    storage_place: str | None
    expected_pickup_date: date | None
    ready_for_pickup_date: datetime | None
    creator_id: int
    creator: PublicUserResult | None
    changed_by_id: int | None
    changed_by: PublicUserResult | None
    orderer_id: int | None
    orderer: PublicUserResult | None
    receiver_id: int | None
    receiver: PublicUserResult | None
    bought_item_id: int | None
    source_item_id: int | None
    virtual_name: str | None
    # The quote request an award created the line from, if any.
    quote_request_line_id: int | None = None
    quote_request_id: int | None = None
    quote_request_number: str = ""
    item_order_code_1: str
    item_order_code_2: str | None
    item_specification: str
    item_article_name: str
    item_part_number: str | None
    # Per-line-type catalogue descriptors; None wherever the line type has no
    # such concept (see the OrderItem entity). item_mass is in grams.
    item_material: str | None
    item_dimension: str | None
    item_type_name: str | None
    item_revision: str | None
    item_base_size: str | None
    item_mass: int | None
    item_manufacturer: str | None
    made_item_id: int | None
    order_id: int
    supplier_id: int
    supplier_name: str
    project_id: int
    project_number: str
    product_number: str | None
    project_customer: str
    project_description: str
    project_status: str
    line_type: str
    lot_position_id: int | None
    lot_id: int | None
    lot_number: str
    fabrication_method: str
    # Lifecycle intents, read-only (see the OrderItem entity).
    requested_at: datetime | None = None
    canceled_at: datetime | None = None
    edit_version: int = 0
    closed_short_at: datetime | None = None
    closed_short_from: float | None = None
    demand_substitutions: list[DemandSubstitutionInfo] = Field(default_factory=list)
    delivery_records: list[DeliveryRecordInfo] = Field(default_factory=list)


OrderResult.model_rebuild()


class DeliverAllSkippedLine(BaseModel):
    """A line deliver-all left alone, with why: not ordered yet, already
    delivered, canceled, on a canceled order, on a canceled lot, or moved
    to another order while deliver-all waited for its lock."""

    order_item_id: int
    position: int
    reason: Literal[
        "not_ordered", "delivered", "canceled", "order_canceled", "lot_canceled", "moved"
    ]


class DeliverAllResult(BaseModel):
    """What deliver-all booked and what it skipped."""

    delivered: list[OrderItemResult] = Field(default_factory=list)
    skipped: list[DeliverAllSkippedLine] = Field(default_factory=list)
