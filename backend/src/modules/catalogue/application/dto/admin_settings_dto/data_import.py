"""
Commands and results for the data import settings: one profile per
spreadsheet import. A result lists every field of the import, with or
without column names, so a client can show the full mapping table.
"""

from pydantic import BaseModel

from src.modules.platform.application.dto.base import ResultBase


class DataImportProfileCommand(BaseModel):
    import_type: str
    header_row: int | None = None
    data_offset: int = 1
    max_rows: int = 100
    column_names: dict[str, list[str]] = {}


class UpdateDataImportSettingsCommand(BaseModel):
    # Profiles not listed keep their stored values.
    profiles: list[DataImportProfileCommand]


class DataImportFieldResult(BaseModel):
    key: str
    column_names: list[str]


class DataImportProfileResult(BaseModel):
    import_type: str
    header_row: int | None
    data_offset: int
    max_rows: int
    fields: list[DataImportFieldResult]


class AdminDataImportSettingsResult(ResultBase):
    profiles: list[DataImportProfileResult]
