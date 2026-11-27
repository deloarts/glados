"""DTOs for the ProductionOrder aggregate."""

from datetime import date
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator
from pydantic import model_validator

from src.modules.fulfillment.domain.services.manufacturing_assessment_rules import (
    assessed_minutes_refusal,
)
from src.modules.fulfillment.domain.value_objects.interruption_reason import InterruptionReason
from src.modules.fulfillment.domain.value_objects.pause_cause import PauseCause
from src.modules.fulfillment.domain.value_objects.production_status import ComplexityClass
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.user_dto import PublicUserResult

# ══════════════════════════════════════════════════════════════════════
# Commands
# ══════════════════════════════════════════════════════════════════════


class AssignInternalPositionOrderInput(BaseModel):
    machine_id: int | None = Field(default=None, gt=0)
    # Instead of machine_id: the concrete machine is chosen later by
    # Auto-Plan or Start.
    machine_pool_id: int | None = Field(default=None, gt=0)
    quantity: float = Field(..., gt=0)

    @model_validator(mode="after")
    def validate_target(self) -> "AssignInternalPositionOrderInput":
        if self.machine_id is not None and self.machine_pool_id is not None:
            raise ValueError("machine_id and machine_pool_id are mutually exclusive.")
        return self


class AssignInternalPositionCommand(BaseModel):
    orders: list[AssignInternalPositionOrderInput] = Field(..., min_length=1)


class SplitProductionOrderCommand(BaseModel):
    quantities: list[float] = Field(..., min_length=2)


class MergeProductionOrdersCommand(BaseModel):
    production_order_ids: list[int] = Field(..., min_length=2)
    # The edit version the client read of each order, by id; an order
    # left out is not checked.
    expected_edit_versions: dict[int, int] = Field(default_factory=dict)


class ReorderProductionOrdersCommand(BaseModel):
    ordered_production_order_ids: list[int] = Field(..., min_length=1)


class ReassignProductionOrderMachineCommand(BaseModel):
    machine_id: int | None = Field(default=None, gt=0)
    # Instead of machine_id. A pool target clears machine_id; a machine
    # target keeps the order's pool.
    machine_pool_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_target(self) -> "ReassignProductionOrderMachineCommand":
        if self.machine_id is not None and self.machine_pool_id is not None:
            raise ValueError("machine_id and machine_pool_id are mutually exclusive.")
        return self


class UpdateProductionOrderCommand(BaseModel):
    """Planner-adjustable fields; only provided fields are updated.

    planned_start and planned_end are a manual override, given together or
    not at all. The order is pinned unless `pinned` is given too, so the
    scheduler never moves it.
    """

    priority: UrgencyClass | None = None
    pinned: bool | None = None
    not_before: date | None = None
    estimated_duration_minutes: int | None = Field(default=None, ge=0)
    note: str | None = None
    planned_start: datetime | None = None
    planned_end: datetime | None = None
    # Computes planned_end from planned_start along the machine calendar.
    recompute_planned_end: bool = False
    # The edit version the client read; a row that moved since answers 409.
    expected_edit_version: int | None = None

    @model_validator(mode="after")
    def validate_schedule(self) -> "UpdateProductionOrderCommand":
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


class StartProductionOrderCommand(BaseModel):
    operator_id: int | None = None  # mandatory when actor.is_shared_account
    # Required exactly when a pool-assigned order has no machine yet.
    machine_id: int | None = Field(default=None, gt=0)


class PauseProductionOrderCommand(BaseModel):
    operator_id: int | None = None
    reason: str | None = None
    # The cause picked from the fixed list, next to the free-text reason.
    pause_cause: PauseCause | None = None


class CancelProductionOrderCommand(BaseModel):
    reason: str | None = None
    # The edit version the client read; a row that moved since answers 409.
    expected_edit_version: int | None = None


class RecordProductionOrderCompletionCommand(BaseModel):
    quantity: float = Field(..., gt=0)
    # Both omitted means everything was accepted.
    quantity_accepted: float | None = Field(default=None, ge=0)
    quantity_rejected: float | None = Field(default=None, ge=0)
    # Inspection only: rework plus scrap must equal quantity_rejected.
    quantity_rework: float = Field(default=0, ge=0)
    quantity_scrap: float = Field(default=0, ge=0)
    # Optional on inspections; mandatory for scrap during production.
    scrap_reason: str | None = None
    # Why the rejected pieces of an inspection failed (ScrapReason).
    reject_reason: str | None = None
    completion_date: date
    note: str | None = None
    operator_id: int | None = None  # mandatory when actor.is_shared_account


class ScrapProductionPiecesCommand(BaseModel):
    """Scraps `quantity` pieces of an internal production order's own
    position: no rework option (QA inspection is the only path that offers
    rework), reason is mandatory.
    `create_replacement` defaults to True, matching the dialog's own
    default checkbox state; unchecked, the origin's demand coverage is
    reduced instead of spawning a follow-up lot."""

    production_order_id: int = Field(..., gt=0)
    quantity: float = Field(..., gt=0)
    reason: str = Field(..., min_length=1)
    note: str | None = None
    create_replacement: bool = True
    operator_id: int | None = None  # mandatory when actor.is_shared_account
    # The edit versions the client read of the order and of its lot; a row
    # that moved since answers 409.
    expected_edit_version: int | None = None
    expected_lot_edit_version: int | None = None


class RecordManufacturingAssessmentCommand(BaseModel):
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


# ══════════════════════════════════════════════════════════════════════
# Results
# ══════════════════════════════════════════════════════════════════════


class ProductionOrderCompletionResult(ResultBase):
    production_order_id: int
    quantity: float
    quantity_accepted: float
    quantity_rejected: float
    quantity_rework: float = 0.0
    quantity_scrap: float = 0.0
    scrap_reason: str | None = None
    reject_reason: str | None = None
    completion_date: date
    note: str | None
    operator_id: int
    operator: PublicUserResult | None
    recorded_by_id: int
    recorded_by: PublicUserResult | None
    created: datetime
    reverses_completion_id: int | None = None
    machine_id: int | None = None


class ProductionOrderInterruptionResult(BaseModel):
    paused_at: datetime
    resumed_at: datetime | None
    reason: str = InterruptionReason.default().value  # InterruptionReason
    paused_operator_id: int | None = None
    pause_cause: str | None = None  # PauseCause


class ManufacturingAssessmentResult(ResultBase):
    production_order_id: int
    operator_id: int
    operator: PublicUserResult | None
    actual_minutes_per_piece: float
    actual_setup_minutes: int | None
    complexity: str
    note: str | None
    created: datetime


class CreatedLotResult(BaseModel):
    id: int
    lot_number: str
    disposition: str


class ProductionOrderResult(ResultBase):
    created: datetime
    changed: datetime | None
    production_order_number: str
    status: str
    priority: str
    pinned: bool
    queue_sequence: int
    quantity: float
    quantity_completed: float
    # Pieces the order processed, accepted and rejected alike, and what is
    # left of its quantity, which a completion may book at most.
    quantity_processed: float
    quantity_open: float
    estimated_duration_minutes: int
    note: str | None
    planned_start: datetime | None
    planned_end: datetime | None
    not_before: date | None
    actual_start: datetime | None
    actual_end: datetime | None
    # Lifecycle intent, read-only (see the ProductionOrder entity).
    canceled_at: datetime | None = None
    edit_version: int = 0
    creator_id: int
    creator: PublicUserResult | None
    changed_by_id: int | None
    changed_by: PublicUserResult | None
    # None means the scheduler set the current plan.
    planned_by_id: int | None
    planned_by: PublicUserResult | None
    # The operator of the latest start or resume.
    started_operator_id: int | None = None
    started_operator: PublicUserResult | None = None
    # planned_end frozen at the first start.
    planned_end_at_start: datetime | None = None
    machine_id: int | None
    machine_internal_name: str
    machine_pool_id: int | None = None
    machine_pool_name: str = ""
    lot_position_id: int
    lot_id: int
    lot_number: str
    # public_ids of the lot/made item this order belongs to, available as
    # @resolve_url:lot_public_id / @resolve_url:made_item_public_id field
    # sources for a template that needs to QR-code a different record than
    # the order itself.
    lot_public_id: UUID | None = None
    made_item_public_id: UUID | None = None
    project_id: int | None = None
    project_number: str = ""
    product_id: int | None = None
    product_number: str | None = None
    made_item_part_number: str
    made_item_id: int
    made_item_revision: str
    made_item_article_name: str
    made_item_material: str | None
    made_item_mass: int | None
    made_item_base_size: str | None
    lot_position_sequence: int
    lot_position_count: int
    completions: list[ProductionOrderCompletionResult] = Field(default_factory=list)
    interruptions: list[ProductionOrderInterruptionResult] = Field(default_factory=list)
    waiting_on_raw_material: bool = False
    can_start: bool = False
    # The lifecycle actions the reading user may take now, from the intent
    # table (lifecycle/intents.py); empty where no user is known.
    actions: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    assessment: ManufacturingAssessmentResult | None = None
    # Only set on a completion response that spawned disposition lots.
    created_lots: list[CreatedLotResult] = Field(default_factory=list)


# ── WIP read model ────────────────────────────────────────────────────


class WipStageResult(BaseModel):
    """One LotPosition's piece-count state within a lot's WIP breakdown."""

    position_id: int
    sequence: int
    kind: str
    status: str
    quantity: float
    quantity_completed: float
    machine_names: list[str] = Field(default_factory=list)  # INTERNAL positions
    supplier_name: str = ""  # EXTERNAL positions


class WipLotResult(ResultBase):
    """One row of the live WIP overview, mirrors the subset of
    LotSummaryResult that's cheaply available (no demand/project fetch),
    plus the per-stage piece-count breakdown from production_wip_service."""

    lot_number: str
    quantity: float
    status: str
    priority: str
    made_item_id: int
    made_item_part_number: str
    made_item_revision: str
    made_item_article_name: str
    raw_count: float
    finished_count: float
    stages: list[WipStageResult] = Field(default_factory=list)


# ── QA task read model ────────────────────────────────────────────────


class QaEvidenceFileResult(BaseModel):
    """One evidence file already attached to a QA task. Carried on the
    worklist row itself because GetQaTasks batch-loads these files anyway
    to compute has_evidence; returning them costs no extra query, whereas
    fetching per row would be one request per visible task (production
    orders have no bulk file endpoint)."""

    id: int
    file_name: str
    mime_type: str
    category: str
    url: str | None


class QaTaskResult(ResultBase):
    """One inspection-role production order, flattened with everything a QA
    engineer needs to triage it without a second fetch: the order's own
    state, the inspection method driving it, the part being inspected, and
    whether the evidence that method demands is already on file.

    Assembled by GetQaTasks; there is no QaTask table. `id` is the
    production order's id, so every existing production-order action
    (start/pause/complete, file upload) applies unchanged."""

    # ── Order ─────────────────────────────────────────────────────────
    production_order_number: str
    status: str
    priority: str
    quantity: float
    quantity_completed: float
    planned_start: datetime | None
    planned_end: datetime | None
    actual_start: datetime | None
    actual_end: datetime | None
    # The operator of the latest completion, not who typed it in.
    finished_by: PublicUserResult | None = None
    can_start: bool
    conflicts: list[str] = Field(default_factory=list)

    # ── Inspection step ───────────────────────────────────────────────
    inspection_method_id: int | None
    inspection_method_name: dict[str, str]
    requires_evidence: bool
    has_evidence: bool
    evidence_files: list[QaEvidenceFileResult] = Field(default_factory=list)

    # ── Position / lot ────────────────────────────────────────────────
    lot_position_id: int
    lot_position_sequence: int
    lot_position_count: int
    lot_id: int
    lot_number: str
    lot_status: str

    # ── Part ──────────────────────────────────────────────────────────
    made_item_id: int
    made_item_part_number: str
    made_item_article_name: str
    made_item_revision: str
    made_item_material: str | None

    # ── Project ───────────────────────────────────────────────────────
    project_id: int | None = None
    project_number: str = ""
    project_customer: str = ""
