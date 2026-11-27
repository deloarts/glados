"""
HTTP schemas for the ProductionOrder aggregate (INTERNAL LotPositions).
Mirrors production_lot_schema.py's conventions.
"""

from datetime import date
from datetime import datetime
from typing import Literal

from fastapi import Query
from pydantic import AwareDatetime
from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator
from pydantic import model_validator

from src.modules.fulfillment.domain.services.manufacturing_assessment_rules import (
    assessed_minutes_refusal,
)
from src.modules.fulfillment.domain.value_objects.interruption_reason import InterruptionReason
from src.modules.fulfillment.domain.value_objects.lot_origin_disposition import LotOriginDisposition
from src.modules.fulfillment.domain.value_objects.pause_cause import PauseCause
from src.modules.fulfillment.domain.value_objects.production_status import ComplexityClass
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.domain.value_objects.schedule_conflict import ScheduleConflictReason
from src.modules.fulfillment.domain.value_objects.scrap_reason import ScrapReason
from src.modules.fulfillment.ports.outbound.repositories.production_order_repository import (
    ProductionOrderFilterDto,
)
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import NonBlankReason
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageParams
from src.modules.platform.adapters.inbound.api.schemas.quantity_fields import NonNegativeQuantity
from src.modules.platform.adapters.inbound.api.schemas.quantity_fields import PositiveQuantity
from src.modules.platform.adapters.inbound.api.schemas.quantity_fields import Quantity
from src.modules.platform.adapters.inbound.api.schemas.user_schema import PublicUserResponse
from src.modules.platform.domain.services.quantities import quantity_eq
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction

# ══════════════════════════════════════════════════════════════════════
# Requests
# ══════════════════════════════════════════════════════════════════════


class AssignInternalPositionOrderInputRequest(BaseModel):
    machine_id: int | None = Field(default=None, gt=0)
    machine_pool_id: int | None = Field(default=None, gt=0)
    quantity: PositiveQuantity

    @model_validator(mode="after")
    def validate_target(self) -> "AssignInternalPositionOrderInputRequest":
        if self.machine_id is not None and self.machine_pool_id is not None:
            raise ValueError("machine_id and machine_pool_id are mutually exclusive.")
        return self


class AssignInternalPositionRequest(BaseModel):
    orders: list[AssignInternalPositionOrderInputRequest] = Field(..., min_length=1)


class SplitProductionOrderRequest(BaseModel):
    quantities: list[Quantity] = Field(..., min_length=2)


class MergeProductionOrdersRequest(BaseModel):
    production_order_ids: list[int] = Field(..., min_length=2)
    # The edit version read of every order merged, keyed by its id; an
    # order that moved since answers 409.
    expected_edit_versions: dict[int, int]

    @model_validator(mode="after")
    def validate_versions(self) -> "MergeProductionOrdersRequest":
        if set(self.expected_edit_versions) != set(self.production_order_ids):
            raise ValueError("expected_edit_versions must name every order merged.")
        return self


class ReorderProductionOrdersRequest(BaseModel):
    ordered_production_order_ids: list[int] = Field(..., min_length=1)


class ReassignProductionOrderMachineRequest(BaseModel):
    machine_id: int | None = Field(default=None, gt=0)
    machine_pool_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_target(self) -> "ReassignProductionOrderMachineRequest":
        if self.machine_id is not None and self.machine_pool_id is not None:
            raise ValueError("machine_id and machine_pool_id are mutually exclusive.")
        return self


class UpdateProductionOrderRequest(BaseModel):
    priority: UrgencyClass | None = None
    pinned: bool | None = None
    not_before: date | None = None
    estimated_duration_minutes: int | None = Field(default=None, ge=0)
    note: str | None = None
    planned_start: datetime | None = None
    planned_end: datetime | None = None
    recompute_planned_end: bool = False
    # The edit version read; a row that moved since answers 409.
    expected_edit_version: int

    @model_validator(mode="after")
    def validate_schedule(self) -> "UpdateProductionOrderRequest":
        if self.recompute_planned_end:
            if self.planned_start is None:
                raise ValueError("planned_start is required when recompute_planned_end is set.")
            if self.planned_end is not None:
                raise ValueError("planned_end must be omitted when recompute_planned_end is set.")
        elif (self.planned_start is None) != (self.planned_end is None):
            raise ValueError("planned_start and planned_end must be provided together.")
        elif self.planned_start and self.planned_end and self.planned_end <= self.planned_start:
            raise ValueError("planned_end must be after planned_start.")
        return self


class StartProductionOrderRequest(BaseModel):
    operator_id: int | None = None
    machine_id: int | None = Field(default=None, gt=0)


class PauseProductionOrderRequest(BaseModel):
    operator_id: int | None = None
    reason: str | None = None
    # Optional, picked from a fixed list next to the free-text reason.
    pause_cause: PauseCause | None = None


class CancelProductionOrderRequest(BaseModel):
    reason: str | None = None
    # The edit version read; a row that moved since answers 409.
    expected_edit_version: int


class ReverseCompletionRequest(BaseModel):
    """Why the completion is taken back, kept on the reversal and on the
    order's changelog."""

    reason: NonBlankReason = Field(..., max_length=500)


class RecordProductionOrderCompletionRequest(BaseModel):
    # The batch total: this completion covers `quantity` pieces.
    # quantity_accepted and quantity_rejected split this total for QA
    # processing. Both omitted defaults to accepted=quantity, rejected=0,
    # so a caller without QA needs neither.
    quantity: PositiveQuantity
    quantity_accepted: NonNegativeQuantity | None = None
    quantity_rejected: NonNegativeQuantity | None = None
    # Disposition of the rejected pieces, see the Command's own docstring
    # for why this isn't (and can't be) validated here at the schema
    # layer; the use case checks it once it knows whether this order's
    # position is an inspection one.
    quantity_rework: NonNegativeQuantity = 0
    quantity_scrap: NonNegativeQuantity = 0
    # Classified reason for the scrapped portion, optional on this QA/
    # inspection path. See ScrapProductionPiecesRequest for the
    # scrap-during-production path, where it's mandatory.
    scrap_reason: ScrapReason | None = None
    # Classified reason the rejected pieces of an inspection failed, kept
    # for the inspection report; ignored without rejected pieces.
    reject_reason: ScrapReason | None = None
    completion_date: date
    note: str | None = None
    operator_id: int | None = None

    @model_validator(mode="after")
    def default_and_validate_split(self) -> "RecordProductionOrderCompletionRequest":
        if self.quantity_accepted is None and self.quantity_rejected is None:
            self.quantity_accepted = self.quantity
            self.quantity_rejected = 0.0
            return self
        accepted = self.quantity_accepted if self.quantity_accepted is not None else 0.0
        rejected = self.quantity_rejected if self.quantity_rejected is not None else 0.0
        if not quantity_eq(accepted + rejected, self.quantity):
            raise ValueError(
                "quantity_accepted + quantity_rejected must equal quantity "
                f"({accepted!r} + {rejected!r} != {self.quantity!r})."
            )
        self.quantity_accepted = accepted
        self.quantity_rejected = rejected
        return self


class ScrapProductionPiecesRequest(BaseModel):
    quantity: PositiveQuantity
    reason: ScrapReason
    note: str | None = None
    create_replacement: bool = True
    operator_id: int | None = None
    # The edit versions read of the order and of its lot; a row that moved
    # since answers 409.
    expected_edit_version: int
    expected_lot_edit_version: int


class RecordManufacturingAssessmentRequest(BaseModel):
    # Decimal minutes with at most two places.
    actual_minutes_per_piece: float = Field(..., ge=0, allow_inf_nan=False)
    actual_setup_minutes: int | None = Field(default=None, ge=0)
    complexity: ComplexityClass
    note: str | None = None

    @field_validator("actual_minutes_per_piece")
    @classmethod
    def _two_decimals(cls, value: float) -> float:
        refusal = assessed_minutes_refusal(value)
        if refusal is not None:
            raise ValueError(refusal)
        return value


class ProductionOrderFilterParams(PageParams):
    search: str | None = Query(default=None)
    status: ProductionOrderStatus | None = Query(default=None)
    statuses: list[ProductionOrderStatus] | None = Query(default=None)
    # Keeps orders last changed (or, never changed, created) at or after this
    # instant, so the queue board can ask for recently finished work only.
    changed_from: AwareDatetime | None = Query(default=None)
    machine_id: int | None = Query(default=None)
    lot_position_id: int | None = Query(default=None)
    lot_id: int | None = Query(default=None)
    order_by: Literal["id", "production_order_number", "created", "queue_sequence"] | None = Query(
        default=None
    )
    order_dir: Literal["asc", "desc"] | None = Query(default=None)

    def to_dto(self) -> ProductionOrderFilterDto:
        return ProductionOrderFilterDto(**self.model_dump())


# ══════════════════════════════════════════════════════════════════════
# Responses
# ══════════════════════════════════════════════════════════════════════


class ProductionOrderCompletionResponse(EntityResponse):
    production_order_id: int
    quantity: float
    quantity_accepted: float
    quantity_rejected: float
    quantity_rework: float = 0.0
    quantity_scrap: float = 0.0
    scrap_reason: ScrapReason | None = None
    reject_reason: ScrapReason | None = None
    completion_date: date
    note: str | None
    operator_id: int
    operator: PublicUserResponse | None
    recorded_by_id: int
    recorded_by: PublicUserResponse | None
    created: datetime
    # Set on a reversal: the completion it takes back.
    reverses_completion_id: int | None = None
    # The machine the batch was booked on, empty for work without one.
    machine_id: int | None = None


class ProductionOrderInterruptionResponse(ResponseModel):
    paused_at: datetime
    resumed_at: datetime | None
    # Always set. Declared optional like the other lifecycle fields, so the
    # generated client type gains it without requiring it, as a default value
    # would make it required there.
    reason: InterruptionReason | None = None
    # The operator who paused the work, empty for a hold no one answers for.
    paused_operator_id: int | None = None
    # The cause picked for a manual pause, empty for a hold and a pause
    # without one.
    pause_cause: PauseCause | None = None


class ManufacturingAssessmentResponse(EntityResponse):
    production_order_id: int
    operator_id: int
    operator: PublicUserResponse | None
    actual_minutes_per_piece: float
    actual_setup_minutes: int | None
    complexity: ComplexityClass
    note: str | None
    created: datetime


class CreatedLotResponse(ResponseModel):
    id: int
    lot_number: str
    disposition: LotOriginDisposition


class ProductionOrderResponse(EntityResponse):
    created: datetime
    changed: datetime | None
    production_order_number: str
    status: ProductionOrderStatus
    # The lifecycle actions the reading user may take now, computed from the
    # aggregate's intent table; the client gates its buttons on them.
    actions: list[LifecycleAction] = Field(default_factory=list)
    priority: UrgencyClass
    pinned: bool
    queue_sequence: int
    quantity: float
    quantity_completed: float
    # Accepted and rejected pieces together, and the quantity left that a
    # completion may still book.
    quantity_processed: float
    quantity_open: float
    estimated_duration_minutes: int
    note: str | None
    planned_start: datetime | None
    planned_end: datetime | None
    not_before: date | None
    actual_start: datetime | None
    actual_end: datetime | None
    # Lifecycle intent, read-only.
    canceled_at: datetime | None = None
    edit_version: int = 0
    creator_id: int
    creator: PublicUserResponse | None
    changed_by_id: int | None
    changed_by: PublicUserResponse | None
    planned_by_id: int | None
    planned_by: PublicUserResponse | None
    started_operator_id: int | None = None
    started_operator: PublicUserResponse | None = None
    planned_end_at_start: datetime | None = None
    machine_id: int | None
    machine_internal_name: str
    machine_pool_id: int | None = None
    machine_pool_name: str = ""
    lot_position_id: int
    lot_id: int
    lot_number: str
    made_item_part_number: str
    made_item_id: int
    made_item_revision: str
    made_item_material: str | None
    made_item_mass: int | None
    made_item_base_size: str | None
    lot_position_sequence: int
    lot_position_count: int
    completions: list[ProductionOrderCompletionResponse] = Field(default_factory=list)
    interruptions: list[ProductionOrderInterruptionResponse] = Field(default_factory=list)
    waiting_on_raw_material: bool = False
    can_start: bool = False
    conflicts: list[ScheduleConflictReason] = Field(default_factory=list)
    assessment: ManufacturingAssessmentResponse | None = None
    created_lots: list[CreatedLotResponse] = Field(default_factory=list)
