"""
DTOs for PLC environments.
"""

from datetime import datetime

from pydantic import BaseModel

from src.modules.platform.application.dto.base import ResultBase
from src.modules.workspace.domain.value_objects.plc_environment_settings import ExportColumnSource


class CharConversionDto(BaseModel):
    source: str
    target: str


class ExportColumnDto(BaseModel):
    header: str
    source: ExportColumnSource
    value: str | None = None


class PlcEnvironmentSettings(BaseModel):
    """The settings of an environment as a save sends them and the template
    for a new one returns them."""

    name: str
    prefixes: dict[str, str]
    max_tag_length: int
    conversions: list[CharConversionDto]
    tag_table: str
    safety_tag_table: str | None = None
    export_sheet: str
    export_columns: list[ExportColumnDto]


class SavePlcEnvironmentCommand(PlcEnvironmentSettings):
    is_default: bool = False


class PlcEnvironmentResult(ResultBase):
    created: datetime
    changed: datetime
    name: str
    is_default: bool
    prefixes: dict[str, str]
    max_tag_length: int
    conversions: list[CharConversionDto]
    tag_table: str
    safety_tag_table: str | None
    export_sheet: str
    export_columns: list[ExportColumnDto]
    archived: bool
