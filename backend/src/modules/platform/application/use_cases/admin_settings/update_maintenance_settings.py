"""Enable or disable maintenance mode globally, audit the change, and determine the
action verb based on state transition."""

from src.modules.platform.application.dto.admin_settings_dto.maintenance import (
    AdminMaintenanceSettingsResult,
)
from src.modules.platform.application.dto.admin_settings_dto.maintenance import (
    UpdateMaintenanceSettingsCommand,
)
from src.modules.platform.application.mappers.admin_settings_mapper.maintenance import (
    MaintenanceSettingsMapper,
)
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.admin_settings.maintenance import AdminMaintenanceSettings
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class UpdateMaintenanceSettings:
    def __init__(self, repo: IPlatformSettingsRepository, *, uow: IUnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    async def execute(
        self, actor: User, cmd: UpdateMaintenanceSettingsCommand
    ) -> AdminMaintenanceSettingsResult:
        SettingsRules.assert_can_write(actor)

        settings = AdminMaintenanceSettings(
            id=1,
            enabled=cmd.enabled,
            message=cmd.message,
            allowed_ips=list(cmd.allowed_ips),
        )
        saved = await self._repo.save_maintenance(settings)

        action = "enabled" if cmd.enabled else "disabled"
        await self._repo.append_audit(
            AdminSettingsAuditEntry.by_actor(
                actor,
                settings_domain="maintenance",
                summary=f"Maintenance mode {action} by {actor.username}.",
            )
        )
        await self._uow.commit()

        log.info(f"{action.capitalize()} maintenance mode.")
        return MaintenanceSettingsMapper.maintenance_to_result(saved)
