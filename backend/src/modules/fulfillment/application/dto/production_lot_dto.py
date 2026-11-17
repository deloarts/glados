"""
DTOs for the ProductionLot / LotStep / LotPosition aggregate.
"""

from datetime import date
from datetime import datetime
from typing import Any
from typing import Literal
from uuid import UUID

from pydantic import BaseModel
from pydantic import Field

from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.application.dto.made_item_demand_dto import MadeItemDemandItemResult
from src.modules.fulfillment.application.dto.production_order_dto import CreatedLotResult
from src.modules.fulfillment.application.dto.production_order_dto import ProductionOrderResult
from src.modules.fulfillment.domain.value_objects.planning_exception_kind import (
    PlanningExceptionKind,
)
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.user_dto import PublicUserResult

# ══════════════════════════════════════════════════════════════════════
# Commands
# ══════════════════════════════════════════════════════════════════════


class LotDemandAllocationInput(BaseModel):
    demand_item_id: int = Field(..., gt=0)
    quantity: float = Field(..., gt=0)


class CreateLotCommand(BaseModel):
    made_item_id: int = Field(..., gt=0)
    project_id: int = Field(..., gt=0)
    quantity: float = Field(..., gt=0)
    note: str | None = None
    priority: UrgencyClass | None = None  # None → auto-prefill from demand_allocations, else NORMAL
    demand_allocations: list[LotDemandAllocationInput] = Field(default_factory=list)
    # Explicit "finish by this day" date, independent of any demand
    # this lot ends up allocated against. See resolve_lot_target_date.
    required_delivery_date: date | None = None


class UpdateLotCommand(BaseModel):
    note: str | None = None
    priority: UrgencyClass | None = None
    quantity: float | None = Field(default=None, gt=0)  # DRAFT-only
    required_delivery_date: date | None = None
    # The edit version the client read; a row that moved since answers 409.
    expected_edit_version: int | None = None


class SwitchLotMaterialSourceCommand(BaseModel):
    bought_item_id: int | None = None
    source_item_id: int | None = None
    made_item_id: int | None = None  # rework/alteration
    # Required to proceed when the lot has a demand this switch replaces,
    # see LotHasOpenDemandError and LotHasPlacedDemandError.
    confirm_replace_demand: bool = False
    # The edit version the client read; a row that moved since answers 409.
    expected_edit_version: int | None = None


class AddLotStepCommand(BaseModel):
    position_id: int = Field(..., gt=0)
    role: StepRole = StepRole.FABRICATION
    fabrication_method_id: int | None = Field(default=None, gt=0)
    inspection_method_id: int | None = Field(default=None, gt=0)
    note: str | None = None
    estimated_setup_minutes: int | None = Field(default=None, ge=0)
    estimated_minutes_per_piece: float | None = Field(default=None, ge=0)


class UpdateLotStepCommand(BaseModel):
    role: StepRole = StepRole.FABRICATION
    fabrication_method_id: int | None = Field(default=None, gt=0)
    inspection_method_id: int | None = Field(default=None, gt=0)
    note: str | None = None
    estimated_setup_minutes: int | None = Field(default=None, ge=0)
    estimated_minutes_per_piece: float | None = Field(default=None, ge=0)


class ReorderLotStepsCommand(BaseModel):
    ordered_step_ids: list[int] = Field(..., min_length=1)


class RegroupLotPositionsCommand(BaseModel):
    groups: list[list[int]] = Field(..., min_length=1)


class AppendLotPositionStepInput(BaseModel):
    role: StepRole = StepRole.FABRICATION
    fabrication_method_id: int | None = Field(default=None, gt=0)
    inspection_method_id: int | None = Field(default=None, gt=0)
    note: str | None = None
    estimated_setup_minutes: int | None = Field(default=None, ge=0)
    estimated_minutes_per_piece: float | None = Field(default=None, ge=0)


class AppendLotPositionCommand(BaseModel):
    steps: list[AppendLotPositionStepInput] = Field(..., min_length=1)


class ReplaceLotStructureStepInput(BaseModel):
    # None for a step this save creates; an existing step's id otherwise.
    # Any existing step the payload leaves out is deleted.
    id: int | None = Field(default=None, gt=0)
    role: StepRole = StepRole.FABRICATION
    fabrication_method_id: int | None = Field(default=None, gt=0)
    inspection_method_id: int | None = Field(default=None, gt=0)
    note: str | None = None
    estimated_setup_minutes: int | None = Field(default=None, ge=0)
    estimated_minutes_per_piece: float | None = Field(default=None, ge=0)


class ReplaceLotStructurePositionInput(BaseModel):
    steps: list[ReplaceLotStructureStepInput] = Field(..., min_length=1)


class ReplaceLotStructureCommand(BaseModel):
    """A lot's complete intended step/position structure, in order.

    One command rather than a replay of add/update/delete/reorder/regroup:
    the step editor stages every change and saves once, so the whole edit
    has to land in a single transaction or not at all."""

    positions: list[ReplaceLotStructurePositionInput] = Field(..., min_length=1)


class AssignExternalPositionCommand(BaseModel):
    """The line always belongs to the lot's project, so the command names
    none."""

    order_id: int = Field(..., gt=0)
    unit: str = Field(..., min_length=1)
    items_per_unit: float = Field(default=1.0, gt=0)
    price: int | None = None
    expected_delivery_date: date | None = None
    expected_pickup_date: date | None = None
    # None assigns the position's full remaining (uncommitted) quantity,
    # the pre-MIXED-kind default behavior. A value < remaining leaves the
    # rest open for a later internal assignment (or vice versa), turning
    # the position MIXED.
    quantity: float | None = Field(default=None, gt=0)


class CancelLotCommand(BaseModel):
    reason: str | None = None
    # The edit version the client read; a row that moved since answers 409.
    expected_edit_version: int | None = None


class CompleteLotCommand(BaseModel):
    reason: str | None = None
    # The edit version the client read; a row that moved since answers 409.
    expected_edit_version: int | None = None


class HoldLotCommand(BaseModel):
    # Pausing mid-run wastes setup time, the reason is required so the
    # cost is visible in the audit trail.
    reason: str = Field(..., min_length=1)


class RejectLotSourceCommand(BaseModel):
    # Trimming/blank-rejection happens in RejectLotSourceRequest (a Pydantic
    # field_validator, so a blank reason 422s cleanly); by the time it
    # reaches this command it's already a non-empty, capped string.
    reason: str = Field(..., min_length=1, max_length=1000)
    expected_edit_version: int | None = None


class RecordLotPositionProvisionCommand(BaseModel):
    quantity: float = Field(..., gt=0)
    provision_date: date
    note: str | None = None


class ScrapLotPiecesCommand(BaseModel):
    """Scraps pieces from a lot's own controls bar/context menu rather than
    from a specific order (ScrapProductionPiecesCommand): position_id
    names which internal position to scrap at, production_order_id is
    only required when that position has more than one open order to
    disambiguate which one the ProductionOrderCompletion record attaches
    to."""

    position_id: int = Field(..., gt=0)
    production_order_id: int | None = Field(default=None, gt=0)
    quantity: float = Field(..., gt=0)
    reason: str = Field(..., min_length=1)
    note: str | None = None
    create_replacement: bool = True
    operator_id: int | None = None
    # The lot's edit version the client read; a lot that moved since
    # answers 409.
    expected_edit_version: int | None = None


# ══════════════════════════════════════════════════════════════════════
# Results
# ══════════════════════════════════════════════════════════════════════


class LotStepResult(ResultBase):
    created: datetime
    note: str | None
    estimated_setup_minutes: int | None
    estimated_minutes_per_piece: float | None
    sequence: int
    creator_id: int
    role: str
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


class LotPositionOrderLineResult(BaseModel):
    """A position's order line older than its newest one."""

    order_item_id: int
    order_id: int | None
    order_number: str
    supplier_name: str
    quantity: float
    quantity_delivered: float
    unit: str
    closed_short: bool


class LotPositionResult(ResultBase):
    created: datetime
    changed: datetime | None
    sequence: int
    kind: str
    status: str
    # The lifecycle actions the reading user may take now, from the intent
    # table (lifecycle/intents.py); empty where no user is known.
    actions: list[str] = Field(default_factory=list)
    quantity: float
    quantity_completed: float
    quantity_remaining: float
    note: str | None
    creator_id: int
    changed_by_id: int | None
    changed_by: PublicUserResult | None
    lot_id: int
    steps: list[LotStepResult] = Field(default_factory=list)
    order_item_id: int | None = None
    order_id: int | None = None
    order_number: str = ""
    supplier_name: str = ""
    order_item_status: str = ""
    # The line was closed short, so the rest of the position takes a new line.
    order_item_closed_short: bool = False
    # The position's earlier lines, each closed short, newest first.
    earlier_order_lines: list[LotPositionOrderLineResult] = Field(default_factory=list)
    expected_delivery_date: date | None = None
    planned_pickup_date: date | None = None
    planned_delivery_date: date | None = None
    production_orders: list[ProductionOrderResult] = Field(default_factory=list)


class FollowUpLotResult(BaseModel):
    id: int
    lot_number: str
    disposition: str
    quantity: float


class LotResult(ResultBase):
    created: datetime
    changed: datetime | None
    lot_number: str
    quantity: float
    quantity_completed: float
    status: str
    # The lifecycle actions the reading user may take now, from the intent
    # table (lifecycle/intents.py); empty where no user is known.
    actions: list[str] = Field(default_factory=list)
    # The actions the state allows now but the reading user lacks a
    # permission for, each with that permission, which the client shows
    # disabled and names.
    blocked_actions: dict[str, str] = Field(default_factory=dict)
    priority: str
    note: str | None
    required_delivery_date: date | None = None
    completed_at: datetime | None = None
    quantity_scrapped: float = 0.0
    # Lifecycle intents, read-only (see the ProductionLot entity).
    held_at: datetime | None = None
    canceled_at: datetime | None = None
    edit_version: int = 0
    force_completed_at: datetime | None = None
    # ids of follow_up_lots whose disposition is "replacement", for a
    # lightweight lineage link where the full follow_up_lots shape isn't
    # needed. See FollowUpLotResult for the full lineage entries.
    replacement_lot_ids: list[int] = Field(default_factory=list)
    creator_id: int
    creator: PublicUserResult | None
    changed_by_id: int | None
    changed_by: PublicUserResult | None
    made_item_id: int
    made_item_part_number: str
    made_item_article_name: str
    made_item_revision: str
    made_item_material: str
    made_item_public_id: UUID | None = None
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
    demand_status: str
    is_alteration: bool
    project_id: int
    project_number: str
    project_customer: str
    product_id: int | None = None
    product_number: str | None = None
    input_demand_id: int | None
    # QA/inspection lineage: origin_lot_id/origin_disposition set only on a
    # rework/replacement lot spawned from an inspection completion's
    # disposition; origin_lot_number denormalized like source_order_number.
    # follow_up_lots is the reverse direction: other lots spawned FROM
    # this one, empty unless this lot has ever had a reject disposed of.
    origin_lot_id: int | None = None
    origin_lot_number: str | None = None
    origin_disposition: str | None = None
    # Source item approval (see source_approval_status.py). Only meaningful
    # while source_item_id is set; not_required otherwise. The two user ids
    # are bare FKs, no embedded user; callers already resolve users via
    # usersStore.getById, the same pattern SourceItemResponse.approver_id
    # uses.
    source_approval_status: str  # SourceApprovalStatus
    source_approved_by_id: int | None = None
    source_approved_date: datetime | None = None
    source_rejected_by_id: int | None = None
    source_rejected_date: datetime | None = None
    source_rejection_reason: str | None = None
    follow_up_lots: list[FollowUpLotResult] = Field(default_factory=list)
    positions: list[LotPositionResult] = Field(default_factory=list)
    steps: list[LotStepResult] = Field(default_factory=list)


class LotSummaryStepResult(ResultBase):
    created: datetime
    note: str | None
    estimated_setup_minutes: int | None
    estimated_minutes_per_piece: float | None
    time_budget_per_piece: float | None
    sequence: int
    creator_id: int
    role: str
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
    # Denormalized from the owning LotPosition, lets the lots list determine
    # per-step clickability (assign to order/machine) without a full-lot
    # fetch. position_needs_machine mirrors ProductionOrder.machine_id's
    # nullability (see reassign_production_order_machine.py): an internal
    # position can be committed with no machine chosen yet.
    position_kind: str
    position_needs_machine: bool
    position_status: str
    # Total quantity the position must cover vs. how much of it is not yet
    # committed to an order/production run, lets the lots list flag a step
    # as partially allocated (e.g. "milling (3/4)") without a full-lot fetch.
    position_quantity: float
    position_quantity_remaining: float
    # The lifecycle actions the reading user may take now, from the intent
    # table (lifecycle/intents.py); empty where no user is known.
    actions: list[str] = Field(default_factory=list)


class LotSummaryProductionOrderResult(BaseModel):
    """The scheduling facts the lots list reads off an internal position's
    production orders.

    A deliberate subset of ProductionOrderResult rather than the whole
    thing: the list renders a date and a machine name per step, and
    embedding full production orders (each carrying its completions) for
    every position on the page would multiply the payload for fields no
    column on this screen reads."""

    id: int
    status: str
    machine_id: int | None
    machine_internal_name: str
    machine_pool_id: int | None = None
    machine_pool_name: str = ""
    planned_start: datetime | None
    planned_end: datetime | None
    actual_start: datetime | None
    actual_end: datetime | None
    quantity_completed: float = 0.0
    # Sent back with a planned-date edit from the list.
    edit_version: int = 0
    # None means the scheduler computed the date on its own and no person
    # ever pinned it; the client renders its own "Auto-planner" label
    # there rather than the backend baking in a display string.
    planned_by_name: str | None
    conflicts: list[str] = Field(default_factory=list)
    # What currently governs this order's earliest possible start (see
    # scheduling.explain_earliest_start): reason is one of
    # in_progress/pinned/not_before/predecessor/material/queue/
    # unknown_chain/missing_material/none, date is the earliest-start date
    # that reason names. Both None for a caller that doesn't compute
    # explanations (the same graceful degradation conflicts already has).
    earliest_start_reason: str | None = None
    earliest_start_date: date | None = None


class LotSummaryPositionResult(BaseModel):
    """A position's procurement/execution facts, flattened for the lots
    list.

    Carries both sides of a position: the bought side's order-item
    delivery/pickup facts (inlined, so resolving "when does this land"
    needs no follow-up fetch of the linked Order) and the made side's
    production orders. Same reduction as LotSummaryStepResult: everything
    the list needs to render a lot, and nothing it doesn't."""

    id: int
    kind: str
    # External/mixed only: the Order this position was assigned to.
    order_id: int | None
    order_number: str
    order_item_id: int | None
    order_item_status: str
    order_item_closed_short: bool = False
    order_item_quantity: float | None
    order_item_quantity_delivered: float | None
    order_item_unit: str
    order_item_items_per_unit: float
    # Sent back with an edit of the line from the list.
    order_item_edit_version: int = 0
    expected_delivery_date: date | None  # projected (target → date)
    delivery_date: datetime | None  # confirmed/arrived (event → timestamp)
    expected_pickup_date: date | None
    ready_for_pickup_date: datetime | None
    # >1 means the item arrived across several shipments: a count, since
    # the list only ever asks whether it was more than one.
    delivery_record_count: int
    ordered_by_name: str | None
    planned_pickup_date: date | None = None
    planned_delivery_date: date | None = None
    # External/mixed only: this position's resolved lead time (see
    # scheduling.resolve_position_lead_days_with_source) and where
    # it came from (supplier/method/default). Both None for an
    # internal/unassigned position, or when no settings were available to
    # resolve them from.
    lead_days: int | None = None
    lead_days_source: str | None = None
    production_orders: list[LotSummaryProductionOrderResult] = Field(default_factory=list)


class LotSummaryResult(ResultBase):
    lot_number: str
    quantity: float
    quantity_completed: float
    status: str
    # The lifecycle actions the reading user may take now, from the intent
    # table (lifecycle/intents.py); empty where no user is known.
    actions: list[str] = Field(default_factory=list)
    # The actions the state allows now but the reading user lacks a
    # permission for, each with that permission, which the client shows
    # disabled and names.
    blocked_actions: dict[str, str] = Field(default_factory=dict)
    priority: str
    created: datetime
    changed: datetime | None
    required_delivery_date: date | None = None
    completed_at: datetime | None = None
    quantity_scrapped: float = 0.0
    replacement_lot_ids: list[int] = Field(default_factory=list)
    edit_version: int = 0
    # What the scheduler actually uses as this lot's due date (see
    # resolve_lot_target_date): the manual required_delivery_date when
    # set, otherwise the earliest desired_delivery_date over the demand
    # items this lot is allocated against. target_date_demand_item_id
    # names which demand item produced it, only when the source is
    # "demand". All three None when neither a manual date nor an
    # allocated demand date exists.
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
    demand_status: str
    is_alteration: bool
    project_id: int
    project_number: str
    project_customer: str
    creator_id: int
    creator: PublicUserResult | None
    changed_by_id: int | None
    changed_by: PublicUserResult | None
    input_demand_id: int | None
    # QA/inspection lineage: set only on a rework/replacement lot spawned by
    # an inspection completion's disposition. The lots list only needs
    # enough to render a small lineage icon; the full lot detail (see
    # LotResult) is where origin_lot_number/follow_up_lots live.
    origin_lot_id: int | None = None
    origin_disposition: str | None = None
    # Source item approval, see LotResult's matching fields for the shape
    # rationale. The full set (not just status) rides along here too: the
    # lots table's sourceStatus column renders a rejected reason in a
    # tooltip directly off the summary row, without opening the lot.
    source_approval_status: str  # SourceApprovalStatus
    source_approved_by_id: int | None = None
    source_approved_date: datetime | None = None
    source_rejected_by_id: int | None = None
    source_rejected_date: datetime | None = None
    source_rejection_reason: str | None = None
    steps: list[LotSummaryStepResult] = Field(default_factory=list)
    positions: list[LotSummaryPositionResult] = Field(default_factory=list)


class LotPositionProvisionResult(ResultBase):
    lot_position_id: int
    quantity: float
    provision_date: date
    note: str | None
    creator_id: int
    creator: PublicUserResult | None
    created: datetime


class LotPositionCompletionResult(BaseModel):
    position_id: int
    sequence: int
    kind: str
    status: str
    quantity: float
    quantity_completed: float


class LotPositionBalanceResult(BaseModel):
    """Where the pieces that reached a position went
    (domain/services/position_reconciliation.py)."""

    position_id: int
    sequence: int
    kind: str
    arrived: float
    good: float
    scrap: float
    rework: float
    lost: float
    wip: float
    difference: float
    produced: float


class LotMaterialReceiptResult(BaseModel):
    """One receipt of the material a lot consumes: a delivery row on an
    order line that supplies the lot's raw material demand."""

    delivery_id: int
    order_item_id: int
    order_id: int
    order_number: str
    delivery_date: datetime
    quantity: float
    supplier_batch: str | None
    delivery_note_number: str | None
    certificate_reference: str | None
    # Set on a correction row, which takes back pieces of the row it names.
    corrects_delivery_id: int | None


class LotEventResult(ResultBase):
    lot_id: int
    occurred_at: datetime
    actor_id: int | None
    actor_username: str | None
    actor_full_name: str
    event_type: str
    entity: str
    entity_id: int | None
    summary: str
    payload: dict[str, Any] | None


class LotDemandResult(MadeItemDemandItemResult):
    """A made-item demand this lot was raised to cover, as seen from the lot's
    side: the demand's own fields plus how much of it this specific lot
    allocates (a demand can span more than one lot)."""

    allocated_quantity: float


class AutoAssignLotGroupDemandResult(BaseModel):
    demand_item_id: int
    quantity: float


class AutoAssignLotGroupResult(BaseModel):
    made_item_id: int
    item_part_number: str
    item_revision: str
    item_article_name: str
    project_id: int
    project_number: str
    project_customer: str
    quantity: float
    high_priority: bool
    demands: list[AutoAssignLotGroupDemandResult]
    # Earliest desired_delivery_date among this group's demands, or None if
    # none of them have one set. Carried onto the created lot as-is.
    required_delivery_date: date | None


class ScrapPiecesResult(BaseModel):
    """Response shape shared by ScrapProductionPieces and ScrapLotPieces:
    the scrapped-from lot's own summary (same shape the lots list uses,
    so a client can patch one row without a shape mismatch) plus whatever
    rework/replacement lot(s) the disposition spawned."""

    lot: LotSummaryResult
    created_lots: list[CreatedLotResult] = Field(default_factory=list)


class ScrapTagResult(ResultBase):
    """The scrap_tag print classifier's root, per PrintRootResolver. Not a
    single persisted row of its own: `id`/`public_id` are the underlying
    ProductionOrderCompletion's or OrderItemDelivery's, whichever record
    this particular scrap occurrence was recorded on (see
    application/services/print_root_resolver.py). Carries one occurrence's
    facts, not the lot's cumulative quantity_scrapped."""

    lot_id: int
    lot_public_id: UUID
    lot_number: str
    made_item_id: int
    made_item_label: str
    quantity: float
    reason: str
    reason_label: str
    scrap_date: date
    operator_full_name: str
    replacement_lot_id: int | None = None
    replacement_lot_number: str = ""


class PlanningExceptionResult(BaseModel):
    """One row of the planner's exception list. `family` and `demand_id`
    name the demand a shortfall concerns, `lot_id` the lot, and `order_id`
    with `line_position` the order line it arose on. `quantity_short` is the
    rest still open, in `unit`. For MATERIAL_SHORT, `unallocated` is the raw
    material no order line or stock covers and `undated` says whether an
    open line has no delivery date. For LATE, `target_date` and
    `planned_end` give the delay. `since` is when the cause was recorded.
    `item_kind` and `item_id` name the catalogue item the row is about, so
    the list can show its picture and open it. `item_number` is a made
    item's part number, a bought item's first order code or a raw
    material's dimension, and `item_name` its article name or material.
    `item_label` joins the two for readers that want one string."""

    kind: PlanningExceptionKind
    family: Literal["bought", "source", "made"] | None = None
    demand_id: int | None = None
    lot_id: int | None = None
    lot_number: str | None = None
    order_id: int | None = None
    order_number: str | None = None
    line_position: int | None = None
    item_kind: Literal["made", "bought", "source"] | None = None
    item_id: int | None = None
    item_number: str = ""
    item_revision: str = ""
    item_name: str = ""
    item_label: str = ""
    project_id: int | None = None
    project_number: str = ""
    project_customer: str = ""
    quantity_short: float | None = None
    unit: str | None = None
    unallocated: float | None = None
    undated: bool = False
    target_date: date | None = None
    planned_end: datetime | None = None
    since: datetime | None = None
