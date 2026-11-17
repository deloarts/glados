"""
HTTP schemas of the bought-item batch create. Rows are permissive on
purpose, see BatchBoughtItemRowInput.
"""

from typing import Literal

from pydantic import BaseModel
from pydantic import Field

from src.modules.catalogue.adapters.inbound.api.schemas.bought_item_schema import (
    BoughtItemWebResponse,
)
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel


class BatchBoughtItemRowSchema(BaseModel):
    row_index: int
    article_name: str | None = None
    order_code_1: str | None = None
    manufacturer_name: str | None = None
    edp_part_number: str | None = None
    order_code_2: str | None = None
    gtin: str | None = None
    ean: str | None = None
    tariff_number: str | None = None
    mass: float | None = None
    note: str | None = None
    weblink: str | None = None
    article_group_names: str | None = None
    product_family_name: str | None = None
    part_number: str | None = None
    edp_part_id: int | None = None
    skip_lookup: bool = False


class BatchBoughtItemsRequest(BaseModel):
    rows: list[BatchBoughtItemRowSchema]
    # Looks every row up in the EPLAN Data Portal.
    lookup: bool = False


class BatchBoughtItemDivergenceResponse(ResponseModel):
    field: Literal[
        "article_name",
        "order_code_2",
        "gtin",
        "ean",
        "tariff_number",
        "mass",
        "weblink",
        "product_family",
    ]
    db_value: str | None
    file_value: str | None


class BatchBoughtItemPortalDifferenceResponse(ResponseModel):
    field: Literal[
        "article_name",
        "order_code_1",
        "order_code_2",
        "ean",
        "weblink",
        "manufacturer",
        "product_family",
    ]
    portal_value: str | None
    file_value: str | None


class EdpPartSummaryResponse(ResponseModel):
    part_id: int
    part_number: str
    order_number: str | None
    type_number: str | None
    designation: str | None
    manufacturer_code: str | None
    manufacturer_name: str | None
    product_family_name: str | None
    picture_url: str | None
    part_page_url: str | None


class BatchBoughtItemRowResponse(ResponseModel):
    row_index: int
    row_status: Literal[
        "ready",
        "exists",
        "duplicate_in_file",
        "not_found",
        "ambiguous",
        "unresolved_reference",
        "invalid",
    ]
    existing_item: BoughtItemWebResponse | None = None
    divergences: list[BatchBoughtItemDivergenceResponse] = Field(default_factory=list)
    resolved_manufacturer_id: int | None = None
    resolved_article_group_ids: list[int] = Field(default_factory=list)
    resolved_product_family_id: int | None = None
    edp_part: EdpPartSummaryResponse | None = None
    candidates: list[EdpPartSummaryResponse] = Field(default_factory=list)
    portal_differences: list[BatchBoughtItemPortalDifferenceResponse] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ValidateBatchBoughtItemsResponse(ResponseModel):
    results: list[BatchBoughtItemRowResponse]
    ready_count: int


class CommitBatchBoughtItemsResponse(ResponseModel):
    created_item_ids: list[int] = Field(default_factory=list)
    linked_item_ids: list[int] = Field(default_factory=list)
    created_row_indexes: list[int] = Field(default_factory=list)
    handled_row_indexes: list[int] = Field(default_factory=list)
