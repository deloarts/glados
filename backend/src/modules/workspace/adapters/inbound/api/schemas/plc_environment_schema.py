"""
HTTP schemas for PLC environments. Sizes are checked here, the rules in
plc_environment_rules.py.
"""

from datetime import datetime

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.workspace.domain.value_objects.plc_environment_settings import ExportColumnSource
from src.modules.workspace.domain.value_objects.product_device_signal import ProductDeviceSignalType


class CharConversionSchema(BaseModel):
    source: str = Field(..., max_length=10)
    target: str = Field(..., max_length=10)


class ExportColumnSchema(BaseModel):
    header: str = Field(..., max_length=100)
    source: ExportColumnSource
    value: str | None = Field(default=None, max_length=200)


class PlcEnvironmentSettingsSchema(BaseModel):
    # The template route answers with this schema too, so its response lists
    # every field as required, as a ResponseModel does; a request still may
    # leave the defaulted ones out.
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)

    name: str = Field(..., max_length=100)
    prefixes: dict[str, str] = Field(..., max_length=20)
    max_tag_length: int
    conversions: list[CharConversionSchema] = Field(..., max_length=200)
    tag_table: str = Field(..., max_length=100)
    safety_tag_table: str | None = Field(default=None, max_length=100)
    export_sheet: str = Field(..., max_length=100)
    export_columns: list[ExportColumnSchema] = Field(..., max_length=50)


class PlcEnvironmentSaveRequest(PlcEnvironmentSettingsSchema):
    is_default: bool = False


class PlcEnvironmentResponse(EntityResponse):
    created: datetime
    changed: datetime
    name: str
    is_default: bool
    prefixes: dict[str, str]
    max_tag_length: int
    conversions: list[CharConversionSchema]
    tag_table: str
    safety_tag_table: str | None
    export_sheet: str
    export_columns: list[ExportColumnSchema]
    archived: bool


class PlcTagResponse(BaseModel):
    device_id: int
    device_name: str
    device_name_ascii: str
    component_id: int
    signal_index: int
    name: str
    tag_table: str
    address: str | None
    comment: str
    signal_type: str
    safety: bool
    data_type: str
    overridden: bool
    too_long: bool
    duplicate: bool
    manual_id: int | None


class PlcTagEnvironmentResponse(BaseModel):
    id: int
    name: str
    max_tag_length: int
    export_sheet: str
    export_columns: list[ExportColumnSchema]


class PlcTagListResponse(BaseModel):
    environment: PlcTagEnvironmentResponse | None
    tags: list[PlcTagResponse]


class ManualPlcTagSaveRequest(BaseModel):
    name: str = Field(..., max_length=200)
    signal_type: ProductDeviceSignalType
    safety: bool = False
    address: str | None = Field(default=None, max_length=30)
    comment: str = Field(default="", max_length=500)


class SignalTagNameRequest(BaseModel):
    component_id: int
    signal_index: int = Field(..., ge=0)
    # Empty or None takes the hand-written name off.
    tag_name: str | None = Field(default=None, max_length=200)
