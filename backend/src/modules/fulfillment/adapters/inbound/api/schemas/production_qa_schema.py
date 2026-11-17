"""
HTTP schemas for the QA worklist (GET /production-qa). A flat read model
of a bounded worklist, served in pages: the rows are assembled and ordered
in the use case (both depend on the computed can_start, see
get_qa_tasks.py) and the endpoint wraps them in the same
PageResponse envelope every other list endpoint uses, so the table's
paginator works the way it does everywhere else.
"""

from datetime import date
from datetime import datetime
from typing import Literal

from fastapi import Query
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import model_validator

from src.modules.fulfillment.domain.value_objects.lot_status import LotStatus
from src.modules.fulfillment.domain.value_objects.production_status import ProductionOrderStatus
from src.modules.fulfillment.domain.value_objects.production_status import UrgencyClass
from src.modules.fulfillment.domain.value_objects.schedule_conflict import ScheduleConflictReason
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.platform.adapters.inbound.api.schemas.user_schema import PublicUserResponse
from src.modules.platform.const import MAX_PAGE_SIZE

# ══════════════════════════════════════════════════════════════════════
# Filters
# ══════════════════════════════════════════════════════════════════════


class QaTaskFilterParams(BaseModel):
    """Defaults mirror the list's own: open tasks only, and nothing that
    can't be worked yet. The three include flags map to the views bar
    toggles, the rest to the table's column filters. Bound as
    `Annotated[..., Query()]` so the list fields read repeated query keys."""

    include_completed: bool = False
    include_canceled: bool = False
    # A "future" task is one Start would refuse (can_start false) or one
    # planned to begin after today, hidden by default so the worklist
    # shows only what is actually actionable now.
    include_future: bool = False
    search: str | None = Field(default=None, max_length=200)
    skip: int | None = Query(default=None, ge=0)
    limit: int | None = Query(default=None, ge=1, le=MAX_PAGE_SIZE)
    # Ordering is server side because the list is paged: sorting a single
    # page client side would only reorder the rows that page happens to hold.
    # None means the worklist's own "most urgent first" order.
    order_by: Literal["planned", "part", "lot", "quantity"] | None = Query(default=None)
    order_dir: Literal["asc", "desc"] | None = Query(default=None)
    # Column filters of the worklist table. A status pick replaces the
    # completed and canceled toggles (see QaTaskFilterDto.statuses); the
    # future toggle still applies on top. Text filters are case-insensitive
    # substring matches, item_text over the part number and article name.
    # Date ranges are inclusive calendar days; finished is the order's
    # actual end.
    status: list[ProductionOrderStatus] | None = Query(default=None, max_length=10)
    inspection_method_id: list[int] | None = Query(default=None, max_length=200)
    lot_number: str | None = Query(default=None, max_length=200)
    project_number: str | None = Query(default=None, max_length=200)
    item_text: str | None = Query(default=None, max_length=200)
    quantity_min: float | None = Query(default=None, ge=0)
    quantity_max: float | None = Query(default=None, ge=0)
    planned_start_from: date | None = Query(default=None)
    planned_start_to: date | None = Query(default=None)
    finished_from: date | None = Query(default=None)
    finished_to: date | None = Query(default=None)
    finished_by_id: list[int] | None = Query(default=None, max_length=200)

    @model_validator(mode="after")
    def validate_quantity_range(self) -> "QaTaskFilterParams":
        if (
            self.quantity_min is not None
            and self.quantity_max is not None
            and self.quantity_min > self.quantity_max
        ):
            raise ValueError("quantity_min must not exceed quantity_max.")
        return self


# ══════════════════════════════════════════════════════════════════════
# Responses
# ══════════════════════════════════════════════════════════════════════


class QaEvidenceFileResponse(ResponseModel):
    """An evidence file attached to a QA task, embedded on the row so the
    worklist can offer it for preview without a per-row request."""

    id: int
    file_name: str
    mime_type: str
    category: str
    url: str | None

    model_config = ConfigDict(from_attributes=True)


class QaTaskResponse(EntityResponse):
    """One inspection production order. `id` is the production order's id,
    so the existing production-order endpoints (start/complete, file
    upload) all apply to it unchanged."""

    # ── Order ─────────────────────────────────────────────────────────
    production_order_number: str
    status: ProductionOrderStatus
    priority: UrgencyClass
    quantity: float
    quantity_completed: float
    planned_start: datetime | None
    planned_end: datetime | None
    actual_start: datetime | None
    actual_end: datetime | None
    # The operator on the most recent completion: who did the inspection,
    # not necessarily the session user who recorded it.
    finished_by: PublicUserResponse | None = None
    can_start: bool
    conflicts: list[ScheduleConflictReason] = Field(default_factory=list)

    # ── Inspection step ───────────────────────────────────────────────
    inspection_method_id: int | None
    inspection_method_name: dict[str, str]
    requires_evidence: bool
    has_evidence: bool
    evidence_files: list[QaEvidenceFileResponse] = Field(default_factory=list)

    # ── Position / lot ────────────────────────────────────────────────
    lot_position_id: int
    lot_position_sequence: int
    lot_position_count: int
    lot_id: int
    lot_number: str
    lot_status: LotStatus

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
