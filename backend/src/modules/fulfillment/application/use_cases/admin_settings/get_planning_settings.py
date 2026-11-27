"""
Reads the planning settings, gated like every other settings read.
"""

from src.modules.fulfillment.application.dto.admin_settings_dto.planning import (
    AdminPlanningSettingsResult,
)
from src.modules.fulfillment.application.mappers.admin_settings_mapper.planning import (
    PlanningSettingsMapper,
)
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules


class GetPlanningSettings:
    def __init__(self, repo: IFulfillmentSettingsRepository) -> None:
        self._repo = repo

    async def execute(self, actor: User) -> AdminPlanningSettingsResult:
        SettingsRules.assert_can_read(actor)
        return PlanningSettingsMapper.planning_to_result(await self._repo.get_planning())
