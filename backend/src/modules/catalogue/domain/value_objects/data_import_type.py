"""
The spreadsheet imports Glados offers. Each one has its own import profile in
the data import settings (header row, data offset, row limit and the column
names per field), see domain/services/data_import_profiles.py.
"""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class DataImportType(StrValueEnum):
    BOUGHT_ITEM_CREATE = "bought_item_create"
    BOUGHT_ITEM_DEMAND = "bought_item_demand"
    MADE_ITEM_DEMAND = "made_item_demand"
