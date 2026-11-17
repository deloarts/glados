"""
Wire schemas for inspection checklists. Header fields, answers and remarks
are keyed by short identifiers the frontend defines; only their shape and
size are checked here, the answer values and counts in the domain.
"""

import re
from typing import Literal

from fastapi import Query
from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator

from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageParams
from src.modules.quality.adapters.inbound.api.schemas.controlled_document_schema import (
    ControlledDocumentResponse,
)
from src.modules.quality.adapters.inbound.api.schemas.controlled_document_schema import (
    DocumentReasonRequest,
)
from src.modules.quality.application.use_cases.checklist.get_checklists import ChecklistListQuery

TYPE_PATTERN = r"^[a-z][a-z0-9_]{0,63}$"

# A checklist type has a few hundred items; the cap leaves room to grow
# while keeping a runaway payload out of the table.
MAX_ITEMS = 2000
MAX_HEADER_FIELDS = 40
MAX_TEXT_LENGTH = 2000

# An item id is "<section key>.<item key>", a header key a plain identifier.
_ITEM_ID = re.compile(r"^[A-Za-z0-9_]{1,64}\.[A-Za-z0-9_]{1,64}$")
_HEADER_KEY = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")

Answer = Literal["na", "yes", "no", "defect"]


def _check_keys(value: dict[str, str], pattern: re.Pattern[str], what: str) -> dict[str, str]:
    bad = [key for key in value if not pattern.match(key)]
    if bad:
        raise ValueError(f"invalid {what} key(s): {bad[:5]}")
    return value


def _check_texts(value: dict[str, str]) -> dict[str, str]:
    long = [key for key, text in value.items() if len(text) > MAX_TEXT_LENGTH]
    if long:
        raise ValueError(f"text longer than {MAX_TEXT_LENGTH} characters for {long[:5]}")
    return value


class _ChecklistContent(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    header: dict[str, str] = Field(default_factory=dict, max_length=MAX_HEADER_FIELDS)
    answers: dict[str, Answer] = Field(default_factory=dict, max_length=MAX_ITEMS)
    remarks: dict[str, str] = Field(default_factory=dict, max_length=MAX_ITEMS)
    definition_version: int = Field(..., ge=1)
    item_count: int = Field(..., ge=1, le=MAX_ITEMS)
    project_id: int | None = None
    product_id: int | None = None

    @field_validator("header")
    @classmethod
    def _header(cls, value: dict[str, str]) -> dict[str, str]:
        return _check_texts(_check_keys(value, _HEADER_KEY, "header"))

    @field_validator("answers")
    @classmethod
    def _answers(cls, value: dict[str, str]) -> dict[str, str]:
        return _check_keys(value, _ITEM_ID, "item")

    @field_validator("remarks")
    @classmethod
    def _remarks(cls, value: dict[str, str]) -> dict[str, str]:
        return _check_texts(_check_keys(value, _ITEM_ID, "item"))


class ChecklistCreateRequest(_ChecklistContent):
    type: str = Field(..., pattern=TYPE_PATTERN)


class ChecklistUpdateRequest(_ChecklistContent):
    pass


class ChecklistReviseRequest(DocumentReasonRequest):
    pass


class ChecklistSummaryResponse(ControlledDocumentResponse):
    type: str
    title: str
    definition_version: int
    item_count: int
    answered_count: int
    finding_count: int
    verdict: Literal["open", "passed", "failed"]
    project_id: int | None
    project_number: str | None
    product_id: int | None
    product_number: str | None
    release_required: bool
    finished: bool
    designation: str | None = Field(
        None, description="The machine the checklist is about, as its header saved it."
    )


class ChecklistResponse(ChecklistSummaryResponse):
    header: dict[str, str]
    answers: dict[str, str]
    remarks: dict[str, str]
    changes: list[str] = Field(default_factory=list)


class ChecklistFilterParams(PageParams):
    project_id: int | None = Query(default=None)
    product_id: int | None = Query(default=None)
    related_product_id: int | None = Query(
        default=None, description="Checklists of this product and of its projects"
    )
    mine: bool = Query(default=False, description="Only checklists the caller created")
    owner: Literal["personal", "project", "product"] | None = Query(
        default=None, description="Only checklists of this owner kind"
    )
    type: str | None = Query(default=None, pattern=TYPE_PATTERN)
    verdict: Literal["open", "passed", "failed"] | None = Query(default=None)
    released: bool | None = Query(
        default=None, description="True for released checklists only, false for the others"
    )
    search: str | None = Query(
        default=None, max_length=200, description="Part of the title or the document number"
    )
    all_revisions: bool = Query(
        default=False, description="Include earlier revisions, not only the latest of each"
    )
    order_by: (
        Literal["number", "title", "type", "verdict", "created", "changed", "released"] | None
    ) = Query(
        default=None, description="Sort field; the most recently changed come first without one"
    )
    order_dir: Literal["asc", "desc"] | None = Query(default=None)

    def to_query(self) -> ChecklistListQuery:
        return ChecklistListQuery(
            skip=self.skip,
            limit=self.limit,
            project_id=self.project_id,
            product_id=self.product_id,
            related_product_id=self.related_product_id,
            mine=self.mine,
            owner=self.owner,
            type=self.type,
            verdict=self.verdict,
            released=self.released,
            search=(self.search or "").strip() or None,
            latest_only=not self.all_revisions,
            order_by=self.order_by,
            order_dir=self.order_dir,
        )
