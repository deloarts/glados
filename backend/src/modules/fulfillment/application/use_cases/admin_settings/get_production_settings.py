"""
Routes the /production GET through the use-case layer, matching the
module's other GETs (GetAllAdminSettings, GetHostStats,
GetAdminSettingsAudit) instead of an inline permission check and direct
mapper call in the adapter.
"""

from src.modules.fulfillment.application.dto.admin_settings_dto.production import (
    AdminProductionSettingsResult,
)
from src.modules.fulfillment.application.mappers.admin_settings_mapper.production import (
    ProductionSettingsMapper,
)
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
from src.modules.platform.application.services.tenant_timezone import tenant_zone
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.shared_kernel.domain.services.clock import today_in


class GetProductionSettings:
    def __init__(self, repo: IFulfillmentSettingsRepository) -> None:
        self._repo = repo

    async def execute(self, actor: User) -> AdminProductionSettingsResult:
        SettingsRules.assert_can_read(actor)
        return ProductionSettingsMapper.production_to_result(
            await self._repo.get_production(), today=today_in(await tenant_zone(self._repo))
        )
