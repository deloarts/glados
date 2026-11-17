"""
HTTP schemas for the ProductionLot / LotStep / LotPosition aggregate.
Mirrors made_item_demand_schema.py's conventions.
"""

from datetime import date
from datetime import datetime
from typing import Any
from typing import Literal

from fastapi import Query
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import model_validator

from src.modules.catalogue.domain.policies.step_role_rules import assert_role_matches_methods
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.adapters.inbound.api.schemas.made_item_demand_schema import (
    MadeItemDemandResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_order_schema import (
    CreatedLotResponse,
)
from src.modules.fulfillment.adapters.inbound.api.schemas.production_order_schema import (
    ProductionOrderResponse,
)
from src.modules.fulfillment.domain.value_objects.lot_event_type import LotEventType
from src.modules.fulfillment.domain.value_objects.lot_origin_disposition import LotOriginDisposition
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionKind
from src.modules.fulfillment.domain.value_objects.lot_status import LotPositionStatus
from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.domain.value_objects.schedule_conflict import ScheduleConflictReason
from src.modules.fulfillment.domain.value_objects.scrap_reason import ScrapReason
from src.modules.fulfillment.domain.value_objects.source_approval_status import SourceApprovalStatus
from src.modules.fulfillment.domain.value_objects.source_item_demand_status import (
    SourceItemDemandStatus,
)
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    LotFilterDto,
)
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import NonBlankReason
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageParams
from src.modules.platform.adapters.inbound.api.schemas.quantity_fields import PositiveQuantity
from src.modules.platform.adapters.inbound.api.schemas.user_schema import PublicUserResponse
from src.modules.platform.domain.exceptions import DomainError
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction


def _assert_step_role_shape(
    role: StepRole, fabrication_method_id: int | None, inspection_method_id: int | None
) -> None:
    """Runs the shared step role rule at request time and raises it as a
    ValueError, so a mismatch is a 422 rather than a 500 from the database
    check constraint, with the same message lot_rules uses."""
    try:
        assert_role_matches_methods(
            role.value,
            fabrication_method_id,
            inspection_method_id,
            error=DomainError,
            noun="step",
        )
    except DomainError as e:
        raise ValueError(str(e)) from None


# ══════════════════════════════════════════════════════════════════════
# Requests
# ══════════════════════════════════════════════════════════════════════


class LotDemandAllocationInputRequest(BaseModel):
    demand_item_id: int = Field(..., gt=0)
    quantity: PositiveQuantity


class LotCreateRequest(BaseModel):
    made_item_id: int = Field(..., gt=0)
    project_id: int = Field(..., gt=0)
    quantity: PositiveQuantity
    note: str | None = None
    priority: UrgencyClass | None = None
    demand_allocations: list[LotDemandAllocationInputRequest] = Field(default_factory=list)
    required_delivery_date: date | None = None


class LotUpdateRequest(BaseModel):
    note: str | None = None
    priority: UrgencyClass | None = None
    quantity: PositiveQuantity | None = None
    required_delivery_date: date | None = None
    # The edit version read; a row that moved since answers 409.
    expected_edit_version: int


class SwitchLotMaterialSourceRequest(BaseModel):
    bought_item_id: int | None = None
    source_item_id: int | None = None
    made_item_id: int | None = None
    confirm_replace_demand: bool = False
    # The edit version read; a switch is irreversible, so a lot that moved
    # since answers 409.
    expected_edit_version: int


# The status keys the lots table's step status cell displays. Several of
# them fold the stored LotPositionStatus together with the position's kind
# (a pending external position reads "allocated", an ordered_or_queued
# internal one reads "queued"), so the filter takes the display key and
# lot.py's _step_display_status_predicate maps it back to stored columns.
StepDisplayStatus = Literal[
    "pending",
    "allocated",
    "ordered",
    "queued",
    "ordered_or_queued",
    "in_progress",
    "partially_completed",
    "completed",
    "canceled",
]


class LotFilterParams(PageParams):
    ids: list[int] | None = Query(default=None, max_length=200)
    search: str | None = Query(default=None, description="Fuzzy search across lot/item text")
    status: LotStatus | None = Query(default=None)
    statuses: list[LotStatus] | None = Query(default=None)
    actionable_for: Literal["orders", "machines", "source"] | None = Query(default=None)
    made_item_id: int | None = Query(default=None)
    project_id: int | None = Query(default=None)
    project_number: str | None = Query(default=None)
    item_article_name: str | None = Query(default=None)
    item_part_number: str | None = Query(default=None)
    creator_id: int | None = Query(default=None)
    changed_by_id: int | None = Query(default=None)
    priority: UrgencyClass | None = Query(default=None)
    created_from: date | None = Query(default=None)
    created_to: date | None = Query(default=None)
    changed_from: date | None = Query(default=None)
    changed_to: date | None = Query(default=None)
    order_by: Literal["id", "lot_number", "created", "quantity"] | None = Query(default=None)
    order_dir: Literal["asc", "desc"] | None = Query(default=None)
    # Mutually exclusive coverage filters: lets a planner narrow the list
    # without opening every lot to check capability by hand. See lot.py's
    # _coverable_lot_exists for the coverage semantics.
    coverable_by_machine_id: int | None = Query(default=None)
    coverable_by_pool_id: int | None = Query(default=None)
    coverable_by_any_pool: bool | None = Query(default=None)
    # "Needs Approval" worklist filter, see LotsViews.vue.
    source_approval_status: SourceApprovalStatus | None = Query(default=None)
    # Per-column filters of the lots table. Field names mirror LotFilterDto
    # exactly (to_dto is a blind model_dump); the DTO's comments explain the
    # semantics of each family.
    lot_number: str | None = Query(default=None)
    target_date_from: date | None = Query(default=None)
    target_date_to: date | None = Query(default=None)
    quantity_min: float | None = Query(default=None, ge=0)
    quantity_max: float | None = Query(default=None, ge=0)
    source_text: str | None = Query(default=None)
    source_dimension: str | None = Query(default=None)
    source_type: str | None = Query(default=None)
    source_status: SourceItemDemandStatus | None = Query(default=None)
    source_delivery_from: date | None = Query(default=None)
    source_delivery_to: date | None = Query(default=None)
    step_fabrication_method_id: int | None = Query(default=None, gt=0)
    step_inspection_method_id: int | None = Query(default=None, gt=0)
    step_status: StepDisplayStatus | None = Query(default=None)
    step_setup_min: int | None = Query(default=None, ge=0)
    step_setup_max: int | None = Query(default=None, ge=0)
    step_per_piece_min: float | None = Query(default=None, ge=0)
    step_per_piece_max: float | None = Query(default=None, ge=0)
    step_planned_start_from: date | None = Query(default=None)
    step_planned_start_to: date | None = Query(default=None)
    step_planned_end_from: date | None = Query(default=None)
    step_planned_end_to: date | None = Query(default=None)
    step_delivery_from: date | None = Query(default=None)
    step_delivery_to: date | None = Query(default=None)
    step_note: str | None = Query(default=None)

    @model_validator(mode="after")
    def validate_step_method_filter(self) -> "LotFilterParams":
        if (
            self.step_fabrication_method_id is not None
            and self.step_inspection_method_id is not None
        ):
            raise ValueError(
                "step_fabrication_method_id and step_inspection_method_id are mutually exclusive."
            )
        return self

    @model_validator(mode="after")
    def validate_range_filters(self) -> "LotFilterParams":
        for name, low, high in (
            ("quantity", self.quantity_min, self.quantity_max),
            ("step_setup", self.step_setup_min, self.step_setup_max),
            ("step_per_piece", self.step_per_piece_min, self.step_per_piece_max),
        ):
            if low is not None and high is not None and low > high:
                raise ValueError(f"{name}_min must not exceed {name}_max.")
        return self

    @model_validator(mode="after")
    def validate_coverage_filter(self) -> "LotFilterParams":
        if (
            sum(
                [
                    self.coverable_by_machine_id is not None,
                    self.coverable_by_pool_id is not None,
                    bool(self.coverable_by_any_pool),
                ]
            )
            > 1
        ):
            raise ValueError(
                "coverable_by_machine_id, coverable_by_pool_id and coverable_by_any_pool "
                "are mutually exclusive."
            )
        return self

    def to_dto(self) -> LotFilterDto:
        return LotFilterDto(**self.model_dump())


class LotBulkReadParams(BaseModel):
    """Query params for GET /production-lots/bulk. `ids` mirrors
    LotFilterParams.ids' max_length=200 ceiling, but is required with at
    least one id: unlike the list endpoint's filter, there is no
    meaningful bulk-read request with no ids at all."""

    ids: list[int] = Query(..., min_length=1, max_length=200)


class AddLotStepRequest(BaseModel):
    position_id: int = Field(..., gt=0)
    role: StepRole = StepRole.FABRICATION
    fabrication_method_id: int | None = Field(default=None, gt=0)
    inspection_method_id: int | None = Field(default=None, gt=0)
    note: str | None = None
    estimated_setup_minutes: int | None = Field(default=None, ge=0)
    estimated_minutes_per_piece: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_role_shape(self) -> "AddLotStepRequest":
        _assert_step_role_shape(self.role, self.fabrication_method_id, self.inspection_method_id)
        return self


class UpdateLotStepRequest(BaseModel):
    role: StepRole = StepRole.FABRICATION
    fabrication_method_id: int | None = Field(default=None, gt=0)
    inspection_method_id: int | None = Field(default=None, gt=0)
    note: str | None = None
    estimated_setup_minutes: int | None = Field(default=None, ge=0)
    estimated_minutes_per_piece: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_role_shape(self) -> "UpdateLotStepRequest":
        _assert_step_role_shape(self.role, self.fabrication_method_id, self.inspection_method_id)
        return self


class ReorderLotStepsRequest(BaseModel):
    ordered_step_ids: list[int] = Field(..., min_length=1)


class RegroupLotPositionsRequest(BaseModel):
    groups: list[list[int]] = Field(..., min_length=1)


class AppendLotPositionStepRequest(BaseModel):
    role: StepRole = StepRole.FABRICATION
    fabrication_method_id: int | None = Field(default=None, gt=0)
    inspection_method_id: int | None = Field(default=None, gt=0)
    note: str | None = None
    estimated_setup_minutes: int | None = Field(default=None, ge=0)
    estimated_minutes_per_piece: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_role_shape(self) -> "AppendLotPositionStepRequest":
        _assert_step_role_shape(self.role, self.fabrication_method_id, self.inspection_method_id)
        return self


class AppendLotPositionRequest(BaseModel):
    steps: list[AppendLotPositionStepRequest] = Field(..., min_length=1)


class ReplaceLotStructureStepRequest(BaseModel):
    id: int | None = Field(default=None, gt=0)
    role: StepRole = StepRole.FABRICATION
    fabrication_method_id: int | None = Field(default=None, gt=0)
    inspection_method_id: int | None = Field(default=None, gt=0)
    note: str | None = None
    estimated_setup_minutes: int | None = Field(default=None, ge=0)
    estimated_minutes_per_piece: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_role_shape(self) -> "ReplaceLotStructureStepRequest":
        _assert_step_role_shape(self.role, self.fabrication_method_id, self.inspection_method_id)
        return self


class ReplaceLotStructurePositionRequest(BaseModel):
    steps: list[ReplaceLotStructureStepRequest] = Field(..., min_length=1)


class ReplaceLotStructureRequest(BaseModel):
    positions: list[ReplaceLotStructurePositionRequest] = Field(..., min_length=1)


class AssignExternalPositionRequest(BaseModel):
    order_id: int = Field(..., gt=0)
    unit: str = Field(..., min_length=1)
    items_per_unit: PositiveQuantity = 1.0
    price: int | None = None
    expected_delivery_date: date | None = None
    expected_pickup_date: date | None = None
    quantity: PositiveQuantity | None = None


class CancelLotRequest(BaseModel):
    reason: str | None = None
    # The edit version read; a row that moved since answers 409.
    expected_edit_version: int


class CompleteLotRequest(BaseModel):
    reason: str | None = None
    # The edit version read; a row that moved since answers 409.
    expected_edit_version: int


class HoldLotRequest(BaseModel):
    reason: str = Field(..., min_length=1)


class ApproveLotSourceRequest(BaseModel):
    # The lot's edit version read; a lot that moved since answers 409.
    expected_edit_version: int


class RejectLotSourceRequest(BaseModel):
    reason: NonBlankReason = Field(..., min_length=1, max_length=1000)
    # The lot's edit version read; a lot that moved since answers 409.
    expected_edit_version: int


class ScrapLotPiecesRequest(BaseModel):
    position_id: int = Field(..., gt=0)
    production_order_id: int | None = Field(default=None, gt=0)
    quantity: PositiveQuantity
    reason: ScrapReason
    note: str | None = None
    create_replacement: bool = True
    operator_id: int | None = None
    # The edit version read; a row that moved since answers 409.
    expected_edit_version: int


class RecordLotPositionProvisionRequest(BaseModel):
    quantity: PositiveQuantity
    provision_date: date
    note: str | None = None


# ══════════════════════════════════════════════════════════════════════
# Responses
# ══════════════════════════════════════════════════════════════════════


class LotStepResponse(EntityResponse):
    created: datetime
    note: str | None
    estimated_setup_minutes: int | None
    estimated_minutes_per_piece: float | None
    sequence: int
    creator_id: int
    role: StepRole
    inspection_method_id: int | None
    fabrication_method_id: int | None
    fabrication_method_name: dict[str, str]
    fabrication_method_requires_machine: bool = True
    fabrication_method_required_external: bool = False
    fabrication_method_default_supplier_id: int | None = None
    inspection_method_name: dict[str, str] | None = None
    inspection_method_requires_evidence: bool | None = None
    lot_id: int
    position_id: int
    source_process_id: int | None
    time_budget_per_piece: float | None


class LotPositionOrderLineResponse(ResponseModel):
    """A position's order line older than its newest one. Only a line closed
    short can be followed by another, so each one was closed short."""

    order_item_id: int
    order_id: int | None
    order_number: str
    supplier_name: str
    quantity: float
    quantity_delivered: float
    unit: str
    closed_short: bool


class LotPositionResponse(EntityResponse):
    created: datetime
    changed: datetime | None
    sequence: int
    kind: LotPositionKind
    status: LotPositionStatus
    # The lifecycle actions the reading user may take now, computed from the
    # aggregate's intent table; the client gates its buttons on them.
    actions: list[LifecycleAction] = Field(default_factory=list)
    quantity: float
    quantity_completed: float
    quantity_remaining: float
    note: str | None
    creator_id: int
    changed_by_id: int | None
    changed_by: PublicUserResponse | None
    lot_id: int
    steps: list[LotStepResponse] = Field(default_factory=list)
    order_item_id: int | None = None
    order_id: int | None = None
    order_number: str = ""
    supplier_name: str = ""
    order_item_status: OrderItemStatus | Literal[""] = ""
    # The line was closed short, so the rest of the position takes a new line.
    order_item_closed_short: bool = False
    # The position's earlier lines, newest first, below the line above.
    earlier_order_lines: list[LotPositionOrderLineResponse] = Field(default_factory=list)
    expected_delivery_date: date | None = None
    # Scheduler forecast, EXTERNAL/MIXED positions only, NULL while the
    # chain feeding this position isn't known yet. A typed date above
    # always wins for readiness once set; these exist so the position
    # shows a forecast even when nobody has typed one yet.
    planned_pickup_date: date | None = None
    planned_delivery_date: date | None = None
    production_orders: list[ProductionOrderResponse] = Field(default_factory=list)


class FollowUpLotResponse(ResponseModel):
    id: int
    lot_number: str
    disposition: LotOriginDisposition
    quantity: float


class LotResponse(EntityResponse):
    created: datetime
    changed: datetime | None
    lot_number: str
    quantity: float
    quantity_completed: float
    status: LotStatus
    # The lifecycle actions the reading user may take now, computed from the
    # aggregate's intent table; the client gates its buttons on them.
    actions: list[LifecycleAction] = Field(default_factory=list)
    # The actions the state allows now but the reading user lacks a
    # permission for, each with that permission; the client shows them
    # disabled and names the permission.
    blocked_actions: dict[LifecycleAction, str] = Field(default_factory=dict)
    priority: UrgencyClass
    note: str | None
    required_delivery_date: date | None = None
    completed_at: datetime | None = None
    quantity_scrapped: float = 0.0
    # Lifecycle intents, read-only.
    held_at: datetime | None = None
    canceled_at: datetime | None = None
    edit_version: int = 0
    force_completed_at: datetime | None = None
    replacement_lot_ids: list[int] = Field(default_factory=list)
    creator_id: int
    creator: PublicUserResponse | None
    changed_by_id: int | None
    changed_by: PublicUserResponse | None
    made_item_id: int
    made_item_part_number: str
    made_item_article_name: str
    made_item_revision: str
    made_item_material: str
    source_bought_item_id: int | None
    source_item_id: int | None
    source_made_item_id: int | None
    source_label: str
    source_sublabel: str
    # Where the lot's raw material is coming in from, resolved through
    # input_demand_id's allocations. All None for a lot with no demand, a
    # purely stock-fulfilled one, or one not yet allocated.
    source_order_id: int | None = None
    source_order_number: str | None = None
    source_expected_delivery_date: date | None = None
    source_delivery_date: datetime | None = None
    demand_status: SourceItemDemandStatus | Literal[""]
    is_alteration: bool
    project_id: int
    project_number: str
    project_customer: str
    input_demand_id: int | None
    origin_lot_id: int | None = None
    origin_lot_number: str | None = None
    origin_disposition: LotOriginDisposition | None = None
    # Source item approval. Bare user ids, no embedded user object, the
    # same call SourceItemWebResponse.approver_id already makes; the frontend
    # resolves them via usersStore.getById (see LotRecordSourceDemand.vue).
    source_approval_status: SourceApprovalStatus
    source_approved_by_id: int | None = None
    source_approved_date: datetime | None = None
    source_rejected_by_id: int | None = None
    source_rejected_date: datetime | None = None
    source_rejection_reason: str | None = None
    follow_up_lots: list[FollowUpLotResponse] = Field(default_factory=list)
    positions: list[LotPositionResponse] = Field(default_factory=list)
    steps: list[LotStepResponse] = Field(default_factory=list)


class LotSummaryStepResponse(EntityResponse):
    created: datetime
    note: str | None
    estimated_setup_minutes: int | None
    estimated_minutes_per_piece: float | None
    time_budget_per_piece: float | None
    sequence: int
    creator_id: int
    role: StepRole
    inspection_method_id: int | None
    fabrication_method_id: int | None
    fabrication_method_name: dict[str, str]
    fabrication_method_requires_machine: bool = True
    fabrication_method_required_external: bool = False
    fabrication_method_default_supplier_id: int | None = None
    inspection_method_name: dict[str, str] | None = None
    inspection_method_requires_evidence: bool | None = None
    lot_id: int
    position_id: int
    source_process_id: int | None
    position_kind: LotPositionKind
    position_needs_machine: bool
    position_status: LotPositionStatus
    position_quantity: float
    position_quantity_remaining: float
    # The lifecycle actions the reading user may take now, computed from the
    # aggregate's intent table; the client gates its buttons on them.
    actions: list[LifecycleAction] = Field(default_factory=list)


class LotSummaryProductionOrderResponse(ResponseModel):
    """The scheduling facts of an internal position's production orders that
    the lots list shows, a subset of the full production order."""

    id: int
    status: ProductionOrderStatus
    machine_id: int | None
    machine_internal_name: str
    machine_pool_id: int | None = None
    machine_pool_name: str = ""
    planned_start: datetime | None
    planned_end: datetime | None
    actual_start: datetime | None
    actual_end: datetime | None
    quantity_completed: float = 0.0
    edit_version: int = 0
    planned_by_name: str | None
    conflicts: list[ScheduleConflictReason] = Field(default_factory=list)
    # What currently governs this order's earliest possible start, see
    # LotSummaryProductionOrderResult.
    earliest_start_reason: str | None = None
    earliest_start_date: date | None = None


class LotSummaryPositionResponse(ResponseModel):
    """A position's procurement and execution facts, flattened for the lots
    list: the order line's delivery and pickup facts and the position's
    production orders."""

    id: int
    kind: LotPositionKind
    order_id: int | None
    order_number: str
    order_item_id: int | None
    order_item_status: OrderItemStatus | Literal[""]
    order_item_closed_short: bool = False
    order_item_quantity: float | None
    order_item_quantity_delivered: float | None
    order_item_unit: str
    order_item_items_per_unit: float
    order_item_edit_version: int = 0
    expected_delivery_date: date | None  # projected (target → date)
    delivery_date: datetime | None  # confirmed/arrived (event → timestamp)
    expected_pickup_date: date | None
    ready_for_pickup_date: datetime | None
    delivery_record_count: int
    ordered_by_name: str | None
    # Scheduler forecast, see LotPositionResponse's matching fields.
    planned_pickup_date: date | None = None
    planned_delivery_date: date | None = None
    # External/mixed only, see LotSummaryPositionResult's matching fields.
    lead_days: int | None = None
    lead_days_source: str | None = None
    production_orders: list[LotSummaryProductionOrderResponse] = Field(default_factory=list)


class LotSummaryResponse(EntityResponse):
    lot_number: str
    quantity: float
    quantity_completed: float
    status: LotStatus
    # The lifecycle actions the reading user may take now, computed from the
    # aggregate's intent table; the client gates its buttons on them.
    actions: list[LifecycleAction] = Field(default_factory=list)
    # The actions the state allows now but the reading user lacks a
    # permission for, each with that permission; the client shows them
    # disabled and names the permission.
    blocked_actions: dict[LifecycleAction, str] = Field(default_factory=dict)
    priority: UrgencyClass
    created: datetime
    changed: datetime | None
    required_delivery_date: date | None = None
    completed_at: datetime | None = None
    quantity_scrapped: float = 0.0
    replacement_lot_ids: list[int] = Field(default_factory=list)
    edit_version: int = 0
    # What the scheduler uses as this lot's due date, see
    # LotSummaryResult's matching fields.
    target_date: date | None = None
    target_date_source: Literal["lot", "demand"] | None = None
    target_date_demand_item_id: int | None = None
    made_item_id: int
    made_item_part_number: str
    made_item_article_name: str
    made_item_revision: str
    made_item_material: str
    source_bought_item_id: int | None
    source_item_id: int | None
    source_made_item_id: int | None
    source_label: str
    source_sublabel: str
    # The source material's own material string, for comparing against
    # made_item_material. Only resolvable for a stock (source item) source;
    # "" for a bought/made-item source, which has no comparable material.
    source_material: str = ""
    # Where the lot's raw material is coming in from, resolved through
    # input_demand_id's allocations. All None for a lot with no demand, a
    # purely stock-fulfilled one, or one not yet allocated.
    source_order_id: int | None = None
    source_order_number: str | None = None
    source_expected_delivery_date: date | None = None
    source_delivery_date: datetime | None = None
    demand_status: SourceItemDemandStatus | Literal[""]
    is_alteration: bool
    project_id: int
    project_number: str
    project_customer: str
    creator_id: int
    creator: PublicUserResponse | None
    changed_by_id: int | None
    changed_by: PublicUserResponse | None
    input_demand_id: int | None
    origin_lot_id: int | None = None
    origin_disposition: LotOriginDisposition | None = None
    # Source item approval: see LotResponse's matching fields. Carried on
    # the summary too (not just status) so the lots table can render a
    # rejected reason in a tooltip without opening the lot.
    source_approval_status: SourceApprovalStatus
    source_approved_by_id: int | None = None
    source_approved_date: datetime | None = None
    source_rejected_by_id: int | None = None
    source_rejected_date: datetime | None = None
    source_rejection_reason: str | None = None
    steps: list[LotSummaryStepResponse] = Field(default_factory=list)
    positions: list[LotSummaryPositionResponse] = Field(default_factory=list)


class LotPositionProvisionResponse(EntityResponse):
    lot_position_id: int
    quantity: float
    provision_date: date
    note: str | None
    creator_id: int
    creator: PublicUserResponse | None
    created: datetime


class LotPositionCompletionResponse(ResponseModel):
    position_id: int
    sequence: int
    kind: LotPositionKind
    status: LotPositionStatus
    quantity: float
    quantity_completed: float

    model_config = ConfigDict(from_attributes=True)


class LotPositionBalanceResponse(ResponseModel):
    """A position's piece balance: arrived = good + scrap + rework + lost +
    wip, a negative difference where it booked more than reached it, and the
    ISO 22400 produced quantity (good plus scrap)."""

    position_id: int
    sequence: int
    kind: LotPositionKind
    arrived: float
    good: float
    scrap: float
    rework: float
    lost: float
    wip: float
    difference: float
    produced: float

    model_config = ConfigDict(from_attributes=True)


class LotMaterialReceiptResponse(ResponseModel):
    """One receipt of the material a lot consumes, with its batch or heat
    number, delivery note and certificate."""

    delivery_id: int
    order_item_id: int
    order_id: int
    order_number: str
    delivery_date: datetime
    quantity: float
    supplier_batch: str | None
    delivery_note_number: str | None
    certificate_reference: str | None
    corrects_delivery_id: int | None

    model_config = ConfigDict(from_attributes=True)


class LotEventResponse(EntityResponse):
    lot_id: int
    occurred_at: datetime
    actor_id: int | None
    actor_username: str | None
    actor_full_name: str
    event_type: LotEventType
    entity: Literal["lot", "position", "step", "order"]
    entity_id: int | None
    summary: str
    payload: dict[str, Any] | None


class LotDemandResponse(MadeItemDemandResponse):
    """A made-item demand this lot was raised to cover, plus how much of it
    this specific lot allocates (a demand can span more than one lot)."""

    allocated_quantity: float


class AutoAssignLotGroupDemandResponse(ResponseModel):
    demand_item_id: int
    quantity: float


class AutoAssignLotGroupResponse(ResponseModel):
    made_item_id: int
    item_part_number: str
    item_revision: str
    item_article_name: str
    project_id: int
    project_number: str
    project_customer: str
    quantity: float
    high_priority: bool
    demands: list[AutoAssignLotGroupDemandResponse]
    required_delivery_date: date | None


class ScrapPiecesResponse(ResponseModel):
    """Response shape shared by POST /production-orders/{id}/scrap and
    POST /production-lots/{id}/scrap."""

    lot: LotSummaryResponse
    created_lots: list[CreatedLotResponse] = Field(default_factory=list)
