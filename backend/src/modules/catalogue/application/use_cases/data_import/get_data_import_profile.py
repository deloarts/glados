"""
Backs GET /data-import/profiles/{import_type}: the import profile a
spreadsheet import reads before it parses a file (header row, data offset,
row limit, column names per field).

Permission: any signed-in user. A profile holds no secret, and every import
that reads it is gated by its own permission when its rows are validated
and committed, so gating the profile as well would only break the upload
step for a user who may import.
"""

from src.modules.catalogue.application.dto.admin_settings_dto.data_import import (
    DataImportProfileResult,
)
from src.modules.catalogue.application.mappers.admin_settings_mapper.data_import import (
    DataImportSettingsMapper,
)
from src.modules.catalogue.domain.value_objects.data_import_type import DataImportType
from src.modules.catalogue.ports.outbound.catalogue_settings_repository import (
    ICatalogueSettingsRepository,
)
from src.modules.platform.domain.entities.user import User


class GetDataImportProfile:
    def __init__(self, repo: ICatalogueSettingsRepository) -> None:
        self._repo = repo

    async def execute(self, actor: User, import_type: DataImportType) -> DataImportProfileResult:
        settings = await self._repo.get_data_import()
        return DataImportSettingsMapper.data_import_profile_to_result(
            import_type, settings.profile(import_type)
        )
