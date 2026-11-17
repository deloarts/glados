"""
Results and commands of the EPLAN Data Portal search in the create dialog
and of the lookup on an existing bought item.
"""

from typing import Literal

from pydantic import BaseModel
from pydantic import Field

from src.modules.catalogue.application.dto.bought_item_dto import BoughtItemResult
from src.modules.external_data.application.dto.bought_item_import_dto import EdpPartSummary

EdpLookupField = Literal[
    "article_name",
    "order_code_1",
    "order_code_2",
    "ean",
    "weblink",
    "manufacturer_id",
    "product_family_id",
]


class EdpItemDraftResult(BaseModel):
    """The bought-item values a portal part fills, see
    application.services.edp_item_draft."""

    edp_part_id: int
    article_name: str | None
    order_code_1: str | None
    order_code_2: str | None
    ean: str | None
    weblink: str | None
    manufacturer_code: str | None
    manufacturer_id: int | None
    product_family_name: str | None
    product_family_id: int | None
    article_group_ids: list[int] = Field(default_factory=list)


class EdpSearchHitResult(BaseModel):
    part: EdpPartSummary
    draft: EdpItemDraftResult
    # The catalogue item that already describes this part, if any.
    existing_item: BoughtItemResult | None = None


class EdpSearchResult(BaseModel):
    hits: list[EdpSearchHitResult]


class EdpAvailabilityResult(BaseModel):
    enabled: bool


class EdpLookupFieldResult(BaseModel):
    field: EdpLookupField
    item_value: str | None
    portal_value: str | None
    differs: bool
    # The portal value can be written: it exists, differs, and the field is
    # not owned by PDM on this row.
    applicable: bool


class EdpItemLookupResult(BaseModel):
    """What the lookup on an item found: the part it matched, the
    candidates when the number is ambiguous, and the field comparison."""

    item_id: int
    part: EdpPartSummary | None = None
    candidates: list[EdpPartSummary] = Field(default_factory=list)
    fields: list[EdpLookupFieldResult] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ApplyEdpLookupCommand(BaseModel):
    part_id: int
    # The fields whose portal value replaces the item's; empty only links.
    fields: list[EdpLookupField] = Field(default_factory=list)
