"""
HTTP schemas of the EPLAN Data Portal search in the create dialog, of the
lookup on an existing bought item, and of the read-only portal routes of
the pat surface.
"""

from typing import Literal

from pydantic import BaseModel
from pydantic import Field

from src.modules.catalogue.adapters.inbound.api.schemas.bought_item_schema import BoughtItemResponse
from src.modules.external_data.adapters.inbound.api.schemas.bought_item_import_schema import (
    EdpPartSummaryResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel

EdpLookupFieldName = Literal[
    "article_name",
    "order_code_1",
    "order_code_2",
    "ean",
    "weblink",
    "manufacturer_id",
    "product_family_id",
]


class EdpItemDraftResponse(ResponseModel):
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


class EdpSearchHitResponse(ResponseModel):
    part: EdpPartSummaryResponse
    draft: EdpItemDraftResponse
    existing_item: BoughtItemResponse | None = None


class EdpSearchResponse(ResponseModel):
    hits: list[EdpSearchHitResponse]


class EdpAvailabilityResponse(ResponseModel):
    enabled: bool


class EdpLookupFieldResponse(ResponseModel):
    field: EdpLookupFieldName
    item_value: str | None
    portal_value: str | None
    differs: bool
    applicable: bool


class EdpItemLookupResponse(ResponseModel):
    item_id: int
    part: EdpPartSummaryResponse | None = None
    candidates: list[EdpPartSummaryResponse] = Field(default_factory=list)
    fields: list[EdpLookupFieldResponse] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ApplyEdpLookupRequest(BaseModel):
    part_id: int
    fields: list[EdpLookupFieldName] = Field(default_factory=list)
