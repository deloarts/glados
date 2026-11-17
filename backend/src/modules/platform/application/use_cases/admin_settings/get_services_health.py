"""
Live connectivity status for the admin Host tab's service panel.

Requires read:settings like every other admin settings read. Not secret,
but describes the deployment rather than business data.
"""

from src.modules.platform.application.dto.admin_settings_dto.host import ServiceHealthResult
from src.modules.platform.application.dto.admin_settings_dto.host import ServicesHealthResult
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.ports.outbound.service_health_port import IServiceHealthChecker


class GetServicesHealth:
    def __init__(self, checker: IServiceHealthChecker) -> None:
        self._checker = checker

    async def execute(self, actor: User) -> ServicesHealthResult:
        SettingsRules.assert_can_read(actor)

        return ServicesHealthResult(
            services=[
                ServiceHealthResult(
                    name=s.name,
                    label=s.label,
                    status=s.status,
                    latency_ms=s.latency_ms,
                    detail=s.detail,
                )
                for s in await self._checker.check()
            ]
        )
