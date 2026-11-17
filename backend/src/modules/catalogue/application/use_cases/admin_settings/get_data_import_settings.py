"""Routes GET /admin/settings/data-import through the use-case layer: every
import profile with all of its fields, for the Data import settings tab."""

from src.modules.catalogue.application.dto.admin_settings_dto.data_import import (
    AdminDataImportSettingsResult,
)
from src.modules.catalogue.application.mappers.admin_settings_mapper.data_import import (
    DataImportSettingsMapper,
)
from src.modules.catalogue.ports.outbound.catalogue_settings_repository import (
    ICatalogueSettingsRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules


class GetDataImportSettings:
    def __init__(self, repo: ICatalogueSettingsRepository) -> None:
        self._repo = repo

    async def execute(self, actor: User) -> AdminDataImportSettingsResult:
        SettingsRules.assert_can_read(actor)
        return DataImportSettingsMapper.data_import_to_result(await self._repo.get_data_import())
