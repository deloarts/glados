"""
DTOs for the BoughtItem catalogue and DemandItem aggregates.
Order/OrderItem DTOs live in order_dto.py.
"""

from datetime import datetime

from pydantic import BaseModel
from pydantic import Field

from src.modules.catalogue.application.dto.article_group_dto import ArticleGroupResult
from src.modules.catalogue.application.dto.product_family_dto import ProductFamilyResult
from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.base import ResultModel
from src.modules.platform.application.dto.user_dto import PublicUserResult

# ══════════════════════════════════════════════════════════════════════
# BoughtItem (catalogue)
# ══════════════════════════════════════════════════════════════════════


class BoughtItemPdfFileResult(ResultModel):
    """A PDF file of the item, embedded in the catalogue rows so the list can
    show one entry per PDF without a second request. The item's file list
    has the full metadata."""

    id: int
    file_name: str
    mime_type: str


class CreateBoughtItemCommand(BaseModel):
    order_code_1: str = Field(..., min_length=1)
    order_code_2: str | None = None
    gtin: str | None = None
    ean: str | None = None
    tariff_number: str | None = None
    article_name: str = Field(..., min_length=1)
    article_group_ids: list[int] = Field(default_factory=list)
    # Only PDM ingest passes CAD; the web and pat create requests do not
    # carry the field, so every other row is born WEB.
    data_source: str = "WEB"
    status: str = "active"
    part_number: str | None = None
    mass: int | None = None
    note: str | None = None
    weblink: str | None = None
    manufacturer_id: int = Field(..., gt=0)
    product_family_id: int | None = None
    over_delivery_tolerance_percent: float | None = None
    under_delivery_tolerance_percent: float | None = None
    # The EPLAN Data Portal part the item is created from; sets the link
    # fields and requests the portal picture.
    edp_part_id: int | None = None


class UpdateBoughtItemCommand(BaseModel):
    order_code_1: str = Field(..., min_length=1)
    order_code_2: str | None = None
    gtin: str | None = None
    ean: str | None = None
    tariff_number: str | None = None
    article_name: str = Field(..., min_length=1)
    article_group_ids: list[int] = Field(default_factory=list)
    status: str = "active"
    part_number: str | None = None
    mass: int | None = None
    note: str | None = None
    weblink: str | None = None
    manufacturer_id: int = Field(..., gt=0)
    product_family_id: int | None = None
    successor_item_id: int | None = None
    # Sent by the web form only; an update without them keeps the item's.
    over_delivery_tolerance_percent: float | None = None
    under_delivery_tolerance_percent: float | None = None
    # The edit version the client read, checked when given; a row changed
    # since answers 409. The web routes require it, the `pat` API does not.
    expected_edit_version: int | None = None


class BoughtItemResult(ResultBase):
    status: str
    created: datetime
    changed: datetime
    archived: bool
    order_code_1: str
    order_code_2: str | None
    gtin: str | None
    ean: str | None
    tariff_number: str | None
    article_name: str
    article_groups: list[ArticleGroupResult] = Field(default_factory=list)
    data_source: str
    vault_id: str | None = None
    pdm_file_id: int | None = None
    pdm_file_version: int | None = None
    pdm_synced_at: datetime | None = None
    pdm_sync_state: str | None = None
    part_number: str | None
    revision: str | None = None  # read-only, PDM-owned, null on WEB rows
    mass: int | None
    note: str | None
    weblink: str | None
    successor_item_id: int | None
    creator_id: int
    creator: PublicUserResult | None
    changed_by_id: int | None
    changed_by: PublicUserResult | None
    manufacturer_id: int
    manufacturer_name: str
    product_family_id: int | None = None
    product_family: ProductFamilyResult | None = None
    edp_part_id: int | None = None
    edp_synced_at: datetime | None = None
    over_delivery_tolerance_percent: float | None = None
    under_delivery_tolerance_percent: float | None = None
    pdf_files: list[BoughtItemPdfFileResult] = Field(default_factory=list)
    changes: list[str] = Field(default_factory=list)
    # PDM-owned field names this row's caller may not currently write
    # (src.modules.catalogue.domain.policies.pdm_ownership.pdm_locked_fields), empty unless
    # the caller resolved it (GetBoughtItem, UpdateBoughtItem), since it
    # needs the current PDM settings and the actor. Additive: A7,
    # 2026-09-08.
    pdm_locked_fields: list[str] = Field(default_factory=list)
    # The row's edit version, which an edit sends back as expected_edit_version.
    edit_version: int = 0


class MergeBoughtItemCommand(BaseModel):
    target_id: int


class BoughtItemMergeTargetResult(BaseModel):
    """A candidate target of a merge: the item, why it may not take the
    merge (None when it may), and whether the merge makes it active again."""

    item: BoughtItemResult
    refusal: str | None
    reactivates: bool


# ══════════════════════════════════════════════════════════════════════
# DemandItem
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# Procurement pipeline
# ══════════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════════
# Batch demand import (Excel)
# ══════════════════════════════════════════════════════════════════════
