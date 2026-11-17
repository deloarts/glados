"""
DTOs for a product's PLC tag list.
"""

from pydantic import BaseModel

from src.modules.workspace.application.dto.plc_environment_dto import ExportColumnDto
from src.modules.workspace.domain.value_objects.product_device_signal import ProductDeviceSignalType


class PlcTagResult(BaseModel):
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
    # Data types are not modelled yet, so the export leaves the column empty.
    data_type: str
    overridden: bool
    too_long: bool
    duplicate: bool
    # The id of a manual tag; None for a tag built from a device signal.
    manual_id: int | None = None


class PlcTagEnvironmentResult(BaseModel):
    id: int
    name: str
    max_tag_length: int
    export_sheet: str
    export_columns: list[ExportColumnDto]


class PlcTagListResult(BaseModel):
    # None while no PLC environment exists.
    environment: PlcTagEnvironmentResult | None
    tags: list[PlcTagResult]


class SaveManualPlcTagCommand(BaseModel):
    name: str
    signal_type: ProductDeviceSignalType
    safety: bool = False
    address: str | None = None
    comment: str = ""


class SetSignalTagNameCommand(BaseModel):
    component_id: int
    signal_index: int
    # None takes the hand-written name off, so the built one applies again.
    tag_name: str | None = None
