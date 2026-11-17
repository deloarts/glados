"""
HTTP request and response schemas for the data import settings and for the
import profile a spreadsheet import reads. Range checks mirror
domain/services/data_import_profiles.py, which repeats them for every caller.
"""

from pydantic import BaseModel
from pydantic import Field

from src.modules.catalogue.domain.services.data_import_profiles import MAX_DATA_OFFSET
from src.modules.catalogue.domain.services.data_import_profiles import MAX_HEADER_ROW
from src.modules.catalogue.domain.services.data_import_profiles import MAX_ROWS_LIMIT
from src.modules.catalogue.domain.value_objects.data_import_type import DataImportType
from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.adapters.inbound.api.schemas.base import ResponseModel


class DataImportProfileRequest(BaseModel):
    import_type: DataImportType
    # None detects the header row from the column names.
    header_row: int | None = Field(default=None, ge=1, le=MAX_HEADER_ROW)
    data_offset: int = Field(default=1, ge=1, le=MAX_DATA_OFFSET)
    max_rows: int = Field(default=100, ge=1, le=MAX_ROWS_LIMIT)
    column_names: dict[str, list[str]] = Field(default_factory=dict)


class UpdateDataImportSettingsRequest(BaseModel):
    profiles: list[DataImportProfileRequest]


class DataImportFieldResponse(ResponseModel):
    key: str
    column_names: list[str]


class DataImportProfileResponse(ResponseModel):
    import_type: DataImportType
    header_row: int | None
    data_offset: int
    max_rows: int
    fields: list[DataImportFieldResponse]


class AdminDataImportSettingsResponse(EntityResponse):
    profiles: list[DataImportProfileResponse]
