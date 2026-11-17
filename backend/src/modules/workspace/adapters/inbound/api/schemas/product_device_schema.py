"""
HTTP schemas for product devices and for the hand-maintained lists they
pick from (driving media, component roles, energy behaviours, kinds with
positions, parameters and signals).
"""

from datetime import datetime
from typing import Annotated
from typing import Any
from typing import Literal

from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel
from src.modules.platform.adapters.inbound.api.schemas.localized_text_schema import LocalizedTextIn
from src.modules.platform.adapters.inbound.api.schemas.user_schema import PublicUserResponse
from src.modules.workspace.domain.value_objects.device_plan import DevicePlan
from src.modules.workspace.domain.value_objects.product_device_option_category import (
    ProductDeviceOptionCategory,
)
from src.modules.workspace.domain.value_objects.product_device_parameter_type import (
    ProductDeviceParameterType,
)
from src.modules.workspace.domain.value_objects.product_device_signal import ProductDeviceSignalType

_Unit = Annotated[str, Field(max_length=20)]

# ── Resource requests ─────────────────────────────────────────────────


class ProductDeviceOptionCreateRequest(BaseModel):
    category: ProductDeviceOptionCategory
    label: LocalizedTextIn
    letter: str | None = Field(default=None, max_length=4)


class ProductDeviceOptionUpdateRequest(BaseModel):
    label: LocalizedTextIn
    letter: str | None = Field(default=None, max_length=4)
    sort_order: int | None = Field(default=None, ge=0)


class ProductDeviceKindPositionRequest(BaseModel):
    id: int | None = None
    label: LocalizedTextIn
    takes_value: bool = False
    unit: _Unit | None = None
    plc_state_name: str | None = Field(default=None, max_length=40)
    plc_command_name: str | None = Field(default=None, max_length=40)


class ProductDeviceKindParameterRequest(BaseModel):
    id: int | None = None
    label: LocalizedTextIn
    unit: _Unit | None = None
    value_type: ProductDeviceParameterType = ProductDeviceParameterType.NUMBER


class ProductDeviceKindSignalRequest(BaseModel):
    id: int | None = None
    label: LocalizedTextIn
    signal_type: ProductDeviceSignalType
    # Ends the tag of a device signal that picks it.
    plc_name: str = Field(max_length=40)


class ProductDeviceKindSaveRequest(BaseModel):
    label: LocalizedTextIn
    sort_order: int | None = Field(default=None, ge=0)
    # Operator devices: no driving medium, no letter in the name.
    without_driving_medium: bool = False
    positions: list[ProductDeviceKindPositionRequest] = Field(default_factory=list, max_length=50)
    parameters: list[ProductDeviceKindParameterRequest] = Field(default_factory=list, max_length=50)
    signals: list[ProductDeviceKindSignalRequest] = Field(default_factory=list, max_length=50)


# ── Resource responses ────────────────────────────────────────────────


class ProductDeviceOptionResponse(EntityResponse):
    created: datetime
    changed: datetime
    category: ProductDeviceOptionCategory
    label: dict[str, str]
    letter: str | None
    sort_order: int
    archived: bool
    creator_id: int
    creator: PublicUserResponse | None
    changed_by_id: int | None
    changed_by: PublicUserResponse | None


class ProductDeviceKindPositionResponse(EntityResponse):
    label: dict[str, str]
    takes_value: bool
    unit: str | None
    sort_order: int
    archived: bool
    plc_state_name: str | None
    plc_command_name: str | None


class ProductDeviceKindParameterResponse(EntityResponse):
    label: dict[str, str]
    unit: str | None
    value_type: ProductDeviceParameterType
    sort_order: int
    archived: bool


class ProductDeviceKindSignalResponse(EntityResponse):
    label: dict[str, str]
    signal_type: ProductDeviceSignalType
    plc_name: str
    sort_order: int
    archived: bool


class ProductDeviceKindResponse(EntityResponse):
    created: datetime
    changed: datetime
    label: dict[str, str]
    sort_order: int
    without_driving_medium: bool
    archived: bool
    creator_id: int
    creator: PublicUserResponse | None
    changed_by_id: int | None
    changed_by: PublicUserResponse | None
    positions: list[ProductDeviceKindPositionResponse]
    parameters: list[ProductDeviceKindParameterResponse]
    signals: list[ProductDeviceKindSignalResponse]


# ── Device requests ───────────────────────────────────────────────────


class ProductDeviceSignalRequest(BaseModel):
    signal_type: ProductDeviceSignalType
    # Needed only when the signal names neither a position nor a kind signal.
    meaning: str = Field(default="", max_length=200)
    # The position of the device's kind this input confirms.
    confirms_position_id: int | None = None
    # The position of the device's kind this output drives to.
    drives_position_id: int | None = None
    safety: bool = False
    address: str | None = Field(default=None, max_length=30)
    # Replaces the position's state or command name in the tag.
    tag_suffix: str | None = Field(default=None, max_length=200)
    # Replaces the whole tag name.
    tag_name: str | None = Field(default=None, max_length=200)
    # The signal of the device's kind this one is, for a signal without a
    # position; it sets the signal type and the tag's suffix.
    kind_signal_id: int | None = None


class ProductDeviceComponentRequest(BaseModel):
    id: int | None = None
    role_id: int
    bought_item_id: int | None = None
    eplan_tag: str | None = Field(default=None, max_length=200)
    b10d_cycles: int | None = Field(default=None, gt=0)
    mttfd_years: float | None = Field(default=None, gt=0)
    note: str | None = Field(default=None, max_length=2000)
    signals: list[ProductDeviceSignalRequest] = Field(default_factory=list, max_length=20)


class ProductDeviceSaveRequest(BaseModel):
    location: str = Field(default="", max_length=500)
    name: str = Field(max_length=500)
    driving_medium_id: int | None = None
    number: int | None = Field(default=None, ge=1)
    kind_id: int
    description: str | None = Field(default=None, max_length=5000)
    initial_position_id: int | None = None
    initial_position_value: float | None = None
    energy_loss_behaviour_id: int | None = None
    energy_restoration_behaviour_id: int | None = None
    monitoring_time_ms: int | None = Field(default=None, ge=0)
    # Another device of the product whose output moves this one too.
    driven_by_id: int | None = None
    # Driver position id to own position id, for a driver of another kind.
    driven_position_map: dict[str, str] = Field(default_factory=dict, max_length=50)
    safety_relevant: bool = False
    parameters: dict[str, Any] = Field(default_factory=dict)
    position_labels: dict[str, str] = Field(default_factory=dict)
    # Kind position id to the nominal time in ms the device takes to reach it.
    travel_times_ms: dict[str, int] = Field(default_factory=dict, max_length=50)
    marker_x: float | None = None
    marker_y: float | None = None
    components: list[ProductDeviceComponentRequest] = Field(default_factory=list, max_length=50)


class ProductDeviceUpdateRequest(ProductDeviceSaveRequest):
    """An edit of a device, which carries the edit version the form read."""

    # The edit version the form read; a row changed since answers 409.
    expected_edit_version: int


class ProductDeviceNamePreviewRequest(BaseModel):
    location: str = Field(default="", max_length=500)
    name: str = Field(default="", max_length=500)
    driving_medium_id: int | None = None
    number: int | None = Field(default=None, ge=1)
    device_id: int | None = None
    # The kind, so the preview can tell the longest tag the name produces.
    kind_id: int | None = None


# ── Device responses ──────────────────────────────────────────────────


class ProductDeviceSignalResponse(ResponseModel):
    signal_type: ProductDeviceSignalType
    meaning: str
    confirms_position_id: int | None
    drives_position_id: int | None
    safety: bool
    address: str | None
    tag_suffix: str | None
    tag_name: str | None
    kind_signal_id: int | None


class ProductDeviceComponentResponse(EntityResponse):
    role_id: int
    sort_order: int
    bought_item_id: int | None
    bought_item_part_number: str | None
    bought_item_article_name: str | None
    eplan_tag: str | None
    b10d_cycles: int | None
    mttfd_years: float | None
    note: str | None
    signals: list[ProductDeviceSignalResponse]


class ProductDeviceResponse(EntityResponse):
    created: datetime
    changed: datetime
    archived: bool
    product_id: int
    product_number: str
    location: str
    name: str
    driving_medium_id: int | None
    driving_medium_letter: str | None
    number: int
    # Without the product number, as stored.
    name_utf8: str
    name_ascii: str
    # With the product number in front, composed on read.
    full_name_utf8: str
    full_name_ascii: str
    kind_id: int
    description: str | None
    initial_position_id: int | None
    initial_position_value: float | None
    energy_loss_behaviour_id: int | None
    energy_restoration_behaviour_id: int | None
    monitoring_time_ms: int | None
    driven_by_id: int | None
    driven_position_map: dict[str, str]
    safety_relevant: bool
    parameters: dict[str, Any]
    position_labels: dict[str, str]
    travel_times_ms: dict[str, int]
    rendering_file_id: int | None
    assembly_file_id: int | None
    marker_x: float | None
    marker_y: float | None
    creator_id: int
    creator: PublicUserResponse | None
    changed_by_id: int | None
    changed_by: PublicUserResponse | None
    components: list[ProductDeviceComponentResponse]
    # Sent back as expected_edit_version by an edit of the row.
    edit_version: int = 0


class ProductDeviceNamePreviewResponse(ResponseModel):
    number: int
    name_utf8: str
    name_ascii: str
    full_name_utf8: str
    full_name_ascii: str
    invalid_characters: list[str]
    taken: bool
    # The longest PLC tag the name produces with the kind's positions, and
    # the limit of the product's PLC environment; None without either.
    longest_tag_length: int | None
    max_tag_length: int | None


# ── Completeness ──────────────────────────────────────────────────────


class ProductDeviceCheckResponse(ResponseModel):
    plan: DevicePlan
    checked_by_name: str
    checked_at: datetime


class ProductDeviceCompletenessResponse(ResponseModel):
    device_id: int
    checks: list[ProductDeviceCheckResponse]
    # "released" when a valid released sequence moves or checks the device,
    # "draft" when only a draft does, "none" otherwise.
    sequence_coverage: Literal["released", "draft", "none"]


class ProductDeviceCheckRequest(BaseModel):
    checked: bool
