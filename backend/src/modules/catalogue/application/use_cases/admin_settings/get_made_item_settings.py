"""
Routes the /made-items GET through the use-case layer, matching the
module's other GETs (GetAllAdminSettings, GetHostStats,
GetAdminSettingsAudit) instead of an inline permission check and direct
mapper call in the adapter.
"""

from src.modules.catalogue.application.dto.admin_settings_dto.made_items import (
    AdminMadeItemSettingsResult,
)
from src.modules.catalogue.application.mappers.admin_settings_mapper.made_items import (
    MadeItemSettingsMapper,
)
from src.modules.catalogue.ports.outbound.catalogue_settings_repository import (
    ICatalogueSettingsRepository,
)
from src.modules.platform.application.services.tenant_timezone import tenant_zone
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.shared_kernel.domain.services.clock import today_in


class GetMadeItemSettings:
    def __init__(self, repo: ICatalogueSettingsRepository) -> None:
        self._repo = repo

    async def execute(self, actor: User) -> AdminMadeItemSettingsResult:
        SettingsRules.assert_can_read(actor)
        return MadeItemSettingsMapper.made_items_to_result(
            await self._repo.get_made_items(), today=today_in(await tenant_zone(self._repo))
        )
