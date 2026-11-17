"""
HTTP schemas for the BoughtItem catalogue and DemandItem aggregates, plus the
procurement pipeline view. Order/OrderItem schemas live in order_schema.py.
Old v1-era schemas (BoughtItemCreateRequest with partnumber/manufacturer/etc.)
are replaced entirely.
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

from src.modules.catalogue.adapters.inbound.api.schemas.article_group_schema import (
    ArticleGroupResponse,
)
from src.modules.catalogue.adapters.inbound.api.schemas.article_group_schema import (
    ArticleGroupWebResponse,
)
from src.modules.catalogue.adapters.inbound.api.schemas.delivery_tolerance_schema import (
    DeliveryToleranceFields,
)
from src.modules.catalogue.adapters.inbound.api.schemas.product_family_schema import (
    ProductFamilyResponse,
)
from src.modules.catalogue.domain.policies.catalogue_item_status import MergeTargetRefusal
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.pdm_sync_state import PdmSyncState
from src.modules.catalogue.ports.outbound.catalogue_queries import BoughtItemFilterDto
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.platform.adapters.inbound.api.schemas.base import expand_change_window
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageParams
from src.modules.platform.adapters.inbound.api.schemas.user_schema import PublicUserResponse

TGroup = TypeVar("TGroup")

# ══════════════════════════════════════════════════════════════════════
# BoughtItem (catalogue)
# ══════════════════════════════════════════════════════════════════════


class BoughtItemPdfFileResponse(ResponseModel):
    """Slim PDF-file projection embedded in BoughtItemResponse so the catalogue
    list can render one icon per PDF. Full metadata: BoughtItemFileResponse."""

    id: int
    file_name: str
    mime_type: str


class BoughtItemCreateRequest(BaseModel):
    order_code_1: str = Field(..., min_length=1)
    order_code_2: str | None = None
    gtin: str | None = None
    ean: str | None = None
    tariff_number: str | None = None
    article_name: str = Field(..., min_length=1)
    article_group_ids: list[int] = Field(default_factory=list)
    status: BoughtItemCatalogueStatus = BoughtItemCatalogueStatus.ACTIVE
    part_number: str | None = None
    mass: int | None = None
    note: str | None = None
    weblink: str | None = None
    manufacturer_id: int = Field(..., gt=0)
    product_family_id: int | None = None
    edp_part_id: int | None = None


class BoughtItemUpdateRequest(BaseModel):
    """A full update of the item. `status` has no default, so an update that
    leaves it out is refused instead of setting the item active again."""

    order_code_1: str = Field(..., min_length=1)
    order_code_2: str | None = None
    gtin: str | None = None
    ean: str | None = None
    tariff_number: str | None = None
    article_name: str = Field(..., min_length=1)
    article_group_ids: list[int] = Field(default_factory=list)
    status: BoughtItemCatalogueStatus
    part_number: str | None = None
    mass: int | None = None
    note: str | None = None
    weblink: str | None = None
    manufacturer_id: int = Field(..., gt=0)
    product_family_id: int | None = None
    successor_item_id: int | None = None
    # The edit version the client read, checked when given; a row changed
    # since answers 409. The web form's update requires it.
    expected_edit_version: int | None = None


class BoughtItemWebCreateRequest(BoughtItemCreateRequest, DeliveryToleranceFields):
    """The web form's create, which also sets the item's delivery tolerances."""


class BoughtItemWebUpdateRequest(BoughtItemUpdateRequest, DeliveryToleranceFields):
    """The web form's update, which also sets the item's delivery tolerances
    and requires the edit version."""

    # The edit version the form read; a row changed since answers 409.
    expected_edit_version: int


class MergeBoughtItemRequest(BaseModel):
    """The item that absorbs the merged one."""

    target_id: int


class _BoughtItemFields(EntityResponse, Generic[TGroup]):
    part_number: str | None
    revision: str | None = None  # read-only, PDM-owned, null on WEB rows
    status: BoughtItemCatalogueStatus
    created: datetime
    changed: datetime
    archived: bool
    order_code_1: str
    order_code_2: str | None
    gtin: str | None
    ean: str | None
    tariff_number: str | None
    article_name: str
    article_groups: list[TGroup] = Field(default_factory=list)
    data_source: DataSource
    vault_id: str | None = None
    pdm_file_id: int | None = None
    pdm_file_version: int | None = None
    pdm_synced_at: datetime | None = None
    pdm_sync_state: PdmSyncState | None = None
    mass: int | None
    note: str | None
    weblink: str | None
    successor_item_id: int | None
    creator_id: int
    creator: PublicUserResponse | None
    changed_by_id: int | None
    changed_by: PublicUserResponse | None
    manufacturer_id: int
    manufacturer_name: str
    product_family_id: int | None = None
    product_family: ProductFamilyResponse | None = None
    edp_part_id: int | None = None
    edp_synced_at: datetime | None = None
    over_delivery_tolerance_percent: float | None = None
    under_delivery_tolerance_percent: float | None = None
    pdf_files: list[BoughtItemPdfFileResponse] = Field(default_factory=list)
    # PDM-owned field names this row's caller may not currently write;
    # see src.modules.catalogue.domain.policies.pdm_ownership.pdm_locked_fields. Empty when
    # the PDM integration is disabled, cad_items_read_only is off, the
    # actor is exempt, or the row is not PDM-owned. Additive: A7,
    # 2026-09-08.
    pdm_locked_fields: list[str] = Field(default_factory=list)
    # Sent back as expected_edit_version by an edit of the row.
    edit_version: int = 0


# The pat shape: catalogue labels in the request's label languages.
class BoughtItemResponse(_BoughtItemFields[ArticleGroupResponse]):
    pass


class BoughtItemWebResponse(_BoughtItemFields[ArticleGroupWebResponse]):
    """The web shape: catalogue labels as language maps."""


class BoughtItemMergeTargetResponse(ResponseModel):
    """A candidate target of a merge: the item, why it may not take the
    merge (null when it may), and whether the merge makes it active again."""

    item: BoughtItemWebResponse
    refusal: MergeTargetRefusal | None
    reactivates: bool


class BoughtItemFilterParams(PageParams):
    search: str | None = Query(default=None, description="Fuzzy search across all text columns")
    id: int | None = Query(default=None)
    status: BoughtItemCatalogueStatus | None = Query(default=None)
    order_code_1: str | None = Query(default=None)
    order_code_2: str | None = Query(default=None)
    gtin: str | None = Query(default=None)
    ean: str | None = Query(default=None)
    tariff_number: str | None = Query(default=None)
    article_name: str | None = Query(default=None)
    article_group_id: int | None = Query(default=None)
    product_family_id: int | None = Query(default=None)
    data_source: DataSource | None = Query(default=None)
    part_number: str | None = Query(default=None)
    mass: int | None = Query(default=None)
    note: str | None = Query(default=None)
    weblink: str | None = Query(default=None)
    successor_item_id: int | None = Query(default=None)
    manufacturer_id: int | None = Query(default=None)
    manufacturer_name: str | None = Query(default=None)
    creator_id: int | None = Query(default=None)
    changed_by_id: int | None = Query(default=None)
    creator_full_name: str | None = Query(default=None)
    approver_id: int | None = Query(default=None)
    include_archived: bool = Query(default=False)
    created_from: date | datetime | None = Query(default=None)
    created_to: date | datetime | None = Query(default=None)
    changed_from: date | datetime | None = Query(default=None)
    changed_to: date | datetime | None = Query(default=None)
    order_by: Literal["id", "article_name", "manufacturer_name", "changed", "created"] | None = (
        Query(default=None)
    )
    order_dir: Literal["asc", "desc"] | None = Query(default=None)

    def to_dto(self, zone: tzinfo) -> BoughtItemFilterDto:
        return BoughtItemFilterDto(**expand_change_window(self.model_dump(), zone))


# ══════════════════════════════════════════════════════════════════════
# DemandItem
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# Batch demand import (Excel)
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# Procurement pipeline
# ══════════════════════════════════════════════════════════════════════
