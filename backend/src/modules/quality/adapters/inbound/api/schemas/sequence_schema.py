"""
Wire schemas for flow sequences. The step models fix the shape of the
content and its sizes; whether the devices, positions, steps and variants
it names fit together is checked by the domain (see sequence_rules.py).
Variant ids are object keys, so they travel as strings.
"""

from typing import Literal

from fastapi import Query
from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.platform.adapters.inbound.api.schemas.pagination_schema import PageParams
from src.modules.quality.adapters.inbound.api.schemas.controlled_document_schema import (
    ControlledDocumentResponse,
)
from src.modules.quality.adapters.inbound.api.schemas.controlled_document_schema import (
    DocumentReasonRequest,
)
from src.modules.quality.application.use_cases.sequence.get_sequences import SequenceListQuery
from src.modules.quality.domain.services.sequence_rules import MAX_ACTIONS
from src.modules.quality.domain.services.sequence_rules import MAX_STEPS
from src.modules.quality.domain.services.sequence_rules import MAX_TERMS
from src.modules.quality.domain.services.sequence_rules import MAX_TRANSITIONS
from src.modules.quality.domain.services.sequence_rules import NAME_MAX_LENGTH
from src.modules.quality.domain.services.sequence_rules import TEXT_MAX_LENGTH

KEY_PATTERN = r"^[A-Za-z0-9_-]{1,40}$"


class SequenceVariantValueSchema(BaseModel):
    common: float | None = None
    per_variant: dict[str, float] = Field(default_factory=dict, max_length=200)


class SequenceConditionTermSchema(BaseModel):
    kind: Literal["device_position", "device_value", "step_complete", "time", "external"]
    device_id: int | None = None
    position_id: int | None = None
    comparator: Literal["ge", "le"] | None = None
    value: SequenceVariantValueSchema | None = None
    step_key: str | None = Field(default=None, pattern=KEY_PATTERN)
    duration_ms: SequenceVariantValueSchema | None = None
    text: str | None = Field(default=None, max_length=TEXT_MAX_LENGTH)


class SequenceActionSchema(BaseModel):
    key: str = Field(..., pattern=KEY_PATTERN)
    kind: Literal["device", "text"]
    qualifier: Literal["stored", "continuous", "pulse"] = "stored"
    device_id: int | None = None
    position_id: int | None = None
    value: SequenceVariantValueSchema | None = None
    text: str | None = Field(default=None, max_length=TEXT_MAX_LENGTH)
    description: str | None = Field(default=None, max_length=TEXT_MAX_LENGTH)
    condition: list[SequenceConditionTermSchema] = Field(default_factory=list, max_length=MAX_TERMS)
    # The estimated time in ms; None uses the device's travel time.
    duration_ms: SequenceVariantValueSchema | None = None


class SequenceTransitionSchema(BaseModel):
    key: str = Field(..., pattern=KEY_PATTERN)
    # A step key, "next" or "end".
    target: str = Field(default="next", pattern=KEY_PATTERN)
    condition: list[SequenceConditionTermSchema] = Field(default_factory=list, max_length=MAX_TERMS)


class SequenceStepSchema(BaseModel):
    key: str = Field(..., pattern=KEY_PATTERN)
    description: str | None = Field(default=None, max_length=TEXT_MAX_LENGTH)
    timeout_ms: int | None = Field(default=None, ge=1)
    # How long the step is expected to take in ms.
    expected_duration_ms: SequenceVariantValueSchema | None = None
    actions: list[SequenceActionSchema] = Field(default_factory=list, max_length=MAX_ACTIONS)
    transitions: list[SequenceTransitionSchema] = Field(
        default_factory=list, max_length=MAX_TRANSITIONS
    )


class SequenceCreateRequest(BaseModel):
    product_id: int
    name: str = Field(..., min_length=1, max_length=NAME_MAX_LENGTH)
    steps: list[SequenceStepSchema] = Field(default_factory=list, max_length=MAX_STEPS)


class SequenceUpdateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=NAME_MAX_LENGTH)
    steps: list[SequenceStepSchema] = Field(..., max_length=MAX_STEPS)


class SequenceReviseRequest(DocumentReasonRequest):
    pass


class SequenceSummaryResponse(ControlledDocumentResponse):
    product_id: int
    product_number: str | None
    name: str
    step_count: int


class SequenceFrozenPositionSchema(ResponseModel):
    label: dict[str, str]
    device_label: str | None
    unit: str | None
    takes_value: bool
    # None when the device has no travel time for this position.
    travel_time_ms: int | None


class SequenceFrozenDeviceSchema(ResponseModel):
    name: str
    name_ascii: str
    kind: dict[str, str]
    initial_position_id: int | None
    initial_position_value: float | None
    positions: dict[str, SequenceFrozenPositionSchema]
    # None and an empty map for a device no other device drives.
    driven_by_id: int | None
    driven_position_map: dict[str, str]


class SequenceFrozenSchema(ResponseModel):
    """The names a released revision shows, keyed by id."""

    product_number: str | None
    devices: dict[str, SequenceFrozenDeviceSchema]
    variants: dict[str, str]


class SequenceResponse(SequenceSummaryResponse):
    steps: list[SequenceStepSchema]
    frozen: SequenceFrozenSchema | None
    changes: list[str] = Field(default_factory=list)


class SequenceFilterParams(PageParams):
    product_id: int | None = Query(default=None)
    mine: bool = Query(default=False, description="Only sequences the caller created")
    search: str | None = Query(
        default=None, max_length=200, description="Part of the name or the document number"
    )
    released: bool | None = Query(
        default=None, description="True for released sequences only, false for drafts only"
    )
    all_revisions: bool = Query(
        default=False, description="Include earlier revisions, not only the latest of each"
    )
    order_by: Literal["number", "title", "created", "changed", "released"] | None = Query(
        default=None,
        description="Sort field, title sorts by the name; the most recently changed come first "
        "without one",
    )
    order_dir: Literal["asc", "desc"] | None = Query(default=None)

    def to_query(self) -> SequenceListQuery:
        return SequenceListQuery(
            skip=self.skip,
            limit=self.limit,
            product_id=self.product_id,
            mine=self.mine,
            search=(self.search or "").strip() or None,
            released=self.released,
            latest_only=not self.all_revisions,
            order_by=self.order_by,
            order_dir=self.order_dir,
        )
