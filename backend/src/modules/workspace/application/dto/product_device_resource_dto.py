"""
Commands and results of the product device resource use cases: the plain
option lists and the device kinds with their positions, parameters and
signals.
"""

from datetime import datetime

from pydantic import BaseModel

from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.application.dto.user_dto import PublicUserResult
from src.modules.workspace.domain.value_objects.product_device_option_category import (
    ProductDeviceOptionCategory,
)
from src.modules.workspace.domain.value_objects.product_device_parameter_type import (
    ProductDeviceParameterType,
)
from src.modules.workspace.domain.value_objects.product_device_signal import ProductDeviceSignalType

# ── Commands ──────────────────────────────────────────────────────────


class CreateProductDeviceOptionCommand(BaseModel):
    category: ProductDeviceOptionCategory
    label: dict[str, str]
    letter: str | None = None


class UpdateProductDeviceOptionCommand(BaseModel):
    label: dict[str, str]
    letter: str | None = None
    sort_order: int | None = None


class ProductDeviceKindPositionDraft(BaseModel):
    id: int | None = None
    label: dict[str, str]
    takes_value: bool = False
    unit: str | None = None
    plc_state_name: str | None = None
    plc_command_name: str | None = None


class ProductDeviceKindParameterDraft(BaseModel):
    id: int | None = None
    label: dict[str, str]
    unit: str | None = None
    value_type: ProductDeviceParameterType = ProductDeviceParameterType.NUMBER


class ProductDeviceKindSignalDraft(BaseModel):
    id: int | None = None
    label: dict[str, str]
    signal_type: ProductDeviceSignalType
    plc_name: str


class SaveProductDeviceKindCommand(BaseModel):
    label: dict[str, str]
    sort_order: int | None = None
    without_driving_medium: bool = False
    positions: list[ProductDeviceKindPositionDraft] = []
    parameters: list[ProductDeviceKindParameterDraft] = []
    signals: list[ProductDeviceKindSignalDraft] = []


# ── Results ───────────────────────────────────────────────────────────


class ProductDeviceOptionResult(ResultBase):
    created: datetime
    changed: datetime
    category: ProductDeviceOptionCategory
    label: dict[str, str]
    letter: str | None
    sort_order: int
    archived: bool
    creator_id: int
    creator: PublicUserResult | None
    changed_by_id: int | None
    changed_by: PublicUserResult | None


class ProductDeviceKindPositionResult(ResultBase):
    label: dict[str, str]
    takes_value: bool
    unit: str | None
    sort_order: int
    archived: bool
    plc_state_name: str | None
    plc_command_name: str | None


class ProductDeviceKindParameterResult(ResultBase):
    label: dict[str, str]
    unit: str | None
    value_type: ProductDeviceParameterType
    sort_order: int
    archived: bool


class ProductDeviceKindSignalResult(ResultBase):
    label: dict[str, str]
    signal_type: ProductDeviceSignalType
    plc_name: str
    sort_order: int
    archived: bool


class ProductDeviceKindResult(ResultBase):
    created: datetime
    changed: datetime
    label: dict[str, str]
    sort_order: int
    without_driving_medium: bool
    archived: bool
    creator_id: int
    creator: PublicUserResult | None
    changed_by_id: int | None
    changed_by: PublicUserResult | None
    positions: list[ProductDeviceKindPositionResult]
    parameters: list[ProductDeviceKindParameterResult]
    signals: list[ProductDeviceKindSignalResult]
