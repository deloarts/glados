"""
Wire schemas for saved calculations. `inputs` and `results` are whatever
the tool sends; only their size is checked here, so a runaway payload
cannot fill the table.
"""

import json
from typing import Any
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
from src.modules.quality.application.use_cases.calculation.get_calculations import (
    CalculationListQuery,
)

# Per payload (inputs and results each). The largest tool state planned, a
# filled checklist with remarks, stays well below this.
MAX_PAYLOAD_BYTES = 256 * 1024

TOOL_PATTERN = r"^[a-z][a-z0-9_]{0,63}$"


def _check_payload_size(value: dict[str, Any]) -> dict[str, Any]:
    size = len(json.dumps(value, separators=(",", ":")).encode("utf-8"))
    if size > MAX_PAYLOAD_BYTES:
        raise ValueError(f"payload is {size} bytes, the limit is {MAX_PAYLOAD_BYTES}")
    return value


class CalculationCreateRequest(BaseModel):
    tool: str = Field(..., pattern=TOOL_PATTERN)
    title: str = Field(..., min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=2000)
    inputs: dict[str, Any]
    results: dict[str, Any]
    input_version: int = Field(..., ge=1)
    engine_version: int = Field(..., ge=1)
    project_id: int | None = None
    product_id: int | None = None
    product_device_id: int | None = None

    _payload_size = field_validator("inputs", "results")(_check_payload_size)


class CalculationUpdateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    note: str | None = Field(default=None, max_length=2000)
    inputs: dict[str, Any]
    results: dict[str, Any]
    input_version: int = Field(..., ge=1)
    engine_version: int = Field(..., ge=1)
    project_id: int | None = None
    product_id: int | None = None
    product_device_id: int | None = None

    _payload_size = field_validator("inputs", "results")(_check_payload_size)


class CalculationDeviceRequest(BaseModel):
    # None unlinks the calculation from its device.
    product_device_id: int | None = None


class CalculationReviseRequest(DocumentReasonRequest):
    pass


class CalculationSummaryResponse(ControlledDocumentResponse):
    tool: str
    title: str
    note: str | None
    results: dict[str, Any]
    input_version: int
    engine_version: int
    project_id: int | None
    project_number: str | None
    product_id: int | None
    product_number: str | None
    product_device_id: int | None
    product_device_name: str | None


class CalculationResponse(CalculationSummaryResponse):
    inputs: dict[str, Any]
    changes: list[str] = Field(default_factory=list)


class CalculationFilterParams(PageParams):
    project_id: int | None = Query(default=None)
    product_id: int | None = Query(default=None)
    related_product_id: int | None = Query(
        default=None, description="Calculations of this product and of its projects"
    )
    product_device_id: int | None = Query(
        default=None, description="Only calculations that refer to this product device"
    )
    personal_only: bool = Query(
        default=False, description="Only calculations without project and product"
    )
    mine: bool = Query(default=False, description="Only calculations the caller created")
    tool: str | None = Query(default=None, pattern=TOOL_PATTERN)
    search: str | None = Query(
        default=None, max_length=200, description="Part of the title or the document number"
    )
    owner: Literal["personal", "project", "product"] | None = Query(
        default=None, description="Only calculations of this owner kind"
    )
    released: bool | None = Query(
        default=None, description="True for released calculations only, false for drafts only"
    )
    all_revisions: bool = Query(
        default=False, description="Include earlier revisions, not only the latest of each"
    )
    order_by: Literal["number", "title", "tool", "created", "changed", "released"] | None = Query(
        default=None, description="Sort field; the most recently changed come first without one"
    )
    order_dir: Literal["asc", "desc"] | None = Query(default=None)

    def to_query(self) -> CalculationListQuery:
        return CalculationListQuery(
            skip=self.skip,
            limit=self.limit,
            project_id=self.project_id,
            product_id=self.product_id,
            related_product_id=self.related_product_id,
            product_device_id=self.product_device_id,
            personal_only=self.personal_only,
            mine=self.mine,
            tool=self.tool,
            search=(self.search or "").strip() or None,
            owner=self.owner,
            released=self.released,
            latest_only=not self.all_revisions,
            order_by=self.order_by,
            order_dir=self.order_dir,
        )
