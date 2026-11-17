"""
HTTP schemas for the MadeItem catalogue and MadeItemProcess aggregates.
"""

from datetime import date
from datetime import datetime
from datetime import tzinfo
from typing import Generic
from typing import Literal
from typing import TypeVar

from fastapi import Query
from pydantic import BaseModel
from pydantic import Field
from pydantic import model_validator

from src.modules.catalogue.adapters.inbound.api.schemas.article_group_schema import (
    ArticleGroupResponse,
)
from src.modules.catalogue.adapters.inbound.api.schemas.article_group_schema import (
    ArticleGroupWebResponse,
)
from src.modules.catalogue.adapters.inbound.api.schemas.bought_item_schema import BoughtItemResponse
from src.modules.catalogue.adapters.inbound.api.schemas.bought_item_schema import (
    BoughtItemWebResponse,
)
from src.modules.catalogue.adapters.inbound.api.schemas.source_item_schema import SourceItemResponse
from src.modules.catalogue.adapters.inbound.api.schemas.source_item_schema import (
    SourceItemWebResponse,
)
from src.modules.catalogue.domain.policies.catalogue_item_status import MergeTargetRefusal
from src.modules.catalogue.domain.policies.step_role_rules import assert_role_matches_methods
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.pdm_sync_state import PdmSyncState
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.catalogue.ports.outbound.catalogue_queries import MadeItemFilterDto
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.platform.adapters.inbound.api.schemas.base import expand_change_window
from src.modules.platform.adapters.inbound.api.schemas.localized_text_schema import ResolvedLabel
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageParams
from src.modules.platform.adapters.inbound.api.schemas.user_schema import PublicUserResponse
from src.modules.platform.domain.exceptions import DomainError

TLabel = TypeVar("TLabel")
TGroup = TypeVar("TGroup")
TBought = TypeVar("TBought")
TSource = TypeVar("TSource")
TProcess = TypeVar("TProcess")

# ══════════════════════════════════════════════════════════════════════
# MadeItemProcess (referenced by MadeItemCreateRequest below)
# ══════════════════════════════════════════════════════════════════════


def _assert_process_role_shape(
    role: StepRole, fabrication_method_id: int | None, inspection_method_id: int | None
) -> None:
    """Runs the shared step role rule at request time and raises it as a
    ValueError, so a mismatch is a 422 rather than a 500 from the database
    check constraint, with the same message made_item_rules uses."""
    try:
        assert_role_matches_methods(
            role.value,
            fabrication_method_id,
            inspection_method_id,
            error=DomainError,
            noun="process",
        )
    except DomainError as e:
        raise ValueError(str(e)) from None


class MadeItemProcessCreateRequest(BaseModel):
    role: StepRole = StepRole.FABRICATION
    fabrication_method_id: int | None = Field(default=None, gt=0)
    inspection_method_id: int | None = Field(default=None, gt=0)
    note: str | None = None
    estimated_setup_minutes: int | None = None
    estimated_minutes_per_piece: float | None = None
    group_index: int | None = None

    @model_validator(mode="after")
    def validate_role_shape(self) -> "MadeItemProcessCreateRequest":
        _assert_process_role_shape(self.role, self.fabrication_method_id, self.inspection_method_id)
        return self


# ══════════════════════════════════════════════════════════════════════
# MadeItem (catalogue)
# ══════════════════════════════════════════════════════════════════════


class MadeItemCreateRequest(BaseModel):
    revision: str = Field(..., min_length=1)
    revision_date: date | None = None
    revision_note: str | None = None
    article_name: str = Field(..., min_length=1)
    article_group_ids: list[int] = Field(default_factory=list)
    status: MadeItemCatalogueStatus = MadeItemCatalogueStatus.ACTIVE
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
    processes: list[MadeItemProcessCreateRequest] = Field(default_factory=list)


class MadeItemUpdateRequest(BaseModel):
    # Revision is immutable in place; PUT never accepts it. A new revision
    # is a new row, created via POST /made-items/{id}/revisions.
    revision_date: date | None = None
    revision_note: str | None = None
    article_name: str = Field(..., min_length=1)
    article_group_ids: list[int] = Field(default_factory=list)
    # No default: an update that leaves the status out is refused instead of
    # setting the item active again.
    status: MadeItemCatalogueStatus
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
    # The edit version the form read; a row changed since answers 409.
    expected_edit_version: int


class _MadeItemProcessFields(EntityResponse, Generic[TLabel]):
    created: datetime
    note: str | None
    estimated_setup_minutes: int | None
    estimated_minutes_per_piece: float | None
    creator_id: int
    role: StepRole
    inspection_method_id: int | None
    fabrication_method_id: int | None
    fabrication_method_name: TLabel
    inspection_method_name: TLabel | None = None
    made_item_id: int
    position: int
    group_index: int


# The pat shape: catalogue labels in the request's label languages.
class MadeItemProcessResponse(_MadeItemProcessFields[ResolvedLabel]):
    pass


class MadeItemProcessWebResponse(_MadeItemProcessFields[dict[str, str]]):
    """The web shape: catalogue labels as language maps."""


class _MadeItemFields(EntityResponse, Generic[TGroup, TBought, TSource, TProcess]):
    part_number: str | None
    status: MadeItemCatalogueStatus
    created: datetime
    changed: datetime
    archived: bool
    revision: str
    revision_date: date | None
    revision_note: str | None
    article_name: str
    article_groups: list[TGroup] = Field(default_factory=list)
    data_source: DataSource
    vault_id: str | None = None
    pdm_file_id: int | None = None
    pdm_file_version: int | None = None
    pdm_synced_at: datetime | None = None
    pdm_sync_state: PdmSyncState | None = None
    material: str | None
    mass: int | None
    base_size: str | None
    note: str | None
    weblink: str | None
    successor_item_id: int | None
    creator_id: int
    creator: PublicUserResponse | None
    changed_by_id: int | None = None
    changed_by: PublicUserResponse | None = None
    bought_item_id: int | None
    bought_item: TBought | None
    source_item_id: int | None
    pdm_source_item_id: int | None = None
    source_item: TSource | None
    customer_id: int | None
    # The customer's name, so a list shows it without a customer lookup.
    customer_name: str | None
    customer_part_number: str | None
    customer_revision: str | None
    source_label: str = ""
    source_sublabel: str = ""
    processes: list[TProcess] = Field(default_factory=list)
    # PDM-owned field names this row's caller may not currently write;
    # see src.modules.catalogue.domain.policies.pdm_ownership.pdm_locked_fields. Empty when
    # the PDM integration is disabled, cad_items_read_only is off, the
    # actor is exempt, or the row is not PDM-owned. Additive: A7,
    # 2026-09-08.
    pdm_locked_fields: list[str] = Field(default_factory=list)
    # Sent back as expected_edit_version by an edit of the row.
    edit_version: int = 0


# The pat shape: catalogue labels in the request's label languages.
class MadeItemResponse(
    _MadeItemFields[
        ArticleGroupResponse, BoughtItemResponse, SourceItemResponse, MadeItemProcessResponse
    ]
):
    pass


class MadeItemWebResponse(
    _MadeItemFields[
        ArticleGroupWebResponse,
        BoughtItemWebResponse,
        SourceItemWebResponse,
        MadeItemProcessWebResponse,
    ]
):
    """The web shape: catalogue labels as language maps."""


class MadeItemMergeTargetResponse(ResponseModel):
    """A candidate target of a merge: the item, why it may not take the
    merge (null when it may), and whether the merge makes it active again."""

    item: MadeItemWebResponse
    refusal: MergeTargetRefusal | None
    reactivates: bool


class MadeItemFilterParams(PageParams):
    search: str | None = Query(default=None, description="Fuzzy search across all text columns")
    id: int | None = Query(default=None)
    status: MadeItemCatalogueStatus | None = Query(default=None)
    article_name: str | None = Query(default=None)
    article_group_id: int | None = Query(default=None)
    data_source: DataSource | None = Query(default=None)
    part_number: str | None = Query(default=None)
    revision: str | None = Query(default=None)
    material: str | None = Query(default=None)
    mass: int | None = Query(default=None)
    note: str | None = Query(default=None)
    weblink: str | None = Query(default=None)
    successor_item_id: int | None = Query(default=None)
    bought_item_id: int | None = Query(default=None)
    source_item_id: int | None = Query(default=None)
    customer_id: int | None = Query(default=None)
    creator_id: int | None = Query(default=None)
    creator_full_name: str | None = Query(default=None)
    approver_id: int | None = Query(default=None)
    include_archived: bool = Query(default=False)
    created_from: date | datetime | None = Query(default=None)
    created_to: date | datetime | None = Query(default=None)
    changed_from: date | datetime | None = Query(default=None)
    changed_to: date | datetime | None = Query(default=None)
    latest_only: bool | None = Query(
        default=None,
        description=(
            "Keep only the newest revision of each part-number family "
            "(highest revision wins, by length then alphabetically, ties broken "
            "by creation date desc then id desc). Rows with no part number "
            "always pass."
        ),
    )
    order_by: Literal["id", "article_name", "changed", "created"] | None = Query(default=None)
    order_dir: Literal["asc", "desc"] | None = Query(default=None)

    def to_dto(self, zone: tzinfo) -> MadeItemFilterDto:
        return MadeItemFilterDto(**expand_change_window(self.model_dump(), zone))


class MergeMadeItemRequest(BaseModel):
    target_id: int


# ══════════════════════════════════════════════════════════════════════
# Made-item revisions
# ══════════════════════════════════════════════════════════════════════


class MadeItemRevisionItemRequest(BaseModel):
    """MadeItemCreateRequest's shape minus revision and part_number. The new
    revision always inherits the same part number and is always born WEB,
    active, with no successor and no files."""

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
    processes: list[MadeItemProcessCreateRequest] = Field(default_factory=list)


class MadeItemCreateRevisionRequest(BaseModel):
    # Concrete only; the frontend resolves the "ask" setting before
    # sending this request.
    predecessor_status: Literal["replaced", "inactive", "active"]
    item: MadeItemRevisionItemRequest


class MadeItemRevisionSummaryResponse(EntityResponse):
    revision: str
    revision_date: date | None
    status: MadeItemCatalogueStatus
    successor_item_id: int | None
    created: datetime
    is_newest: bool


class MadeItemRevisionsResponse(ResponseModel):
    items: list[MadeItemRevisionSummaryResponse]
    next_revision: str | None
    next_revision_error: str | None
    can_create: bool
    reason: Literal["cad", "no_write"] | None


# ══════════════════════════════════════════════════════════════════════
# MadeItemProcess
# ══════════════════════════════════════════════════════════════════════


class MadeItemProcessUpdateRequest(BaseModel):
    role: StepRole = StepRole.FABRICATION
    fabrication_method_id: int | None = Field(default=None, gt=0)
    inspection_method_id: int | None = Field(default=None, gt=0)
    note: str | None = None
    estimated_setup_minutes: int | None = None
    estimated_minutes_per_piece: float | None = None

    @model_validator(mode="after")
    def validate_role_shape(self) -> "MadeItemProcessUpdateRequest":
        _assert_process_role_shape(self.role, self.fabrication_method_id, self.inspection_method_id)
        return self


class MadeItemProcessReorderRequest(BaseModel):
    ordered_process_ids: list[int] = Field(..., min_length=1)


class MadeItemProcessRegroupRequest(BaseModel):
    groups: list[list[int]] = Field(..., min_length=1)
