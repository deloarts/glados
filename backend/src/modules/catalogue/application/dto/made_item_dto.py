"""
DTOs for the MadeItem catalogue and MadeItemProcess aggregates.
"""

from datetime import date
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import Field

from src.modules.catalogue.application.dto.article_group_dto import ArticleGroupResult
from src.modules.catalogue.application.dto.bought_item_dto import BoughtItemResult
from src.modules.catalogue.application.dto.source_item_dto import SourceItemResult
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.user_dto import PublicUserResult

# ══════════════════════════════════════════════════════════════════════
# MadeItemProcess (referenced by CreateMadeItemCommand below)
# ══════════════════════════════════════════════════════════════════════


class CreateMadeItemProcessCommand(BaseModel):
    role: StepRole = StepRole.FABRICATION
    fabrication_method_id: int | None = Field(default=None, gt=0)
    inspection_method_id: int | None = Field(default=None, gt=0)
    note: str | None = None
    estimated_setup_minutes: int | None = None
    estimated_minutes_per_piece: float | None = None
    group_index: int | None = None


# ══════════════════════════════════════════════════════════════════════
# MadeItem (catalogue)
# ══════════════════════════════════════════════════════════════════════


class CreateMadeItemCommand(BaseModel):
    revision: str = Field(..., min_length=1)
    revision_date: date | None = None
    revision_note: str | None = None
    article_name: str = Field(..., min_length=1)
    article_group_ids: list[int] = Field(default_factory=list)
    # Only PDM ingest passes CAD; the web and pat create requests do not
    # carry the field, so every other row is born WEB.
    data_source: str = "WEB"
    status: str = "active"
    part_number: str | None = None
    material: str | None = None
    mass: int | None = None
    base_size: str | None = None
    note: str | None = None
    weblink: str | None = None
    bought_item_id: int | None = None
    source_item_id: int | None = None
    customer_id: int | None = None
    customer_part_number: str | None = None
    customer_revision: str | None = None
    processes: list[CreateMadeItemProcessCommand] = Field(default_factory=list)


class UpdateMadeItemCommand(BaseModel):
    # revision is immutable in place: a new revision is a new row,
    # created via CreateMadeItemRevision, never via this command.
    revision_date: date | None = None
    revision_note: str | None = None
    article_name: str = Field(..., min_length=1)
    article_group_ids: list[int] = Field(default_factory=list)
    status: str = "active"
    part_number: str | None = None
    material: str | None = None
    mass: int | None = None
    base_size: str | None = None
    note: str | None = None
    weblink: str | None = None
    bought_item_id: int | None = None
    source_item_id: int | None = None
    customer_id: int | None = None
    customer_part_number: str | None = None
    customer_revision: str | None = None
    successor_item_id: int | None = None
    # The edit version the client read, checked when given; a row changed
    # since answers 409. The web routes require it, the `pat` API does not.
    expected_edit_version: int | None = None


class MadeItemProcessResult(ResultBase):
    created: datetime
    note: str | None
    estimated_setup_minutes: int | None
    estimated_minutes_per_piece: float | None
    creator_id: int
    role: str
    inspection_method_id: int | None
    fabrication_method_id: int | None
    fabrication_method_name: dict[str, str]
    inspection_method_name: dict[str, str] | None = None
    made_item_id: int
    position: int
    group_index: int


class MadeItemResult(ResultBase):
    status: str
    created: datetime
    changed: datetime
    archived: bool
    revision: str
    revision_date: date | None
    revision_note: str | None
    article_name: str
    article_groups: list[ArticleGroupResult] = Field(default_factory=list)
    data_source: str
    vault_id: str | None = None
    pdm_file_id: int | None = None
    pdm_file_version: int | None = None
    pdm_synced_at: datetime | None = None
    pdm_sync_state: str | None = None
    part_number: str | None
    material: str | None
    mass: int | None
    base_size: str | None
    note: str | None
    weblink: str | None
    successor_item_id: int | None
    creator_id: int
    creator: PublicUserResult | None
    changed_by_id: int | None = None
    changed_by: PublicUserResult | None = None
    bought_item_id: int | None
    bought_item: BoughtItemResult | None = None
    source_item_id: int | None
    pdm_source_item_id: int | None = None
    source_item: SourceItemResult | None = None
    customer_id: int | None = None
    customer_name: str | None = None
    customer_part_number: str | None = None
    customer_revision: str | None = None
    source_label: str = ""
    source_sublabel: str = ""
    processes: list[MadeItemProcessResult] = Field(default_factory=list)
    changes: list[str] = Field(default_factory=list)
    # PDM-owned field names this row's caller may not currently write
    # (src.modules.catalogue.domain.policies.pdm_ownership.pdm_locked_fields), empty unless
    # the caller resolved it (GetMadeItem, UpdateMadeItem), since it needs
    # the current PDM settings and the actor, neither of which a bare
    # entity->DTO mapping has.
    pdm_locked_fields: list[str] = Field(default_factory=list)
    # The row's edit version, which an edit sends back as expected_edit_version.
    edit_version: int = 0


class MergeMadeItemCommand(BaseModel):
    target_id: int


class MadeItemMergeTargetResult(BaseModel):
    """A candidate target of a merge: the item, why it may not take the
    merge (None when it may), and whether the merge makes it active again."""

    item: MadeItemResult
    refusal: str | None
    reactivates: bool


# ══════════════════════════════════════════════════════════════════════
# Made-item revisions
# ══════════════════════════════════════════════════════════════════════


class MadeItemRevisionItemCommand(BaseModel):
    """CreateMadeItemCommand's shape minus revision/part_number/data_source:
    the new revision always inherits the same part number, gets its
    revision from the increment (or through an explicit `revision`
    override), and is always born WEB (or through an explicit
    `data_source` override)."""

    revision_date: date | None = None
    revision_note: str | None = None
    article_name: str = Field(..., min_length=1)
    article_group_ids: list[int] = Field(default_factory=list)
    material: str | None = None
    mass: int | None = None
    base_size: str | None = None
    note: str | None = None
    weblink: str | None = None
    bought_item_id: int | None = None
    source_item_id: int | None = None
    customer_id: int | None = None
    customer_part_number: str | None = None
    customer_revision: str | None = None
    processes: list[CreateMadeItemProcessCommand] = Field(default_factory=list)


class CreateMadeItemRevisionCommand(BaseModel):
    predecessor_status: str
    item: MadeItemRevisionItemCommand
    # Overrides only PDM ingest sets: an explicit revision label skips the
    # increment (still uniqueness-checked), and a data_source override
    # replaces the default WEB. The web endpoint sets neither.
    revision: str | None = None
    data_source: str | None = None


class MadeItemRevisionSummary(BaseModel):
    id: int
    public_id: UUID
    revision: str
    revision_date: date | None
    status: str
    successor_item_id: int | None
    created: datetime
    is_newest: bool

    model_config = {"from_attributes": True}


class MadeItemRevisionsResult(BaseModel):
    items: list[MadeItemRevisionSummary]
    next_revision: str | None
    next_revision_error: str | None
    can_create: bool
    reason: str | None


# ══════════════════════════════════════════════════════════════════════
# MadeItemProcess
# ══════════════════════════════════════════════════════════════════════


class UpdateMadeItemProcessCommand(BaseModel):
    role: StepRole = StepRole.FABRICATION
    fabrication_method_id: int | None = Field(default=None, gt=0)
    inspection_method_id: int | None = Field(default=None, gt=0)
    note: str | None = None
    estimated_setup_minutes: int | None = None
    estimated_minutes_per_piece: float | None = None


class ReorderMadeItemProcessesCommand(BaseModel):
    ordered_process_ids: list[int] = Field(..., min_length=1)


class RegroupMadeItemProcessesCommand(BaseModel):
    groups: list[list[int]] = Field(..., min_length=1)
