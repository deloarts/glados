"""
HTTP schemas for the Order/OrderItem vertical.
"""

from datetime import date
from datetime import datetime
from typing import Annotated
from typing import Literal

from fastapi import Query
from pydantic import BaseModel
from pydantic import Field
from pydantic import model_validator

from src.modules.fulfillment.application.dto.order_dto import DeliveryRecordInfo
from src.modules.fulfillment.application.dto.order_dto import DeliveryRejectionInput
from src.modules.fulfillment.application.dto.order_dto import DemandSubstitutionInfo
from src.modules.fulfillment.application.dto.order_dto import OrderLineDemandAllocationInput
from src.modules.fulfillment.application.dto.order_dto import check_line_demand_allocations
from src.modules.fulfillment.domain.value_objects.extra_cost_kind import ExtraCostKind
from src.modules.fulfillment.domain.value_objects.material_receipt import MAX_REFERENCE_LENGTH
from src.modules.fulfillment.domain.value_objects.material_receipt import MaterialReceipt
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.order_status import OrderStatus
from src.modules.fulfillment.domain.value_objects.rejection_after_receipt import (
    RejectionAfterReceipt,
)
from src.modules.fulfillment.domain.value_objects.rejection_outcome import RejectionOutcome
from src.modules.fulfillment.domain.value_objects.scrap_reason import ScrapReason
from src.modules.fulfillment.ports.outbound.repositories.order_repository import OrderFilterDto
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import NonBlankReason
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.platform.adapters.inbound.api.schemas.quantity_fields import NonNegativeQuantity
from src.modules.platform.adapters.inbound.api.schemas.quantity_fields import PositiveQuantity
from src.modules.platform.adapters.inbound.api.schemas.user_schema import PublicUserResponse
from src.modules.platform.const import MAX_PAGE_SIZE
from src.modules.workspace.domain.value_objects.project_status import ProjectStatus
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction

# ══════════════════════════════════════════════════════════════════════
# Order
# ══════════════════════════════════════════════════════════════════════


class OrderCreateRequest(BaseModel):
    supplier_id: int = Field(..., gt=0)
    note: str | None = None


class OrderUpdateRequest(BaseModel):
    note: str | None = None
    expected_delivery_date: date | None = None
    storage_place: str | None = None
    supplier_id: int | None = None
    update_items_delivery_date: bool = False
    # The edit version read; a row that moved since answers 409.
    expected_edit_version: int


class OrderSupplierOrderNumbersUpdateRequest(BaseModel):
    """Replaces every supplier order number of the order, in entry order."""

    numbers: list[Annotated[str, Field(max_length=100)]] = Field(
        default_factory=list, max_length=50
    )
    # The edit version read; a row that moved since answers 409.
    expected_edit_version: int


class OrderExtraCostRequest(BaseModel):
    kind: ExtraCostKind
    # Net, in EUR cents; a discount is sent as a positive amount.
    amount: int = Field(..., gt=0)
    label: str | None = Field(default=None, max_length=120)
    note: str | None = None
    # The line the cost belongs to; left out for the whole order.
    order_item_id: int | None = Field(default=None, gt=0)


class OrderExtraCostsUpdateRequest(BaseModel):
    """Replaces every extra cost of the order, in display order."""

    costs: list[OrderExtraCostRequest] = Field(default_factory=list, max_length=50)
    # The edit version read; a row that moved since answers 409.
    expected_edit_version: int


class OrderExtraCostResponse(EntityResponse):
    kind: ExtraCostKind
    amount: int
    position: int
    label: str | None
    note: str | None
    order_item_id: int | None


class OrderQuoteRequestResponse(ResponseModel):
    id: int
    request_number: str


class OrderResponse(EntityResponse):
    order_number: str
    status: OrderStatus
    # The lifecycle actions the reading user may take now, computed from the
    # aggregate's intent table; the client gates its buttons on them.
    actions: list[LifecycleAction] = Field(default_factory=list)
    # The actions the state allows now but the reading user lacks a
    # permission for, each with that permission; the client shows them
    # disabled and names the permission.
    blocked_actions: dict[LifecycleAction, str] = Field(default_factory=dict)
    created: datetime
    changed: datetime | None
    note: str | None
    ordered_date: datetime | None
    expected_delivery_date: date | None
    delivery_date: datetime | None
    storage_place: str | None
    # The supplier's own numbers for the order, in entry order.
    supplier_order_numbers: list[str]
    creator_id: int
    creator: PublicUserResponse | None
    changed_by_id: int | None
    changed_by: PublicUserResponse | None
    supplier_id: int
    supplier_name: str
    supplier_vat_id: str
    # Whether the supplier was archived; the order still names it.
    supplier_archived: bool
    # Lifecycle intents, read-only.
    requested_at: datetime | None = None
    canceled_at: datetime | None = None
    edit_version: int = 0
    items: list["OrderItemResponse"] = Field(default_factory=list)
    extra_costs: list[OrderExtraCostResponse] = Field(default_factory=list)
    # The quote requests the order's lines were awarded from, read through
    # the lines' links.
    quote_requests: list[OrderQuoteRequestResponse] = Field(default_factory=list)
    # Totals in net EUR cents: the priced lines that are not canceled (None
    # while no line has a price), the extra costs with discounts
    # subtracted, and both added (None while the order has neither).
    lines_total: int | None
    extra_costs_total: int
    net_total: int | None


class OrderFilterParams:
    def __init__(
        self,
        skip: Annotated[int | None, Query(ge=0)] = None,
        limit: Annotated[int | None, Query(ge=1, le=MAX_PAGE_SIZE)] = None,
        ids: Annotated[list[int] | None, Query(max_length=200)] = None,
        status: Annotated[list[OrderStatus] | None, Query()] = None,
        supplier_id: Annotated[int | None, Query()] = None,
        creator_id: Annotated[int | None, Query()] = None,
        changed_by_id: Annotated[int | None, Query()] = None,
        has_invoice: Annotated[bool | None, Query()] = None,
        ordered_from: Annotated[date | None, Query()] = None,
        ordered_to: Annotated[date | None, Query()] = None,
        expected_delivery_from: Annotated[date | None, Query()] = None,
        expected_delivery_to: Annotated[date | None, Query()] = None,
        delivered_from: Annotated[date | None, Query()] = None,
        delivered_to: Annotated[date | None, Query()] = None,
        created_from: Annotated[date | None, Query()] = None,
        created_to: Annotated[date | None, Query()] = None,
        bought_item_id: Annotated[int | None, Query()] = None,
        source_item_id: Annotated[int | None, Query()] = None,
        made_item_id: Annotated[int | None, Query()] = None,
        project_id: Annotated[int | None, Query()] = None,
        product_id: Annotated[
            int | None,
            Query(description="Orders with an item for a project built on this product"),
        ] = None,
        order_number: Annotated[str | None, Query()] = None,
        note: Annotated[str | None, Query()] = None,
        storage_place: Annotated[str | None, Query()] = None,
        search: Annotated[str | None, Query()] = None,
        order_by: Annotated[
            Literal["id", "order_number", "ordered_date", "expected_delivery_date", "created"]
            | None,
            Query(),
        ] = None,
        order_dir: Annotated[Literal["asc", "desc"] | None, Query()] = None,
    ):
        self.skip = skip
        self.limit = limit
        self.ids = ids
        self.status = status
        self.supplier_id = supplier_id
        self.creator_id = creator_id
        self.changed_by_id = changed_by_id
        self.has_invoice = has_invoice
        self.ordered_from = ordered_from
        self.ordered_to = ordered_to
        self.expected_delivery_from = expected_delivery_from
        self.expected_delivery_to = expected_delivery_to
        self.delivered_from = delivered_from
        self.delivered_to = delivered_to
        self.created_from = created_from
        self.created_to = created_to
        self.bought_item_id = bought_item_id
        self.source_item_id = source_item_id
        self.made_item_id = made_item_id
        self.project_id = project_id
        self.product_id = product_id
        self.order_number = order_number
        self.note = note
        self.storage_place = storage_place
        self.search = search
        self.order_by = order_by
        self.order_dir = order_dir

    def to_dto(self) -> OrderFilterDto:
        return OrderFilterDto(
            skip=self.skip,
            limit=self.limit,
            ids=self.ids,
            status=[s.value for s in self.status] if self.status else None,
            supplier_id=self.supplier_id,
            creator_id=self.creator_id,
            changed_by_id=self.changed_by_id,
            has_invoice=self.has_invoice,
            ordered_from=self.ordered_from,
            ordered_to=self.ordered_to,
            expected_delivery_from=self.expected_delivery_from,
            expected_delivery_to=self.expected_delivery_to,
            delivered_from=self.delivered_from,
            delivered_to=self.delivered_to,
            created_from=self.created_from,
            created_to=self.created_to,
            bought_item_id=self.bought_item_id,
            source_item_id=self.source_item_id,
            made_item_id=self.made_item_id,
            project_id=self.project_id,
            product_id=self.product_id,
            order_number=self.order_number,
            note=self.note,
            storage_place=self.storage_place,
            search=self.search,
            order_by=self.order_by,
            order_dir=self.order_dir,
        )


# ══════════════════════════════════════════════════════════════════════
# OrderItem
# ══════════════════════════════════════════════════════════════════════


class OrderLineDemandAllocationRequest(BaseModel):
    demand_item_id: int = Field(..., gt=0)
    quantity: PositiveQuantity


class OrderItemCreateRequest(BaseModel):
    bought_item_id: int | None = Field(default=None, gt=0)
    source_item_id: int | None = Field(default=None, gt=0)
    virtual_name: str | None = None
    order_id: int = Field(..., gt=0)
    supplier_id: int = Field(..., gt=0)
    project_id: int = Field(..., gt=0)
    quantity: PositiveQuantity
    unit: str = Field(..., min_length=1)
    items_per_unit: PositiveQuantity = 1.0
    price: int | None = None
    note: str | None = None
    expected_delivery_date: date | None = None
    expected_pickup_date: date | None = None
    # The share of the new line each demand takes, so the buyer decides
    # which demand a substitute or a short line is meant for.
    bought_demand_allocations: list[OrderLineDemandAllocationRequest] = Field(default_factory=list)
    source_demand_allocations: list[OrderLineDemandAllocationRequest] = Field(default_factory=list)
    substitute_reason: str | None = None

    @model_validator(mode="after")
    def require_exactly_one_item_reference(self) -> "OrderItemCreateRequest":
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
            bought=[
                OrderLineDemandAllocationInput(**a.model_dump())
                for a in self.bought_demand_allocations
            ],
            source=[
                OrderLineDemandAllocationInput(**a.model_dump())
                for a in self.source_demand_allocations
            ],
        )
        return self


class OrderItemUpdateRequest(BaseModel):
    quantity: PositiveQuantity
    unit: str = Field(..., min_length=1)
    items_per_unit: PositiveQuantity = 1.0
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
    # The edit version read; a row that moved since answers 409.
    expected_edit_version: int


class MoveOrderItemRequest(BaseModel):
    target_order_id: int = Field(..., gt=0)


class DeliveryRejectionRequest(BaseModel):
    """Optional details booked together with a single-line delivery
    (PUT /bought-items-allocations/order-item/{order_item_id}/deliver): a
    rejection and where the received material comes from. `quantity` and
    `storage_place` stay query parameters on that endpoint, so a delivery
    with neither omits this body."""

    quantity_rejected: NonNegativeQuantity = 0.0
    rejection_reason: ScrapReason | None = None
    rejection_note: str | None = None
    rejection_outcome: RejectionOutcome | None = None
    create_replacement: bool = True
    # The material's origin: the supplier's batch or heat number, the
    # delivery note and the inspection certificate (EN 10204 3.1).
    supplier_batch: str | None = Field(default=None, max_length=MAX_REFERENCE_LENGTH)
    delivery_note_number: str | None = Field(default=None, max_length=MAX_REFERENCE_LENGTH)
    certificate_reference: str | None = Field(default=None, max_length=MAX_REFERENCE_LENGTH)
    # Whether damage was noted on the carrier's delivery note at handover.
    damage_noted_on_delivery_note: bool = False

    def material(self) -> MaterialReceipt:
        return MaterialReceipt(
            supplier_batch=self.supplier_batch,
            delivery_note_number=self.delivery_note_number,
            certificate_reference=self.certificate_reference,
            damage_noted_on_delivery_note=self.damage_noted_on_delivery_note,
        )


class OrderItemRejectionRequest(BaseModel):
    """One line's rejection within a DeliverAllOrderItemsRequest."""

    order_item_id: int = Field(..., gt=0)
    quantity_rejected: PositiveQuantity
    rejection_reason: ScrapReason
    rejection_note: str | None = None
    rejection_outcome: RejectionOutcome
    create_replacement: bool = True

    def to_input(self) -> DeliveryRejectionInput:
        return DeliveryRejectionInput(
            order_item_id=self.order_item_id,
            quantity_rejected=self.quantity_rejected,
            rejection_reason=self.rejection_reason.value,
            rejection_note=self.rejection_note,
            rejection_outcome=self.rejection_outcome.value,
            create_replacement=self.create_replacement,
        )


class DeliverAllOrderItemsRequest(BaseModel):
    """Optional body for PUT /orders/{id}/deliver-all-items: only lines
    that need a rejection booked are listed, every other line that can
    take a delivery still gets its full remaining quantity delivered."""

    rejections: list[OrderItemRejectionRequest] = Field(default_factory=list)
    # The shipment's delivery note, recorded on every line it books, and
    # whether damage was noted on it at handover.
    delivery_note_number: str | None = Field(default=None, max_length=MAX_REFERENCE_LENGTH)
    damage_noted_on_delivery_note: bool = False

    @model_validator(mode="after")
    def _one_rejection_per_line(self) -> "DeliverAllOrderItemsRequest":
        """A line takes one rejection per delivery: of two entries for one
        line only one could be booked, and the other's pieces would count
        as accepted."""
        seen: set[int] = set()
        for rejection in self.rejections:
            if rejection.order_item_id in seen:
                raise ValueError(
                    f"Order item #{rejection.order_item_id} has more than one rejection; "
                    "send one per line."
                )
            seen.add(rejection.order_item_id)
        return self


class RejectionAfterReceiptRequest(BaseModel):
    """Pieces a correction takes back as rejected ones, for damage found
    after the goods were accepted: why, what happens to them and a note."""

    rejection_reason: ScrapReason
    rejection_outcome: RejectionOutcome
    rejection_note: str | None = Field(default=None, max_length=1000)

    def to_value(self) -> RejectionAfterReceipt:
        note = (self.rejection_note or "").strip() or None
        return RejectionAfterReceipt(
            reason=self.rejection_reason.value, outcome=self.rejection_outcome, note=note
        )


class CorrectDeliveryRequest(BaseModel):
    """Body of POST /orders/{id}/items/{id}/deliveries/{id}/correct: how
    many accepted pieces of the delivery row to take back, and why. With
    `rejection` the pieces are taken back as rejected ones and `reason` may
    be left out; without it `reason` is required."""

    quantity: PositiveQuantity
    reason: NonBlankReason | None = Field(default=None, min_length=1, max_length=1000)
    rejection: RejectionAfterReceiptRequest | None = None
    # The line's edit version read; a line that moved since answers 409.
    expected_edit_version: int

    @model_validator(mode="after")
    def _explained(self) -> "CorrectDeliveryRequest":
        if self.rejection is None and self.reason is None:
            raise ValueError("A correction without a rejection needs a reason.")
        return self


class OrderItemResponse(EntityResponse):
    status: OrderItemStatus
    # The lifecycle actions the reading user may take now, computed from the
    # aggregate's intent table; the client gates its buttons on them.
    actions: list[LifecycleAction] = Field(default_factory=list)
    # The actions the state allows now but the reading user lacks a
    # permission for, each with that permission; the client shows them
    # disabled and names the permission.
    blocked_actions: dict[LifecycleAction, str] = Field(default_factory=dict)
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
    creator: PublicUserResponse | None
    changed_by_id: int | None
    changed_by: PublicUserResponse | None
    orderer_id: int | None
    orderer: PublicUserResponse | None
    receiver_id: int | None
    receiver: PublicUserResponse | None
    bought_item_id: int | None
    source_item_id: int | None
    virtual_name: str | None
    # The quote request an award created the line from, if any.
    quote_request_line_id: int | None
    quote_request_id: int | None
    quote_request_number: str
    item_order_code_1: str
    item_order_code_2: str | None
    item_specification: str
    item_article_name: str
    item_part_number: str | None
    # Per-line-type catalogue descriptors; null wherever the line type has no
    # such concept (see OrderItem entity). item_mass is in grams.
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
    project_customer: str
    project_description: str
    project_status: ProjectStatus
    line_type: OrderLineType
    lot_position_id: int | None
    lot_id: int | None
    lot_number: str
    fabrication_method: str
    # Lifecycle intents, read-only.
    requested_at: datetime | None = None
    canceled_at: datetime | None = None
    edit_version: int = 0
    closed_short_at: datetime | None = None
    closed_short_from: float | None = None
    demand_substitutions: list[DemandSubstitutionInfo] = Field(default_factory=list)
    delivery_records: list[DeliveryRecordInfo] = Field(default_factory=list)


OrderResponse.model_rebuild()


class DeliverAllSkippedLineResponse(ResponseModel):
    order_item_id: int
    position: int
    reason: Literal[
        "not_ordered", "delivered", "canceled", "order_canceled", "lot_canceled", "moved"
    ]


class DeliverAllResponse(ResponseModel):
    """The lines deliver-all booked and the ones it skipped, with why."""

    delivered: list[OrderItemResponse] = Field(default_factory=list)
    skipped: list[DeliverAllSkippedLineResponse] = Field(default_factory=list)
