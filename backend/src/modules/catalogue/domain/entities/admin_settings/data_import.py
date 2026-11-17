"""
Domain entity for the data import settings singleton: one import profile per
spreadsheet import. A profile says where the header row is (a fixed row or
detected from the column names), how many rows below it the data starts, how
many data rows one upload may hold, and which column names map to each field
of the import. The rules that validate a profile live in
domain/services/data_import_profiles.py.
"""

from dataclasses import dataclass
from dataclasses import field

from src.modules.catalogue.domain.value_objects.data_import_type import DataImportType
from src.shared_kernel.domain.entities.base import Entity

DEFAULT_DATA_OFFSET = 1
DEFAULT_MAX_ROWS = 100


@dataclass(frozen=True)
class DataImportProfile:
    # 1-based row of the column headers; None detects it from the column names.
    header_row: int | None = None
    # Rows between the header and the first data row, 1 is directly below.
    data_offset: int = DEFAULT_DATA_OFFSET
    max_rows: int = DEFAULT_MAX_ROWS
    # Field key to the column names that map to it, compared case-insensitively.
    column_names: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class AdminDataImportSettings(Entity):
    profiles: dict[str, DataImportProfile]

    def profile(self, import_type: DataImportType) -> DataImportProfile:
        """The stored profile of `import_type`, or an empty default profile
        when none was saved yet (an import type added after the settings
        were seeded)."""
        return self.profiles.get(import_type.value, DataImportProfile())
