"""
Commands and results of the product device use cases.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel
from pydantic import Field

from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.user_dto import PublicUserResult
from src.modules.workspace.domain.value_objects.product_device_signal import ProductDeviceSignalType

# ── Commands ──────────────────────────────────────────────────────────


class ProductDeviceSignalDraft(BaseModel):
    signal_type: ProductDeviceSignalType
    meaning: str = ""
    confirms_position_id: int | None = None
    drives_position_id: int | None = None
    safety: bool = False
    address: str | None = None
    tag_suffix: str | None = None
    tag_name: str | None = None
    kind_signal_id: int | None = None


class ProductDeviceComponentDraft(BaseModel):
    id: int | None = None
    role_id: int
    bought_item_id: int | None = None
    eplan_tag: str | None = None
    b10d_cycles: int | None = None
    mttfd_years: float | None = None
    note: str | None = None
    signals: list[ProductDeviceSignalDraft] = []


class SaveProductDeviceCommand(BaseModel):
    location: str = ""
    name: str
    driving_medium_id: int | None = None
    # None asks for the next free number.
    number: int | None = None
    kind_id: int
    description: str | None = None
    initial_position_id: int | None = None
    initial_position_value: float | None = None
    energy_loss_behaviour_id: int | None = None
    energy_restoration_behaviour_id: int | None = None
    monitoring_time_ms: int | None = None
    driven_by_id: int | None = None
    driven_position_map: dict[str, str] = Field(default_factory=dict)
    safety_relevant: bool = False
    parameters: dict[str, Any] = {}
    position_labels: dict[str, str] = {}
    travel_times_ms: dict[str, int] = {}
    marker_x: float | None = None
    marker_y: float | None = None
    components: list[ProductDeviceComponentDraft] = []
    # The edit version the client read, checked when given; a row changed
    # since answers 409. The web routes require it, the `pat` API does not.
    expected_edit_version: int | None = None


class PreviewProductDeviceNameCommand(BaseModel):
    location: str = ""
    name: str = ""
    driving_medium_id: int | None = None
    number: int | None = None
    # The device being edited, so its own name does not count as taken.
    device_id: int | None = None
    kind_id: int | None = None


# ── Results ───────────────────────────────────────────────────────────


class ProductDeviceSignalResult(BaseModel):
    signal_type: ProductDeviceSignalType
    meaning: str
    confirms_position_id: int | None
    drives_position_id: int | None
    safety: bool
    address: str | None
    tag_suffix: str | None
    tag_name: str | None
    kind_signal_id: int | None


class ProductDeviceComponentResult(ResultBase):
    role_id: int
    sort_order: int
    bought_item_id: int | None
    bought_item_part_number: str | None
    bought_item_article_name: str | None
    eplan_tag: str | None
    b10d_cycles: int | None
    mttfd_years: float | None
    note: str | None
    signals: list[ProductDeviceSignalResult]


class ProductDeviceResult(ResultBase):
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
    name_utf8: str
    name_ascii: str
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
    creator: PublicUserResult | None
    changed_by_id: int | None
    changed_by: PublicUserResult | None
    components: list[ProductDeviceComponentResult]
    # The row's edit version, which an edit sends back as expected_edit_version.
    edit_version: int = 0


class ProductDeviceNamePreviewResult(BaseModel):
    number: int
    name_utf8: str
    name_ascii: str
    full_name_utf8: str
    full_name_ascii: str
    # Characters the name or location may not contain; empty when valid.
    invalid_characters: list[str]
    # Another device of the product already has this name.
    taken: bool
    longest_tag_length: int | None = None
    max_tag_length: int | None = None
