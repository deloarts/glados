"""Routes GET /admin/settings/eplan-data-portal through the use-case layer."""

from src.modules.external_data.application.dto.admin_settings_dto.eplan_data_portal import (
    AdminEdpSettingsResult,
)
from src.modules.external_data.application.mappers.admin_settings_mapper.eplan_data_portal import (
    EdpSettingsMapper,
)
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules


class GetEdpSettings:
    def __init__(self, repo: IExternalDataSettingsRepository) -> None:
        self._repo = repo

    async def execute(self, actor: User) -> AdminEdpSettingsResult:
        SettingsRules.assert_can_read(actor)
        return EdpSettingsMapper.edp_to_result(await self._repo.get_edp())
