"""
Rows, results and commands of the bought-item batch create, the spreadsheet
import that creates catalogue items. The row is permissive on purpose: a
blank or garbled cell surfaces as that row's `invalid` status with a
message, not as a 422 for the whole batch.
"""

from typing import Literal

from pydantic import BaseModel
from pydantic import Field

from src.modules.catalogue.application.dto.bought_item_dto import BoughtItemResult

BatchBoughtItemRowStatus = Literal[
    "ready",
    "exists",
    "duplicate_in_file",
    "not_found",
    "ambiguous",
    "unresolved_reference",
    "invalid",
]

BatchBoughtItemDivergenceField = Literal[
    "article_name",
    "order_code_2",
    "gtin",
    "ean",
    "tariff_number",
    "mass",
    "weblink",
    "product_family",
]

BatchBoughtItemPortalField = Literal[
    "article_name",
    "order_code_1",
    "order_code_2",
    "ean",
    "weblink",
    "manufacturer",
    "product_family",
]


class BatchBoughtItemRowInput(BaseModel):
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
    # Names separated by ";" or ",".
    article_group_names: str | None = None
    product_family_name: str | None = None
    part_number: str | None = None
    # The portal part the user picked for an ambiguous row; it is used as it
    # is instead of looking the row up again.
    edp_part_id: int | None = None
    # Creates the row from the file alone although the lookup is on, for a
    # part the portal does not know.
    skip_lookup: bool = False


class BatchBoughtItemDivergence(BaseModel):
    field: BatchBoughtItemDivergenceField
    db_value: str | None
    file_value: str | None


class BatchBoughtItemPortalDifference(BaseModel):
    """A field where the portal, which wins, and the file disagree."""

    field: BatchBoughtItemPortalField
    portal_value: str | None
    file_value: str | None


class EdpPartSummary(BaseModel):
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


class BatchBoughtItemRowResult(BaseModel):
    row_index: int
    row_status: BatchBoughtItemRowStatus
    # The catalogue item an `exists` row matched.
    existing_item: BoughtItemResult | None = None
    divergences: list[BatchBoughtItemDivergence] = Field(default_factory=list)
    resolved_manufacturer_id: int | None = None
    resolved_article_group_ids: list[int] = Field(default_factory=list)
    resolved_product_family_id: int | None = None
    # The portal part a looked-up row resolved to, and the candidates of an
    # ambiguous one.
    edp_part: EdpPartSummary | None = None
    candidates: list[EdpPartSummary] = Field(default_factory=list)
    portal_differences: list[BatchBoughtItemPortalDifference] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ValidateBatchBoughtItemsResult(BaseModel):
    results: list[BatchBoughtItemRowResult]
    ready_count: int


class CommitBatchBoughtItemsResult(BaseModel):
    created_item_ids: list[int] = Field(default_factory=list)
    # Existing items a looked-up row linked to its portal part.
    linked_item_ids: list[int] = Field(default_factory=list)
    created_row_indexes: list[int] = Field(default_factory=list)
    # Row indexes the commit is done with: the created rows and the rows of
    # existing items. Every other row stays in the client's draft.
    handled_row_indexes: list[int] = Field(default_factory=list)
