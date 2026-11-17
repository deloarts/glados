"""
Outbound webhooks are managed separately at /admin/webhooks (multi-subscription
system), this domain only covers the settings shared by every subscription,
currently the per-delivery timeout.
"""

from src.modules.platform.application.dto.admin_settings_dto.notifications import (
    AdminNotificationSettingsResult,
)
from src.modules.platform.application.dto.admin_settings_dto.notifications import (
    UpdateNotificationSettingsCommand,
)
from src.modules.platform.application.mappers.admin_settings_mapper.notifications import (
    NotificationSettingsMapper,
)
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.admin_settings.notifications import (
    AdminNotificationSettings,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.platform_settings_repository import (
    IPlatformSettingsRepository,
)
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class UpdateNotificationSettings:
    def __init__(self, repo: IPlatformSettingsRepository, *, uow: IUnitOfWork) -> None:
        self._repo = repo
        self._uow = uow

    async def execute(
        self, actor: User, cmd: UpdateNotificationSettingsCommand
    ) -> AdminNotificationSettingsResult:
        SettingsRules.assert_can_write(actor)

        settings = AdminNotificationSettings(
            id=1,
            webhook_timeout_seconds=cmd.webhook_timeout_seconds,
        )
        saved = await self._repo.save_notifications(settings)

        await self._repo.append_audit(
            AdminSettingsAuditEntry.by_actor(
                actor,
                settings_domain="notifications",
                summary=f"Notification settings updated by {actor.username}.",
            )
        )
        await self._uow.commit()

        log.info("Updated notification settings.")
        return NotificationSettingsMapper.notifications_to_result(saved)
