"""
Maps the data import settings entity and its profiles to result DTOs. Every
field of an import is listed in the catalogue's order, a field without
column names with an empty list.
"""

from src.modules.catalogue.application.dto.admin_settings_dto.data_import import (
    AdminDataImportSettingsResult,
)
from src.modules.catalogue.application.dto.admin_settings_dto.data_import import (
    DataImportFieldResult,
)
from src.modules.catalogue.application.dto.admin_settings_dto.data_import import (
    DataImportProfileResult,
)
from src.modules.catalogue.domain.entities.admin_settings.data_import import AdminDataImportSettings
from src.modules.catalogue.domain.entities.admin_settings.data_import import DataImportProfile
from src.modules.catalogue.domain.services.data_import_profiles import IMPORT_FIELDS
from src.modules.catalogue.domain.value_objects.data_import_type import DataImportType


class DataImportSettingsMapper:
    @staticmethod
    def data_import_profile_to_result(
        import_type: DataImportType, profile: DataImportProfile
    ) -> DataImportProfileResult:
        return DataImportProfileResult(
            import_type=import_type.value,
            header_row=profile.header_row,
            data_offset=profile.data_offset,
            max_rows=profile.max_rows,
            fields=[
                DataImportFieldResult(key=key, column_names=list(profile.column_names.get(key, [])))
                for key in IMPORT_FIELDS[import_type]
            ],
        )

    @staticmethod
    def data_import_to_result(e: AdminDataImportSettings) -> AdminDataImportSettingsResult:
        return AdminDataImportSettingsResult(
            id=e.id,
            public_id=e.public_id,
            profiles=[
                DataImportSettingsMapper.data_import_profile_to_result(t, e.profile(t))
                for t in DataImportType
            ],
        )
